# 暂时放mock数据
from typing import List, Dict, Optional, Any

class DeviceRepository:
    """
    设备数据访问层 (Repository)
    当前阶段使用 Mock 数据，后续替换为 SQLAlchemy 查询逻辑
    """
    
    # 模拟 MySQL phm_device 表的初始数据
    _mock_data: List[Dict[str, Any]] = [
        {"device_id": 1, "car_no": "CR400AF-0201", "atp_type": "CTCS-3", "attach_bureau": "北京局", "device_status": 1},
        {"device_id": 2, "car_no": "CR400BF-0512", "atp_type": "CTCS-3", "attach_bureau": "上海局", "device_status": 1},
        {"device_id": 3, "car_no": "CRH380A-2217", "atp_type": "CTCS-2", "attach_bureau": "广州局", "device_status": 0},
        {"device_id": 4, "car_no": "CR400AF-2011", "atp_type": "CTCS-3", "attach_bureau": "济南局", "device_status": 1},
        {"device_id": 5, "car_no": "CRH2A-1024", "atp_type": "CTCS-2", "attach_bureau": "武汉局", "device_status": 1}
    ]

    @classmethod
    def find_all(cls) -> List[Dict[str, Any]]:
        """查询所有设备"""
        return cls._mock_data

    @classmethod
    def find_filtered(
        cls,
        device_id: Optional[int] = None,
        car_no: Optional[str] = None,
        device_status: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """按最小台账条件筛选设备列表"""
        devices = cls.find_all()

        if device_id is not None:
            devices = [device for device in devices if device.get("device_id") == device_id]

        if car_no:
            keyword = car_no.strip().lower()
            devices = [
                device for device in devices
                if keyword in str(device.get("car_no", "")).lower()
            ]

        if device_status is not None:
            devices = [
                device for device in devices
                if device.get("device_status") == device_status
            ]

        return devices

    @classmethod
    def find_by_id(cls, device_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 查询设备"""
        for device in cls._mock_data:
            if device["device_id"] == device_id:
                return device
        return None
