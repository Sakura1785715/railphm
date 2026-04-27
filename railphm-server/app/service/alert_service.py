# app/service/alert_service.py
from datetime import datetime
from typing import Dict, Any, Optional
from app.core.errors import BusinessException
from app.repository.alert_repository import AlertRepository
from app.schema.alert_schema import AlertSchema

class AlertService:
    """
    告警业务层 (Service)
    负责分页校验与业务流转编排
    """
    VALID_ALERT_STATUSES = {"PENDING", "PROCESSING", "RESOLVED"}

    @staticmethod
    def _parse_pagination(page_str: Any, size_str: Any) -> tuple[int, int]:
        """解析并校验分页参数"""
        try:
            page = int(page_str)
            size = int(size_str)
            if page <= 0:
                raise ValueError
            if size <= 0:
                raise ValueError
            return page, size
        except (ValueError, TypeError):
            raise BusinessException(code=400, message="page 和 size 必须为正整数", status_code=400)

    @staticmethod
    def get_alert_list(page_str: Any, size_str: Any, alert_status: Optional[str], alert_level: Optional[str], device_id_str: Optional[str]) -> Dict[str, Any]:
        page, size = AlertService._parse_pagination(page_str, size_str)
        
        device_id = None
        if device_id_str is not None:
            try:
                device_id = int(device_id_str)
            except ValueError:
                raise BusinessException(code=400, message="device_id 必须为整数", status_code=400)

        total, items = AlertRepository.query_alerts(page, size, alert_status, alert_level, device_id)
        return AlertSchema.dump_page(items, total, page, size)

    @staticmethod
    def get_alert_detail(alert_id: int) -> Dict[str, Any]:
        record = AlertRepository.get_alert_by_id(alert_id)
        if not record:
            raise BusinessException(code=404, message=f"未找到告警ID为 {alert_id} 的告警记录", status_code=404)
        return AlertSchema.dump_detail(record)

    @staticmethod
    def update_alert_status(alert_id: int, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not payload or not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体不能为空", status_code=400)

        alert_status = payload.get("alert_status")
        if not alert_status:
            raise BusinessException(code=400, message="alert_status 不能为空", status_code=400)
        if alert_status not in AlertService.VALID_ALERT_STATUSES:
            raise BusinessException(code=400, message="非法告警状态", status_code=400)

        handler_id = None
        if "handler_id" in payload:
            if isinstance(payload["handler_id"], bool):
                raise BusinessException(code=400, message="handler_id 必须为正整数", status_code=400)
            try:
                handler_id = int(payload["handler_id"])
            except (ValueError, TypeError):
                raise BusinessException(code=400, message="handler_id 必须为正整数", status_code=400)
            if handler_id <= 0:
                raise BusinessException(code=400, message="handler_id 必须为正整数", status_code=400)

        handle_note = None
        if "handle_note" in payload:
            handle_note = payload["handle_note"]
            if not isinstance(handle_note, str):
                raise BusinessException(code=400, message="handle_note 必须为字符串", status_code=400)

        handle_time = None
        if alert_status in {"PROCESSING", "RESOLVED"}:
            handle_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record = AlertRepository.update_alert_status(
            alert_id=alert_id,
            alert_status=alert_status,
            handler_id=handler_id,
            handle_note=handle_note,
            handle_time=handle_time,
        )
        if not record:
            raise BusinessException(code=404, message=f"未找到告警ID为 {alert_id} 的告警记录", status_code=404)

        return AlertSchema.dump_detail(record)
