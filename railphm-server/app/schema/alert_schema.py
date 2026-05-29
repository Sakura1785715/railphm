from datetime import datetime
from typing import List, Dict, Any

class AlertSchema:
    """
    告警数据序列化 (Schema/DTO 层)
    分离列表摘要与详情全量字段
    """

    @staticmethod
    def dump_list_item(record: Dict[str, Any]) -> Dict[str, Any]:
        """列表摘要字段"""
        return {
            "alert_id": record.get("alert_id"),
            "run_record_id": record.get("run_record_id"),
            "risk_result_id": record.get("risk_result_id"),
            "device_id": record.get("device_id"),
            "device_code": record.get("device_code"),
            "alert_level": record.get("alert_level"),
            "alert_status": record.get("alert_status"),
            "alert_status_text": record.get("alert_status_text"),
            "alert_time": record.get("alert_time"),
            "message": record.get("alert_message") or record.get("message"),
            "alert_message": record.get("alert_message") or record.get("message"),
            "risk_score": record.get("risk_score"),
            "health_score": record.get("health_score"),
            "health_level": record.get("health_level"),
            "health_status": record.get("health_status"),
        }

    @staticmethod
    def dump_detail(record: Dict[str, Any]) -> Dict[str, Any]:
        """详情全量字段"""
        base = AlertSchema.dump_list_item(record)
        base.update({
            "alert_advice": record.get("alert_advice"),
            "target_label_value": record.get("target_label_value"),
            "target_time": record.get("target_time"),
            "handler_id": record.get("handler_id"),
            "handle_time": record.get("handle_time"),
            "handle_desc": record.get("handle_desc"),
            "create_time": record.get("create_time"),
            "update_time": record.get("update_time"),
            "alert_source": record.get("alert_source"),
            "alert_position": record.get("alert_position"),
            "alert_object_type": record.get("alert_object_type"),
            "alert_object_code": record.get("alert_object_code"),
        })
        return base

    @classmethod
    def dump_diagnosis(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """告警研判详情响应结构。"""
        alert = payload.get("alert")
        representative_risk = payload.get("representative_risk")
        run_record = payload.get("run_record")
        return {
            "alert": cls.dump_detail(alert) if isinstance(alert, dict) else None,
            "run_record": cls._dump_optional_dict(run_record),
            "representative_risk": cls._dump_optional_dict(representative_risk),
            "monitor_series": cls._dump_list(payload.get("monitor_series")),
            "risk_series": cls._dump_list(payload.get("risk_series")),
            "health_series": cls._dump_list(payload.get("health_series")),
            "condition_segments": cls._dump_list(payload.get("condition_segments")),
            "diagnosis_summary": cls._dump_diagnosis_summary(payload.get("diagnosis_summary")),
        }

    @classmethod
    def dump_page(cls, items: List[Dict[str, Any]], total: int, page: int, size: int) -> Dict[str, Any]:
        """组装标准分页响应"""
        return {
            "items": [cls.dump_list_item(i) for i in items],
            "total": total,
            "page": page,
            "size": size
        }

    @classmethod
    def _dump_diagnosis_summary(cls, summary: Any) -> Dict[str, Any]:
        source = summary if isinstance(summary, dict) else {}
        return {
            "event_time": cls._format_datetime(source.get("event_time")),
            "context_start_time": cls._format_datetime(source.get("context_start_time")),
            "context_end_time": cls._format_datetime(source.get("context_end_time")),
            "monitor_point_count": cls._to_int(source.get("monitor_point_count")),
            "risk_point_count": cls._to_int(source.get("risk_point_count")),
            "max_risk_score": cls._to_float(source.get("max_risk_score")),
            "min_health_score": cls._to_float(source.get("min_health_score")),
            "representative_risk_result_id": source.get("representative_risk_result_id"),
            "run_record_id": source.get("run_record_id"),
            "source_segment": source.get("source_segment"),
            "evidence_text": source.get("evidence_text") or "",
        }

    @classmethod
    def _dump_optional_dict(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return None
        return {key: cls._normalize_value(item) for key, item in value.items()}

    @classmethod
    def _dump_list(cls, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [
            {key: cls._normalize_value(item) for key, item in row.items()}
            for row in value
            if isinstance(row, dict)
        ]

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return cls._format_datetime(value)
        if isinstance(value, dict):
            return {key: cls._normalize_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._normalize_value(item) for item in value]
        return value

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value).replace("T", " ").removesuffix("Z")

    @staticmethod
    def _to_int(value: Any, fallback: int = 0) -> int:
        if value is None or value == "":
            return fallback
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _to_float(value: Any) -> Any:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
