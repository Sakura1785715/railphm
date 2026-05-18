# app/service/alert_service.py
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.core.errors import BusinessException
from app.core.risk_rules import (
    ALERT_ADVICE_HIGH,
    ALERT_ADVICE_LOW,
    ALERT_ADVICE_MEDIUM,
    ALERT_ADVICE_NONE,
    ALERT_LEVEL_HIGH,
    ALERT_LEVEL_LOW,
    ALERT_LEVEL_MEDIUM,
    ALERT_LEVEL_NONE,
    ALERT_MESSAGE_HIGH,
    ALERT_MESSAGE_LOW,
    ALERT_MESSAGE_MEDIUM,
    ALERT_MESSAGE_NONE,
    ALERT_STATUS_NONE,
    ALERT_STATUS_TEXT_NONE,
    ALERT_STATUS_TEXT_UNHANDLED,
    ALERT_STATUS_UNHANDLED,
    RISK_THRESHOLD_CRITICAL,
    RISK_THRESHOLD_NORMAL,
    RISK_THRESHOLD_WARNING,
)
from app.repository.alert_repository import AlertRepository
from app.schema.alert_schema import AlertSchema


class AlertService:
    """
    告警业务层 (Service)
    负责分页校验与业务流转编排
    """
    VALID_ALERT_STATUSES = {"unhandled", "processing", "resolved"}

    def __init__(
        self,
        risk_threshold_normal: float = RISK_THRESHOLD_NORMAL,
        risk_threshold_warning: float = RISK_THRESHOLD_WARNING,
        risk_threshold_critical: float = RISK_THRESHOLD_CRITICAL,
        logger: logging.Logger | None = None,
    ):
        self.risk_threshold_normal = float(risk_threshold_normal)
        self.risk_threshold_warning = float(risk_threshold_warning)
        self.risk_threshold_critical = float(risk_threshold_critical)
        self.logger = logger or logging.getLogger(__name__)

    def evaluate(
        self,
        risk_score: Any,
        health_score: float | None = None,
        health_level: str | None = None,
        predicted_label: int | None = None,
    ) -> Dict[str, Any]:
        """
        根据 risk_score 生成本次推理的告警判断结果。
        alert_level 表示告警严重程度，不等同于 health_level；本方法不写数据库。
        """
        normalized_risk_score = self._parse_risk_score(risk_score)
        clipped_risk_score = self._clip_risk_score(normalized_risk_score)

        if clipped_risk_score < self.risk_threshold_normal:
            return {
                "alert_generated": False,
                "alert_level": ALERT_LEVEL_NONE,
                "alert_status": ALERT_STATUS_NONE,
                "alert_status_text": ALERT_STATUS_TEXT_NONE,
                "alert_message": ALERT_MESSAGE_NONE,
                "alert_advice": ALERT_ADVICE_NONE,
            }

        if clipped_risk_score < self.risk_threshold_warning:
            return {
                "alert_generated": True,
                "alert_level": ALERT_LEVEL_LOW,
                "alert_status": ALERT_STATUS_UNHANDLED,
                "alert_status_text": ALERT_STATUS_TEXT_UNHANDLED,
                "alert_message": ALERT_MESSAGE_LOW,
                "alert_advice": ALERT_ADVICE_LOW,
            }

        if clipped_risk_score < self.risk_threshold_critical:
            return {
                "alert_generated": True,
                "alert_level": ALERT_LEVEL_MEDIUM,
                "alert_status": ALERT_STATUS_UNHANDLED,
                "alert_status_text": ALERT_STATUS_TEXT_UNHANDLED,
                "alert_message": ALERT_MESSAGE_MEDIUM,
                "alert_advice": ALERT_ADVICE_MEDIUM,
            }

        self.logger.info(
            "High risk alert generated",
            extra={
                "health_score": health_score,
                "health_level": health_level,
                "predicted_label": predicted_label,
            },
        )
        return {
            "alert_generated": True,
            "alert_level": ALERT_LEVEL_HIGH,
            "alert_status": ALERT_STATUS_UNHANDLED,
            "alert_status_text": ALERT_STATUS_TEXT_UNHANDLED,
            "alert_message": ALERT_MESSAGE_HIGH,
            "alert_advice": ALERT_ADVICE_HIGH,
        }

    def _parse_risk_score(self, risk_score: Any) -> float:
        if risk_score is None or risk_score == "":
            raise BusinessException(
                code=400,
                message="risk_score 不能为空",
                status_code=400,
            )
        if isinstance(risk_score, bool):
            raise BusinessException(
                code=400,
                message="risk_score 格式非法",
                status_code=400,
            )
        try:
            return float(risk_score)
        except (TypeError, ValueError) as exc:
            raise BusinessException(
                code=400,
                message="risk_score 格式非法",
                status_code=400,
            ) from exc

    def _clip_risk_score(self, risk_score: float) -> float:
        if risk_score < 0.0:
            self.logger.warning("risk_score below 0, clipped to 0 for alert evaluation")
            return 0.0
        if risk_score > 1.0:
            self.logger.warning("risk_score above 1, clipped to 1 for alert evaluation")
            return 1.0
        return risk_score

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

        try:
            normalized_status = AlertRepository._normalize_alert_status(alert_status)
            normalized_level = AlertRepository._normalize_alert_level(alert_level)
        except ValueError as exc:
            raise BusinessException(code=400, message=str(exc), status_code=400) from exc

        total, items = AlertRepository.query_alerts(
            page,
            size,
            normalized_status,
            normalized_level,
            device_id_str,
        )
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
        try:
            normalized_status = AlertRepository._normalize_alert_status(alert_status)
        except ValueError as exc:
            raise BusinessException(code=400, message=str(exc), status_code=400) from exc
        if normalized_status not in AlertService.VALID_ALERT_STATUSES:
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
        if normalized_status in {"processing", "resolved"}:
            handle_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record = AlertRepository.update_alert_status(
            alert_id=alert_id,
            alert_status=normalized_status,
            handler_id=handler_id,
            handle_note=handle_note,
            handle_time=handle_time,
        )
        if not record:
            raise BusinessException(code=404, message=f"未找到告警ID为 {alert_id} 的告警记录", status_code=404)

        return AlertSchema.dump_detail(record)
