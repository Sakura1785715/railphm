# 返回结果结构化
from datetime import datetime
from typing import Dict, Any

class DeviceSchema:
    """
    设备数据轻量级序列化结构 (Schema/DTO 层)
    目前不引入 Marshmallow 等复杂依赖，仅作最小结构控制
    """
    DEVICE_STATUS_TEXT = {
        1: "正常",
        2: "关注",
        3: "预警",
        4: "告警",
    }

    @staticmethod
    def dump(device: Dict[str, Any]) -> Dict[str, Any]:
        """将底层设备字典转换为 API 返回格式"""
        if not device:
            return {}
        device_status = device.get("device_status")
        ledger_status = device.get("ledger_status", device_status)
        current_status = device.get("current_status", device_status)
        return {
            "device_id": device.get("device_id"),
            "device_code": device.get("device_code"),
            "device_name": device.get("device_name"),
            "device_type": device.get("device_type"),
            "device_status": device_status,
            "device_status_text": DeviceSchema.DEVICE_STATUS_TEXT.get(device_status, "未知"),
            "ledger_status": ledger_status,
            "ledger_status_text": device.get("ledger_status_text") or DeviceSchema.DEVICE_STATUS_TEXT.get(ledger_status, "未知"),
            "current_status": current_status,
            "current_status_text": device.get("current_status_text") or DeviceSchema.DEVICE_STATUS_TEXT.get(current_status, "未知"),
            "status_source": device.get("status_source") or "device_status",
            "current_risk_score": device.get("current_risk_score"),
            "current_health_score": device.get("current_health_score"),
            "current_alert_level": device.get("current_alert_level"),
            "current_alert_status": device.get("current_alert_status"),
            "latest_prediction_time": DeviceSchema._format_datetime(device.get("latest_prediction_time")),
            "active_alert_count": device.get("active_alert_count"),
            "current_event_time": DeviceSchema._format_datetime(device.get("current_event_time")),
            "current_message": device.get("current_message"),
            "current_risk_result_id": device.get("current_risk_result_id"),
            "highest_active_alert_level": device.get("highest_active_alert_level"),
            "highest_active_alert_time": DeviceSchema._format_datetime(device.get("highest_active_alert_time")),
            "latest_alert_id": device.get("latest_alert_id"),
            "latest_alert_message": device.get("latest_alert_message"),
            "latest_alert_status": device.get("latest_alert_status"),
            "atp_type": device.get("atp_type"),
            "car_no": device.get("car_no"),
            "train_no": device.get("train_no"),
            "attach_bureau": device.get("attach_bureau"),
            "create_time": DeviceSchema._format_datetime(device.get("create_time")),
            "update_time": DeviceSchema._format_datetime(device.get("update_time")),
        }

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value
