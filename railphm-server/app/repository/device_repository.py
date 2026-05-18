import copy
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

import pymysql

from app.core.errors import BusinessException
from app.extensions.db import get_connection


class DeviceRepository:
    """
    设备数据访问层 (Repository)
    阶段 5 起接口数据源切换为 phm_device，mock 数据仅保留历史兼容。
    """

    _initial_mock_data: List[Dict[str, Any]] = [
        {"device_id": 1, "car_no": "CR400AF-0201", "atp_type": "CTCS-3", "attach_bureau": "北京局", "device_status": 1},
        {"device_id": 2, "car_no": "CR400BF-0512", "atp_type": "CTCS-3", "attach_bureau": "上海局", "device_status": 1},
        {"device_id": 3, "car_no": "CRH380A-2217", "atp_type": "CTCS-2", "attach_bureau": "广州局", "device_status": 0},
        {"device_id": 4, "car_no": "CR400AF-2011", "atp_type": "CTCS-3", "attach_bureau": "济南局", "device_status": 1},
        {"device_id": 5, "car_no": "CRH2A-1024", "atp_type": "CTCS-2", "attach_bureau": "武汉局", "device_status": 1},
    ]
    _mock_data: List[Dict[str, Any]] = copy.deepcopy(_initial_mock_data)

    _DEVICE_SELECT_FIELDS = """
        device_id,
        device_code,
        device_name,
        device_type,
        device_status,
        atp_type,
        car_no,
        train_no,
        attach_bureau,
        create_time,
        update_time
    """

    @classmethod
    def reset_mock_data(cls) -> None:
        """重置可变 mock 数据，避免历史测试之间互相污染。"""
        cls._mock_data = copy.deepcopy(cls._initial_mock_data)

    @classmethod
    def find_all(cls) -> List[Dict[str, Any]]:
        """查询所有设备。"""
        total, items = cls.find_filtered(page=1, size=100000)
        return items

    @classmethod
    def find_filtered(
        cls,
        page: int = 1,
        size: int = 10,
        device_id: Optional[int] = None,
        device_code: Optional[str] = None,
        device_name: Optional[str] = None,
        device_type: Optional[str] = None,
        car_no: Optional[str] = None,
        atp_type: Optional[str] = None,
        train_no: Optional[str] = None,
        attach_bureau: Optional[str] = None,
        device_status: Optional[int] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """按设备台账字段筛选真实设备列表。"""
        where_sql, params = cls._build_filter_where(
            device_id=device_id,
            device_code=device_code,
            device_name=device_name,
            device_type=device_type,
            car_no=car_no,
            atp_type=atp_type,
            train_no=train_no,
            attach_bureau=attach_bureau,
            device_status=device_status,
        )
        offset = (page - 1) * size

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM phm_device
                    {where_sql}
                    """,
                    params,
                )
                total_record = cursor.fetchone() or {}
                total = int(total_record.get("total", 0))

                cursor.execute(
                    f"""
                    SELECT {cls._DEVICE_SELECT_FIELDS}
                    FROM phm_device
                    {where_sql}
                    ORDER BY device_id ASC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, size, offset],
                )
                items = cursor.fetchall()
        finally:
            connection.close()

        return total, [cls._normalize_device_record(item) for item in items]

    @classmethod
    def find_by_id(cls, device_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 查询真实设备。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._DEVICE_SELECT_FIELDS}
                    FROM phm_device
                    WHERE device_id = %s
                    LIMIT 1
                    """,
                    (device_id,),
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_device_record(record) if record else None

    @classmethod
    def find_by_code(cls, device_code: str) -> Optional[Dict[str, Any]]:
        """根据设备业务编号查询真实设备。"""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {cls._DEVICE_SELECT_FIELDS}
                    FROM phm_device
                    WHERE device_code = %s
                    LIMIT 1
                    """,
                    (device_code,),
                )
                record = cursor.fetchone()
        finally:
            connection.close()

        return cls._normalize_device_record(record) if record else None

    @classmethod
    def create_device(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """新增真实设备台账记录。"""
        cls._check_device_code_conflict(payload["device_code"])

        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO phm_device (
                        device_code,
                        device_name,
                        device_type,
                        device_status,
                        atp_type,
                        car_no,
                        train_no,
                        attach_bureau
                    ) VALUES (
                        %(device_code)s,
                        %(device_name)s,
                        %(device_type)s,
                        %(device_status)s,
                        %(atp_type)s,
                        %(car_no)s,
                        %(train_no)s,
                        %(attach_bureau)s
                    )
                    """,
                    payload,
                )
                device_id = cursor.lastrowid
            connection.commit()
        except pymysql.err.IntegrityError as exc:
            connection.rollback()
            if "device_code" in str(exc).lower() or "duplicate" in str(exc).lower():
                raise BusinessException(code=400, message="device_code 已存在", status_code=400) from exc
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return cls.find_by_id(device_id)

    @classmethod
    def update_device(cls, device_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """编辑真实设备台账记录。"""
        if cls.find_by_id(device_id) is None:
            return None
        cls._check_device_code_conflict(payload["device_code"], exclude_device_id=device_id)

        params = {
            **payload,
            "device_id": device_id,
        }
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE phm_device
                    SET
                        device_code = %(device_code)s,
                        device_name = %(device_name)s,
                        device_type = %(device_type)s,
                        device_status = %(device_status)s,
                        atp_type = %(atp_type)s,
                        car_no = %(car_no)s,
                        train_no = %(train_no)s,
                        attach_bureau = %(attach_bureau)s
                    WHERE device_id = %(device_id)s
                    """,
                    params,
                )
            connection.commit()
        except pymysql.err.IntegrityError as exc:
            connection.rollback()
            if "device_code" in str(exc).lower() or "duplicate" in str(exc).lower():
                raise BusinessException(code=400, message="device_code 已存在", status_code=400) from exc
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return cls.find_by_id(device_id)

    @classmethod
    def _check_device_code_conflict(
        cls,
        device_code: str,
        exclude_device_id: Optional[int] = None,
    ) -> None:
        existing_device = cls.find_by_code(device_code)
        if not existing_device:
            return
        if exclude_device_id is not None and existing_device.get("device_id") == exclude_device_id:
            return
        raise BusinessException(code=400, message="device_code 已存在", status_code=400)

    @classmethod
    def _build_filter_where(
        cls,
        device_id: Optional[int] = None,
        device_code: Optional[str] = None,
        device_name: Optional[str] = None,
        device_type: Optional[str] = None,
        car_no: Optional[str] = None,
        atp_type: Optional[str] = None,
        train_no: Optional[str] = None,
        attach_bureau: Optional[str] = None,
        device_status: Optional[int] = None,
    ) -> tuple[str, list[Any]]:
        where_clauses = []
        params: list[Any] = []

        if device_id is not None:
            where_clauses.append("device_id = %s")
            params.append(device_id)
        cls._add_like_filter(where_clauses, params, "device_code", device_code)
        cls._add_like_filter(where_clauses, params, "device_name", device_name)
        cls._add_exact_filter(where_clauses, params, "device_type", device_type)
        cls._add_like_filter(where_clauses, params, "car_no", car_no)
        cls._add_exact_filter(where_clauses, params, "atp_type", atp_type)
        cls._add_like_filter(where_clauses, params, "train_no", train_no)
        cls._add_like_filter(where_clauses, params, "attach_bureau", attach_bureau)
        if device_status is not None:
            where_clauses.append("device_status = %s")
            params.append(device_status)

        if not where_clauses:
            return "", params
        return "WHERE " + " AND ".join(where_clauses), params

    @staticmethod
    def _add_like_filter(
        where_clauses: list[str],
        params: list[Any],
        column: str,
        value: Optional[str],
    ) -> None:
        if value:
            where_clauses.append(f"{column} LIKE %s")
            params.append(f"%{value}%")

    @staticmethod
    def _add_exact_filter(
        where_clauses: list[str],
        params: list[Any],
        column: str,
        value: Optional[str],
    ) -> None:
        if value:
            where_clauses.append(f"{column} = %s")
            params.append(value)

    @classmethod
    def _normalize_device_record(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        normalized_record = dict(record)
        normalized_record["create_time"] = cls._normalize_datetime(
            normalized_record.get("create_time")
        )
        normalized_record["update_time"] = cls._normalize_datetime(
            normalized_record.get("update_time")
        )
        return normalized_record

    @staticmethod
    def _normalize_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value
