import json
from datetime import datetime
from typing import Any, Dict, List


class RunRecordSchema:
    """运行记录 API 输出结构。"""

    OUTPUT_FIELDS = (
        "run_record_id",
        "run_record_code",
        "device_id",
        "device_code",
        "source_segment",
        "source_file",
        "record_start_time",
        "record_end_time",
        "point_count",
        "duration_seconds",
        "atp_type",
        "line_id",
        "direction",
        "condition_summary",
        "has_alarm_label",
        "status",
        "max_risk_score",
        "max_risk_result_id",
        "max_alert_level",
        "alert_id",
        "created_at",
        "updated_at",
    )

    @classmethod
    def dump(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        if not record:
            return {}

        item = {}
        for field in cls.OUTPUT_FIELDS:
            value = record.get(field)
            if field in {"record_start_time", "record_end_time", "created_at", "updated_at"}:
                value = cls._format_datetime(value)
            elif field == "condition_summary":
                value = cls._parse_json(value)
            elif field == "has_alarm_label":
                value = bool(value)
            item[field] = value
        return item

    @classmethod
    def dump_list(cls, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [cls.dump(record) for record in records]

    @classmethod
    def dump_monitor_history(
        cls,
        run_record: Dict[str, Any],
        rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "device_code": run_record.get("device_code"),
            "run_record_id": run_record.get("run_record_id"),
            "source_segment": run_record.get("source_segment"),
            "start_time": cls._format_datetime(run_record.get("record_start_time")),
            "end_time": cls._format_datetime(run_record.get("record_end_time")),
            "count": len(rows),
            "data_source": "influxdb",
            "series": rows,
        }

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)

    @staticmethod
    def _parse_json(value: Any) -> Any:
        if value is None or value == "":
            return {}
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="ignore")
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return value
        return value
