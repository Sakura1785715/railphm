# 返回结果结构化
from typing import Dict, Any

class DeviceSchema:
    """
    设备数据轻量级序列化结构 (Schema/DTO 层)
    目前不引入 Marshmallow 等复杂依赖，仅作最小结构控制
    """
    @staticmethod
    def dump(device: Dict[str, Any]) -> Dict[str, Any]:
        """将底层数据（目前是字典，未来可能是ORM对象）转换为 API 返回格式"""
        if not device:
            return {}
        return {
            "device_id": device.get("device_id"),
            "car_no": device.get("car_no"),
            "atp_type": device.get("atp_type"),
            "attach_bureau": device.get("attach_bureau"),
            "device_status": device.get("device_status")
        }