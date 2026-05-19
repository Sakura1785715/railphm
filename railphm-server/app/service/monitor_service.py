from datetime import datetime
from typing import Dict, Any, Optional

from flask import current_app

from app.core.errors import BusinessException
from app.repository.device_repository import DeviceRepository
from app.repository.monitor_repository import MonitorRepository
from app.schema.monitor_schema import MonitorSchema


class MonitorService:
    """
    监测业务逻辑层 (Service)
    负责参数校验、设备解析和 InfluxDB 查询编排。
    """

    MAX_QUERY_LIMIT = 20000

    @staticmethod
    def get_historical_series(
        device_value: Optional[str] = None,
        start_str: Optional[str] = None,
        end_str: Optional[str] = None,
        limit_value: Any = None,
        condition_label: Optional[str] = None,
        device_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_device_code = MonitorService._resolve_device_code(device_code or device_value)
        start_dt, end_dt = MonitorService._parse_time_range(start_str, end_str)
        limit = MonitorService._parse_limit(limit_value)

        rows = MonitorRepository.query_history_by_device_and_range(
            device_code=resolved_device_code,
            start_dt=start_dt,
            end_dt=end_dt,
            limit=limit,
            condition_label=condition_label.strip() if isinstance(condition_label, str) and condition_label.strip() else None,
        )

        return MonitorSchema.dump_history(
            device_code=resolved_device_code,
            start_time=start_str,
            end_time=end_str,
            rows=rows,
        )

    @staticmethod
    def _resolve_device_code(device_value: Optional[str]) -> str:
        if device_value is None or str(device_value).strip() == "":
            raise BusinessException(code=400, message="device_code 不能为空", status_code=400)

        normalized_value = str(device_value).strip()
        if normalized_value.isdigit():
            device = DeviceRepository.find_by_id(int(normalized_value))
            if device:
                return device.get("device_code") or normalized_value
            return normalized_value

        return normalized_value

    @staticmethod
    def _parse_time_range(start_str: Optional[str], end_str: Optional[str]) -> tuple[datetime, datetime]:
        if not start_str:
            raise BusinessException(code=400, message="start_time 不能为空", status_code=400)
        if not end_str:
            raise BusinessException(code=400, message="end_time 不能为空", status_code=400)

        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise BusinessException(
                code=400,
                message="时间格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            ) from exc

        if start_dt >= end_dt:
            raise BusinessException(code=400, message="开始时间必须早于结束时间", status_code=400)
        return start_dt, end_dt

    @staticmethod
    def _parse_limit(limit_value: Any) -> int:
        default_limit = int(current_app.config.get("MONITOR_QUERY_LIMIT", 5000))
        if limit_value is None or limit_value == "":
            return min(default_limit, MonitorService.MAX_QUERY_LIMIT)
        if isinstance(limit_value, bool):
            raise BusinessException(code=400, message="limit 必须为正整数", status_code=400)
        try:
            limit = int(limit_value)
        except (TypeError, ValueError) as exc:
            raise BusinessException(code=400, message="limit 必须为正整数", status_code=400) from exc
        if limit <= 0:
            raise BusinessException(code=400, message="limit 必须为正整数", status_code=400)
        return min(limit, MonitorService.MAX_QUERY_LIMIT)
