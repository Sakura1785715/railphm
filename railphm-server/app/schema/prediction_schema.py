from typing import List, Dict, Any, Optional

class PredictionSchema:
    """
    预测结果数据序列化 (Schema/DTO 层)
    对内屏蔽数据库字段差异，对外暴露标准稳定结构
    """

    @staticmethod
    def _format_item(record: Dict[str, Any]) -> Dict[str, Any]:
        """统一单条结果格式转换"""
        return {
            "device_id": record["device_id"],
            "risk_score": record["calibrated_risk_score"], 
            "risk_std": record["risk_std"],
            "health_score": record["health_score"],
            "model_version": record["model_version"],
            "window_start_time": record["window_start_time"],
            "window_end_time": record["window_end_time"]
        }

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