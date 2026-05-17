from datetime import datetime
from typing import Dict, Any, Optional

from flask import current_app

from app.clients import AIClient, AIResponseFormatError, AIServiceError
from app.core.errors import BusinessException
from app.repository.prediction_repository import PredictionRepository
from app.schema.prediction_schema import PredictionSchema
from app.service.alert_service import AlertService
from app.service.health_service import HealthService


class PredictionService:
    """
    预测结果业务层 (Service)
    负责参数解析、时间校验以及逻辑编排
    """

    @staticmethod
    def _build_health_service() -> HealthService:
        return HealthService(
            risk_threshold_normal=current_app.config.get("RISK_THRESHOLD_NORMAL", 0.26),
            risk_threshold_warning=current_app.config.get("RISK_THRESHOLD_WARNING", 0.45),
            risk_threshold_critical=current_app.config.get("RISK_THRESHOLD_CRITICAL", 0.65),
            health_score_decimals=current_app.config.get("HEALTH_SCORE_DECIMALS", 2),
            logger=current_app.logger,
        )

    @staticmethod
    def _build_alert_service() -> AlertService:
        return AlertService(
            risk_threshold_normal=current_app.config.get("RISK_THRESHOLD_NORMAL", 0.26),
            risk_threshold_warning=current_app.config.get("RISK_THRESHOLD_WARNING", 0.45),
            risk_threshold_critical=current_app.config.get("RISK_THRESHOLD_CRITICAL", 0.65),
            logger=current_app.logger,
        )

    @staticmethod
    def _attach_health_fields(result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            health_result = PredictionService._build_health_service().evaluate(
                result.get("risk_score")
            )
        except BusinessException:
            current_app.logger.warning("Health mapping failed for infer result")
            raise

        return {
            **result,
            **health_result,
        }

    @staticmethod
    def _attach_alert_fields(result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            alert_result = PredictionService._build_alert_service().evaluate(
                risk_score=result.get("risk_score"),
                health_score=result.get("health_score"),
                health_level=result.get("health_level"),
                predicted_label=result.get("predicted_label"),
            )
        except BusinessException:
            current_app.logger.warning("Alert evaluation failed for infer result")
            raise

        return {
            **result,
            **alert_result,
        }

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
    def _parse_infer_device_id(device_id_value: Any) -> Any:
        if device_id_value is None or device_id_value == "":
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        if isinstance(device_id_value, bool):
            raise BusinessException(code=400, message="device_id 格式非法", status_code=400)
        if isinstance(device_id_value, int):
            return {
                "device_id": device_id_value,
                "ai_device_id": device_id_value,
            }
        if not isinstance(device_id_value, str):
            raise BusinessException(code=400, message="device_id 格式非法", status_code=400)
        normalized_device_id = device_id_value.strip()
        if not normalized_device_id:
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        if normalized_device_id.isdigit():
            return {
                "device_id": normalized_device_id,
                "ai_device_id": int(normalized_device_id),
            }
        return {
            "device_id": normalized_device_id,
            "ai_device_id": PredictionService._build_ai_device_id(normalized_device_id),
        }

    @staticmethod
    def _build_ai_device_id(device_id: str) -> int:
        """
        当前 railphm-ai /infer schema 仍要求 device_id 为整数。
        server 对外保留业务设备编号，同时从编号中提取数字部分转给 AI；
        例如 ATP001 -> 1。没有数字时使用 0，仅作为现阶段本地窗口样本推理适配。
        """
        digits = "".join(char for char in device_id if char.isdigit())
        return int(digits) if digits else 0

    @staticmethod
    def _parse_optional_positive_int(value: Any, field_name: str, default: int) -> int:
        if value is None or value == "":
            return default
        if isinstance(value, bool) or not isinstance(value, int):
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        if value <= 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        return value

    @staticmethod
    def _parse_optional_non_negative_int(value: Any, field_name: str, default: int) -> int:
        if value is None or value == "":
            return default
        if isinstance(value, bool) or not isinstance(value, int):
            raise BusinessException(code=400, message=f"{field_name} 必须为非负整数", status_code=400)
        if value < 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为非负整数", status_code=400)
        return value

    @staticmethod
    def _validate_infer_request(request_data: Any) -> Dict[str, Any]:
        if not isinstance(request_data, dict):
            raise BusinessException(code=400, message="请求体必须为 JSON 对象", status_code=400)

        device_info = PredictionService._parse_infer_device_id(request_data.get("device_id"))
        return {
            "device_id": device_info["device_id"],
            "ai_device_id": device_info["ai_device_id"],
            "ts_end": PredictionService._parse_ts_end(request_data.get("ts_end")),
            "window_minutes": PredictionService._parse_optional_positive_int(
                request_data.get("window_minutes"),
                "window_minutes",
                30,
            ),
            "sample_index": PredictionService._parse_optional_non_negative_int(
                request_data.get("sample_index"),
                "sample_index",
                0,
            ),
            "mc_samples": PredictionService._parse_optional_positive_int(
                request_data.get("mc_samples"),
                "mc_samples",
                20,
            ),
        }

    @staticmethod
    def _build_ai_payload(validated_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "device_id": validated_data["ai_device_id"],
            "ts_end": validated_data["ts_end"],
            "window_minutes": validated_data["window_minutes"],
            "sample_index": validated_data["sample_index"],
            "mc_samples": validated_data["mc_samples"],
        }

    @staticmethod
    def _parse_ai_float(value: Any, field_name: str, *, required: bool, default: float | None = None) -> float:
        if value is None or value == "":
            if required:
                raise AIResponseFormatError(f"AI 推理服务返回缺少必要字段: {field_name}")
            return float(default)
        if isinstance(value, bool):
            raise AIResponseFormatError("AI 推理服务返回数据格式非法")
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise AIResponseFormatError("AI 推理服务返回数据格式非法") from exc

    @staticmethod
    def _normalize_ai_result(ai_data: Dict[str, Any], request_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(ai_data, dict):
            raise AIResponseFormatError()

        risk_score = PredictionService._parse_ai_float(
            ai_data.get("risk_score"),
            "risk_score",
            required=True,
        )
        threshold = PredictionService._parse_ai_float(
            ai_data.get("threshold"),
            "threshold",
            required=False,
            default=current_app.config.get("AI_DEFAULT_THRESHOLD", 0.26),
        )
        risk_raw = PredictionService._parse_ai_float(
            ai_data.get("risk_raw"),
            "risk_raw",
            required=False,
            default=risk_score,
        )
        risk_std = PredictionService._parse_ai_float(
            ai_data.get("risk_std"),
            "risk_std",
            required=False,
            default=0.0,
        )

        predicted_label = ai_data.get("predicted_label")
        if predicted_label is None or predicted_label == "":
            predicted_label = int(risk_score >= threshold)
        elif isinstance(predicted_label, bool) or not isinstance(predicted_label, int):
            raise AIResponseFormatError("AI 推理服务返回数据格式非法")

        return {
            "device_id": request_data["device_id"],
            "device_code": str(request_data["device_id"]),
            "sample_index": ai_data.get("sample_index", request_data["sample_index"]),

            "risk_raw": risk_raw,
            "risk_score": risk_score,
            "risk_raw_std": PredictionService._parse_ai_float(
                ai_data.get("risk_raw_std"),
                "risk_raw_std",
                required=False,
                default=0.0,
            ),
            "risk_std": risk_std,
            "threshold": threshold,
            "predicted_label": predicted_label,

            "model_name": ai_data.get("model_name") or "unknown",
            "model_version": ai_data.get("model_version") or "unknown",

            "calibration_enabled": bool(ai_data.get("calibration_enabled", False)),
            "calibration_method": ai_data.get("calibration_method"),
            "uncertainty_enabled": bool(ai_data.get("uncertainty_enabled", False)),
            "uncertainty_method": ai_data.get("uncertainty_method") or "unknown",
            "mc_samples": ai_data.get("mc_samples", request_data["mc_samples"]),

            "condition_label": ai_data.get("condition_label"),
            "y_true": ai_data.get("y_true"),
            "trace": ai_data.get("trace") or {},
            "runtime_error": ai_data.get("runtime_error"),

            "window_start_time": ai_data.get("window_start_time"),
            "window_end_time": ai_data.get("window_end_time") or request_data["ts_end"],
            "ts_end": ai_data.get("ts_end") or request_data["ts_end"],
            "window_minutes": ai_data.get("window_minutes") or request_data["window_minutes"],
            "data_source": ai_data.get("data_source") or "ai_service",
        }

    @staticmethod
    def _build_mock_fallback(validated_data: Dict[str, Any]) -> Dict[str, Any]:
        profiles = (
            {"risk_score": 0.21, "risk_std": 0.02},
            {"risk_score": 0.52, "risk_std": 0.04},
            {"risk_score": 0.82, "risk_std": 0.07},
        )
        profile = profiles[validated_data["sample_index"] % len(profiles)]
        risk_score = profile["risk_score"]
        threshold = current_app.config.get("AI_DEFAULT_THRESHOLD", 0.26)

        return {
            "device_id": validated_data["device_id"],
            "sample_index": validated_data["sample_index"],
            "risk_raw": risk_score,
            "risk_score": risk_score,
            "risk_std": profile["risk_std"],
            "threshold": threshold,
            "predicted_label": int(risk_score >= threshold),
            "model_version": "mock",
            "window_start_time": None,
            "window_end_time": validated_data["ts_end"],
            "data_source": "mock_fallback",
            "uncertainty_method": "unknown",
            "risk_raw_std": 0.0,
            "model_name": "mock",
            "calibration_enabled": False,
            "calibration_method": None,
            "uncertainty_enabled": False,
            "mc_samples": 0,
            "condition_label": None,
            "y_true": None,
            "trace": {},
            "runtime_error": None,
            "device_code": str(validated_data["device_id"]),
            "ts_end": validated_data["ts_end"],
            "window_minutes": validated_data["window_minutes"],
        }

    @staticmethod
    def infer_prediction(request_data: Any) -> Dict[str, Any]:
        validated_data = PredictionService._validate_infer_request(request_data)
        ai_payload = PredictionService._build_ai_payload(validated_data)

        try:
            ai_result = AIClient().infer(ai_payload)
        except AIResponseFormatError:
            raise
        except AIServiceError as exc:
            if current_app.config.get("AI_ENABLE_FALLBACK", False):
                current_app.logger.warning(
                    "AI infer failed; returning mock fallback",
                    extra={"error": exc.message},
                )
                return PredictionSchema.dump_infer_result(
                    PredictionService._attach_alert_fields(
                        PredictionService._attach_health_fields(
                            PredictionService._build_mock_fallback(validated_data)
                        )
                    )
                )
            raise

        record = PredictionService._normalize_ai_result(ai_result, validated_data)
        record = PredictionService._attach_health_fields(record)
        record = PredictionService._attach_alert_fields(record)
        return PredictionSchema.dump_infer_result(record)
