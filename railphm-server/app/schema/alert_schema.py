# app/schema/alert_schema.py
from typing import List, Dict, Any

class AlertSchema:
    """
    告警数据序列化 (Schema/DTO 层)
    分离列表摘要与详情全量字段
    """

    @staticmethod
    def dump_list_item(record: Dict[str, Any]) -> Dict[str, Any]:
        """列表摘要字段"""
        return {
            "alert_id": record["alert_id"],
            "alert_level": record["alert_level"],
            "alert_status": record["alert_status"],
            "alert_time": record["alert_time"],
            "device_id": record["device_id"],
            "message": record["message"]
        }

    @staticmethod
    def dump_detail(record: Dict[str, Any]) -> Dict[str, Any]:
        """详情全量字段"""
        base = AlertSchema.dump_list_item(record)
        base.update({
            "handler_id": record["handler_id"],
            "risk_result_id": record["risk_result_id"],
            "alert_source": record["alert_source"],
            "alert_position": record["alert_position"],
            "alert_object_type": record["alert_object_type"],
            "alert_object_code": record["alert_object_code"],
            "handle_time": record["handle_time"],
            "handle_desc": record["handle_desc"]
        })
        return base

    @classmethod
    def dump_page(cls, items: List[Dict[str, Any]], total: int, page: int, size: int) -> Dict[str, Any]:
        """组装标准分页响应"""
        return {
            "items": [cls.dump_list_item(i) for i in items],
            "total": total,
            "page": page,
            "size": size
        }