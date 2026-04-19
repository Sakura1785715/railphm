from typing import Any, Dict
from datetime import datetime, timedelta
from flask import current_app
from app.core.errors import BusinessException
from app.repository.infer_repository import InferRepository
from app.schema.infer_schema import InferRequestSchema, InferResponseSchema

class InferService:
    """
    推理业务层。
    负责参数校验、业务编排与响应数据组织。
    """

    @staticmethod
    def infer(payload: Any) -> Dict[str, Any]:
        if not payload:
            raise BusinessException(code=400, message="请求格式非法或为空")

        device_id = payload.get("device_id")
        if device_id is None:
            raise BusinessException(code=400, message="device_id 不能为空")
        if not isinstance(device_id, int):
            raise BusinessException(code=400, message="必须为整数")

        ts_end = payload.get("ts_end")
        if not ts_end:
            raise BusinessException(code=400, message="ts_end 不能为空")
        try:
            end_dt = datetime.strptime(ts_end, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # 精确匹配测试要求的关键词 "YYYY-MM-DD"
            raise BusinessException(code=400, message="ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式")

        window_minutes = payload.get("window_minutes")
        if window_minutes is None:
            raise BusinessException(code=400, message="window_minutes 不能为空")
        if not isinstance(window_minutes, int) or window_minutes <= 0:
            raise BusinessException(code=400, message="必须为正整数")
        
        validated_data = InferRequestSchema.load(payload)
        
        # 业务逻辑：根据结束时间和窗口分钟数，倒推开始时间
        start_dt = end_dt - timedelta(minutes=validated_data.get("window_minutes", window_minutes))
        start_time_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 从配置中安全获取 mock 模型版本
        model_version = current_app.config.get("MODEL_VERSION", "mock-bilstm-attention-v1")
        
        result = InferRepository.infer(
            device_id=validated_data.get("device_id", device_id),
            ts_end=validated_data.get("ts_end", ts_end),
            window_minutes=validated_data.get("window_minutes", window_minutes),
            model_version=model_version,
        )

        # 将时间计算结果补齐到 result 字典中，供 Response Schema 使用
        result["window_start_time"] = start_time_str
        result["window_end_time"] = ts_end
        # 如果 Repository 没有返回原始入参，这里确保补齐，防止 Schema 序列化丢失
        result["device_id"] = validated_data.get("device_id", device_id)
        result["window_minutes"] = validated_data.get("window_minutes", window_minutes)
        # 格式化输出
        return InferResponseSchema.dump(result)