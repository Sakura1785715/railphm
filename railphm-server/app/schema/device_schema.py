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
        return {
            "device_id": device.get("device_id"),
            "device_code": device.get("device_code"),
            "device_name": device.get("device_name"),
            "device_type": device.get("device_type"),
            "device_status": device_status,
            "device_status_text": DeviceSchema.DEVICE_STATUS_TEXT.get(device_status, "未知"),
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
