from datetime import datetime
from typing import Any, Dict, List


class DashboardSchema:
    """Dashboard 聚合响应序列化。"""

    HEALTH_BUCKETS = (
        ("normal", "正常", 1),
        ("attention", "关注", 2),
        ("warning", "预警", 3),
        ("critical", "告警", 4),
    )

    DEVICE_STATUS_TEXT = {
        1: "正常",
        2: "关注",
        3: "预警",
        4: "告警",
    }

    ALERT_STATUS_TEXT = {
        "pending": "未处理",
        "unhandled": "未处理",
        "processing": "处理中",
        "resolved": "已处理",
        "ignored": "已忽略",
    }

    @classmethod
    def dump_overview(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """输出稳定 Dashboard overview 结构。"""
        device_status_cards = payload.get("device_status_cards")
        return {
            "kpi": cls._dump_kpi(payload.get("kpi")),
            "device_status_cards": cls._dump_device_status_cards(device_status_cards),
            "health_distribution": cls._dump_health_distribution(
                payload.get("health_distribution"),
                device_status_cards=device_status_cards,
            ),
            "latest_alerts": cls._dump_latest_alerts(payload.get("latest_alerts")),
            "key_devices": cls._dump_key_devices(payload.get("key_devices")),
            "risk_trend": cls._dump_risk_trend(payload.get("risk_trend")),
            "updated_at": cls._format_datetime(datetime.now()),
        }

    @classmethod
    def _dump_kpi(cls, kpi: Any) -> Dict[str, int]:
        source = kpi if isinstance(kpi, dict) else {}
        return {
            "device_total": cls._to_int(source.get("device_total")),
            "normal_device_count": cls._to_int(source.get("normal_device_count")),
            "attention_device_count": cls._to_int(source.get("attention_device_count")),
            "warning_device_count": cls._to_int(source.get("warning_device_count")),
            "warning_only_device_count": cls._to_int(source.get("warning_only_device_count")),
            "critical_device_count": cls._to_int(source.get("critical_device_count")),
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
                "health_status": row.get("health_status"),
                "risk_std": cls._to_float(row.get("risk_std")),
                "condition_label": row.get("condition_label"),
                "record_count": cls._to_int(row.get("record_count"), fallback=1),
                "ts_end": cls._format_datetime(row.get("ts_end")),
                "window_end_time": cls._format_datetime(row.get("window_end_time")),
                "created_at": cls._format_datetime(row.get("created_at")),
            }
            for row in rows
            if isinstance(row, dict)
        ]

    @classmethod
    def _dump_device_status_cards(cls, rows: Any) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            return []

        return [
            {
                "device_id": row.get("device_id"),
                "device_code": row.get("device_code"),
                "device_name": row.get("device_name"),
                "device_type": row.get("device_type"),
                "location": row.get("location"),
                "device_status": cls._to_int(row.get("device_status"), fallback=1),
                "device_status_text": row.get("device_status_text") or cls._format_device_status(row.get("device_status")),
                "current_status": cls._normalize_current_status(row.get("current_status")),
                "current_status_text": row.get("current_status_text") or cls._format_current_status(row.get("current_status")),
                "current_status_level": cls._current_status_level(row.get("current_status")),
                "status_source": row.get("status_source"),
                "risk_result_id": row.get("risk_result_id"),
                "risk_score": cls._to_float(row.get("risk_score")),
                "health_score": cls._to_float(row.get("health_score")),
                "health_level": row.get("health_level"),
                "health_status": row.get("health_status"),
                "health_description": row.get("health_description"),
                "latest_prediction_time": cls._format_datetime(row.get("latest_prediction_time")),
                "window_end_time": cls._format_datetime(row.get("window_end_time")),
                "active_alert_count": cls._to_int(row.get("active_alert_count")),
                "highest_active_alert_level": cls._normalize_alert_level(row.get("highest_active_alert_level")),
                "highest_active_alert_time": cls._format_datetime(row.get("highest_active_alert_time")),
                "latest_alert_id": row.get("latest_alert_id"),
                "latest_alert_message": row.get("latest_alert_message"),
                "latest_alert_status": cls._normalize_key(row.get("latest_alert_status")) or None,
                "current_risk_score": cls._to_float(row.get("current_risk_score")),
                "current_health_score": cls._to_float(row.get("current_health_score")),
                "current_event_time": cls._format_datetime(row.get("current_event_time")),
                "current_message": row.get("current_message"),
                "current_alert_level": cls._normalize_alert_level(row.get("current_alert_level")),
                "current_alert_status": cls._normalize_key(row.get("current_alert_status")) or None,
                "current_risk_result_id": row.get("current_risk_result_id"),
                "updated_at": cls._format_datetime(row.get("updated_at")),
            }
            for row in rows
            if isinstance(row, dict)
        ]

    @classmethod
    def _dump_health_distribution(
        cls,
        rows: Any,
        device_status_cards: Any = None,
    ) -> List[Dict[str, Any]]:
        counts = {status: 0 for _level, _label, status in cls.HEALTH_BUCKETS}
        if isinstance(device_status_cards, list):
            for row in device_status_cards:
                if not isinstance(row, dict):
                    continue
                status = cls._to_int(row.get("current_status"))
                if status in counts:
                    counts[status] += 1
        elif isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if "status" in row and "count" in row:
                    status = cls._to_int(row.get("status"))
                    if status in counts:
                        counts[status] += cls._to_int(row.get("count"))
                    continue
                level = cls._normalize_health_level(row.get("health_level") or row.get("health_status"))
                status = cls._status_from_level(level)
                if status == 0:
                    status = cls._to_int(row.get("device_status"))
                if status in counts:
                    counts[status] += 1

        return [
            {
                "level": level,
                "label": label,
                "status": status,
                "count": counts[status],
            }
            for level, label, status in cls.HEALTH_BUCKETS
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
                "alert_time": cls._format_datetime(row.get("alert_time") or row.get("created_at") or row.get("create_time")),
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
                "device_status_text": row.get("device_status_text") or cls._format_device_status(row.get("device_status")),
                "current_status": cls._normalize_current_status(row.get("current_status") or row.get("device_status")),
                "current_status_text": row.get("current_status_text") or cls._format_current_status(row.get("current_status") or row.get("device_status")),
                "current_status_level": cls._current_status_level(row.get("current_status") or row.get("device_status")),
                "status_text": row.get("current_status_text") or cls._format_current_status(row.get("current_status") or row.get("device_status")),
                "status_source": row.get("status_source"),
                "risk_score": cls._to_float(row.get("risk_score")),
                "health_score": cls._to_float(row.get("health_score")),
                "health_level": cls._normalize_health_level(row.get("health_level") or row.get("health_status")),
                "health_status": row.get("health_status"),
                "current_risk_score": cls._to_float(row.get("current_risk_score")),
                "current_health_score": cls._to_float(row.get("current_health_score")),
                "current_event_time": cls._format_datetime(row.get("current_event_time")),
                "current_message": row.get("current_message"),
                "current_alert_level": cls._normalize_alert_level(row.get("current_alert_level")),
                "current_alert_status": cls._normalize_key(row.get("current_alert_status")) or None,
                "current_risk_result_id": row.get("current_risk_result_id"),
                "active_alert_count": cls._to_int(row.get("active_alert_count")),
                "alert_level": cls._normalize_alert_level(row.get("alert_level") or row.get("highest_active_alert_level")),
                "alert_status": cls._normalize_alert_status(row.get("alert_status") or row.get("latest_alert_status")),
                "highest_active_alert_level": cls._normalize_alert_level(row.get("highest_active_alert_level")),
                "highest_active_alert_time": cls._format_datetime(row.get("highest_active_alert_time")),
                "latest_alert_id": row.get("latest_alert_id"),
                "latest_alert_message": row.get("latest_alert_message"),
                "latest_alert_status": cls._normalize_key(row.get("latest_alert_status")) or None,
                "latest_prediction_time": cls._format_datetime(row.get("latest_prediction_time")),
                "window_end_time": cls._format_datetime(row.get("window_end_time") or row.get("ts_end") or row.get("updated_at")),
                "updated_at": cls._format_datetime(row.get("updated_at") or row.get("window_end_time") or row.get("ts_end")),
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
            "严重": "critical",
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
    def _normalize_current_status(cls, value: Any) -> int:
        status = cls._to_int(value, fallback=1)
        return status if status in cls.DEVICE_STATUS_TEXT else 1

    @classmethod
    def _format_current_status(cls, value: Any) -> str:
        return cls.DEVICE_STATUS_TEXT.get(cls._normalize_current_status(value), "正常")

    @classmethod
    def _current_status_level(cls, value: Any) -> str:
        status = cls._normalize_current_status(value)
        return {
            1: "normal",
            2: "attention",
            3: "warning",
            4: "critical",
        }.get(status, "normal")

    @staticmethod
    def _status_from_level(level: Any) -> int:
        return {
            "normal": 1,
            "attention": 2,
            "warning": 3,
            "critical": 4,
        }.get(level, 0)

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
            "warn": "medium",
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
