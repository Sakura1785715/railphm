from __future__ import annotations

from typing import Any

from app.core.errors import BusinessException
from app.repository.range_infer_repository import RangeInferRepository
from app.schema.range_infer_schema import RangeInferRequestSchema, RangeInferResponseSchema


class RangeInferService:
    """在线区间推理业务层。"""

    @staticmethod
    def infer_range(payload: Any) -> dict[str, Any]:
        if not payload:
            raise BusinessException(code=400, message="请求格式非法或为空", status_code=400)

        validated_data = RangeInferRequestSchema.load(payload)
        result = RangeInferRepository.infer_range(validated_data)
        return RangeInferResponseSchema.dump(result)
