from datetime import datetime
from typing import Dict, Any, Optional
from app.core.errors import BusinessException
from app.repository.prediction_repository import PredictionRepository
from app.schema.prediction_schema import PredictionSchema

class PredictionService:
    """
    预测结果业务层 (Service)
    负责参数解析、时间校验以及逻辑编排
    """

    @staticmethod
    def _parse_device_id(device_id_str: str) -> int:
        if not device_id_str:
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        try:
            return int(device_id_str)
        except ValueError:
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