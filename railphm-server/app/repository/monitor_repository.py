from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from flask import current_app

from app.extensions.influxdb import get_query_api


class MonitorRepository:
    """
    监测数据访问层 (Repository)
    运行时数据源为 InfluxDB，不再读取本地样例数据。
    """

    FIELD_COLUMNS = (
        "speed",
        "mileage",
        "source_time",
        "source_train_no",
        "source_car_no",
        "source_driver_id",
        "source_unique_id",
        "station_name",
        "balise_id",
        "balise_mileage",
        "balise_type",
        "signal_id",
        "signal_name",
        "signal_mileage",
        "longitude",
        "latitude",
        "outdoor_temperature",
        "weather",
        "road_condition",
        "humidity",
        "alarm_part",
    )

    DEFAULT_QUERY_FIELDS = (
        "speed",
        "mileage",
        "source_time",
        "station_name",
        "longitude",
        "latitude",
        "outdoor_temperature",
        "humidity",
        "weather",
    )

    TAG_COLUMNS = (
        "device_code",
        "condition_label",
        "source_segment",
        "atp_type",
        "line_id",
        "direction",
    )

    @classmethod
    def query_history_by_device_and_range(
        cls,
        device_code: str,
        start_dt: datetime,
        end_dt: datetime,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        condition_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """从 InfluxDB 查询指定设备、时间范围内的监测点。"""
        bucket = current_app.config["INFLUXDB_BUCKET"]
        measurement = current_app.config.get("MONITOR_MEASUREMENT", "atp_monitor")
        query_limit = limit or current_app.config.get("MONITOR_QUERY_LIMIT", 5000)
        selected_fields = fields or list(cls.DEFAULT_QUERY_FIELDS)

        flux = cls._build_flux_query(
            bucket=bucket,
            measurement=measurement,
            device_code=device_code,
            start_dt=start_dt,
            end_dt=end_dt,
            fields=selected_fields,
            limit=query_limit,
            condition_label=condition_label,
        )

        tables = get_query_api().query(flux, org=current_app.config["INFLUXDB_ORG"])
        rows: List[Dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                rows.append(cls._normalize_record(record.values))

        rows.sort(key=lambda item: item.get("sample_time") or "")
        return rows

    @classmethod
    def _build_flux_query(
        cls,
        bucket: str,
        measurement: str,
        device_code: str,
        start_dt: datetime,
        end_dt: datetime,
        fields: List[str],
        limit: int,
        condition_label: Optional[str] = None,
    ) -> str:
        field_set = {field for field in fields if field in cls.FIELD_COLUMNS}
        if not field_set:
            field_set = set(cls.FIELD_COLUMNS)
        field_filter = " or ".join(
            f'r._field == "{cls._escape_flux_string(field)}"'
            for field in sorted(field_set)
        )

        filters = [
            f'r._measurement == "{cls._escape_flux_string(measurement)}"',
            f'r.device_code == "{cls._escape_flux_string(device_code)}"',
            f"({field_filter})",
        ]
        if condition_label:
            filters.append(
                f'r.condition_label == "{cls._escape_flux_string(condition_label)}"'
            )

        filter_body = " and ".join(filters)
        keep_columns = ["_time", *cls.TAG_COLUMNS, *sorted(field_set)]
        keep_columns_literal = ", ".join(f'"{column}"' for column in keep_columns)

        return f"""
from(bucket: "{cls._escape_flux_string(bucket)}")
  |> range(start: {cls._format_flux_time(start_dt)}, stop: {cls._format_flux_time(end_dt)})
  |> filter(fn: (r) => {filter_body})
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: [{keep_columns_literal}])
  |> sort(columns: ["_time"])
  |> limit(n: {int(limit)})
"""

    @staticmethod
    def _escape_flux_string(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _format_flux_time(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def _normalize_record(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        sample_time = cls._format_datetime(values.get("_time"))
        item = {
            "sample_time": sample_time,
        }

        for column in (*cls.TAG_COLUMNS, *cls.FIELD_COLUMNS):
            if column in values:
                item[column] = cls._normalize_value(values.get(column))

        return item

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value
