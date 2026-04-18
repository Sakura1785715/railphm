# 时序数据核心参数校验与时间逻辑处理
from datetime import datetime
from typing import Dict, Any
from app.core.errors import BusinessException
from app.repository.monitor_repository import MonitorRepository
from app.schema.monitor_schema import MonitorSchema

class MonitorService:
    """
    监测业务逻辑层 (Service)
    负责参数校验、时间边界计算及业务流程调度
    """

    @staticmethod
    def get_historical_series(device_id: str, start_str: str, end_str: str) -> Dict[str, Any]:
        # 必填校验
        if not device_id:
            raise BusinessException(code=400, message="device_id 不能为空", status_code=400)
        if not start_str:
            raise BusinessException(code=400, message="start_time 不能为空", status_code=400)
        if not end_str:
            raise BusinessException(code=400, message="end_time 不能为空", status_code=400)

        # 时间格式解析与校验
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise BusinessException(code=400, message="时间格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式", status_code=400)

        # 时间逻辑范围校验
        if start_dt >= end_dt:
            raise BusinessException(code=400, message="开始时间必须早于结束时间", status_code=400)

        try:
            device_id_int = int(device_id)
        except ValueError:
            raise BusinessException(code=400, message="device_id 必须为整数", status_code=400)

        # 调用存储层获取原始时序点
        raw_data = MonitorRepository.query_series(device_id_int, start_dt, end_dt)

        # 交由 Schema 层转换为前端可视化结构
        return MonitorSchema.format_to_series(device_id_int, start_str, end_str, raw_data)