from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from flask import current_app

# 导入告警文案和建议
from app.core.risk_rules import (
    ALERT_ADVICE_HIGH,
    ALERT_ADVICE_MEDIUM,
    ALERT_MESSAGE_HIGH,
    ALERT_MESSAGE_MEDIUM,
)
from app.core.errors import BusinessException
# Repository 层
from app.repository.alert_repository import AlertRepository # 查/写告警表
from app.repository.monitor_repository import MonitorRepository # 查 InfluxDB 监测数据
from app.repository.prediction_repository import PredictionRepository # 查/写 phm_risk_result 风险结果表
from app.repository.run_record_repository import RunRecordRepository # 查/更新 phm_run_record 运行记录表
# 整理返回格式
from app.schema.alert_schema import AlertSchema
from app.schema.run_record_schema import RunRecordSchema
from app.service.prediction_service import PredictionService


class RunRecordService:
    """运行记录池业务服务。"""

    MAX_PAGE_SIZE = 100
    MAX_MONITOR_LIMIT = 20000

    @classmethod
    # 前端运行记录池列表页
    def list_records(
        cls,
        page: Any = 1,
        page_size: Any = 10,
        device_code: Optional[str] = None,
        status: Optional[str] = None,
        has_alarm_label: Any = None,
        min_risk_score: Any = None,
    ) -> Dict[str, Any]:
        normalized_page = cls._parse_positive_int(page, "page")
        normalized_page_size = min(
            cls._parse_positive_int(page_size, "page_size"),
            cls.MAX_PAGE_SIZE,
        )
        # 整理筛选条件
        filters = {
            "device_code": cls._clean_text(device_code),
            "status": cls._clean_text(status),
            "has_alarm_label": cls._parse_optional_bool(has_alarm_label, "has_alarm_label"),
            "min_risk_score": cls._parse_optional_float(min_risk_score, "min_risk_score"),
        }
        # 去 MySQL 查 phm_run_record 表
        result = RunRecordRepository.list_records(
            filters=filters,
            page=normalized_page,
            page_size=normalized_page_size,
        )
        return {
            "items": RunRecordSchema.dump_list(result["items"]),
            "total": result["total"],
            "page": normalized_page,
            "page_size": normalized_page_size,
        }

    @classmethod
    # 查单条运行记录详情
    def get_detail(cls, run_record_id: Any) -> Dict[str, Any]:
        record_id = cls._parse_positive_int(run_record_id, "run_record_id")
        record = RunRecordRepository.get_by_id(record_id)
        if not record:
            raise BusinessException(
                code=404,
                message=f"未找到运行记录ID为 {record_id} 的记录",
                status_code=404,
            )
        return RunRecordSchema.dump(record)

    @classmethod
    def get_random(cls, device_code: Optional[str] = None) -> Dict[str, Any]:
        record = RunRecordRepository.get_random({"device_code": cls._clean_text(device_code)})
        if not record:
            raise BusinessException(code=404, message="未找到可用运行记录", status_code=404)
        return RunRecordSchema.dump(record)

    @classmethod
    # 查某条运行记录的监测数据
    def get_monitor_history(
        cls,
        run_record_id: Any,
        limit_value: Any = None,
    ) -> Dict[str, Any]:
        record_id = cls._parse_positive_int(run_record_id, "run_record_id")
        record = RunRecordRepository.get_by_id(record_id)
        if not record:
            raise BusinessException(
                code=404,
                message=f"未找到运行记录ID为 {record_id} 的记录",
                status_code=404,
            )
        # 从运行记录里取字段
        device_code = cls._clean_text(record.get("device_code")) # 设备编号
        source_segment = cls._clean_text(record.get("source_segment")) # 数据片段编号
        if not device_code:
            raise BusinessException(code=400, message="运行记录缺少 device_code", status_code=400)
        if not source_segment:
            raise BusinessException(code=400, message="运行记录缺少 source_segment", status_code=400)

        start_dt = cls._parse_time(record.get("record_start_time"), "record_start_time")
        end_dt = cls._parse_time(record.get("record_end_time"), "record_end_time")
        # 防止一次查太多监测点，最大 20000 条
        limit = min(cls._parse_optional_limit(limit_value), cls.MAX_MONITOR_LIMIT)
        # 查 InfluxDB
        rows = MonitorRepository.query_history_by_device_and_segment(
            device_code=device_code,
            source_segment=source_segment,
            start_time=start_dt,
            end_time=end_dt + timedelta(seconds=1),
            limit=limit,
        )
        # 整理返回
        return RunRecordSchema.dump_monitor_history(record, rows)

    @classmethod
    # 执行运行记录风险预测
    def infer_record(
        cls,
        run_record_id: Any,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        把 run_record_id 翻译成 PredictionService.range_infer() 需要的完整参数
        """
        record_id = cls._parse_positive_int(run_record_id, "run_record_id")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体必须为 JSON 对象", status_code=400)
        # 根据id查运行记录
        record = RunRecordRepository.get_by_id(record_id)
        if not record:
            raise BusinessException(code=404, message="运行记录不存在", status_code=404)
        # 从运行记录中取核心字段
        device_code = cls._clean_text(record.get("device_code"))
        source_segment = cls._clean_text(record.get("source_segment"))
        record_start_time = cls._clean_text(record.get("record_start_time"))
        record_end_time = cls._clean_text(record.get("record_end_time"))
        if not device_code:
            raise BusinessException(code=400, message="运行记录缺少 device_code", status_code=400)
        if not source_segment:
            raise BusinessException(code=400, message="运行记录缺少 source_segment", status_code=400)
        if not record_start_time:
            raise BusinessException(code=400, message="运行记录缺少 record_start_time", status_code=400)
        if not record_end_time:
            raise BusinessException(code=400, message="运行记录缺少 record_end_time", status_code=400)
        # 根据运行记录构建区间推理请求
        range_payload = {
            "run_record_id": record_id,
            "device_code": device_code,
            "source_segment": source_segment,
            "start_time": record_start_time,
            "end_time": record_end_time,
            "inference_stride_seconds": payload.get(
                "inference_stride_seconds",
                current_app.config.get("RUN_RECORD_INFER_DEFAULT_STRIDE_SECONDS", 1),
            ),
            "mc_samples": payload.get("mc_samples", 20),
            "persist": payload.get("persist", True),
            "generate_alert": False,
        }
        # 进行推理
        result = PredictionService.range_infer(range_payload)
        # 统计本次推理的最高风险
        summary = cls._build_infer_summary(result.get("risk_series") or [])
        # 更新 phm_run_record 中对应的运行记录状态
        updated_record = RunRecordRepository.update_after_infer(
            run_record_id=record_id,
            summary={
                "status": "inferred",
                "max_risk_score": summary["max_risk_score"],
                "max_risk_result_id": summary["max_risk_result_id"],
                "max_alert_level": summary["max_alert_level"],
            },
        )

        return {
            **result,
            "run_record_id": record_id,
            "run_record_code": record.get("run_record_code"),
            "device_code": device_code,
            "source_segment": source_segment,
            "record_start_time": record_start_time,
            "record_end_time": record_end_time,
            "max_risk_score": summary["max_risk_score"],
            "max_risk_result_id": summary["max_risk_result_id"],
            "max_alert_level": summary["max_alert_level"],
            "run_record_status": (updated_record or {}).get("status", "inferred"),
            "alert_generation_skipped": True,
            "alert_generation_skip_reason": "run_record_alert_not_implemented",
        }

    @classmethod
    # 生成运行记录告警
    def generate_record_alert(
        cls,
        run_record_id: Any,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        根据已经保存的预测结果，找到这条运行记录的最高风险点，然后决定是否生成告警。
        """
        record_id = cls._parse_positive_int(run_record_id, "run_record_id")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体必须为 JSON 对象", status_code=400)
        # 查运行记录
        run_record = RunRecordRepository.get_by_id(record_id)
        if not run_record:
            raise BusinessException(code=404, message="运行记录不存在", status_code=404)
        # 检查是否已经有告警
        existing_alert = cls._get_existing_run_record_alert(run_record)
        if existing_alert:
            cls._sync_run_record_alert_summary(run_record, existing_alert)
            return cls._build_existing_alert_response(run_record, existing_alert)
        # 查最高风险点
        max_risk_record = PredictionRepository.get_max_risk_by_run_record_id(record_id)
        if not max_risk_record:
            raise BusinessException(
                code=400,
                message="运行记录尚未完成风险推理，请先执行推理",
                status_code=400,
            )
        
        # 取最高风险分数
        max_risk_score = cls._get_risk_score(max_risk_record)
        if max_risk_score is None:
            raise BusinessException(
                code=400,
                message="运行记录最高风险分数为空或非法",
                status_code=400,
            )   

        # 根据风险分数计算告警等级
        max_alert_level = cls._resolve_max_alert_level(max_risk_score)
        summary = {
            "status": "inferred",
            "max_risk_score": max_risk_score,
            "max_risk_result_id": max_risk_record.get("risk_result_id"),
            "max_alert_level": max_alert_level,
        }

        # 如果风险低于 warning，不生成告警
        warning_threshold = float(current_app.config.get("RISK_THRESHOLD_WARNING", 0.65))
        if max_risk_score < warning_threshold:
            RunRecordRepository.update_after_infer(record_id, summary)
            return {
                "run_record_id": record_id,
                "run_record_code": run_record.get("run_record_code"),
                "device_code": run_record.get("device_code"),
                "source_segment": run_record.get("source_segment"),
                "alert_generated": False,
                "created": False,
                "existing": False,
                "reason": "max_risk_below_warning_threshold",
                "risk_result_id": max_risk_record.get("risk_result_id"),
                "max_risk_score": max_risk_score,
                "max_risk_result_id": max_risk_record.get("risk_result_id"),
                "max_alert_level": max_alert_level,
                "health_score": max_risk_record.get("health_score"),
                "health_level": max_risk_record.get("health_level"),
                "health_status": max_risk_record.get("health_status"),
            }

        # 风险足够高，生成告警
        alert_payload = cls._build_run_record_alert_payload(max_alert_level)
        alert_record = AlertRepository.create_from_run_record(
            run_record=run_record,
            risk_record=max_risk_record,
            alert_payload=alert_payload,
        )
        if not alert_record:
            raise BusinessException(code=500, message="运行记录告警创建失败", status_code=500)

        RunRecordRepository.update_after_infer(record_id, summary)
        RunRecordRepository.update_after_alert(
            run_record_id=record_id,
            alert_id=int(alert_record["alert_id"]),
            alert_level=max_alert_level,
        )

        return {
            "run_record_id": record_id,
            "run_record_code": run_record.get("run_record_code"),
            "device_code": run_record.get("device_code"),
            "source_segment": run_record.get("source_segment"),
            "alert_generated": True,
            "created": True,
            "existing": False,
            "alert_id": alert_record.get("alert_id"),
            "alert_level": alert_record.get("alert_level"),
            "risk_result_id": max_risk_record.get("risk_result_id"),
            "max_risk_score": max_risk_score,
            "max_risk_result_id": max_risk_record.get("risk_result_id"),
            "max_alert_level": max_alert_level,
            "health_score": max_risk_record.get("health_score"),
            "health_level": max_risk_record.get("health_level"),
            "health_status": max_risk_record.get("health_status"),
            "message": alert_record.get("alert_message") or alert_record.get("message"),
            "alert": AlertSchema.dump_detail(alert_record),
        }

    @classmethod
    # 检查这条运行记录是否已经有告警。
    def _get_existing_run_record_alert(
        cls,
        run_record: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        alert_id = run_record.get("alert_id")
        if alert_id:
            try:
                existing = AlertRepository.get_alert_by_id(int(alert_id))
            except (TypeError, ValueError):
                existing = None
            if existing:
                return existing
        return AlertRepository.get_by_run_record_id(int(run_record["run_record_id"]))

    @classmethod
    # 如果已有告警，就把运行记录表里的 alert_id、alert_level 同步一下
    def _sync_run_record_alert_summary(
        cls,
        run_record: Dict[str, Any],
        alert_record: Dict[str, Any],
    ) -> None:
        RunRecordRepository.update_after_alert(
            run_record_id=int(run_record["run_record_id"]),
            alert_id=int(alert_record["alert_id"]),
            alert_level=alert_record.get("alert_level") or run_record.get("max_alert_level"),
        )

    @staticmethod
    # 把已有告警整理成前端能直接用的返回格式。
    def _build_existing_alert_response(
        run_record: Dict[str, Any],
        alert_record: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "run_record_id": run_record.get("run_record_id"),
            "run_record_code": run_record.get("run_record_code"),
            "device_code": run_record.get("device_code"),
            "source_segment": run_record.get("source_segment"),
            "alert_generated": True,
            "created": False,
            "existing": True,
            "alert_id": alert_record.get("alert_id"),
            "alert_level": alert_record.get("alert_level"),
            "risk_result_id": alert_record.get("risk_result_id"),
            "max_risk_score": alert_record.get("risk_score") or run_record.get("max_risk_score"),
            "max_risk_result_id": alert_record.get("risk_result_id") or run_record.get("max_risk_result_id"),
            "max_alert_level": alert_record.get("alert_level") or run_record.get("max_alert_level"),
            "health_score": alert_record.get("health_score"),
            "health_level": alert_record.get("health_level"),
            "health_status": alert_record.get("health_status"),
            "message": alert_record.get("alert_message") or alert_record.get("message"),
            "alert": AlertSchema.dump_detail(alert_record),
        }

    @staticmethod
    # 根据告警等级选择告警文案和处置建议。
    def _build_run_record_alert_payload(alert_level: str) -> Dict[str, Any]:
        if alert_level == "high":
            return {
                "alert_level": "high",
                "alert_message": ALERT_MESSAGE_HIGH,
                "alert_advice": ALERT_ADVICE_HIGH,
            }
        return {
            "alert_level": "medium",
            "alert_message": ALERT_MESSAGE_MEDIUM,
            "alert_advice": ALERT_ADVICE_MEDIUM,
        }

    @classmethod
    def _get_risk_score(cls, risk_record: Dict[str, Any]) -> Optional[float]:
        return cls._parse_optional_float(
            risk_record.get("risk_score")
            if risk_record.get("risk_score") is not None
            else risk_record.get("calibrated_risk_score"),
            "max_risk_score",
        )

    @classmethod
    def _build_infer_summary(cls, risk_series: list[Dict[str, Any]]) -> Dict[str, Any]:
        max_point = None
        for point in risk_series:
            if not isinstance(point, dict):
                continue
            risk_score = cls._parse_optional_float(point.get("risk_score"), "risk_score")
            if risk_score is None:
                continue
            if max_point is None or risk_score > max_point["risk_score"]:
                max_point = {
                    "risk_score": risk_score,
                    "risk_result_id": point.get("risk_result_id"),
                }

        if max_point is None:
            return {
                "max_risk_score": None,
                "max_risk_result_id": None,
                "max_alert_level": None,
            }

        return {
            "max_risk_score": max_point["risk_score"],
            "max_risk_result_id": max_point["risk_result_id"],
            "max_alert_level": cls._resolve_max_alert_level(max_point["risk_score"]),
        }

    @staticmethod
    def _resolve_max_alert_level(risk_score: float) -> str:
        risk_value = max(0.0, min(1.0, float(risk_score)))
        normal = float(current_app.config.get("RISK_THRESHOLD_NORMAL", 0.40))
        warning = float(current_app.config.get("RISK_THRESHOLD_WARNING", 0.65))
        critical = float(current_app.config.get("RISK_THRESHOLD_CRITICAL", 0.85))

        if risk_value < normal:
            return "none"
        if risk_value < warning:
            return "low"
        if risk_value < critical:
            return "medium"
        return "high"

    @staticmethod
    def _parse_positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400) from exc
        if parsed <= 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        return parsed

    @classmethod
    def _parse_optional_limit(cls, value: Any) -> int:
        if value is None or value == "":
            return cls.MAX_MONITOR_LIMIT
        return cls._parse_positive_int(value, "limit")

    @staticmethod
    def _parse_optional_bool(value: Any, field_name: str) -> Optional[bool]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        raise BusinessException(code=400, message=f"{field_name} 必须为布尔值", status_code=400)

    @staticmethod
    def _parse_optional_float(value: Any, field_name: str) -> Optional[float]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise BusinessException(code=400, message=f"{field_name} 必须为数字", status_code=400)
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise BusinessException(code=400, message=f"{field_name} 必须为数字", status_code=400) from exc

    @staticmethod
    def _parse_time(value: Any, field_name: str) -> datetime:
        if not value:
            raise BusinessException(code=400, message=f"运行记录缺少 {field_name}", status_code=400)
        if isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise BusinessException(
                code=400,
                message=f"{field_name} 格式非法，请使用 YYYY-MM-DD HH:mm:ss 格式",
                status_code=400,
            ) from exc

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
