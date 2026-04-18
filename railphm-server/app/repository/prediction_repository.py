# 预测，暂时mock
from typing import List, Dict, Any, Optional
from datetime import datetime

class PredictionRepository:
    """
    风险预测结果访问层 (Repository)
    当前使用 Mock 数据，未来替换为 SQLAlchemy 对 phm_risk_result (结合 segment) 的查询
    """
    
    # Mock 数据：risk_score 呈现上升趋势，health_score 呈现下降趋势
    # 注意：底层使用真实表语义 calibrated_risk_score，在上层 API 转换为 risk_score
    _mock_data: List[Dict[str, Any]] = [
        # Device 1 数据
        {"device_id": 1, "calibrated_risk_score": 0.45, "risk_std": 0.03, "health_score": 89.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 09:00:00", "window_end_time": "2026-04-01 09:05:00"},
        {"device_id": 1, "calibrated_risk_score": 0.52, "risk_std": 0.04, "health_score": 84.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 09:05:00", "window_end_time": "2026-04-01 09:10:00"},
        {"device_id": 1, "calibrated_risk_score": 0.82, "risk_std": 0.07, "health_score": 68.5, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 10:00:00", "window_end_time": "2026-04-01 10:05:00"}, # 最新一条
        
        # Device 2 数据
        {"device_id": 2, "calibrated_risk_score": 0.21, "risk_std": 0.01, "health_score": 95.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 08:00:00", "window_end_time": "2026-04-01 08:05:00"},
        {"device_id": 2, "calibrated_risk_score": 0.25, "risk_std": 0.02, "health_score": 92.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 08:05:00", "window_end_time": "2026-04-01 08:10:00"},
    ]

    @classmethod
    def get_latest_by_device_id(cls, device_id: int) -> Optional[Dict[str, Any]]:
        """获取某设备最新预测结果"""
        device_records = [r for r in cls._mock_data if r["device_id"] == device_id]
        if not device_records:
            return None
        
        # 按照 window_end_time 降序排列，取第一条
        device_records.sort(
            key=lambda x: datetime.strptime(x["window_end_time"], "%Y-%m-%d %H:%M:%S"), 
            reverse=True
        )
        return device_records[0]

    @classmethod
    def query_history_by_device_and_range(cls, device_id: int, start_dt: datetime, end_dt: datetime) -> List[Dict[str, Any]]:
        """获取某设备某时间范围内的历史预测结果"""
        results = []
        for r in cls._mock_data:
            if r["device_id"] != device_id:
                continue
            
            r_start = datetime.strptime(r["window_start_time"], "%Y-%m-%d %H:%M:%S")
            # 过滤：分析窗口的起点落在查询范围内
            if start_dt <= r_start <= end_dt:
                results.append(r)
                
        # 按照 window_start_time 升序排列，方便前端直接画趋势图
        results.sort(key=lambda x: datetime.strptime(x["window_start_time"], "%Y-%m-%d %H:%M:%S"))
        return results