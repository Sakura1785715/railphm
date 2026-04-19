from datetime import datetime
from typing import Dict, Any, Optional

from app.clients import AIClient
from app.core.errors import BusinessException
from app.repository.prediction_repository import PredictionRepository
from app.rules import calculate_health_score, clamp_risk_score, map_alert_level
from app.schema.prediction_schema import PredictionSchema


class PredictionService:
    """
    预测结果业务层 (Service)
    负责参数解析、时间校验以及逻辑编排
    """

    @staticmethod
    def _parse_device_id(device_id_value: Any) -> int:
        if device_id_value is None or device_id_value == "":
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        if isinstance(device_id_value, bool):
            raise BusinessException(code=400, message="device_id 必须为整数", status_code=400)
        try:
            return int(device_id_value)
        except (TypeError, ValueError):
            raise BusinessException(code=400, message="device_id 必须为整数", status_code=400)

    @staticmethod
    def get_latest_prediction(device_id_str: str) -> Optional[Dict[str, Any]]:
        device_id = PredictionService._parse_device_id(device_id_str)

        record = PredictionRepository.get_latest_by_device_id(device_id)
        return PredictionSchema.dump_latest(record)

    @staticmethod
    def get_prediction_history(device_id_str: str, start_str: str, end_str: str) -> Dict[str, Any]:
        device_id = PredictionService._parse_device_id(device_id_str)

        if not start_str:
            raise BusinessException(code=400, message="start_time 不能为空", status_code=400)
        if not end_str:
            raise BusinessException(code=400, message="end_time 不能为空", status_code=400)

        # 解析与校验时间
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise BusinessException(code=400, message="时间格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式", status_code=400)

        if start_dt >= end_dt:
            raise BusinessException(code=400, message="开始时间必须早于结束时间", status_code=400)

        records = PredictionRepository.query_history_by_device_and_range(device_id, start_dt, end_dt)
        return PredictionSchema.dump_history(device_id, start_str, end_str, records)

    @staticmethod
    def _parse_ts_end(ts_end: Any) -> str:
        if ts_end is None or ts_end == "":
            raise BusinessException(code=400, message="ts_end 不能为空", status_code=400)
        if not isinstance(ts_end, str):
            raise BusinessException(
                code=400,
                message="ts_end 时间格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            )

        try:
            datetime.strptime(ts_end, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise BusinessException(
                code=400,
                message="ts_end 时间格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            )
        return ts_end

    @staticmethod
    def _parse_window_minutes(window_minutes_value: Any) -> int:
        if window_minutes_value is None or window_minutes_value == "":
            raise BusinessException(code=400, message="window_minutes 不能为空", status_code=400)
        if isinstance(window_minutes_value, bool):
            raise BusinessException(code=400, message="window_minutes 必须为正整数", status_code=400)

        try:
            window_minutes = int(window_minutes_value)
        except (TypeError, ValueError):
            raise BusinessException(code=400, message="window_minutes 必须为正整数", status_code=400)

        if window_minutes <= 0:
            raise BusinessException(code=400, message="window_minutes 必须为正整数", status_code=400)
        return window_minutes

    @staticmethod
    def _parse_risk_score(risk_score_value: Any) -> float:
        if risk_score_value is None or risk_score_value == "":
            raise BusinessException(code=502, message="AI 推理服务返回缺少必要字段", status_code=502)
        if isinstance(risk_score_value, bool):
            raise BusinessException(code=502, message="AI 推理服务返回数据格式非法", status_code=502)

        try:
            return float(risk_score_value)
        except (TypeError, ValueError):
            raise BusinessException(code=502, message="AI 推理服务返回数据格式非法", status_code=502)

    @staticmethod
    def _build_infer_result(record: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(record, dict):
            raise BusinessException(code=502, message="AI 推理服务返回数据格式非法", status_code=502)

        raw_risk_score = PredictionService._parse_risk_score(record.get("risk_score"))
        normalized_risk_score = clamp_risk_score(raw_risk_score)
        health_score = calculate_health_score(normalized_risk_score)
        alert_level = map_alert_level(health_score)

        # 当前阶段健康度与告警级别属于后端业务解释规则。
        # 后续即使接入真实模型，也优先保持该规则在 server 侧稳定，仅替换风险分数来源。
        return {
            **record,
            "risk_score": normalized_risk_score,
            "health_score": health_score,
            "alert_level": alert_level,
        }

    @staticmethod
    def infer_prediction(device_id_value: Any, ts_end: Any, window_minutes_value: Any) -> Dict[str, Any]:
        device_id = PredictionService._parse_device_id(device_id_value)
        normalized_ts_end = PredictionService._parse_ts_end(ts_end)
        window_minutes = PredictionService._parse_window_minutes(window_minutes_value)

        ai_result = AIClient().infer(
            device_id=device_id,
            ts_end=normalized_ts_end,
            window_minutes=window_minutes,
        )
        record = PredictionService._build_infer_result(ai_result)
        return PredictionSchema.dump_infer_result(record)
