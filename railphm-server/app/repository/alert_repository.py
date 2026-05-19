import copy
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from app.extensions.db import get_connection


class AlertRepository:
    """
    告警数据访问层 (Repository)
    阶段 4 起接口数据源切换为 phm_alert_record，mock 数据仅保留历史兼容。
    """

    _initial_mock_data: List[Dict[str, Any]] = [
        {"alert_id": 1001, "alert_level": "HIGH", "alert_status": "PENDING", "alert_time": "2026-04-01 10:08:00", "handler_id": None, "risk_result_id": 501, "device_id": 1, "message": "设备 1 在指定时间窗内风险持续升高，已触发高等级预警", "alert_source": "RISK_ENGINE", "alert_position": "车载ATP主机", "alert_object_type": "ATP_DEVICE", "alert_object_code": "ATP-0001", "handle_time": None, "handle_desc": None},
        {"alert_id": 1002, "alert_level": "MEDIUM", "alert_status": "PROCESSING", "alert_time": "2026-04-01 11:15:00", "handler_id": 2, "risk_result_id": 502, "device_id": 2, "message": "设备 2 健康度下降至关注区间，请及时复核", "alert_source": "HEALTH_ASSESSMENT", "alert_position": "应答器信息接收单元", "alert_object_type": "BTM_UNIT", "alert_object_code": "BTM-002", "handle_time": None, "handle_desc": None},
        {"alert_id": 1003, "alert_level": "LOW", "alert_status": "RESOLVED", "alert_time": "2026-03-31 09:00:00", "handler_id": 3, "risk_result_id": 480, "device_id": 1, "message": "设备 1 测速单元轻微波动", "alert_source": "RISK_ENGINE", "alert_position": "测速测距单元", "alert_object_type": "SDU_UNIT", "alert_object_code": "SDU-001", "handle_time": "2026-03-31 10:30:00", "handle_desc": "已复核，属于正常噪声波动，忽略"},
        {"alert_id": 1004, "alert_level": "HIGH", "alert_status": "PENDING", "alert_time": "2026-04-02 08:20:00", "handler_id": None, "risk_result_id": 505, "device_id": 3, "message": "设备 3 DMI显示异常预警", "alert_source": "RULE_ENGINE", "alert_position": "人机交互接口单元", "alert_object_type": "DMI_UNIT", "alert_object_code": "DMI-003", "handle_time": None, "handle_desc": None},
        {"alert_id": 1005, "alert_level": "MEDIUM", "alert_status": "RESOLVED", "alert_time": "2026-04-01 14:00:00", "handler_id": 1, "risk_result_id": 508, "device_id": 2, "message": "设备 2 BTM天线通信延迟", "alert_source": "RISK_ENGINE", "alert_position": "应答器天线", "alert_object_type": "ANTENNA", "alert_object_code": "ANT-002", "handle_time": "2026-04-01 15:00:00", "handle_desc": "入库检修后恢复正常"},
    ]
    _mock_data: List[Dict[str, Any]] = copy.deepcopy(_initial_mock_data)

    _ALERT_SELECT_FIELDS = """
        alert_id,
        risk_result_id,
        device_id,
        device_code,
        alert_level,
        alert_status,
        alert_status_text,
        alert_time,
        alert_message,
        alert_advice,
        risk_score,
        health_score,
        health_level,
        health_status,
        target_label_value,
        target_time,
        handler_id,
        handle_time,
        handle_desc,
        create_time,
        update_time
    """

    @classmethod
    def reset_mock_data(cls) -> None:
        """重置可变 mock 数据，避免历史测试之间互相污染。"""
        cls._mock_data = copy.deepcopy(cls._initial_mock_data)

    @classmethod
    def get_by_risk_result_id(cls, risk_result_id: int) -> Optional[Dict[str, Any]]:
        """查询某个风险结果是否已生成告警，避免重复插入。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._ALERT_SELECT_FIELDS}
                    FROM phm_alert_record
                    WHERE risk_result_id = %s
                    ORDER BY alert_id DESC
                    LIMIT 1
                    """,
                    (risk_result_id,),
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_alert_record(record) if record else None

    @classmethod
    def create_from_prediction(cls, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """根据一次真实风险预测结果创建告警记录。"""
        if not record.get("alert_generated"):
            return None
        if record.get("alert_level") in (None, "", "none"):
            return None

        risk_result_id = record.get("risk_result_id")
        device_code = record.get("device_code")
        if not risk_result_id or not device_code:
            return None

        existing_alert = cls.get_by_risk_result_id(int(risk_result_id))
        if existing_alert:
            return existing_alert

        trace = record.get("trace") if isinstance(record.get("trace"), dict) else {}
        target_label_value = (
            record.get("target_label_value")
            or trace.get("target_label_value")
            or trace.get("target_alarm_value")
        )
        target_time = record.get("target_time") or trace.get("target_time")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        params = {
            "risk_result_id": risk_result_id,
            "device_id": record.get("device_id"),
            "device_code": device_code,
            "alert_level": cls._normalize_alert_level(record.get("alert_level")),
            "alert_status": "unhandled",
            "alert_status_text": cls._alert_status_text("unhandled"),
            "alert_time": now,
            "alert_message": record.get("alert_message"),
            "alert_advice": record.get("alert_advice"),
            "risk_score": record.get("risk_score"),
            "health_score": record.get("health_score"),
            "health_level": record.get("health_level"),
            "health_status": record.get("health_status"),
            "target_label_value": target_label_value,
            "target_time": cls._normalize_datetime(target_time),
        }

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO phm_alert_record (
                        risk_result_id,
                        device_id,
                        device_code,
                        alert_level,
                        alert_status,
                        alert_status_text,
                        alert_time,
                        alert_message,
                        alert_advice,
                        risk_score,
                        health_score,
                        health_level,
                        health_status,
                        target_label_value,
                        target_time,
                        handler_id,
                        handle_time,
                        handle_desc
                    ) VALUES (
                        %(risk_result_id)s,
                        %(device_id)s,
                        %(device_code)s,
                        %(alert_level)s,
                        %(alert_status)s,
                        %(alert_status_text)s,
                        %(alert_time)s,
                        %(alert_message)s,
                        %(alert_advice)s,
                        %(risk_score)s,
                        %(health_score)s,
                        %(health_level)s,
                        %(health_status)s,
                        %(target_label_value)s,
                        %(target_time)s,
                        NULL,
                        NULL,
                        NULL
                    )
                    """,
                    params,
                )
                alert_id = cursor.lastrowid
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return cls.get_alert_by_id(alert_id)

    @classmethod
    def query_alerts(
        cls,
        page: int,
        size: int,
        alert_status: Optional[str] = None,
        alert_level: Optional[str] = None,
        device_id: Optional[Any] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """列表查询：支持过滤与分页。"""
        where_sql, params = cls._build_alert_filters(alert_status, alert_level, device_id)
        offset = (page - 1) * size

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM phm_alert_record
                    {where_sql}
                    """,
                    params,
                )
                total_record = cursor.fetchone() or {}
                total = int(total_record.get("total", 0))

                cursor.execute(
                    f"""
                    SELECT {cls._ALERT_SELECT_FIELDS}
                    FROM phm_alert_record
                    {where_sql}
                    ORDER BY alert_time DESC, alert_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, size, offset],
                )
                items = cursor.fetchall()
        finally:
            connection.close()

        return total, [cls._normalize_alert_record(item) for item in items]

    @classmethod
    def get_alert_by_id(cls, alert_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取真实告警详情。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._ALERT_SELECT_FIELDS}
                    FROM phm_alert_record
                    WHERE alert_id = %s
                    LIMIT 1
                    """,
                    (alert_id,),
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_alert_record(record) if record else None

    @classmethod
    def update_alert_status(
        cls,
        alert_id: int,
        alert_status: str,
        handler_id: Optional[int] = None,
        handle_note: Optional[str] = None,
        handle_time: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """更新真实告警处理状态。"""
        old_record = cls.get_alert_by_id(alert_id)
        if not old_record:
            return None

        normalized_status = cls._normalize_alert_status(alert_status)
        effective_handler_id = handler_id if handler_id is not None else old_record.get("handler_id")
        effective_handle_desc = handle_note if handle_note is not None else old_record.get("handle_desc")
        effective_handle_time = (
            handle_time
            if handle_time is not None
            else old_record.get("handle_time")
        )

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE phm_alert_record
                    SET
                        alert_status = %s,
                        alert_status_text = %s,
                        handler_id = %s,
                        handle_time = %s,
                        handle_desc = %s
                    WHERE alert_id = %s
                    """,
                    (
                        normalized_status,
                        cls._alert_status_text(normalized_status),
                        effective_handler_id,
                        cls._normalize_datetime(effective_handle_time),
                        effective_handle_desc,
                        alert_id,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return cls.get_alert_by_id(alert_id)

    @classmethod
    def _build_alert_filters(
        cls,
        alert_status: Optional[str],
        alert_level: Optional[str],
        device_id: Optional[Any],
    ) -> tuple[str, list[Any]]:
        where_clauses = []
        params: list[Any] = []

        normalized_status = cls._normalize_alert_status(alert_status)
        if normalized_status:
            where_clauses.append("alert_status = %s")
            params.append(normalized_status)

        normalized_level = cls._normalize_alert_level(alert_level)
        if normalized_level:
            where_clauses.append("alert_level = %s")
            params.append(normalized_level)

        if device_id is not None and str(device_id).strip():
            device_value = str(device_id).strip()
            if device_value.isdigit():
                where_clauses.append("device_id = %s")
                params.append(int(device_value))
            else:
                where_clauses.append("device_code = %s")
                params.append(device_value)

        if not where_clauses:
            return "", params
        return "WHERE " + " AND ".join(where_clauses), params

    @staticmethod
    def _normalize_alert_status(status: Optional[str]) -> Optional[str]:
        if status is None or status == "":
            return None
        normalized_status = str(status).strip().lower()
        aliases = {
            "pending": "unhandled",
            "unhandled": "unhandled",
            "processing": "processing",
            "resolved": "resolved",
        }
        if normalized_status not in aliases:
            raise ValueError("非法告警状态")
        return aliases[normalized_status]

    @staticmethod
    def _normalize_alert_level(level: Optional[str]) -> Optional[str]:
        if level is None or level == "":
            return None
        normalized_level = str(level).strip().lower()
        if normalized_level not in {"low", "medium", "high"}:
            raise ValueError("非法告警等级")
        return normalized_level

    @staticmethod
    def _alert_status_text(status: str) -> str:
        return {
            "unhandled": "未处理",
            "processing": "处理中",
            "resolved": "已处理",
        }.get(status, "未处理")

    @classmethod
    def _normalize_alert_record(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        normalized_record = dict(record)
        for field in ("alert_time", "target_time", "handle_time", "create_time", "update_time"):
            normalized_record[field] = cls._format_datetime(normalized_record.get(field))
        normalized_record["alert_status"] = cls._normalize_alert_status(
            normalized_record.get("alert_status")
        )
        normalized_record["alert_status_text"] = cls._alert_status_text(
            normalized_record["alert_status"]
        )
        normalized_record["alert_level"] = cls._normalize_alert_level(
            normalized_record.get("alert_level")
        )
        normalized_record["message"] = normalized_record.get("alert_message")
        normalized_record.setdefault("alert_source", None)
        normalized_record.setdefault("alert_position", None)
        normalized_record.setdefault("alert_object_type", None)
        normalized_record.setdefault("alert_object_code", None)
        return normalized_record

    @staticmethod
    def _normalize_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, str):
            return value.strip() or None
        return value

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value
