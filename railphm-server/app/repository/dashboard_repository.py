from typing import Any, Dict, List, Optional

from app.extensions.db import get_connection


class DashboardRepository:
    """Dashboard 聚合数据访问层。"""

    ACTIVE_ALERT_STATUSES = ("pending", "unhandled", "processing")
    ALERT_STATUS_LEVEL = {
        "high": 4,
        "critical": 4,
        "medium": 3,
        "warning": 3,
        "warn": 3,
        "low": 2,
        "info": 2,
    }
    HEALTH_STATUS_LEVEL = {
        "normal": 1,
        "healthy": 1,
        "health": 1,
        "ok": 1,
        "正常": 1,
        "健康": 1,
        "attention": 2,
        "focus": 2,
        "关注": 2,
        "warning": 3,
        "warn": 3,
        "prewarning": 3,
        "预警": 3,
        "critical": 4,
        "danger": 4,
        "alert": 4,
        "告警": 4,
        "严重": 4,
        "危险": 4,
    }
    DEVICE_STATUS_TEXT = {
        1: "正常",
        2: "关注",
        3: "预警",
        4: "告警",
    }

    @classmethod
    def get_device_status_overview(cls) -> List[Dict[str, Any]]:
        """以设备台账为基准，合并活跃告警与最新风险结果得到设备当前状态。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        device_id,
                        device_code,
                        device_name,
                        device_type,
                        attach_bureau AS location,
                        device_status,
                        create_time,
                        update_time
                    FROM phm_device
                    ORDER BY device_id ASC
                    """
                )
                devices = list(cursor.fetchall() or [])

                cursor.execute(
                    f"""
                    SELECT
                        risk_result_id,
                        device_id,
                        device_code,
                        calibrated_risk_score AS risk_score,
                        health_score,
                        health_level,
                        health_status,
                        health_description,
                        ts_end,
                        window_end_time,
                        created_at,
                        COALESCE(window_end_time, ts_end, created_at) AS latest_prediction_time
                    FROM ({cls._latest_risk_sql()}) AS latest_risk
                    """
                )
                risk_rows = list(cursor.fetchall() or [])

                cursor.execute(
                    """
                    SELECT
                        alert_id,
                        risk_result_id,
                        device_id,
                        device_code,
                        alert_level,
                        alert_status,
                        alert_status_text,
                        alert_message,
                        risk_score,
                        health_score,
                        health_level,
                        health_status,
                        alert_time,
                        create_time,
                        update_time
                    FROM phm_alert_record
                    WHERE LOWER(alert_status) IN ('pending', 'unhandled', 'processing')
                    """
                )
                alert_rows = list(cursor.fetchall() or [])
        finally:
            connection.close()

        latest_risk_by_device_id = cls._index_latest_risk_by_device_id(risk_rows)
        latest_risk_by_device_code = cls._index_latest_risk_by_device_code(risk_rows)
        alerts_by_device_id = cls._index_alerts_by_device_id(alert_rows)
        alerts_by_device_code = cls._index_alerts_by_device_code(alert_rows)

        cards = []
        for device in devices:
            device_id = device.get("device_id")
            device_code = device.get("device_code")
            device_status = cls._normalize_device_status(device.get("device_status"))
            risk = latest_risk_by_device_id.get(device_id) or latest_risk_by_device_code.get(device_code)
            active_alerts = cls._collect_device_alerts(
                device_id=device_id,
                device_code=device_code,
                alerts_by_device_id=alerts_by_device_id,
                alerts_by_device_code=alerts_by_device_code,
            )
            alert_summary = cls._summarize_active_alerts(active_alerts)

            if active_alerts:
                current_status = alert_summary["current_status"]
                status_source = "active_alert"
                updated_at = alert_summary["latest_alert_time"]
                current_display = cls._build_active_alert_display(alert_summary)
            else:
                risk_status = cls._map_health_to_status(
                    (risk or {}).get("health_level"),
                    (risk or {}).get("health_status"),
                )
                if risk and risk_status is not None:
                    current_status = risk_status
                    status_source = "latest_risk"
                    updated_at = risk.get("latest_prediction_time")
                    current_display = cls._build_latest_risk_display(risk)
                else:
                    current_status = device_status
                    status_source = "device_status"
                    updated_at = device.get("update_time") or device.get("create_time")
                    current_display = cls._build_device_status_display(device)

            cards.append(
                {
                    "device_id": device_id,
                    "device_code": device_code,
                    "device_name": device.get("device_name"),
                    "device_type": device.get("device_type"),
                    "location": device.get("location"),
                    "device_status": device_status,
                    "device_status_text": cls._format_status_text(device_status),
                    "current_status": current_status,
                    "current_status_text": cls._format_status_text(current_status),
                    "status_source": status_source,
                    "risk_result_id": (risk or {}).get("risk_result_id"),
                    "risk_score": (risk or {}).get("risk_score"),
                    "health_score": (risk or {}).get("health_score"),
                    "health_level": (risk or {}).get("health_level"),
                    "health_status": (risk or {}).get("health_status"),
                    "health_description": (risk or {}).get("health_description"),
                    "latest_prediction_time": (risk or {}).get("latest_prediction_time"),
                    "window_end_time": (risk or {}).get("window_end_time"),
                    "active_alert_count": alert_summary["active_alert_count"],
                    "highest_active_alert_level": alert_summary["highest_active_alert_level"],
                    "highest_active_alert_time": alert_summary["highest_active_alert_time"],
                    "latest_alert_id": alert_summary["latest_alert_id"],
                    "latest_alert_message": alert_summary["latest_alert_message"],
                    "latest_alert_status": alert_summary["latest_alert_status"],
                    "current_risk_score": current_display["current_risk_score"],
                    "current_health_score": current_display["current_health_score"],
                    "current_event_time": current_display["current_event_time"],
                    "current_message": current_display["current_message"],
                    "current_alert_level": current_display["current_alert_level"],
                    "current_alert_status": current_display["current_alert_status"],
                    "current_risk_result_id": current_display["current_risk_result_id"],
                    "updated_at": updated_at,
                }
            )

        return cards

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
        """查询最近若干条真实风险结果，按设备运行窗口时间升序返回。"""
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
                            ts_end,
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
                    f"""
                    SELECT
                        d.device_id,
                        d.device_code,
                        d.device_status,
                        latest_risk.health_level,
                        latest_risk.health_status
                    FROM phm_device AS d
                    LEFT JOIN ({cls._latest_risk_sql()}) AS latest_risk
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
                        COALESCE(a.health_status, r.health_status) AS health_status,
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
                    f"""
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
                        COALESCE(latest_risk.window_end_time, latest_risk.ts_end, latest_risk.created_at) AS window_end_time,
                        COALESCE(latest_risk.window_end_time, latest_risk.ts_end, latest_risk.created_at, d.update_time, d.create_time) AS updated_at
                    FROM ({cls._latest_risk_sql()}) AS latest_risk
                    LEFT JOIN phm_device AS d
                        ON d.device_id = latest_risk.device_id
                        OR (
                            latest_risk.device_id IS NULL
                            AND d.device_code = latest_risk.device_code
                        )
                    LEFT JOIN ({cls._latest_alert_sql()}) AS latest_alert
                        ON latest_alert.device_id = COALESCE(d.device_id, latest_risk.device_id)
                        OR (
                            latest_alert.device_id IS NULL
                            AND latest_alert.device_code = COALESCE(d.device_code, latest_risk.device_code)
                        )
                    ORDER BY latest_risk.calibrated_risk_score DESC,
                             COALESCE(latest_risk.window_end_time, latest_risk.ts_end, latest_risk.created_at) DESC
                    LIMIT %s
                    """,
                    (normalized_limit,),
                )
                rows = cursor.fetchall()
        finally:
            connection.close()

        return list(rows or [])

    @classmethod
    def _index_latest_risk_by_device_id(cls, rows: List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]:
        index: Dict[Any, Dict[str, Any]] = {}
        for row in rows:
            device_id = row.get("device_id")
            if device_id is None:
                continue
            if cls._is_newer_risk(row, index.get(device_id)):
                index[device_id] = row
        return index

    @classmethod
    def _index_latest_risk_by_device_code(cls, rows: List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]:
        index: Dict[Any, Dict[str, Any]] = {}
        for row in rows:
            device_code = row.get("device_code")
            if not device_code:
                continue
            if cls._is_newer_risk(row, index.get(device_code)):
                index[device_code] = row
        return index

    @staticmethod
    def _index_alerts_by_device_id(rows: List[Dict[str, Any]]) -> Dict[Any, List[Dict[str, Any]]]:
        index: Dict[Any, List[Dict[str, Any]]] = {}
        for row in rows:
            device_id = row.get("device_id")
            if device_id is None:
                continue
            index.setdefault(device_id, []).append(row)
        return index

    @staticmethod
    def _index_alerts_by_device_code(rows: List[Dict[str, Any]]) -> Dict[Any, List[Dict[str, Any]]]:
        index: Dict[Any, List[Dict[str, Any]]] = {}
        for row in rows:
            device_code = row.get("device_code")
            if not device_code:
                continue
            index.setdefault(device_code, []).append(row)
        return index

    @classmethod
    def _collect_device_alerts(
        cls,
        device_id: Any,
        device_code: Any,
        alerts_by_device_id: Dict[Any, List[Dict[str, Any]]],
        alerts_by_device_code: Dict[Any, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[Any, Dict[str, Any]] = {}
        for row in alerts_by_device_id.get(device_id, []):
            merged[row.get("alert_id")] = row
        for row in alerts_by_device_code.get(device_code, []):
            merged[row.get("alert_id")] = row
        return list(merged.values())

    @classmethod
    def _summarize_active_alerts(cls, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not alerts:
            return {
                "active_alert_count": 0,
                "current_status": None,
                "highest_alert": None,
                "highest_active_alert_level": None,
                "highest_active_alert_time": None,
                "latest_alert_id": None,
                "latest_alert_message": None,
                "latest_alert_status": None,
                "latest_alert_time": None,
            }

        highest_alert = max(alerts, key=cls._alert_severity_sort_key)
        latest_alert = max(alerts, key=cls._alert_time_sort_key)
        return {
            "active_alert_count": len(alerts),
            "current_status": cls._map_alert_to_status(highest_alert.get("alert_level")),
            "highest_alert": highest_alert,
            "highest_active_alert_level": highest_alert.get("alert_level"),
            "highest_active_alert_time": cls._alert_time_value(highest_alert),
            "latest_alert_id": latest_alert.get("alert_id"),
            "latest_alert_message": latest_alert.get("alert_message"),
            "latest_alert_status": latest_alert.get("alert_status"),
            "latest_alert_time": cls._alert_time_value(latest_alert),
        }

    @classmethod
    def _build_active_alert_display(cls, alert_summary: Dict[str, Any]) -> Dict[str, Any]:
        alert = alert_summary.get("highest_alert") or {}
        return {
            "current_risk_score": alert.get("risk_score"),
            "current_health_score": alert.get("health_score"),
            "current_event_time": cls._alert_time_value(alert),
            "current_message": alert.get("alert_message"),
            "current_alert_level": alert.get("alert_level"),
            "current_alert_status": alert.get("alert_status"),
            "current_risk_result_id": alert.get("risk_result_id"),
        }

    @staticmethod
    def _build_latest_risk_display(risk: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "current_risk_score": risk.get("risk_score"),
            "current_health_score": risk.get("health_score"),
            "current_event_time": risk.get("latest_prediction_time") or risk.get("window_end_time") or risk.get("ts_end") or risk.get("created_at"),
            "current_message": risk.get("health_description"),
            "current_alert_level": None,
            "current_alert_status": None,
            "current_risk_result_id": risk.get("risk_result_id"),
        }

    @staticmethod
    def _build_device_status_display(device: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "current_risk_score": None,
            "current_health_score": None,
            "current_event_time": device.get("update_time") or device.get("create_time"),
            "current_message": None,
            "current_alert_level": None,
            "current_alert_status": None,
            "current_risk_result_id": None,
        }

    @classmethod
    def _is_newer_risk(cls, candidate: Dict[str, Any], current: Optional[Dict[str, Any]]) -> bool:
        if current is None:
            return True
        return cls._risk_sort_key(candidate) > cls._risk_sort_key(current)

    @staticmethod
    def _risk_sort_key(row: Dict[str, Any]) -> tuple:
        return (
            str(row.get("latest_prediction_time") or row.get("window_end_time") or row.get("ts_end") or row.get("created_at") or ""),
            row.get("risk_result_id") or 0,
        )

    @classmethod
    def _alert_severity_sort_key(cls, row: Dict[str, Any]) -> tuple:
        return (
            cls._map_alert_to_status(row.get("alert_level")),
            str(cls._alert_time_value(row) or ""),
            row.get("alert_id") or 0,
        )

    @classmethod
    def _alert_time_sort_key(cls, row: Dict[str, Any]) -> tuple:
        return (
            str(cls._alert_time_value(row) or ""),
            row.get("alert_id") or 0,
        )

    @staticmethod
    def _alert_time_value(row: Dict[str, Any]) -> Any:
        return row.get("alert_time") or row.get("create_time") or row.get("update_time")

    @classmethod
    def _map_alert_to_status(cls, value: Any) -> int:
        return cls.ALERT_STATUS_LEVEL.get(cls._normalize_key(value), 2)

    @classmethod
    def _map_health_to_status(cls, health_level: Any, health_status: Any) -> Optional[int]:
        for value in (health_level, health_status):
            status = cls.HEALTH_STATUS_LEVEL.get(cls._normalize_key(value))
            if status is not None:
                return status
        return None

    @classmethod
    def _normalize_device_status(cls, value: Any) -> int:
        try:
            status = int(value)
        except (TypeError, ValueError):
            return 1
        return status if status in cls.DEVICE_STATUS_TEXT else 1

    @classmethod
    def _format_status_text(cls, value: Any) -> str:
        return cls.DEVICE_STATUS_TEXT.get(cls._normalize_device_status(value), "正常")

    @staticmethod
    def _latest_risk_sql() -> str:
        return """
            SELECT r.*
            FROM phm_risk_result AS r
            WHERE NOT EXISTS (
                SELECT 1
                FROM phm_risk_result AS newer
                WHERE COALESCE(newer.device_code, CAST(newer.device_id AS CHAR)) =
                      COALESCE(r.device_code, CAST(r.device_id AS CHAR))
                  AND (
                      COALESCE(newer.window_end_time, newer.ts_end, newer.created_at) >
                      COALESCE(r.window_end_time, r.ts_end, r.created_at)
                      OR (
                          COALESCE(newer.window_end_time, newer.ts_end, newer.created_at) =
                          COALESCE(r.window_end_time, r.ts_end, r.created_at)
                          AND newer.risk_result_id > r.risk_result_id
                      )
                  )
            )
        """

    @staticmethod
    def _latest_alert_sql() -> str:
        return """
            SELECT a.*
            FROM phm_alert_record AS a
            WHERE NOT EXISTS (
                SELECT 1
                FROM phm_alert_record AS newer
                WHERE COALESCE(newer.device_code, CAST(newer.device_id AS CHAR)) =
                      COALESCE(a.device_code, CAST(a.device_id AS CHAR))
                  AND (
                      COALESCE(newer.alert_time, newer.create_time, newer.update_time) >
                      COALESCE(a.alert_time, a.create_time, a.update_time)
                      OR (
                          COALESCE(newer.alert_time, newer.create_time, newer.update_time) =
                          COALESCE(a.alert_time, a.create_time, a.update_time)
                          AND newer.alert_id > a.alert_id
                      )
                  )
            )
        """

    @staticmethod
    def _normalize_limit(value: Any, default: int) -> int:
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return default

        return limit if 0 < limit <= 200 else default

    @staticmethod
    def _normalize_key(value: Any) -> str:
        if value is None or value == "":
            return ""
        return str(value).strip().lower()
