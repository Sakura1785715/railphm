from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import current_app

from app.core.errors import BusinessException


class RangeInferRequestSchema:
    """在线区间推理请求校验。"""

    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def load(cls, payload: Any) -> dict[str, Any]:
        if payload is None:
            raise BusinessException(code=400, message="请求体必须为 JSON", status_code=400)
        if not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体必须为 JSON 对象", status_code=400)

        device_id = cls._parse_device_id(payload.get("device_id"))
        device_code = cls._parse_non_empty_string(payload.get("device_code"), "device_code")
        start_dt = cls._parse_datetime(payload.get("start_time"), "start_time")
        end_dt = cls._parse_datetime(payload.get("end_time"), "end_time")
        if start_dt > end_dt:
            raise BusinessException(code=400, message="start_time 不能晚于 end_time", status_code=400)

        inference_stride_seconds = cls._parse_positive_int(
            payload.get("inference_stride_seconds"),
            "inference_stride_seconds",
            current_app.config.get("AI_DEFAULT_RANGE_INFERENCE_STRIDE_SECONDS", 60),
        )
        mc_samples = cls._parse_positive_int(
            payload.get("mc_samples"),
            "mc_samples",
            current_app.config.get("AI_DEFAULT_RANGE_MC_SAMPLES", 20),
        )

        max_mc_samples = current_app.config.get("AI_MAX_MC_SAMPLES", 1000)
        if mc_samples > max_mc_samples:
            raise BusinessException(
                code=400,
                message=f"mc_samples 不能超过 {max_mc_samples}",
                status_code=400,
            )

        monitor_rows = payload.get("monitor_rows")
        if not isinstance(monitor_rows, list) or not monitor_rows:
            raise BusinessException(code=400, message="monitor_rows 必须为非空列表", status_code=400)
        if not all(isinstance(row, dict) for row in monitor_rows):
            raise BusinessException(code=400, message="monitor_rows 每一项必须为 JSON 对象", status_code=400)

        max_monitor_rows = current_app.config.get("AI_MAX_MONITOR_ROWS", 20000)
        if len(monitor_rows) > max_monitor_rows:
            raise BusinessException(
                code=400,
                message=f"monitor_rows 不能超过 {max_monitor_rows}",
                status_code=400,
            )

        total_candidate_points = cls._count_candidate_points(
            start_dt=start_dt,
            end_dt=end_dt,
            stride_seconds=inference_stride_seconds,
        )
        max_range_points = current_app.config.get("AI_MAX_RANGE_POINTS", 200)
        if total_candidate_points > max_range_points:
            raise BusinessException(
                code=400,
                message=f"候选预测点不能超过 {max_range_points}",
                status_code=400,
            )

        return {
            "device_id": device_id,
            "device_code": device_code,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "start_time": start_dt.strftime(cls.DATETIME_FORMAT),
            "end_time": end_dt.strftime(cls.DATETIME_FORMAT),
            "inference_stride_seconds": inference_stride_seconds,
            "mc_samples": mc_samples,
            "monitor_rows": monitor_rows,
            "total_candidate_points": total_candidate_points,
        }

    @classmethod
    def _parse_device_id(cls, value: Any) -> int:
        if value is None or value == "":
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        if isinstance(value, bool) or not isinstance(value, int):
            raise BusinessException(code=400, message="device_id 必须为整数", status_code=400)
        return value

    @classmethod
    def _parse_non_empty_string(cls, value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise BusinessException(code=400, message=f"{field_name} 必须为非空字符串", status_code=400)
        return value.strip()

    @classmethod
    def _parse_datetime(cls, value: Any, field_name: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise BusinessException(
                code=400,
                message=f"{field_name} 必须使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            )
        try:
            return datetime.strptime(value.strip(), cls.DATETIME_FORMAT)
        except ValueError as exc:
            raise BusinessException(
                code=400,
                message=f"{field_name} 必须使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            ) from exc

    @classmethod
    def _parse_positive_int(cls, value: Any, field_name: str, default: int) -> int:
        if value is None or value == "":
            return int(default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        if value <= 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        return value

    @staticmethod
    def _count_candidate_points(
        *,
        start_dt: datetime,
        end_dt: datetime,
        stride_seconds: int,
    ) -> int:
        total_seconds = int((end_dt - start_dt).total_seconds())
        return total_seconds // stride_seconds + 1


class RangeInferResponseSchema:
    """在线区间推理响应输出规范。"""

    RESPONSE_FIELDS = (
        "device_id",
        "device_code",
        "start_time",
        "end_time",
        "inference_stride_seconds",
        "monitor_point_count",
        "total_candidate_points",
        "result_count",
        "skipped_window_count",
        "model_name",
        "model_version",
        "calibration_enabled",
        "calibration_method",
        "uncertainty_enabled",
        "uncertainty_method",
        "results",
        "skipped_windows",
    )

    REQUIRED_FIELDS = (
        "device_id",
        "device_code",
        "start_time",
        "end_time",
        "inference_stride_seconds",
        "monitor_point_count",
        "total_candidate_points",
        "result_count",
        "skipped_window_count",
        "model_name",
        "model_version",
        "calibration_enabled",
        "uncertainty_enabled",
        "results",
        "skipped_windows",
    )

    @classmethod
    def dump(cls, result: dict[str, Any]) -> dict[str, Any]:
        missing_fields = [field for field in cls.REQUIRED_FIELDS if field not in result]
        if missing_fields:
            raise BusinessException(code=500, message="区间推理结果缺少必要字段", status_code=500)
        if not isinstance(result.get("results"), list):
            raise BusinessException(code=500, message="区间推理结果 results 必须为列表", status_code=500)
        if not isinstance(result.get("skipped_windows"), list):
            raise BusinessException(code=500, message="区间推理结果 skipped_windows 必须为列表", status_code=500)
        return {field: result[field] for field in cls.RESPONSE_FIELDS if field in result}
