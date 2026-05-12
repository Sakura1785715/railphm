import logging
from typing import Any, Dict

from app.core.errors import BusinessException
from app.core.risk_rules import (
    HEALTH_DESCRIPTION_ATTENTION,
    HEALTH_DESCRIPTION_CRITICAL,
    HEALTH_DESCRIPTION_NORMAL,
    HEALTH_DESCRIPTION_WARNING,
    HEALTH_LEVEL_ATTENTION,
    HEALTH_LEVEL_CRITICAL,
    HEALTH_LEVEL_NORMAL,
    HEALTH_LEVEL_WARNING,
    HEALTH_SCORE_DECIMALS,
    HEALTH_STATUS_ATTENTION,
    HEALTH_STATUS_CRITICAL,
    HEALTH_STATUS_NORMAL,
    HEALTH_STATUS_WARNING,
    RISK_THRESHOLD_CRITICAL,
    RISK_THRESHOLD_NORMAL,
    RISK_THRESHOLD_WARNING,
)


class HealthService:
    """
    健康度映射服务。
    risk_score 越高代表故障风险越高，health_score = 100 * (1 - risk_score)。
    """

    def __init__(
        self,
        risk_threshold_normal: float = RISK_THRESHOLD_NORMAL,
        risk_threshold_warning: float = RISK_THRESHOLD_WARNING,
        risk_threshold_critical: float = RISK_THRESHOLD_CRITICAL,
        health_score_decimals: int = HEALTH_SCORE_DECIMALS,
        logger: logging.Logger | None = None,
    ):
        self.risk_threshold_normal = float(risk_threshold_normal)
        self.risk_threshold_warning = float(risk_threshold_warning)
        self.risk_threshold_critical = float(risk_threshold_critical)
        self.health_score_decimals = int(health_score_decimals)
        self.logger = logger or logging.getLogger(__name__)

    def evaluate(self, risk_score: Any) -> Dict[str, Any]:
        normalized_risk_score = self._parse_risk_score(risk_score)
        clipped_risk_score = self._clip_risk_score(normalized_risk_score)
        health_score = round(
            100 * (1 - clipped_risk_score),
            self.health_score_decimals,
        )

        if clipped_risk_score < self.risk_threshold_normal:
            return {
                "health_score": health_score,
                "health_level": HEALTH_LEVEL_NORMAL,
                "health_status": HEALTH_STATUS_NORMAL,
                "health_description": HEALTH_DESCRIPTION_NORMAL,
            }

        if clipped_risk_score < self.risk_threshold_warning:
            return {
                "health_score": health_score,
                "health_level": HEALTH_LEVEL_ATTENTION,
                "health_status": HEALTH_STATUS_ATTENTION,
                "health_description": HEALTH_DESCRIPTION_ATTENTION,
            }

        if clipped_risk_score < self.risk_threshold_critical:
            return {
                "health_score": health_score,
                "health_level": HEALTH_LEVEL_WARNING,
                "health_status": HEALTH_STATUS_WARNING,
                "health_description": HEALTH_DESCRIPTION_WARNING,
            }

        return {
            "health_score": health_score,
            "health_level": HEALTH_LEVEL_CRITICAL,
            "health_status": HEALTH_STATUS_CRITICAL,
            "health_description": HEALTH_DESCRIPTION_CRITICAL,
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
            self.logger.warning("risk_score below 0, clipped to 0")
            return 0.0
        if risk_score > 1.0:
            self.logger.warning("risk_score above 1, clipped to 1")
            return 1.0
        return risk_score
