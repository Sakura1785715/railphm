import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.extensions.db import get_connection


class PredictionRepository:
    """
    风险预测结果访问层 (Repository)
    infer 写入与 latest/history 查询均使用 phm_risk_result；旧 mock 数据仅保留兼容历史代码。
    """

    _RISK_RESULT_SELECT_FIELDS = """
        risk_result_id,
        device_id,
        device_code,
        sample_index,
        risk_raw,
        calibrated_risk_score,
        risk_std,
        threshold,
        predicted_label,
        health_score,
        health_level,
        health_status,
        health_description,
        y_true,
        condition_label,
        ts_end,
        window_minutes,
        window_start_time,
        window_end_time,
        sample_id,
        segment_id,
        segment_file,
        target_time,
        target_label_value,
        target_alarm_value,
        target_atp_type,
        target_car_no,
        target_train_no,
        target_attach_bureau,
        trace_json,
        created_at
    """
    
    # 旧 Mock 数据保留给历史代码参考；latest/history 已切换到 MySQL。
    _mock_data: List[Dict[str, Any]] = [
        # Device 1 数据
        {"device_id": 1, "calibrated_risk_score": 0.45, "risk_std": 0.03, "health_score": 55.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 09:00:00", "window_end_time": "2026-04-01 09:05:00"},
        {"device_id": 1, "calibrated_risk_score": 0.52, "risk_std": 0.04, "health_score": 48.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 09:05:00", "window_end_time": "2026-04-01 09:10:00"},
        {"device_id": 1, "calibrated_risk_score": 0.82, "risk_std": 0.07, "health_score": 18.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 10:00:00", "window_end_time": "2026-04-01 10:05:00"}, # 最新一条
        
        # Device 2 数据
        {"device_id": 2, "calibrated_risk_score": 0.21, "risk_std": 0.01, "health_score": 79.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 08:00:00", "window_end_time": "2026-04-01 08:05:00"},
        {"device_id": 2, "calibrated_risk_score": 0.25, "risk_std": 0.02, "health_score": 75.0, "model_version": "bilstm-attention-v1", "window_start_time": "2026-04-01 08:05:00", "window_end_time": "2026-04-01 08:10:00"},
    ]

    @classmethod
    def save_infer_result(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """保存真实 AI 推理结果，fallback 结果不应调用此方法。"""
        device_value = record.get("device_id")
        if device_value is None or device_value == "":
            device_value = record.get("device_code")
        device_info = cls._resolve_device(device_value)
        trace_fields = cls._extract_trace_fields(record.get("trace"))

        params = {
            "device_id": device_info["device_id"],
            "device_code": device_info["device_code"],
            "sample_index": cls._normalize_optional_int(record.get("sample_index")),
            "risk_raw": cls._normalize_optional_float(record.get("risk_raw")),
            "calibrated_risk_score": cls._normalize_optional_float(record.get("risk_score")),
            "risk_std": cls._normalize_optional_float(record.get("risk_std")),
            "threshold": cls._normalize_optional_float(record.get("threshold")),
            "predicted_label": cls._normalize_optional_int(record.get("predicted_label")),
            "health_score": cls._normalize_optional_float(record.get("health_score")),
            "health_level": record.get("health_level"),
            "health_status": record.get("health_status"),
            "health_description": record.get("health_description"),
            "y_true": cls._normalize_y_true(record.get("y_true")),
            "condition_label": record.get("condition_label"),
            "ts_end": cls._normalize_datetime(record.get("ts_end")),
            "window_minutes": cls._normalize_optional_int(record.get("window_minutes")),
            "window_start_time": cls._normalize_datetime(record.get("window_start_time")),
            "window_end_time": cls._normalize_datetime(record.get("window_end_time")),
            **trace_fields,
            "trace_json": cls._json_dumps(record.get("trace") or {}),
        }

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO phm_risk_result (
                        device_id,
                        device_code,
                        sample_index,
                        risk_raw,
                        calibrated_risk_score,
                        risk_std,
                        threshold,
                        predicted_label,
                        health_score,
                        health_level,
                        health_status,
                        health_description,
                        y_true,
                        condition_label,
                        ts_end,
                        window_minutes,
                        window_start_time,
                        window_end_time,
                        sample_id,
                        segment_id,
                        segment_file,
                        target_time,
                        target_label_value,
                        target_alarm_value,
                        target_atp_type,
                        target_car_no,
                        target_train_no,
                        target_attach_bureau,
                        window_start_row,
                        window_end_row,
                        target_row,
                        trace_json
                    ) VALUES (
                        %(device_id)s,
                        %(device_code)s,
                        %(sample_index)s,
                        %(risk_raw)s,
                        %(calibrated_risk_score)s,
                        %(risk_std)s,
                        %(threshold)s,
                        %(predicted_label)s,
                        %(health_score)s,
                        %(health_level)s,
                        %(health_status)s,
                        %(health_description)s,
                        %(y_true)s,
                        %(condition_label)s,
                        %(ts_end)s,
                        %(window_minutes)s,
                        %(window_start_time)s,
                        %(window_end_time)s,
                        %(sample_id)s,
                        %(segment_id)s,
                        %(segment_file)s,
                        %(target_time)s,
                        %(target_label_value)s,
                        %(target_alarm_value)s,
                        %(target_atp_type)s,
                        %(target_car_no)s,
                        %(target_train_no)s,
                        %(target_attach_bureau)s,
                        %(window_start_row)s,
                        %(window_end_row)s,
                        %(target_row)s,
                        CAST(%(trace_json)s AS JSON)
                    )
                    """,
                    params,
                )
                risk_result_id = cursor.lastrowid
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        saved_record = cls.get_by_id(risk_result_id)
        if saved_record is None:
            return {
                **params,
                "risk_result_id": risk_result_id,
                "risk_score": params["calibrated_risk_score"],
            }
        return saved_record

    @classmethod
    def get_by_id(cls, risk_result_id: int) -> Optional[Dict[str, Any]]:
        """根据主键查询风险预测结果。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._RISK_RESULT_SELECT_FIELDS}
                    FROM phm_risk_result
                    WHERE risk_result_id = %s
                    LIMIT 1
                    """,
                    (risk_result_id,),
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_risk_record(record) if record else None

    @classmethod
    def _resolve_device(cls, device_value: Any) -> Dict[str, Any]:
        """
        将接口传入的设备编号或数字 ID 解析为数据库主键和标准设备编号。
        查不到设备时保留原始编号，device_id 写入 NULL。
        """
        original_value = "" if device_value is None else str(device_value).strip()
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                if cls._is_numeric_device_value(device_value):
                    cursor.execute(
                        """
                        SELECT device_id, device_code
                        FROM phm_device
                        WHERE device_id = %s
                        LIMIT 1
                        """,
                        (int(original_value),),
                    )
                    record = cursor.fetchone()
                    if record:
                        return {
                            "device_id": record["device_id"],
                            "device_code": record["device_code"],
                        }
                elif original_value:
                    cursor.execute(
                        """
                        SELECT device_id, device_code
                        FROM phm_device
                        WHERE device_code = %s
                        LIMIT 1
                        """,
                        (original_value,),
                    )
                    record = cursor.fetchone()
                    if record:
                        return {
                            "device_id": record["device_id"],
                            "device_code": record["device_code"],
                        }

                if original_value:
                    cursor.execute(
                        """
                        SELECT device_id, device_code
                        FROM phm_device
                        WHERE device_code = %s
                        LIMIT 1
                        """,
                        (original_value,),
                    )
                    record = cursor.fetchone()
                    if record:
                        return {
                            "device_id": record["device_id"],
                            "device_code": record["device_code"],
                        }
        finally:
            connection.close()

        return {
            "device_id": None,
            "device_code": original_value,
        }

    @staticmethod
    def _is_numeric_device_value(value: Any) -> bool:
        if isinstance(value, bool) or value is None:
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, str):
            return value.strip().isdigit()
        return False

    @staticmethod
    def _normalize_datetime(value: Any) -> Any:
        """将空时间值统一转为 NULL，保留合法 datetime 或字符串给 MySQL 处理。"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized_value = value.strip()
            if not normalized_value:
                return None
            return normalized_value.replace("T", " ").removesuffix("Z")
        return value

    @staticmethod
    def _normalize_optional_int(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_optional_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _normalize_y_true(cls, value: Any) -> Optional[int]:
        normalized_value = cls._normalize_optional_int(value)
        if normalized_value in (0, 1):
            return normalized_value
        return None

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value if value else {}, ensure_ascii=False)

    @staticmethod
    def _get_trace_value(trace: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = trace.get(key)
            if value is not None and value != "":
                return value
        return None

    @classmethod
    def _extract_trace_fields(cls, trace: Any) -> Dict[str, Any]:
        """从 AI trace 中拆分常用检索字段，原始 trace 仍完整写入 JSON 列。"""
        if not isinstance(trace, dict):
            trace = {}

        target_label_value = cls._get_trace_value(trace, "target_label_value")
        target_alarm_value = cls._get_trace_value(trace, "target_alarm_value")
        if target_alarm_value is None:
            target_alarm_value = target_label_value

        return {
            "sample_id": cls._get_trace_value(trace, "sample_id"),
            "segment_id": cls._get_trace_value(trace, "segment_id"),
            "segment_file": cls._get_trace_value(trace, "segment_file"),
            "target_time": cls._normalize_datetime(cls._get_trace_value(trace, "target_time")),
            "target_label_value": target_label_value,
            "target_alarm_value": target_alarm_value,
            "target_atp_type": cls._get_trace_value(trace, "target_ATP类型"),
            "target_car_no": cls._get_trace_value(trace, "target_车号"),
            "target_train_no": cls._get_trace_value(trace, "target_车次"),
            "target_attach_bureau": cls._get_trace_value(trace, "target_配属铁路局"),
            "window_start_row": cls._normalize_optional_int(
                cls._get_trace_value(trace, "window_start_row")
            ),
            "window_end_row": cls._normalize_optional_int(
                cls._get_trace_value(trace, "window_end_row")
            ),
            "target_row": cls._normalize_optional_int(cls._get_trace_value(trace, "target_row")),
        }

    @classmethod
    def _build_device_filter(cls, resolved_device: Dict[str, Any]) -> tuple[str, list[Any]]:
        """构造 phm_risk_result 设备查询条件，兼容 device_id 为空的历史记录。"""
        if resolved_device.get("device_id") is not None:
            return "(device_id = %s OR device_code = %s)", [
                resolved_device["device_id"],
                resolved_device["device_code"],
            ]
        return "device_code = %s", [resolved_device["device_code"]]

    @classmethod
    def _normalize_risk_record(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """将数据库风险记录转为接口层可稳定序列化的字典。"""
        normalized_record = dict(record)
        normalized_record["risk_score"] = normalized_record.get("calibrated_risk_score")

        if normalized_record.get("risk_std") is None:
            normalized_record["risk_std"] = 0.0

        trace_json = normalized_record.get("trace_json")
        if isinstance(trace_json, str):
            try:
                normalized_record["trace"] = json.loads(trace_json) if trace_json else {}
            except json.JSONDecodeError:
                normalized_record["trace"] = {}
        elif isinstance(trace_json, dict):
            normalized_record["trace"] = trace_json
        elif trace_json is None:
            normalized_record["trace"] = {}

        for field in (
            "ts_end",
            "window_start_time",
            "window_end_time",
            "target_time",
            "created_at",
        ):
            normalized_record[field] = cls._format_datetime(normalized_record.get(field))

        return normalized_record

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value

    @classmethod
    def get_latest_by_device_id(cls, device_value: Any) -> Optional[Dict[str, Any]]:
        """获取某设备最新一条真实预测结果。"""
        resolved_device = cls._resolve_device(device_value)
        device_filter_sql, device_params = cls._build_device_filter(resolved_device)

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._RISK_RESULT_SELECT_FIELDS}
                    FROM phm_risk_result
                    WHERE {device_filter_sql}
                    ORDER BY COALESCE(window_end_time, ts_end, created_at) DESC,
                             risk_result_id DESC
                    LIMIT 1
                    """,
                    device_params,
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_risk_record(record) if record else None

    @classmethod
    def query_history_by_device_and_range(
        cls,
        device_value: Any,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict[str, Any]]:
        """获取某设备时间范围内的真实历史预测结果。"""
        resolved_device = cls._resolve_device(device_value)
        device_filter_sql, device_params = cls._build_device_filter(resolved_device)

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._RISK_RESULT_SELECT_FIELDS}
                    FROM phm_risk_result
                    WHERE {device_filter_sql}
                      AND COALESCE(window_end_time, ts_end, created_at) >= %s
                      AND COALESCE(window_end_time, ts_end, created_at) <= %s
                    ORDER BY COALESCE(window_end_time, ts_end, created_at) ASC,
                             risk_result_id ASC
                    """,
                    [*device_params, start_dt, end_dt],
                )
                records = cursor.fetchall()
        finally:
            connection.close()

        return [cls._normalize_risk_record(record) for record in records]
