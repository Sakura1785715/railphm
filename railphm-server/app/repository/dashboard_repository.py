from typing import Any, Dict, List

from app.extensions.db import get_connection


class DashboardRepository:
    """Dashboard 聚合数据访问层。"""

    @classmethod
    def get_kpi(cls) -> Dict[str, Any]:
        """查询首页 KPI 汇总。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS device_total,
                        SUM(CASE WHEN device_status = 1 THEN 1 ELSE 0 END) AS normal_device_count,
                        SUM(CASE WHEN device_status IN (3, 4) THEN 1 ELSE 0 END) AS warning_device_count
                    FROM phm_device
                    """
                )
                device_counts = cursor.fetchone() or {}

                cursor.execute(
                    """
                    SELECT COUNT(*) AS unhandled_alert_count
                    FROM phm_alert_record
                    WHERE LOWER(alert_status) IN ('pending', 'unhandled', 'processing')
                    """
                )
                alert_counts = cursor.fetchone() or {}
        finally:
            connection.close()

        return {
            "device_total": device_counts.get("device_total"),
            "normal_device_count": device_counts.get("normal_device_count"),
            "warning_device_count": device_counts.get("warning_device_count"),
            "unhandled_alert_count": alert_counts.get("unhandled_alert_count"),
        }

    @classmethod
    def get_risk_trend(cls, limit: int = 30) -> List[Dict[str, Any]]:
        """查询最近若干条真实风险结果，按时间升序返回。"""
        normalized_limit = cls._normalize_limit(limit, 30)
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT
                            risk_result_id,
                            device_id,
                            device_code,
                            calibrated_risk_score AS risk_score,
                            calibrated_risk_score AS avg_risk_score,
                            calibrated_risk_score AS max_risk_score,
                            health_score,
                            health_level,
                            health_status,
                            risk_std,
                            condition_label,
                            window_end_time,
                            created_at,
                            COALESCE(window_end_time, ts_end, created_at) AS time,
                            1 AS record_count
                        FROM phm_risk_result
                        ORDER BY COALESCE(window_end_time, ts_end, created_at) DESC,
                                 risk_result_id DESC
                        LIMIT %s
                    ) AS recent_risk
                    ORDER BY time ASC, risk_result_id ASC
                    """,
                    (normalized_limit,),
                )
                rows = cursor.fetchall()
        finally:
            connection.close()

        return list(rows or [])

    @classmethod
    def get_health_distribution(cls) -> List[Dict[str, Any]]:
        """查询设备最新健康等级分布。无风险结果设备按设备状态兜底。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        d.device_id,
                        d.device_code,
                        d.device_status,
                        latest_risk.health_level,
                        latest_risk.health_status
                    FROM phm_device AS d
                    LEFT JOIN (
                        SELECT r.*
                        FROM phm_risk_result AS r
                        INNER JOIN (
                            SELECT
                                COALESCE(device_code, CAST(device_id AS CHAR)) AS device_key,
                                MAX(risk_result_id) AS max_risk_result_id
                            FROM phm_risk_result
                            GROUP BY COALESCE(device_code, CAST(device_id AS CHAR))
                        ) AS latest
                            ON latest.max_risk_result_id = r.risk_result_id
                    ) AS latest_risk
                        ON latest_risk.device_id = d.device_id
                        OR (
                            latest_risk.device_id IS NULL
                            AND latest_risk.device_code = d.device_code
                        )
                    """
                )
                rows = cursor.fetchall()
        finally:
            connection.close()

        return list(rows or [])

    @classmethod
    def get_latest_alerts(cls, limit: int = 5) -> List[Dict[str, Any]]:
        """查询最近告警记录。"""
        normalized_limit = cls._normalize_limit(limit, 5)
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        a.alert_id,
                        a.risk_result_id,
                        a.device_id,
                        a.device_code,
                        d.device_name,
                        a.alert_level,
                        a.alert_status,
                        a.alert_status_text,
                        a.alert_message,
                        a.alert_advice,
                        COALESCE(a.risk_score, r.calibrated_risk_score) AS risk_score,
                        COALESCE(a.health_score, r.health_score) AS health_score,
                        COALESCE(a.health_level, r.health_level) AS health_level,
                        a.health_status,
                        a.alert_time,
                        a.create_time AS created_at,
                        a.update_time AS updated_at
                    FROM phm_alert_record AS a
                    LEFT JOIN phm_device AS d
                        ON d.device_id = a.device_id
                        OR (
                            a.device_id IS NULL
                            AND d.device_code = a.device_code
                        )
                    LEFT JOIN phm_risk_result AS r
                        ON r.risk_result_id = a.risk_result_id
                    ORDER BY COALESCE(a.alert_time, a.create_time, a.update_time) DESC,
                             a.alert_id DESC
                    LIMIT %s
                    """,
                    (normalized_limit,),
                )
                rows = cursor.fetchall()
        finally:
            connection.close()

        return list(rows or [])

    @classmethod
    def get_key_devices(cls, limit: int = 5) -> List[Dict[str, Any]]:
        """按最新风险分数查询重点设备。"""
        normalized_limit = cls._normalize_limit(limit, 5)
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        d.device_id,
                        COALESCE(d.device_code, latest_risk.device_code) AS device_code,
                        d.device_name,
                        d.device_type,
                        d.attach_bureau AS location,
                        d.device_status,
                        latest_risk.calibrated_risk_score AS risk_score,
                        latest_risk.health_score,
                        latest_risk.health_level,
                        latest_risk.health_status,
                        latest_alert.alert_level,
                        latest_alert.alert_status,
                        latest_risk.window_end_time,
                        COALESCE(latest_risk.created_at, d.update_time, d.create_time) AS updated_at
                    FROM (
                        SELECT r.*
                        FROM phm_risk_result AS r
                        INNER JOIN (
                            SELECT
                                COALESCE(device_code, CAST(device_id AS CHAR)) AS device_key,
                                MAX(risk_result_id) AS max_risk_result_id
                            FROM phm_risk_result
                            GROUP BY COALESCE(device_code, CAST(device_id AS CHAR))
                        ) AS latest
                            ON latest.max_risk_result_id = r.risk_result_id
                    ) AS latest_risk
                    LEFT JOIN phm_device AS d
                        ON d.device_id = latest_risk.device_id
                        OR (
                            latest_risk.device_id IS NULL
                            AND d.device_code = latest_risk.device_code
                        )
                    LEFT JOIN (
                        SELECT a.*
                        FROM phm_alert_record AS a
                        INNER JOIN (
                            SELECT
                                COALESCE(device_code, CAST(device_id AS CHAR)) AS device_key,
                                MAX(alert_id) AS max_alert_id
                            FROM phm_alert_record
                            GROUP BY COALESCE(device_code, CAST(device_id AS CHAR))
                        ) AS latest
                            ON latest.max_alert_id = a.alert_id
                    ) AS latest_alert
                        ON latest_alert.device_id = COALESCE(d.device_id, latest_risk.device_id)
                        OR (
                            latest_alert.device_id IS NULL
                            AND latest_alert.device_code = COALESCE(d.device_code, latest_risk.device_code)
                        )
                    ORDER BY latest_risk.calibrated_risk_score DESC,
                             COALESCE(latest_risk.window_end_time, latest_risk.created_at) DESC
                    LIMIT %s
                    """,
                    (normalized_limit,),
                )
                rows = cursor.fetchall()
        finally:
            connection.close()

        return list(rows or [])

    @staticmethod
    def _normalize_limit(value: Any, default: int) -> int:
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return default

        return limit if 0 < limit <= 200 else default
