from typing import List, Dict, Any, Tuple, Optional

class AlertRepository:
    """
    告警数据访问层 (Repository)
    当前使用 Mock 数据，未来替换为 SQLAlchemy 对 phm_alert_record 的查询
    """
    
    _mock_data: List[Dict[str, Any]] = [
        {"alert_id": 1001, "alert_level": "HIGH", "alert_status": "PENDING", "alert_time": "2026-04-01 10:08:00", "handler_id": None, "risk_result_id": 501, "device_id": 1, "message": "设备 1 在指定时间窗内风险持续升高，已触发高等级预警", "alert_source": "RISK_ENGINE", "alert_position": "车载ATP主机", "alert_object_type": "ATP_DEVICE", "alert_object_code": "ATP-0001", "handle_time": None, "handle_desc": None},
        {"alert_id": 1002, "alert_level": "MEDIUM", "alert_status": "PROCESSING", "alert_time": "2026-04-01 11:15:00", "handler_id": 2, "risk_result_id": 502, "device_id": 2, "message": "设备 2 健康度下降至关注区间，请及时复核", "alert_source": "HEALTH_ASSESSMENT", "alert_position": "应答器信息接收单元", "alert_object_type": "BTM_UNIT", "alert_object_code": "BTM-002", "handle_time": None, "handle_desc": None},
        {"alert_id": 1003, "alert_level": "LOW", "alert_status": "RESOLVED", "alert_time": "2026-03-31 09:00:00", "handler_id": 3, "risk_result_id": 480, "device_id": 1, "message": "设备 1 测速单元轻微波动", "alert_source": "RISK_ENGINE", "alert_position": "测速测距单元", "alert_object_type": "SDU_UNIT", "alert_object_code": "SDU-001", "handle_time": "2026-03-31 10:30:00", "handle_desc": "已复核，属于正常噪声波动，忽略"},
        {"alert_id": 1004, "alert_level": "HIGH", "alert_status": "PENDING", "alert_time": "2026-04-02 08:20:00", "handler_id": None, "risk_result_id": 505, "device_id": 3, "message": "设备 3 DMI显示异常预警", "alert_source": "RULE_ENGINE", "alert_position": "人机交互接口单元", "alert_object_type": "DMI_UNIT", "alert_object_code": "DMI-003", "handle_time": None, "handle_desc": None},
        {"alert_id": 1005, "alert_level": "MEDIUM", "alert_status": "RESOLVED", "alert_time": "2026-04-01 14:00:00", "handler_id": 1, "risk_result_id": 508, "device_id": 2, "message": "设备 2 BTM天线通信延迟", "alert_source": "RISK_ENGINE", "alert_position": "应答器天线", "alert_object_type": "ANTENNA", "alert_object_code": "ANT-002", "handle_time": "2026-04-01 15:00:00", "handle_desc": "入库检修后恢复正常"}
    ]

    @classmethod
    def query_alerts(cls, page: int, size: int, alert_status: Optional[str] = None, alert_level: Optional[str] = None, device_id: Optional[int] = None) -> Tuple[int, List[Dict[str, Any]]]:
        """列表查询：支持过滤与分页"""
        filtered = cls._mock_data
        
        # 1. 过滤
        if alert_status:
            filtered = [r for r in filtered if r["alert_status"] == alert_status]
        if alert_level:
            filtered = [r for r in filtered if r["alert_level"] == alert_level]
        if device_id is not None:
            filtered = [r for r in filtered if r["device_id"] == device_id]
            
        total = len(filtered)
        
        # 2. 分页切片
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paged_items = filtered[start_idx:end_idx]
        
        return total, paged_items

    @classmethod
    def get_alert_by_id(cls, alert_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取单条详情"""
        for r in cls._mock_data:
            if r["alert_id"] == alert_id:
                return r
        return None