import hashlib
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import current_app

from app.core.errors import BusinessException
from app.extensions.influxdb import get_query_api
from app.repository.device_repository import DeviceRepository
from app.repository.run_record_repository import RunRecordRepository


class RunRecordSyncService:
    """从 InfluxDB 聚合 source_segment，并同步到运行记录池。"""

    DEFAULT_MEASUREMENT = "atp_monitor_data"

    @classmethod
    def sync_from_influx(
        cls,
        start_time: str,
        end_time: str,
        device_codes: Optional[list[str]] = None,
        measurement: Optional[str] = None,
        limit_segments: Optional[int] = None,
    ) -> Dict[str, Any]:
        start_dt = cls._parse_time(start_time, "start_time")
        end_dt = cls._parse_time(end_time, "end_time")
        if start_dt >= end_dt:
            raise BusinessException(code=400, message="start_time 必须早于 end_time", status_code=400)

        normalized_devices = cls._normalize_device_codes(device_codes)
        normalized_limit = cls._parse_optional_positive_int(limit_segments, "limit_segments")
        measurement_name = (
            measurement
            or current_app.config.get("MONITOR_MEASUREMENT")
            or cls.DEFAULT_MEASUREMENT
        )

        flux = cls._build_segment_scan_flux(
            start_dt=start_dt,
            end_dt=end_dt,
            measurement=measurement_name,
            device_codes=normalized_devices,
        )
        tables = get_query_api().query(flux, org=current_app.config["INFLUXDB_ORG"])
        aggregates = cls._aggregate_records(tables)
        scanned_segments = len(aggregates)

        records = [
            cls._build_run_record_payload(aggregate)
            for aggregate in aggregates.values()
            if aggregate["device_code"] and aggregate["source_segment"] and aggregate["point_count"] > 0
        ]
        records.sort(key=lambda item: (item["record_start_time"], item["device_code"], item["source_segment"]))
        if normalized_limit is not None:
            records = records[:normalized_limit]

        created_count = 0
        updated_count = 0
        skipped_count = scanned_segments - len(records)
        items_preview = []
        logger = logging.getLogger(__name__)

        for record in records:
            try:
                saved_record = RunRecordRepository.upsert_by_device_segment(record)
            except Exception:
                logger.exception(
                    "同步运行记录失败: device_code=%s source_segment=%s",
                    record.get("device_code"),
                    record.get("source_segment"),
                )
                raise

            if saved_record.get("_created"):
                created_count += 1
            else:
                updated_count += 1
            if len(items_preview) < 10:
                items_preview.append(
                    {
                        "run_record_id": saved_record.get("run_record_id"),
                        "run_record_code": saved_record.get("run_record_code"),
                        "device_code": saved_record.get("device_code"),
                        "source_segment": saved_record.get("source_segment"),
                        "record_start_time": saved_record.get("record_start_time"),
                        "record_end_time": saved_record.get("record_end_time"),
                        "point_count": saved_record.get("point_count"),
                        "status": saved_record.get("status"),
                    }
                )

        return {
            "scanned_segments": scanned_segments,
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": max(skipped_count, 0),
            "start_time": start_time,
            "end_time": end_time,
            "measurement": measurement_name,
            "device_codes": normalized_devices,
            "items_preview": items_preview,
        }

    @classmethod
    def _aggregate_records(cls, tables: Any) -> Dict[tuple[str, str], Dict[str, Any]]:
        aggregates: Dict[tuple[str, str], Dict[str, Any]] = defaultdict(cls._new_aggregate)

        for table in tables:
            for record in table.records:
                values = record.values
                device_code = cls._clean_text(values.get("device_code"))
                source_segment = cls._clean_text(values.get("source_segment"))
                if not device_code or not source_segment:
                    continue

                key = (device_code, source_segment)
                aggregate = aggregates[key]
                aggregate["device_code"] = device_code
                aggregate["source_segment"] = source_segment

                sample_time = values.get("_time")
                field_name = values.get("_field")
                if field_name == "speed":
                    aggregate["point_count"] += 1
                    cls._update_time_range(aggregate, sample_time)
                    cls._collect_tag(aggregate, "atp_type", values.get("atp_type"))
                    cls._collect_tag(aggregate, "line_id", values.get("line_id"))
                    cls._collect_tag(aggregate, "direction", values.get("direction"))
                    condition_label = cls._clean_text(values.get("condition_label"))
                    if condition_label:
                        aggregate["condition_summary"][condition_label] += 1
                elif field_name == "alarm_part" and cls._is_alarm_value(values.get("_value")):
                    aggregate["has_alarm_label"] = True

        return dict(aggregates)

    @staticmethod
    def _new_aggregate() -> Dict[str, Any]:
        return {
            "device_code": None,
            "source_segment": None,
            "record_start_time": None,
            "record_end_time": None,
            "point_count": 0,
            "atp_type": Counter(),
            "line_id": Counter(),
            "direction": Counter(),
            "condition_summary": Counter(),
            "has_alarm_label": False,
        }

    @classmethod
    def _build_run_record_payload(cls, aggregate: Dict[str, Any]) -> Dict[str, Any]:
        start_time = aggregate["record_start_time"]
        end_time = aggregate["record_end_time"]
        source_segment = aggregate["source_segment"]
        device_code = aggregate["device_code"]

        return {
            "run_record_code": cls._build_run_record_code(device_code, source_segment, start_time),
            "device_id": cls._resolve_device_id(device_code),
            "device_code": device_code,
            "source_segment": source_segment,
            "source_file": cls._infer_source_file(source_segment),
            "record_start_time": cls._format_datetime(start_time),
            "record_end_time": cls._format_datetime(end_time),
            "point_count": aggregate["point_count"],
            "duration_seconds": cls._duration_seconds(start_time, end_time),
            "atp_type": cls._most_common_value(aggregate["atp_type"]),
            "line_id": cls._most_common_value(aggregate["line_id"]),
            "direction": cls._most_common_value(aggregate["direction"]),
            "condition_summary": dict(aggregate["condition_summary"]),
            "has_alarm_label": aggregate["has_alarm_label"],
            "status": "ready",
        }

    @classmethod
    def _build_segment_scan_flux(
        cls,
        start_dt: datetime,
        end_dt: datetime,
        measurement: str,
        device_codes: Optional[list[str]],
    ) -> str:
        bucket = current_app.config["INFLUXDB_BUCKET"]
        filters = [
            f'r._measurement == "{cls._escape_flux_string(measurement)}"',
            '(r._field == "speed" or r._field == "alarm_part")',
        ]
        if device_codes:
            device_filter = " or ".join(
                f'r.device_code == "{cls._escape_flux_string(device_code)}"'
                for device_code in device_codes
            )
            filters.append(f"({device_filter})")

        filter_body = " and ".join(filters)
        return f"""
from(bucket: "{cls._escape_flux_string(bucket)}")
  |> range(start: {cls._format_flux_time(start_dt)}, stop: {cls._format_flux_time(end_dt)})
  |> filter(fn: (r) => {filter_body})
  |> filter(fn: (r) => exists r.device_code and exists r.source_segment)
  |> filter(fn: (r) => r.device_code != "" and r.source_segment != "")
  |> keep(columns: ["_time", "_field", "_value", "device_code", "source_segment", "condition_label", "atp_type", "line_id", "direction"])
  |> sort(columns: ["_time"])
"""

    @staticmethod
    def _collect_tag(aggregate: Dict[str, Any], field: str, value: Any) -> None:
        text = RunRecordSyncService._clean_text(value)
        if text:
            aggregate[field][text] += 1

    @staticmethod
    def _update_time_range(aggregate: Dict[str, Any], sample_time: Any) -> None:
        if sample_time is None:
            return
        if aggregate["record_start_time"] is None or sample_time < aggregate["record_start_time"]:
            aggregate["record_start_time"] = sample_time
        if aggregate["record_end_time"] is None or sample_time > aggregate["record_end_time"]:
            aggregate["record_end_time"] = sample_time

    @staticmethod
    def _is_alarm_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip()
        return text not in {"", "0", "0.0", "none", "None", "null", "NULL", "nan", "NaN"}

    @staticmethod
    def _most_common_value(counter: Counter) -> Optional[str]:
        if not counter:
            return None
        return counter.most_common(1)[0][0]

    @staticmethod
    def _duration_seconds(start_time: Any, end_time: Any) -> Optional[int]:
        if not start_time or not end_time:
            return None
        try:
            return int((end_time - start_time).total_seconds())
        except AttributeError:
            return None

    @staticmethod
    def _build_run_record_code(device_code: str, source_segment: str, start_time: Any) -> str:
        date_part = RunRecordSyncService._format_datetime(start_time)[:10].replace("-", "")
        digest = hashlib.sha1(f"{device_code}|{source_segment}".encode("utf-8")).hexdigest()[:12]
        return f"RUN-{date_part}-{device_code}-{digest}"

    @staticmethod
    def _infer_source_file(source_segment: str) -> Optional[str]:
        if not source_segment:
            return None
        return source_segment.split("#", 1)[0]

    @staticmethod
    def _resolve_device_id(device_code: str) -> Optional[int]:
        device = DeviceRepository.find_by_code(device_code)
        return device.get("device_id") if device else None

    @staticmethod
    def _normalize_device_codes(device_codes: Optional[list[str]]) -> Optional[list[str]]:
        if not device_codes:
            return None
        normalized = []
        for device_code in device_codes:
            text = RunRecordSyncService._clean_text(device_code)
            if text:
                normalized.append(text)
        return normalized or None

    @staticmethod
    def _parse_optional_positive_int(value: Any, field_name: str) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400) from exc
        if parsed <= 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        return parsed

    @staticmethod
    def _parse_time(value: str, field_name: str) -> datetime:
        if not value:
            raise BusinessException(code=400, message=f"{field_name} 不能为空", status_code=400)
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise BusinessException(
                code=400,
                message=f"{field_name} 格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            ) from exc

    @staticmethod
    def _format_flux_time(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _escape_flux_string(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"')
