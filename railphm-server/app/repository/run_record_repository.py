import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.extensions.db import get_connection


class RunRecordRepository:
    """运行记录池 MySQL 访问层。"""

    _RUN_RECORD_SELECT_FIELDS = """
        run_record_id,
        run_record_code,
        device_id,
        device_code,
        source_segment,
        source_file,
        record_start_time,
        record_end_time,
        source_start_time,
        source_end_time,
        point_count,
        duration_seconds,
        atp_type,
        line_id,
        direction,
        condition_summary,
        has_alarm_label,
        status,
        max_risk_score,
        max_risk_result_id,
        max_alert_level,
        alert_id,
        created_at,
        updated_at
    """

    @classmethod
    def upsert_by_device_segment(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """按 device_code + source_segment 幂等写入运行记录。"""
        existing = cls.get_by_device_segment(record["device_code"], record["source_segment"])
        params = cls._build_record_params(record)

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                if existing:
                    cursor.execute(
                        """
                        UPDATE phm_run_record
                        SET
                            device_id = %(device_id)s,
                            record_start_time = %(record_start_time)s,
                            record_end_time = %(record_end_time)s,
                            source_start_time = %(source_start_time)s,
                            source_end_time = %(source_end_time)s,
                            point_count = %(point_count)s,
                            duration_seconds = %(duration_seconds)s,
                            condition_summary = %(condition_summary)s,
                            atp_type = %(atp_type)s,
                            line_id = %(line_id)s,
                            direction = %(direction)s,
                            has_alarm_label = %(has_alarm_label)s,
                            source_file = %(source_file)s,
                            updated_at = NOW()
                        WHERE run_record_id = %(run_record_id)s
                        """,
                        {**params, "run_record_id": existing["run_record_id"]},
                    )
                    run_record_id = existing["run_record_id"]
                    created = False
                else:
                    cursor.execute(
                        """
                        INSERT INTO phm_run_record (
                            run_record_code,
                            device_id,
                            device_code,
                            source_segment,
                            source_file,
                            record_start_time,
                            record_end_time,
                            source_start_time,
                            source_end_time,
                            point_count,
                            duration_seconds,
                            atp_type,
                            line_id,
                            direction,
                            condition_summary,
                            has_alarm_label,
                            status
                        ) VALUES (
                            %(run_record_code)s,
                            %(device_id)s,
                            %(device_code)s,
                            %(source_segment)s,
                            %(source_file)s,
                            %(record_start_time)s,
                            %(record_end_time)s,
                            %(source_start_time)s,
                            %(source_end_time)s,
                            %(point_count)s,
                            %(duration_seconds)s,
                            %(atp_type)s,
                            %(line_id)s,
                            %(direction)s,
                            %(condition_summary)s,
                            %(has_alarm_label)s,
                            %(status)s
                        )
                        """,
                        params,
                    )
                    run_record_id = cursor.lastrowid
                    created = True
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        saved_record = cls.get_by_id(run_record_id) or {}
        saved_record["_created"] = created
        return saved_record

    @classmethod
    def list_records(cls, filters: Dict[str, Any], page: int, page_size: int) -> Dict[str, Any]:
        where_sql, params = cls._build_list_where(filters)
        offset = (page - 1) * page_size

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM phm_run_record
                    {where_sql}
                    """,
                    params,
                )
                total_record = cursor.fetchone() or {}
                total = int(total_record.get("total", 0))

                cursor.execute(
                    f"""
                    SELECT {cls._RUN_RECORD_SELECT_FIELDS}
                    FROM phm_run_record
                    {where_sql}
                    ORDER BY record_start_time DESC, run_record_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, page_size, offset],
                )
                items = cursor.fetchall()
        finally:
            connection.close()

        return {
            "items": [cls._normalize_record(item) for item in items],
            "total": total,
        }

    @classmethod
    def get_by_id(cls, run_record_id: int) -> Optional[Dict[str, Any]]:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._RUN_RECORD_SELECT_FIELDS}
                    FROM phm_run_record
                    WHERE run_record_id = %s
                    LIMIT 1
                    """,
                    (run_record_id,),
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_record(record) if record else None

    @classmethod
    def get_by_device_segment(
        cls,
        device_code: str,
        source_segment: str,
    ) -> Optional[Dict[str, Any]]:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._RUN_RECORD_SELECT_FIELDS}
                    FROM phm_run_record
                    WHERE device_code = %s
                      AND source_segment = %s
                    LIMIT 1
                    """,
                    (device_code, source_segment),
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_record(record) if record else None

    @classmethod
    def get_random(cls, filters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        where_sql, params = cls._build_random_where(filters or {})

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._RUN_RECORD_SELECT_FIELDS}
                    FROM phm_run_record
                    {where_sql}
                    ORDER BY RAND()
                    LIMIT 1
                    """,
                    params,
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_record(record) if record else None

    @classmethod
    def update_after_infer(
        cls,
        run_record_id: int,
        summary: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        allowed_fields = {
            "max_risk_score",
            "max_risk_result_id",
            "max_alert_level",
            "status",
        }
        assignments = []
        params: Dict[str, Any] = {"run_record_id": run_record_id}
        for field in allowed_fields:
            if field in summary:
                if field == "status":
                    assignments.append(
                        "status = IF(status = 'alerted' AND alert_id IS NOT NULL, status, %(status)s)"
                    )
                else:
                    assignments.append(f"{field} = %({field})s")
                params[field] = summary.get(field)

        if not assignments:
            return cls.get_by_id(run_record_id)

        assignments.append("updated_at = NOW()")
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE phm_run_record
                    SET {", ".join(assignments)}
                    WHERE run_record_id = %(run_record_id)s
                    """,
                    params,
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return cls.get_by_id(run_record_id)

    @classmethod
    def update_after_alert(
        cls,
        run_record_id: int,
        alert_id: int,
        alert_level: str,
    ) -> Optional[Dict[str, Any]]:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE phm_run_record
                    SET
                        alert_id = %s,
                        max_alert_level = %s,
                        status = 'alerted',
                        updated_at = NOW()
                    WHERE run_record_id = %s
                    """,
                    (alert_id, alert_level, run_record_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return cls.get_by_id(run_record_id)

    @classmethod
    def _build_list_where(cls, filters: Dict[str, Any]) -> tuple[str, list[Any]]:
        conditions = []
        params: list[Any] = []

        device_code = cls._clean_text(filters.get("device_code"))
        if device_code:
            conditions.append("device_code = %s")
            params.append(device_code)

        status = cls._clean_text(filters.get("status"))
        if status:
            conditions.append("status = %s")
            params.append(status)

        if filters.get("has_alarm_label") is not None:
            conditions.append("has_alarm_label = %s")
            params.append(1 if filters.get("has_alarm_label") else 0)

        min_risk_score = filters.get("min_risk_score")
        if min_risk_score is not None:
            conditions.append("max_risk_score >= %s")
            params.append(min_risk_score)

        if not conditions:
            return "", params
        return "WHERE " + " AND ".join(conditions), params

    @classmethod
    def _build_random_where(cls, filters: Dict[str, Any]) -> tuple[str, list[Any]]:
        conditions = ["point_count > 0"]
        params: list[Any] = []

        device_code = cls._clean_text(filters.get("device_code"))
        if device_code:
            conditions.append("device_code = %s")
            params.append(device_code)

        return "WHERE " + " AND ".join(conditions), params

    @classmethod
    def _build_record_params(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        condition_summary = record.get("condition_summary")
        if isinstance(condition_summary, (dict, list)):
            condition_summary = json.dumps(condition_summary, ensure_ascii=False)

        return {
            "run_record_code": cls._clean_text(record.get("run_record_code")),
            "device_id": record.get("device_id"),
            "device_code": cls._clean_text(record.get("device_code")),
            "source_segment": cls._clean_text(record.get("source_segment")),
            "source_file": cls._clean_text(record.get("source_file")),
            "record_start_time": cls._format_datetime(record.get("record_start_time")),
            "record_end_time": cls._format_datetime(record.get("record_end_time")),
            "source_start_time": cls._format_datetime(record.get("source_start_time")),
            "source_end_time": cls._format_datetime(record.get("source_end_time")),
            "point_count": int(record.get("point_count") or 0),
            "duration_seconds": record.get("duration_seconds"),
            "atp_type": cls._clean_text(record.get("atp_type")),
            "line_id": cls._clean_text(record.get("line_id")),
            "direction": cls._clean_text(record.get("direction")),
            "condition_summary": condition_summary,
            "has_alarm_label": 1 if record.get("has_alarm_label") else 0,
            "status": cls._clean_text(record.get("status")) or "ready",
        }

    @classmethod
    def _normalize_record(cls, record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not record:
            return {}
        normalized = dict(record)
        for field in (
            "record_start_time",
            "record_end_time",
            "source_start_time",
            "source_end_time",
            "created_at",
            "updated_at",
        ):
            normalized[field] = cls._format_datetime(normalized.get(field))
        normalized["has_alarm_label"] = bool(normalized.get("has_alarm_label"))
        return normalized

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)
