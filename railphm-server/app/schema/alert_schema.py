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
            "alert_id": record.get("alert_id"),
            "risk_result_id": record.get("risk_result_id"),
            "device_id": record.get("device_id"),
            "device_code": record.get("device_code"),
            "alert_level": record.get("alert_level"),
            "alert_status": record.get("alert_status"),
            "alert_status_text": record.get("alert_status_text"),
            "alert_time": record.get("alert_time"),
            "message": record.get("alert_message") or record.get("message"),
            "alert_message": record.get("alert_message") or record.get("message"),
            "risk_score": record.get("risk_score"),
            "health_score": record.get("health_score"),
            "health_level": record.get("health_level"),
            "health_status": record.get("health_status"),
        }

    @staticmethod
    def dump_detail(record: Dict[str, Any]) -> Dict[str, Any]:
        """详情全量字段"""
        base = AlertSchema.dump_list_item(record)
        base.update({
            "alert_advice": record.get("alert_advice"),
            "target_label_value": record.get("target_label_value"),
            "target_time": record.get("target_time"),
            "handler_id": record.get("handler_id"),
            "handle_time": record.get("handle_time"),
            "handle_desc": record.get("handle_desc"),
            "create_time": record.get("create_time"),
            "update_time": record.get("update_time"),
            "alert_source": record.get("alert_source"),
            "alert_position": record.get("alert_position"),
            "alert_object_type": record.get("alert_object_type"),
            "alert_object_code": record.get("alert_object_code"),
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
