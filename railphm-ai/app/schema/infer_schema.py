from datetime import datetime
from typing import Any, Dict

from app.core.errors import BusinessException


class InferRequestSchema:
    """推理请求参数校验。"""

    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def load(cls, payload: Any) -> Dict[str, Any]:
        if payload is None:
            raise BusinessException(
                code=400,
                message="请求体必须为 JSON",
                status_code=400,
            )
        if not isinstance(payload, dict):
            raise BusinessException(
                code=400,
                message="请求体格式非法",
                status_code=400,
            )

        device_id = payload.get("device_id")
        ts_end = payload.get("ts_end")
        window_minutes = payload.get("window_minutes")

        if device_id is None:
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        if isinstance(device_id, bool) or not isinstance(device_id, int):
            raise BusinessException(code=400, message="device_id 必须为整数", status_code=400)

        if ts_end is None or ts_end == "":
            raise BusinessException(code=400, message="ts_end 不能为空", status_code=400)
        if not isinstance(ts_end, str):
            raise BusinessException(
                code=400,
                message="ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            )
        try:
            parsed_ts_end = datetime.strptime(ts_end, cls.DATETIME_FORMAT)
        except ValueError as exc:
            raise BusinessException(
                code=400,
                message="ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            ) from exc

        if window_minutes is None:
            raise BusinessException(
                code=400,
                message="window_minutes 不能为空",
                status_code=400,
            )
        if isinstance(window_minutes, bool) or not isinstance(window_minutes, int):
            raise BusinessException(
                code=400,
                message="window_minutes 必须为正整数",
                status_code=400,
            )
        if window_minutes <= 0:
            raise BusinessException(
                code=400,
                message="window_minutes 必须为正整数",
                status_code=400,
            )

        return {
            "device_id": device_id,
            "ts_end": parsed_ts_end,
            "window_minutes": window_minutes,
        }


class InferResponseSchema:
    """推理响应输出规范。"""

    RESPONSE_FIELDS = (
        "device_id",
        "ts_end",
        "window_minutes",
        "window_start_time",
        "window_end_time",
        "condition_label",
        "risk_score",
        "risk_std",
        "model_version",
    )

    @staticmethod
    def dump(result: Dict[str, Any]) -> Dict[str, Any]:
        missing_fields = [field for field in InferResponseSchema.RESPONSE_FIELDS if field not in result]
        if missing_fields:
            raise BusinessException(code=500, message="推理结果缺少必要字段", status_code=500)

        return {field: result[field] for field in InferResponseSchema.RESPONSE_FIELDS}
