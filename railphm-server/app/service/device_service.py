import re
from typing import Dict, Any, Optional, List

from app.core.errors import BusinessException
from app.repository.dashboard_repository import DashboardRepository
from app.repository.device_repository import DeviceRepository
from app.schema.device_schema import DeviceSchema


class DeviceService:
    """
    设备业务逻辑层 (Service)
    负责参数校验、异常抛出与 DTO 转换。
    """

    REQUIRED_TEXT_FIELDS = {
        "device_code": "device_code 不能为空",
        "device_name": "device_name 不能为空",
        "atp_type": "atp_type 不能为空",
        "car_no": "car_no 不能为空",
        "attach_bureau": "attach_bureau 不能为空",
    }
    VALID_DEVICE_STATUSES = {1, 2, 3, 4}

    @staticmethod
    def _validate_device_payload(
        payload: Optional[Dict[str, Any]],
        require_device_code: bool = True,
    ) -> Dict[str, Any]:
        """校验并规范化设备台账请求体。"""
        if not payload or not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体不能为空", status_code=400)

        validated: Dict[str, Any] = {}
        required_fields = dict(DeviceService.REQUIRED_TEXT_FIELDS)
        if not require_device_code:
            required_fields.pop("device_code", None)

        for field, message in required_fields.items():
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise BusinessException(code=400, message=message, status_code=400)
            validated[field] = value.strip()

        device_type = payload.get("device_type", "ATP")
        if device_type is None or device_type == "":
            device_type = "ATP"
        if not isinstance(device_type, str):
            raise BusinessException(code=400, message="device_type 必须为字符串", status_code=400)
        validated["device_type"] = device_type.strip() or "ATP"

        if "device_status" not in payload or payload.get("device_status") == "":
            raise BusinessException(code=400, message="device_status 不能为空", status_code=400)
        if isinstance(payload["device_status"], bool):
            raise BusinessException(
                code=400,
                message="device_status 只能为 1、2、3 或 4",
                status_code=400,
            )
        try:
            device_status = int(payload["device_status"])
        except (TypeError, ValueError) as exc:
            raise BusinessException(
                code=400,
                message="device_status 只能为 1、2、3 或 4",
                status_code=400,
            ) from exc
        if device_status not in DeviceService.VALID_DEVICE_STATUSES:
            raise BusinessException(
                code=400,
                message="device_status 只能为 1、2、3 或 4",
                status_code=400,
            )
        validated["device_status"] = device_status

        train_no = payload.get("train_no")
        if train_no is None or train_no == "":
            validated["train_no"] = None
        elif isinstance(train_no, str):
            validated["train_no"] = train_no.strip() or None
        else:
            raise BusinessException(code=400, message="train_no 必须为字符串", status_code=400)

        return validated

    @staticmethod
    def _parse_positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        try:
            parsed_value = int(value)
        except (TypeError, ValueError) as exc:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400) from exc
        if parsed_value <= 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        return parsed_value

    @staticmethod
    def _parse_optional_positive_int(value: Any, field_name: str) -> Optional[int]:
        if value is None or value == "":
            return None
        return DeviceService._parse_positive_int(value, field_name)

    @staticmethod
    def _parse_optional_device_status(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise BusinessException(
                code=400,
                message="device_status 只能为 1、2、3 或 4",
                status_code=400,
            )
        try:
            device_status = int(value)
        except (TypeError, ValueError) as exc:
            raise BusinessException(
                code=400,
                message="device_status 只能为 1、2、3 或 4",
                status_code=400,
            ) from exc
        if device_status not in DeviceService.VALID_DEVICE_STATUSES:
            raise BusinessException(
                code=400,
                message="device_status 只能为 1、2、3 或 4",
                status_code=400,
            )
        return device_status

    @staticmethod
    def get_device_list(
        page: int = 1,
        size: int = 10,
        device_id: Optional[int] = None,
        device_code: Optional[str] = None,
        device_name: Optional[str] = None,
        device_type: Optional[str] = None,
        car_no: Optional[str] = None,
        atp_type: Optional[str] = None,
        train_no: Optional[str] = None,
        attach_bureau: Optional[str] = None,
        device_status: Optional[int] = None,
        current_status: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取设备分页列表。"""
        normalized_page = DeviceService._parse_positive_int(page, "page")
        normalized_size = DeviceService._parse_positive_int(size, "size")
        normalized_device_id = DeviceService._parse_optional_positive_int(device_id, "device_id")
        normalized_current_status = DeviceService._parse_optional_device_status(
            current_status if current_status is not None and current_status != "" else device_status
        )

        devices = DeviceRepository.find_filtered_all(
            device_id=normalized_device_id,
            device_code=device_code,
            device_name=device_name,
            device_type=device_type,
            car_no=car_no,
            atp_type=atp_type,
            train_no=train_no,
            attach_bureau=attach_bureau,
        )
        enriched_devices = DeviceService._merge_current_status(devices)

        if normalized_current_status is not None:
            enriched_devices = [
                device
                for device in enriched_devices
                if DeviceService._normalize_status_value(device.get("current_status")) == normalized_current_status
            ]

        total = len(enriched_devices)
        start_index = (normalized_page - 1) * normalized_size
        page_devices = enriched_devices[start_index:start_index + normalized_size]

        return {
            "items": [DeviceSchema.dump(device) for device in page_devices],
            "total": total,
            "page": normalized_page,
            "size": normalized_size,
        }

    @staticmethod
    def get_next_device_code() -> Dict[str, Any]:
        """生成下一个 ATP 设备业务编号。"""
        return {"device_code": DeviceService._generate_next_device_code(DeviceRepository.find_all_device_codes())}

    @staticmethod
    def get_device_detail(device_id: int) -> Dict[str, Any]:
        """获取单一设备详情。"""
        device = DeviceRepository.find_by_id(device_id)
        if not device:
            raise BusinessException(
                code=404,
                message=f"未找到设备ID为 {device_id} 的设备",
                status_code=404,
            )

        return DeviceSchema.dump(device)

    @staticmethod
    def create_device(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """新增设备台账。"""
        normalized_payload = dict(payload or {})
        if not isinstance(payload, dict):
            normalized_payload = {}
        if not isinstance(normalized_payload.get("device_code"), str) or not normalized_payload.get("device_code", "").strip():
            normalized_payload["device_code"] = DeviceService.get_next_device_code()["device_code"]

        validated_payload = DeviceService._validate_device_payload(normalized_payload)
        device = DeviceRepository.create_device(validated_payload)
        return DeviceSchema.dump(device)

    @staticmethod
    def update_device(device_id: int, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """编辑设备台账。"""
        validated_payload = DeviceService._validate_device_payload(payload, require_device_code=False)
        device = DeviceRepository.update_device(device_id, validated_payload)

        if not device:
            raise BusinessException(
                code=404,
                message=f"未找到设备ID为 {device_id} 的设备",
                status_code=404,
            )

        return DeviceSchema.dump(device)

    @staticmethod
    def _generate_next_device_code(device_codes: List[str]) -> str:
        max_number = 0
        for code in device_codes:
            match = re.fullmatch(r"ATP(\d+)", str(code).strip(), re.IGNORECASE)
            if not match:
                continue
            max_number = max(max_number, int(match.group(1)))

        return f"ATP{max_number + 1:03d}"

    @staticmethod
    def _normalize_status_value(value: Any) -> Optional[int]:
        try:
            status = int(value)
        except (TypeError, ValueError):
            return None

        return status if status in DeviceService.VALID_DEVICE_STATUSES else None

    @staticmethod
    def _merge_current_status(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        overview_rows = DashboardRepository.get_device_status_overview()
        overview_by_id = {
            row.get("device_id"): row
            for row in overview_rows
            if row.get("device_id") is not None
        }
        overview_by_code = {
            row.get("device_code"): row
            for row in overview_rows
            if row.get("device_code")
        }

        enriched_devices: List[Dict[str, Any]] = []
        for device in devices:
            status_row = overview_by_id.get(device.get("device_id")) or overview_by_code.get(device.get("device_code")) or {}
            enriched_device = dict(device)
            enriched_device.update(
                {
                    "ledger_status": device.get("device_status"),
                    "ledger_status_text": status_row.get("device_status_text"),
                    "current_status": status_row.get("current_status", device.get("device_status")),
                    "current_status_text": status_row.get("current_status_text"),
                    "status_source": status_row.get("status_source", "device_status"),
                    "current_risk_score": status_row.get("current_risk_score"),
                    "current_health_score": status_row.get("current_health_score"),
                    "current_alert_level": status_row.get("current_alert_level"),
                    "latest_prediction_time": status_row.get("latest_prediction_time"),
                    "active_alert_count": status_row.get("active_alert_count", 0),
                    "current_event_time": status_row.get("current_event_time"),
                    "current_message": status_row.get("current_message"),
                    "current_alert_status": status_row.get("current_alert_status"),
                    "current_risk_result_id": status_row.get("current_risk_result_id"),
                    "highest_active_alert_level": status_row.get("highest_active_alert_level"),
                    "highest_active_alert_time": status_row.get("highest_active_alert_time"),
                    "latest_alert_id": status_row.get("latest_alert_id"),
                    "latest_alert_message": status_row.get("latest_alert_message"),
                    "latest_alert_status": status_row.get("latest_alert_status"),
                }
            )
            enriched_devices.append(enriched_device)

        return enriched_devices
