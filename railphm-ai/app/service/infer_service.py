"""
接收原始请求 payload
        ↓
校验请求参数
        ↓
计算窗口起止时间
        ↓
调用 InferRepository 做真实推理或 mock fallback
        ↓
补齐接口响应字段
        ↓
交给 InferResponseSchema 统一格式化输出
"""
from typing import Any, Dict
from datetime import timedelta
from app.core.errors import BusinessException
from app.repository.infer_repository import InferRepository
from app.schema.infer_schema import InferRequestSchema, InferResponseSchema

class InferService:
    """
    推理业务层。
    负责参数校验、业务编排与响应数据组织：
    routes.py 负责接 HTTP 请求
    InferService 负责业务流程
    InferRepository 负责真正调用模型和读取样本
    """
    # 
    @staticmethod
    def infer(payload: Any) -> Dict[str, Any]:
        # payload 是前端或 server 传来的 JSON 请求体
        if not payload:
            raise BusinessException(code=400, message="请求格式非法或为空")
        # 把原始 JSON 请求校验并转换成内部可用的数据
        validated_data = InferRequestSchema.load(payload)

        # 业务逻辑：根据前端请求体中的结束时间和窗口分钟数，倒推开始时间
        end_dt = validated_data["ts_end"]
        window_minutes = validated_data["window_minutes"]
        start_dt = end_dt - timedelta(minutes=window_minutes)
        # 格式化时间字符串
        start_time_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 执行推理！！
        result = InferRepository.infer(validated_data)

        # 将时间计算结果补齐到 result 字典中，供 Response Schema 使用
        result["window_start_time"] = start_time_str    
        result["window_end_time"] = end_time_str
        # 如果 Repository 没有返回原始入参，这里确保补齐，防止 Schema 序列化丢失
        result["device_id"] = validated_data["device_id"]
        result["ts_end"] = end_time_str
        result["window_minutes"] = window_minutes
        result["sample_index"] = validated_data["sample_index"]
        result["mc_samples"] = result.get("mc_samples", validated_data["mc_samples"])
        # 格式化输出
        return InferResponseSchema.dump(result)
