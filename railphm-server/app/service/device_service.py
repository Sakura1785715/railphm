# 业务逻辑编排与抛出异常
from typing import Dict, Any, Optional
from app.repository.device_repository import DeviceRepository
from app.schema.device_schema import DeviceSchema
from app.core.errors import BusinessException

class DeviceService:
    """
    设备业务逻辑层 (Service)
    负责分页计算、异常抛出与 DTO 转换
    """
    REQUIRED_TEXT_FIELDS = {
        "car_no": "car_no 不能为空",
        "atp_type": "atp_type 不能为空",
        "attach_bureau": "attach_bureau 不能为空"
    }

    @staticmethod
    def _validate_device_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """校验并规范化设备台账请求体"""
        if not payload or not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体不能为空", status_code=400)

        validated: Dict[str, Any] = {}
        for field, message in DeviceService.REQUIRED_TEXT_FIELDS.items():
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise BusinessException(code=400, message=message, status_code=400)
            validated[field] = value.strip()

        if "device_status" not in payload:
            raise BusinessException(code=400, message="device_status 不能为空", status_code=400)

        if isinstance(payload["device_status"], bool) or not isinstance(payload["device_status"], int):
            raise BusinessException(code=400, message="device_status 只能为 0 或 1", status_code=400)

        device_status = payload["device_status"]
        if device_status not in (0, 1):
            raise BusinessException(code=400, message="device_status 只能为 0 或 1", status_code=400)

        validated["device_status"] = device_status
        return validated
    
    @staticmethod
    def get_device_list(
        page: int = 1,
        size: int = 10,
        device_id: Optional[int] = None,
        car_no: Optional[str] = None,
        device_status: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取设备分页列表"""
        normalized_page = max(page, 1)
        normalized_size = max(size, 1)
        all_devices = DeviceRepository.find_filtered(
            device_id=device_id,
            car_no=car_no,
            device_status=device_status
        )
        total = len(all_devices)

        # 内存级模拟分页
        start_idx = (normalized_page - 1) * normalized_size
        end_idx = start_idx + normalized_size
        paged_devices = all_devices[start_idx:end_idx]
        
        # 经 Schema 序列化处理
        items = [DeviceSchema.dump(device) for device in paged_devices]
        
        return {
            "items": items,
            "total": total,
            "page": normalized_page,
            "size": normalized_size
        }

    @staticmethod
    def get_device_detail(device_id: int) -> Dict[str, Any]:
        """获取单一设备详情"""
        device = DeviceRepository.find_by_id(device_id)
        
        # 核心业务断言：找不到则抛出业务异常，由全局异常拦截处理
        if not device:
            raise BusinessException(
                code=404, 
                message=f"未找到设备ID为 {device_id} 的设备", 
                status_code=404
            )
            
        return DeviceSchema.dump(device)

    @staticmethod
    def create_device(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """新增设备台账"""
        validated_payload = DeviceService._validate_device_payload(payload)
        device = DeviceRepository.create_device(validated_payload)
        return DeviceSchema.dump(device)

    @staticmethod
    def update_device(device_id: int, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """编辑设备台账"""
        validated_payload = DeviceService._validate_device_payload(payload)
        device = DeviceRepository.update_device(device_id, validated_payload)

        if not device:
            raise BusinessException(
                code=404,
                message=f"未找到设备ID为 {device_id} 的设备",
                status_code=404
            )

        return DeviceSchema.dump(device)
