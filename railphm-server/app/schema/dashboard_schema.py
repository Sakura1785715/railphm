from datetime import datetime
from typing import Any, Dict, List


class DashboardSchema:
    """Dashboard 聚合响应序列化。"""

    HEALTH_BUCKETS = (
        ("normal", "正常"),
        ("attention", "关注"),
        ("warning", "预警"),
        ("critical", "告警"),
    )

    DEVICE_STATUS_TEXT = {
        1: "正常",
        2: "关注",
        3: "预警",
        4: "告警",
    }

    ALERT_STATUS_TEXT = {
        "pending": "待处理",
        "unhandled": "待处理",
        "processing": "处理中",
        "resolved": "已处理",
        "ignored": "已忽略",
    }

    @classmethod
    def dump_overview(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """输出稳定 Dashboard overview 结构。"""
        return {
            "kpi": cls._dump_kpi(payload.get("kpi")),
            "risk_trend": cls._dump_risk_trend(payload.get("risk_trend")),
            "health_distribution": cls._dump_health_distribution(payload.get("health_distribution")),
            "latest_alerts": cls._dump_latest_alerts(payload.get("latest_alerts")),
            "key_devices": cls._dump_key_devices(payload.get("key_devices")),
            "updated_at": cls._format_datetime(datetime.now()),
        }

    @classmethod
    def _dump_kpi(cls, kpi: Any) -> Dict[str, int]:
        source = kpi if isinstance(kpi, dict) else {}
        return {
            "device_total": cls._to_int(source.get("device_total")),
            "normal_device_count": cls._to_int(source.get("normal_device_count")),
            "warning_device_count": cls._to_int(source.get("warning_device_count")),
            "unhandled_alert_count": cls._to_int(source.get("unhandled_alert_count")),
        }

    @classmethod
    def _dump_risk_trend(cls, rows: Any) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            return []

        return [
            {
                "time": cls._format_datetime(row.get("time") or row.get("window_end_time") or row.get("created_at")),
                "risk_result_id": row.get("risk_result_id"),
                "device_id": row.get("device_id"),
                "device_code": row.get("device_code"),
                "risk_score": cls._to_float(row.get("risk_score")),
                "avg_risk_score": cls._to_float(row.get("avg_risk_score") or row.get("risk_score")),
                "max_risk_score": cls._to_float(row.get("max_risk_score") or row.get("risk_score")),
                "health_score": cls._to_float(row.get("health_score")),
                "health_level": cls._normalize_health_level(row.get("health_level") or row.get("health_status")),
                "risk_std": cls._to_float(row.get("risk_std")),
                "condition_label": row.get("condition_label"),
                "record_count": cls._to_int(row.get("record_count"), fallback=1),
                "window_end_time": cls._format_datetime(row.get("window_end_time")),
                "created_at": cls._format_datetime(row.get("created_at")),
            }
            for row in rows
            if isinstance(row, dict)
        ]

    @classmethod
    def _dump_health_distribution(cls, rows: Any) -> List[Dict[str, Any]]:
        counts = {level: 0 for level, _label in cls.HEALTH_BUCKETS}
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                level = cls._normalize_health_level(
                    row.get("health_level") or row.get("health_status")
                )
                if level == "unknown":
                    level = cls._normalize_device_status_level(row.get("device_status"))
                if level in counts:
                    counts[level] += 1

        return [
            {
                "level": level,
                "label": label,
                "count": counts[level],
            }
            for level, label in cls.HEALTH_BUCKETS
        ]

    @classmethod
    def _dump_latest_alerts(cls, rows: Any) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            return []

        return [
            {
                "alert_id": row.get("alert_id"),
                "risk_result_id": row.get("risk_result_id"),
                "device_id": row.get("device_id"),
                "device_code": row.get("device_code"),
                "device_name": row.get("device_name"),
                "alert_level": cls._normalize_alert_level(row.get("alert_level")),
                "alert_status": cls._normalize_alert_status(row.get("alert_status")),
                "alert_status_text": cls._format_alert_status(row.get("alert_status"), row.get("alert_status_text")),
                "alert_message": row.get("alert_message") or row.get("message"),
                "alert_advice": row.get("alert_advice"),
                "risk_score": cls._to_float(row.get("risk_score")),
                "health_score": cls._to_float(row.get("health_score")),
                "health_level": cls._normalize_health_level(row.get("health_level") or row.get("health_status")),
                "health_status": row.get("health_status"),
                "alert_time": cls._format_datetime(row.get("alert_time")),
                "created_at": cls._format_datetime(row.get("created_at") or row.get("create_time")),
                "updated_at": cls._format_datetime(row.get("updated_at") or row.get("update_time")),
            }
            for row in rows
            if isinstance(row, dict)
        ]

    @classmethod
    def _dump_key_devices(cls, rows: Any) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            return []

        return [
            {
                "device_id": row.get("device_id"),
                "device_code": row.get("device_code"),
                "device_name": row.get("device_name"),
                "device_type": row.get("device_type"),
                "location": row.get("location"),
                "device_status": row.get("device_status"),
                "status_text": cls._format_device_status(row.get("device_status")),
                "risk_score": cls._to_float(row.get("risk_score")),
                "health_score": cls._to_float(row.get("health_score")),
                "health_level": cls._normalize_health_level(row.get("health_level") or row.get("health_status")),
                "health_status": row.get("health_status"),
                "alert_level": cls._normalize_alert_level(row.get("alert_level")),
                "alert_status": cls._normalize_alert_status(row.get("alert_status")),
                "window_end_time": cls._format_datetime(row.get("window_end_time")),
                "updated_at": cls._format_datetime(row.get("updated_at")),
            }
            for row in rows
            if isinstance(row, dict)
        ]

    @classmethod
    def _normalize_health_level(cls, value: Any) -> str:
        normalized = cls._normalize_key(value)
        mapping = {
            "normal": "normal",
            "healthy": "normal",
            "health": "normal",
            "ok": "normal",
            "正常": "normal",
            "健康": "normal",
            "attention": "attention",
            "focus": "attention",
            "关注": "attention",
            "warning": "warning",
            "warn": "warning",
            "prewarning": "warning",
            "预警": "warning",
            "critical": "critical",
            "danger": "critical",
            "alert": "critical",
            "告警": "critical",
            "危险": "critical",
        }
        return mapping.get(normalized, "unknown")

    @classmethod
    def _normalize_device_status_level(cls, value: Any) -> str:
        status = cls._to_int(value, fallback=0)
        return {
            1: "normal",
            2: "attention",
            3: "warning",
            4: "critical",
        }.get(status, "unknown")

    @classmethod
    def _format_device_status(cls, value: Any) -> str:
        return cls.DEVICE_STATUS_TEXT.get(cls._to_int(value, fallback=0), "暂无")

    @classmethod
    def _normalize_alert_status(cls, value: Any) -> Any:
        normalized = cls._normalize_key(value)
        if normalized == "pending":
            return "unhandled"
        return normalized or None

    @classmethod
    def _format_alert_status(cls, value: Any, fallback: Any = None) -> str:
        normalized = cls._normalize_alert_status(value)
        if normalized in cls.ALERT_STATUS_TEXT:
            return cls.ALERT_STATUS_TEXT[normalized]
        if fallback:
            return "待处理" if str(fallback).strip() == "未处理" else str(fallback)
        return "暂无"

    @classmethod
    def _normalize_alert_level(cls, value: Any) -> Any:
        normalized = cls._normalize_key(value)
        mapping = {
            "none": "none",
            "info": "info",
            "low": "low",
            "medium": "medium",
            "warning": "medium",
            "high": "high",
            "critical": "critical",
        }
        return mapping.get(normalized, normalized or None)

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

    @staticmethod
    def _normalize_key(value: Any) -> str:
        if value is None or value == "":
            return ""
        return str(value).strip().lower()
