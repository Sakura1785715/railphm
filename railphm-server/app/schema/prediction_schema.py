from typing import List, Dict, Any, Optional

from app.core.errors import BusinessException
from app.rules import calculate_health_score, clamp_risk_score, map_alert_level


class PredictionSchema:
    """
    预测结果数据序列化 (Schema/DTO 层)
    对内屏蔽数据库字段差异，对外暴露标准稳定结构
    """

    INFER_FIELDS = (
        "device_id",
        "device_code",
        "sample_index",

        "risk_raw",
        "risk_score",
        "risk_raw_std",
        "risk_std",
        "threshold",
        "predicted_label",

        "health_score",
        "health_level",
        "health_status",
        "health_description",

        "alert_generated",
        "alert_level",
        "alert_status",
        "alert_status_text",
        "alert_message",
        "alert_advice",

        "model_name",
        "model_version",
        "calibration_enabled",
        "calibration_method",
        "uncertainty_enabled",
        "uncertainty_method",
        "mc_samples",

        "condition_label",
        "y_true",
        "trace",
        "runtime_error",

        "window_start_time",
        "window_end_time",
        "ts_end",
        "window_minutes",
        "data_source",
    )

    @staticmethod
    def _get_raw_risk_score(record: Dict[str, Any]) -> Any:
        if "risk_score" in record:
            return record["risk_score"]
        if "calibrated_risk_score" in record:
            return record["calibrated_risk_score"]
        raise BusinessException(code=500, message="预测结果缺少风险分数字段", status_code=500)

    @classmethod
    def _attach_interpretation_fields(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一补齐业务解释字段。
        Repository 中可能保留历史冗余 health_score，但最终返回口径必须由 server 侧规则生成。
        """
        if not isinstance(record, dict):
            raise BusinessException(code=500, message="预测结果格式非法", status_code=500)

        try:
            risk_score = clamp_risk_score(cls._get_raw_risk_score(record))
            health_score = calculate_health_score(risk_score)
            alert_level = map_alert_level(health_score)
        except (TypeError, ValueError) as exc:
            raise BusinessException(code=500, message="预测结果风险分数字段非法", status_code=500) from exc

        return {
            **record,
            "risk_score": risk_score,
            "health_score": health_score,
            "alert_level": alert_level,
        }

    @classmethod
    def _format_item(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """统一单条结果格式转换"""
        normalized_record = cls._attach_interpretation_fields(record)
        item = {
            "device_id": normalized_record["device_id"],
            "risk_score": normalized_record["risk_score"],
            "risk_std": normalized_record["risk_std"],
            "health_score": normalized_record["health_score"],
            "alert_level": normalized_record["alert_level"],
            "model_version": normalized_record["model_version"],
            "window_start_time": normalized_record["window_start_time"],
            "window_end_time": normalized_record["window_end_time"],
        }

        if "condition_label" in normalized_record:
            item["condition_label"] = normalized_record["condition_label"]

        return item

    @classmethod
    def dump_latest(cls, record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """返回单体对象，查不到时返回 None，以保持前端语义清晰"""
        if not record:
            return None
        return cls._format_item(record)

    @classmethod
    def dump_history(cls, device_id: int, start_str: str, end_str: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """返回带有 items 的稳定数组结构"""
        return {
            "device_id": device_id,
            "start_time": start_str,
            "end_time": end_str,
            "items": [cls._format_item(r) for r in records]
        }

    @classmethod
    def dump_infer_result(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一收口 infer 输出，避免将外部服务原始结构直接透传给前端。
        阶段 4 在风险字段和健康度字段基础上补充告警判定字段，但不生成真实告警记录。
        """
        if not isinstance(record, dict):
            raise BusinessException(code=502, message="AI 推理服务返回数据格式非法", status_code=502)

        missing_fields = [field for field in cls.INFER_FIELDS if field not in record]
        if missing_fields:
            raise BusinessException(code=502, message="AI 推理服务返回缺少必要字段", status_code=502)

        return {field: record[field] for field in cls.INFER_FIELDS}
