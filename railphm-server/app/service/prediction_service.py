import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from flask import current_app

from app.clients import AIClient, AIResponseFormatError, AIServiceError
from app.core.errors import BusinessException
from app.repository.alert_repository import AlertRepository
from app.repository.monitor_repository import MonitorRepository
from app.repository.prediction_repository import PredictionRepository
from app.schema.prediction_schema import PredictionSchema
from app.service.alert_service import AlertService
from app.service.health_curve_service import HealthCurveService
from app.service.health_service import HealthService


class PredictionService:
    """
    预测结果业务层 (Service)
    负责参数解析、时间校验以及逻辑编排
    """

    @staticmethod
    # 健康度计算服务
    def _build_health_service() -> HealthService:
        return HealthService(
            risk_threshold_normal=current_app.config.get("RISK_THRESHOLD_NORMAL", 0.26),
            risk_threshold_warning=current_app.config.get("RISK_THRESHOLD_WARNING", 0.45),
            risk_threshold_critical=current_app.config.get("RISK_THRESHOLD_CRITICAL", 0.65),
            health_score_decimals=current_app.config.get("HEALTH_SCORE_DECIMALS", 2),
            logger=current_app.logger,
        )

    @staticmethod
    # 告警服务
    def _build_alert_service() -> AlertService:
        return AlertService(
            risk_threshold_normal=current_app.config.get("RISK_THRESHOLD_NORMAL", 0.26),
            risk_threshold_warning=current_app.config.get("RISK_THRESHOLD_WARNING", 0.45),
            risk_threshold_critical=current_app.config.get("RISK_THRESHOLD_CRITICAL", 0.65),
            suppress_min_window_minutes=current_app.config.get(
                "ALERT_SUPPRESS_MIN_WINDOW_MINUTES",
                15,
            ),
            suppress_max_window_minutes=current_app.config.get(
                "ALERT_SUPPRESS_MAX_WINDOW_MINUTES",
                60,
            ),
            suppress_lookback_ratio=current_app.config.get(
                "ALERT_SUPPRESS_LOOKBACK_RATIO",
                0.5,
            ),
            logger=current_app.logger,
        )

    @staticmethod
    # 给预测结果补健康度字段
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
    # 给预测结果补告警字段
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
    def _attach_no_alert_fields(result: Dict[str, Any]) -> Dict[str, Any]:
        """fallback 或 AI mock 结果不生成真实告警。"""
        return {
            **result,
            "alert_generated": False,
            "alert_level": "none",
            "alert_status": "none",
            "alert_status_text": "无",
            "alert_message": "当前设备状态正常，暂未生成告警",
            "alert_advice": "保持常规监测",
            "alert_id": None,
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
    def _parse_query_device_value(device_id_value: Any) -> Any:
        """latest/history 查询允许设备主键或业务设备编号。"""
        if device_id_value is None or device_id_value == "":
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        if isinstance(device_id_value, bool):
            raise BusinessException(code=400, message="device_id 格式非法", status_code=400)
        if isinstance(device_id_value, int):
            return device_id_value
        if isinstance(device_id_value, str):
            normalized_device_id = device_id_value.strip()
            if not normalized_device_id:
                raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
            return normalized_device_id
        raise BusinessException(code=400, message="device_id 格式非法", status_code=400)

    @staticmethod
    def get_latest_prediction(device_id_str: str) -> Optional[Dict[str, Any]]:
        device_value = PredictionService._parse_query_device_value(device_id_str)

        record = PredictionRepository.get_latest_by_device_id(device_value)
        return PredictionSchema.dump_latest(record)

    @staticmethod
    def _parse_history_time_range(start_str: str, end_str: str) -> tuple[datetime, datetime]:
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

        return start_dt, end_dt

    @staticmethod
    def _parse_health_curve_alpha(alpha_value: Any) -> float:
        if alpha_value is None or alpha_value == "":
            return HealthCurveService.DEFAULT_ALPHA
        if isinstance(alpha_value, bool):
            raise BusinessException(code=400, message="alpha 必须位于 0 到 1 之间", status_code=400)

        try:
            alpha = float(alpha_value)
        except (TypeError, ValueError):
            raise BusinessException(code=400, message="alpha 必须位于 0 到 1 之间", status_code=400)

        if not math.isfinite(alpha) or alpha <= 0 or alpha > 1:
            raise BusinessException(code=400, message="alpha 必须位于 0 到 1 之间", status_code=400)
        return alpha

    @staticmethod
    def get_prediction_history(device_id_str: str, start_str: str, end_str: str) -> Dict[str, Any]:
        device_value = PredictionService._parse_query_device_value(device_id_str)
        start_dt, end_dt = PredictionService._parse_history_time_range(start_str, end_str)

        records = PredictionRepository.query_history_by_device_and_range(device_value, start_dt, end_dt)
        return PredictionSchema.dump_history(device_value, start_str, end_str, records)

    @staticmethod
    def get_health_curve(
        device_id_str: str,
        start_str: str,
        end_str: str,
        alpha_value: Any = None,
    ) -> Dict[str, Any]:
        device_value = PredictionService._parse_query_device_value(device_id_str)
        start_dt, end_dt = PredictionService._parse_history_time_range(start_str, end_str)
        alpha = PredictionService._parse_health_curve_alpha(alpha_value)

        records = PredictionRepository.query_history_by_device_and_range(device_value, start_dt, end_dt)
        curve_payload = HealthCurveService.build_curve(
            records,
            device_id=device_value,
            start_time=start_str,
            end_time=end_str,
            alpha=alpha,
        )
        return PredictionSchema.dump_health_curve(curve_payload)

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
    def _parse_optional_bool(value: Any, field_name: str, default: bool) -> bool:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        raise BusinessException(code=400, message=f"{field_name} 必须为布尔值", status_code=400)

    @staticmethod
    def _parse_datetime_value(value: Any, field_name: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise BusinessException(
                code=400,
                message=f"{field_name} 时间格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            )
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise BusinessException(
                code=400,
                message=f"{field_name} 时间格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            ) from exc

    @staticmethod
    def _format_datetime_value(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    # 区间推理的参数校验和标准化函数
    def _parse_range_request(request_data: Any) -> Dict[str, Any]:
        if not isinstance(request_data, dict):
            raise BusinessException(code=400, message="请求体必须为 JSON 对象", status_code=400)

        run_record_id = request_data.get("run_record_id")
        if run_record_id is not None and run_record_id != "":
            run_record_id = PredictionService._parse_optional_positive_int(
                run_record_id,
                "run_record_id",
                0,
            )
        else:
            run_record_id = None

        device_code = request_data.get("device_code")
        if not isinstance(device_code, str) or not device_code.strip():
            raise BusinessException(code=400, message="device_code 必须为非空字符串", status_code=400)
        device_code = device_code.strip()

        end_dt = PredictionService._parse_datetime_value(request_data.get("end_time"), "end_time")
        if request_data.get("start_time"):
            start_dt = PredictionService._parse_datetime_value(request_data.get("start_time"), "start_time")
            lookback_minutes = int((end_dt - start_dt).total_seconds() // 60)
        else:
            lookback_minutes = PredictionService._parse_optional_positive_int(
                request_data.get("lookback_minutes"),
                "lookback_minutes",
                current_app.config.get("RANGE_INFER_DEFAULT_LOOKBACK_MINUTES", 60),
            )
            start_dt = end_dt - timedelta(minutes=lookback_minutes)

        if start_dt >= end_dt:
            raise BusinessException(code=400, message="start_time 必须早于 end_time", status_code=400)
        # 限制最大查询范围
        max_lookback_minutes = current_app.config.get("RANGE_INFER_MAX_LOOKBACK_MINUTES", 180)
        actual_lookback_minutes = int((end_dt - start_dt).total_seconds() // 60)
        if actual_lookback_minutes > max_lookback_minutes:
            raise BusinessException(
                code=400,
                message=f"lookback_minutes 不能超过 {max_lookback_minutes}",
                status_code=400,
            )

        source_segment = request_data.get("source_segment")
        if source_segment is not None and source_segment != "":
            if not isinstance(source_segment, str):
                raise BusinessException(code=400, message="source_segment 必须为字符串", status_code=400)
            source_segment = source_segment.strip() or None
        else:
            source_segment = None

        is_run_record_infer = run_record_id is not None and source_segment is not None
        default_stride_seconds = current_app.config.get(
            "RUN_RECORD_INFER_DEFAULT_STRIDE_SECONDS"
            if is_run_record_infer
            else "RANGE_INFER_DEFAULT_STRIDE_SECONDS",
            1 if is_run_record_infer else 60,
        )
        inference_stride_seconds = PredictionService._parse_optional_positive_int(
            request_data.get("inference_stride_seconds"),
            "inference_stride_seconds",
            default_stride_seconds,
        )
        min_stride_seconds = current_app.config.get(
            "RUN_RECORD_INFER_MIN_STRIDE_SECONDS"
            if is_run_record_infer
            else "RANGE_INFER_MIN_STRIDE_SECONDS",
            1 if is_run_record_infer else 10,
        )
        if inference_stride_seconds < min_stride_seconds:
            raise BusinessException(
                code=400,
                message=f"inference_stride_seconds 不能小于 {min_stride_seconds}",
                status_code=400,
            )

        total_candidate_points = int((end_dt - start_dt).total_seconds()) // inference_stride_seconds + 1
        max_points = current_app.config.get(
            "RUN_RECORD_INFER_MAX_POINTS" if is_run_record_infer else "RANGE_INFER_MAX_POINTS",
            5000 if is_run_record_infer else 200,
        )
        if total_candidate_points > max_points:
            raise BusinessException(
                code=400,
                message=f"候选预测点不能超过 {max_points}",
                status_code=400,
            )

        condition_label = request_data.get("condition_label")
        if condition_label is not None and condition_label != "":
            if not isinstance(condition_label, str):
                raise BusinessException(code=400, message="condition_label 必须为字符串", status_code=400)
            condition_label = condition_label.strip() or None
        else:
            condition_label = None

        return {
            "run_record_id": run_record_id,
            "device_code": device_code,
            "source_segment": source_segment,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "start_time": PredictionService._format_datetime_value(start_dt),
            "end_time": PredictionService._format_datetime_value(end_dt),
            "lookback_minutes": actual_lookback_minutes,
            "inference_stride_seconds": inference_stride_seconds,
            "mc_samples": PredictionService._parse_optional_positive_int(
                request_data.get("mc_samples"),
                "mc_samples",
                20,
            ),
            "persist": PredictionService._parse_optional_bool(
                request_data.get("persist"),
                "persist",
                True,
            ),
            "generate_alert": PredictionService._parse_optional_bool(
                request_data.get("generate_alert"),
                "generate_alert",
                False,
            ),
            "condition_label": condition_label,
            "total_candidate_points": total_candidate_points,
        }

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
                fallback_record = PredictionService._attach_health_fields(
                    PredictionService._build_mock_fallback(validated_data)
                )
                fallback_record["risk_result_id"] = None
                return PredictionSchema.dump_infer_result(
                    PredictionService._attach_no_alert_fields(fallback_record)
                )
            raise

        record = PredictionService._normalize_ai_result(ai_result, validated_data)
        record = PredictionService._attach_health_fields(record)
        if record.get("data_source") != "mock_fallback" and not record.get("runtime_error"):
            saved_record = PredictionRepository.save_infer_result(record)
            record = {
                **record,
                "risk_result_id": saved_record.get("risk_result_id"),
                "device_id": saved_record.get("device_id"),
                "device_code": saved_record.get("device_code"),
            }
            record = PredictionService._attach_alert_fields(record)
            if record.get("alert_generated"):
                alert_record = AlertRepository.create_from_prediction(record)
                record["alert_id"] = alert_record.get("alert_id") if alert_record else None
            else:
                record["alert_id"] = None
        else:
            record = PredictionService._attach_no_alert_fields(
                {
                    **record,
                    "risk_result_id": None,
                }
            )
        return PredictionSchema.dump_infer_result(record)

    @staticmethod
    def _build_monitor_query_limit(start_dt: datetime, end_dt: datetime) -> int:
        configured_limit = int(current_app.config.get("MONITOR_QUERY_LIMIT", 5000))
        expected_seconds = int((end_dt - start_dt).total_seconds()) + 10
        return max(configured_limit, expected_seconds * 2)

    @staticmethod
    # 把后端内部数据整理成 railphm-ai 接口需要的格式
    def _build_range_ai_payload(
        validated_data: Dict[str, Any],
        monitor_rows: list[dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "device_id": PredictionService._build_ai_device_id(validated_data["device_code"]),
            "device_code": validated_data["device_code"],
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "inference_stride_seconds": validated_data["inference_stride_seconds"],
            "mc_samples": validated_data["mc_samples"],
            "monitor_rows": monitor_rows,
        }

    @staticmethod
    # 处理 AI 返回的每一个预测点
    def _normalize_range_ai_point(
        ai_point: Dict[str, Any],
        validated_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        # 校验 AI 返回点必须是字典
        if not isinstance(ai_point, dict):
            raise AIResponseFormatError("AI 区间推理结果点格式非法")
        # 解析风险分数
        risk_score = PredictionService._parse_ai_float(
            ai_point.get("risk_score"),
            "risk_score",
            required=True,
        )
        # 解析阈值和预测标签
        threshold = PredictionService._parse_ai_float(
            ai_point.get("threshold"),
            "threshold",
            required=False,
            default=current_app.config.get("AI_DEFAULT_THRESHOLD", 0.26),
        )
        predicted_label = ai_point.get("predicted_label")
        if predicted_label is None or predicted_label == "":
            predicted_label = int(risk_score >= threshold)
        elif isinstance(predicted_label, bool) or not isinstance(predicted_label, int):
            raise AIResponseFormatError("AI 区间推理服务返回 predicted_label 格式非法")
        
        # 构造 trace 追踪信息
        trace = ai_point.get("trace") if isinstance(ai_point.get("trace"), dict) else {}
        model_version = ai_point.get("model_version") or "unknown"
        trace = {
            **trace,
            "model_version": model_version,
            "range_infer_persisted_by": "railphm-server",
        }
        if validated_data.get("run_record_id") is not None:
            trace["run_record_id"] = validated_data["run_record_id"]
        if validated_data.get("source_segment"):
            trace["source_segment"] = validated_data["source_segment"]
            
        # 返回统一格式的预测点
        return {
            "run_record_id": validated_data.get("run_record_id"),
            "source_segment": validated_data.get("source_segment"),
            "device_id": None,
            "device_code": validated_data["device_code"],
            "sample_index": None,
            "risk_raw": PredictionService._parse_ai_float(
                ai_point.get("risk_raw"),
                "risk_raw",
                required=False,
                default=risk_score,
            ),
            "risk_score": risk_score,
            "risk_raw_std": PredictionService._parse_ai_float(
                ai_point.get("risk_raw_std"),
                "risk_raw_std",
                required=False,
                default=0.0,
            ),
            "risk_std": PredictionService._parse_ai_float(
                ai_point.get("risk_std"),
                "risk_std",
                required=False,
                default=0.0,
            ),
            "threshold": threshold,
            "predicted_label": predicted_label,
            "model_name": ai_point.get("model_name") or "unknown",
            "model_version": model_version,
            "calibration_enabled": bool(ai_point.get("calibration_enabled", False)),
            "calibration_method": ai_point.get("calibration_method"),
            "uncertainty_enabled": bool(ai_point.get("uncertainty_enabled", False)),
            "uncertainty_method": ai_point.get("uncertainty_method"),
            "mc_samples": ai_point.get("mc_samples", validated_data["mc_samples"]),
            "condition_label": ai_point.get("condition_label"),
            "trace": trace,
            "window_start_time": ai_point.get("window_start_time"),
            "window_end_time": ai_point.get("window_end_time"),
            "ts_end": ai_point.get("time") or ai_point.get("window_end_time"),
            "window_minutes": validated_data["lookback_minutes"],
            "data_source": ai_point.get("data_source") or "influxdb_online_range",
            "time": ai_point.get("time") or ai_point.get("window_end_time"),
        }

    @staticmethod
    def _merge_existing_range_record(
        existing_record: Dict[str, Any],
        transient_record: Dict[str, Any],
        persist_status: str,
    ) -> Dict[str, Any]:
        """用已落库风险结果覆盖本次临时 AI 推理值，保证告警与风险结果一致。"""
        existing_trace = existing_record.get("trace")
        if not isinstance(existing_trace, dict):
            existing_trace = {}

        risk_result_id = existing_record.get("risk_result_id")
        risk_score = existing_record.get("risk_score")
        if risk_score is None:
            risk_score = existing_record.get("calibrated_risk_score")

        window_end_time = (
            existing_record.get("window_end_time")
            or existing_record.get("ts_end")
            or transient_record.get("window_end_time")
        )
        window_start_time = existing_record.get("window_start_time") or transient_record.get("window_start_time")
        ts_end = existing_record.get("ts_end") or window_end_time

        trace = {
            **existing_trace,
            "persist_status": persist_status,
            "risk_result_id": risk_result_id,
            "range_infer_existing_record_reused": True,
        }

        return {
            **transient_record,
            "risk_result_id": risk_result_id,
            "run_record_id": existing_record.get("run_record_id") or transient_record.get("run_record_id"),
            "source_segment": transient_record.get("source_segment"),
            "device_id": existing_record.get("device_id"),
            "device_code": existing_record.get("device_code") or transient_record.get("device_code"),
            "risk_raw": existing_record.get("risk_raw"),
            "risk_score": risk_score,
            "risk_raw_std": existing_record.get(
                "risk_raw_std",
                transient_record.get("risk_raw_std"),
            ),
            "risk_std": existing_record.get("risk_std"),
            "threshold": existing_record.get("threshold"),
            "predicted_label": existing_record.get("predicted_label"),
            "health_score": existing_record.get("health_score"),
            "health_level": existing_record.get("health_level"),
            "health_status": existing_record.get("health_status"),
            "health_description": existing_record.get("health_description"),
            "condition_label": existing_record.get("condition_label"),
            "window_start_time": window_start_time,
            "window_end_time": window_end_time,
            "ts_end": ts_end,
            "time": window_end_time or ts_end or transient_record.get("time"),
            "window_minutes": existing_record.get("window_minutes") or transient_record.get("window_minutes"),
            "trace": trace,
            "persist_status": persist_status,
        }

    @staticmethod
    def range_infer(request_data: Any) -> Dict[str, Any]:
        validated_data = PredictionService._parse_range_request(request_data)

        context_seconds = int(current_app.config.get("RANGE_INFER_CONTEXT_SECONDS", 30))
        monitor_query_start_dt = validated_data["start_dt"] - timedelta(seconds=context_seconds)
        monitor_query_end_dt = validated_data["end_dt"] + timedelta(seconds=1)
        # 从 InfluxDB 查询监测数据
        monitor_rows = MonitorRepository.query_history_by_device_and_range(
            device_code=validated_data["device_code"],
            start_dt=monitor_query_start_dt,
            end_dt=monitor_query_end_dt,
            fields=list(MonitorRepository.FIELD_COLUMNS), # 要查询的监测字段
            limit=PredictionService._build_monitor_query_limit(
                monitor_query_start_dt,
                monitor_query_end_dt,
            ),
            condition_label=validated_data["condition_label"],
            source_segment=validated_data["source_segment"],
        )

        if not monitor_rows:
            raise BusinessException(
                code=404,
                message="指定设备和时间范围内未查询到监测数据",
                status_code=404,
            )
        # 构造发给 AI 的请求
        ai_payload = PredictionService._build_range_ai_payload(validated_data, monitor_rows)

        try:
            # 调用 railphm-ai 区间推理接口
            ai_data = AIClient().infer_range(ai_payload)
        except AIResponseFormatError:
            raise
        except AIServiceError:
            current_app.logger.warning("AI range infer failed")
            raise
        # 结果容器
        risk_series: list[Dict[str, Any]] = [] # 给前端画风险曲线
        health_series: list[Dict[str, Any]] = [] # 给前端画健康度曲线
        prediction_records: list[Dict[str, Any]] = [] # 给告警模块使用的完整预测记录
        saved_count = 0 # 本次新保存了多少条风险结果
        skipped_existing_count = 0 # 有多少条因为数据库已有而跳过保存

        # 循环处理 AI 返回的每个预测点
        for ai_point in ai_data.get("results", []):
            record = PredictionService._normalize_range_ai_point(ai_point, validated_data)
            record = PredictionService._attach_health_fields(record)

            # 默认认为这个预测点还没有保存到数据库。
            risk_result_id = None
            persist_status = "not_persisted"

            # 如果 persist=True，就保存到 MySQL
            if validated_data["persist"]:
                # 检查数据库中是否已有相同窗口结果
                existing_record = PredictionRepository.get_existing_by_device_window(
                    validated_data["device_code"],
                    record.get("window_start_time"),
                    record.get("window_end_time"),
                    run_record_id=validated_data["run_record_id"],
                )
                # 防止重复保存结果
                if existing_record:
                    skipped_existing_count += 1
                    persist_status = "skipped_existing"
                    record = PredictionService._merge_existing_range_record(
                        existing_record=existing_record,
                        transient_record=record,
                        persist_status=persist_status,
                    )
                    risk_result_id = record.get("risk_result_id")
                else:
                    # 如果已有记录，复用已有结果
                    saved_record = PredictionRepository.save_infer_result(record)
                    saved_count += 1
                    risk_result_id = saved_record.get("risk_result_id")
                    record["run_record_id"] = saved_record.get("run_record_id")
                    record["device_id"] = saved_record.get("device_id")
                    record["device_code"] = saved_record.get("device_code") or record["device_code"]
                    persist_status = "saved"

            record["risk_result_id"] = risk_result_id
            record["run_record_id"] = validated_data["run_record_id"]
            record["source_segment"] = validated_data["source_segment"]
            record["persist_status"] = persist_status
            record["trace"] = {
                **(record.get("trace") or {}),
                "persist_status": persist_status,
                "risk_result_id": risk_result_id,
                "run_record_id": validated_data["run_record_id"],
                "source_segment": validated_data["source_segment"],
            }
            # 构造风险曲线点 risk_point
            risk_point = {
                "risk_result_id": record.get("risk_result_id"),
                "run_record_id": record.get("run_record_id"),
                "source_segment": record.get("source_segment"),
                "time": record.get("time"),
                "window_start_time": record.get("window_start_time"),
                "window_end_time": record.get("window_end_time"),
                "risk_raw": record.get("risk_raw"),
                "risk_score": record.get("risk_score"),
                "risk_raw_std": record.get("risk_raw_std"),
                "risk_std": record.get("risk_std"),
                "threshold": record.get("threshold"),
                "predicted_label": record.get("predicted_label"),
                "health_score": record.get("health_score"),
                "health_level": record.get("health_level"),
                "health_status": record.get("health_status"),
                "health_description": record.get("health_description"),
                "condition_label": record.get("condition_label"),
                "persist_status": record.get("persist_status"),
            }
            risk_series.append(risk_point)
            prediction_records.append(record)
            # 构造健康度曲线点
            health_series.append(
                {
                    "run_record_id": record.get("run_record_id"),
                    "source_segment": record.get("source_segment"),
                    "time": record.get("time"),
                    "health_score": record.get("health_score"),
                    "health_level": record.get("health_level"),
                    "health_status": record.get("health_status"),
                }
            )

        alert_service = PredictionService._build_alert_service()
        if validated_data["generate_alert"] and validated_data["persist"]:
            alert_summary = alert_service.generate_range_alerts(
                prediction_records=prediction_records,
                lookback_minutes=validated_data["lookback_minutes"],
                range_start_time=validated_data["start_time"],
                range_end_time=validated_data["end_time"],
                inference_stride_seconds=validated_data["inference_stride_seconds"],
            )
            alert_summary = {
                **alert_summary,
                "alert_generation_skipped": False,
                "alert_generation_skip_reason": "",
            }
        elif validated_data["generate_alert"]:
            alert_summary = alert_service.build_empty_range_alert_summary(
                generate_alert=True,
                skip_reason="persist_false",
                lookback_minutes=validated_data["lookback_minutes"],
                range_start_time=validated_data["start_time"],
                range_end_time=validated_data["end_time"],
            )
        else:
            alert_summary = alert_service.build_empty_range_alert_summary(
                generate_alert=False,
                skip_reason="generate_alert_false",
                lookback_minutes=validated_data["lookback_minutes"],
                range_start_time=validated_data["start_time"],
                range_end_time=validated_data["end_time"],
            )
        # 最终响应结果,返回给前端
        response = {
            "run_record_id": validated_data["run_record_id"], # 运行记录 ID
            "device_code": validated_data["device_code"], # 设备编号
            "source_segment": validated_data["source_segment"], # source_segment
            "start_time": validated_data["start_time"],  # 推理起始时间
            "end_time": validated_data["end_time"], # 结束时间
            "lookback_minutes": validated_data["lookback_minutes"], # 回看分钟（30min)
            "inference_stride_seconds": validated_data["inference_stride_seconds"], # 推理步长（1s）
            "mc_samples": validated_data["mc_samples"], # 蒙特卡洛采样次数
            "monitor_query_start_time": PredictionService._format_datetime_value(
                monitor_query_start_dt
            ),
            "monitor_point_count": ai_data.get("monitor_point_count", len(monitor_rows)),
            "total_candidate_points": ai_data.get(
                "total_candidate_points",
                validated_data["total_candidate_points"],
            ),
            "result_count": len(risk_series),
            "saved_count": saved_count,
            "skipped_existing_count": skipped_existing_count,
            "skipped_window_count": ai_data.get("skipped_window_count", 0),
            "model_name": ai_data.get("model_name"),
            "model_version": ai_data.get("model_version"),
            "calibration_enabled": ai_data.get("calibration_enabled"),
            "calibration_method": ai_data.get("calibration_method"),
            "uncertainty_enabled": ai_data.get("uncertainty_enabled"),
            "uncertainty_method": ai_data.get("uncertainty_method"),
            "risk_series": risk_series,
            "health_series": health_series,
            "skipped_windows": [
                {
                    **window,
                    "run_record_id": validated_data["run_record_id"],
                    "source_segment": validated_data["source_segment"],
                }
                if isinstance(window, dict)
                else window
                for window in ai_data.get("skipped_windows", [])
            ],
            **alert_summary,
        }
        return PredictionSchema.dump_range_infer_result(response)
