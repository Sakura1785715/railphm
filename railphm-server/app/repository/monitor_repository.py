from typing import List, Dict, Any
from datetime import datetime

class MonitorRepository:
    """
    监测数据访问层 (Repository)
    严格使用原始 CSV (segment_001_20150109102323.csv) 字段风格构建 Mock
    """
    
    # 模拟 MySQL 中的设备台账映射（真实业务中，这一步是查询 MySQL）
    # 映射关系: device_id (内部主键) -> TrainID (车号)
    _device_map = {
        1: "3001003"
    }

    # 完全按照 CSV 真实数据字段定义 Mock 数据
    # 时间格式为 YYYYMMDDHHMMSS (如 20150109102323)
    _mock_raw_csv_data: List[Dict[str, Any]] = [
        {"TrainID": "3001003", "DataTime": "20150109102323", "Speed": 11, "Mileage": 12, "RunDistance": 12},
        {"TrainID": "3001003", "DataTime": "20150109102324", "Speed": 12, "Mileage": 13, "RunDistance": 13},
        {"TrainID": "3001003", "DataTime": "20150109102325", "Speed": 13, "Mileage": 14, "RunDistance": 14},
        # 此处模拟一条不在查询范围内的数据用于验证过滤逻辑
        {"TrainID": "3001003", "DataTime": "20150109102355", "Speed": 82, "Mileage": 44, "RunDistance": 44},
    ]

    @classmethod
    def query_series(cls, device_id: int, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """
        按内部 device_id 和时间范围查询时序数据
        """
        # 1. 将内部 device_id 转换为真实业务数据中的 车号(TrainID)
        target_train_id = cls._device_map.get(device_id)
        if not target_train_id:
            return []

        results = []
        for point in cls._mock_raw_csv_data:
            # 过滤非本车号的数据
            if str(point.get("TrainID")) != target_train_id:
                continue
                
            # 2. 解析原始 CSV 特殊的时间格式 (如: 20150109102323)
            raw_time_str = str(point.get("DataTime"))
            try:
                p_time = datetime.strptime(raw_time_str, "%Y%m%d%H%M%S")
            except ValueError:
                continue # 容错：如果原始数据时间脏了则跳过
                
            # 3. 时间闭区间过滤
            if start <= p_time <= end:
                point["_parsed_datetime"] = p_time
                results.append(point)
        
        return results