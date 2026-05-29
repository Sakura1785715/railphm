# app/service/alert_service.py
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

from app.core.errors import BusinessException
from app.core.risk_rules import (
    ALERT_ADVICE_HIGH,
    ALERT_ADVICE_LOW,
    ALERT_ADVICE_MEDIUM,
    ALERT_ADVICE_NONE,
    ALERT_LEVEL_HIGH,
    ALERT_LEVEL_LOW,
    ALERT_LEVEL_MEDIUM,
    ALERT_LEVEL_NONE,
    ALERT_MESSAGE_HIGH,
    ALERT_MESSAGE_LOW,
    ALERT_MESSAGE_MEDIUM,
    ALERT_MESSAGE_NONE,
    ALERT_STATUS_NONE,
    ALERT_STATUS_TEXT_NONE,
    ALERT_STATUS_TEXT_UNHANDLED,
    ALERT_STATUS_UNHANDLED,
    RISK_THRESHOLD_CRITICAL,
    RISK_THRESHOLD_NORMAL,
    RISK_THRESHOLD_WARNING,
)
from app.repository.alert_repository import AlertRepository
from app.repository.monitor_repository import MonitorRepository
from app.repository.prediction_repository import PredictionRepository
from app.repository.run_record_repository import RunRecordRepository
from app.schema.alert_schema import AlertSchema


class AlertService:
    """
    告警业务层 (Service)
    负责分页校验与业务流转编排
    """
    VALID_ALERT_STATUSES = {"unhandled", "processing", "resolved"}

    def __init__(
        self,
        risk_threshold_normal: float = RISK_THRESHOLD_NORMAL,
        risk_threshold_warning: float = RISK_THRESHOLD_WARNING,
        risk_threshold_critical: float = RISK_THRESHOLD_CRITICAL,
        suppress_min_window_minutes: int = 15,
        suppress_max_window_minutes: int = 60,
        suppress_lookback_ratio: float = 0.5,
        logger: logging.Logger | None = None,
    ):
        self.risk_threshold_normal = float(risk_threshold_normal)
        self.risk_threshold_warning = float(risk_threshold_warning)
        self.risk_threshold_critical = float(risk_threshold_critical)
        self.suppress_min_window_minutes = int(suppress_min_window_minutes)
        self.suppress_max_window_minutes = int(suppress_max_window_minutes)
        self.suppress_lookback_ratio = float(suppress_lookback_ratio)
        self.logger = logger or logging.getLogger(__name__)

    def evaluate(
        self,
        risk_score: Any,
        health_score: float | None = None,
        health_level: str | None = None,
        predicted_label: int | None = None,
    ) -> Dict[str, Any]:
        """
        根据 risk_score 生成本次推理的告警判断结果。
        alert_level 表示告警严重程度，不等同于 health_level；本方法不写数据库。
        """
        normalized_risk_score = self._parse_risk_score(risk_score)
        clipped_risk_score = self._clip_risk_score(normalized_risk_score)

        if clipped_risk_score < self.risk_threshold_normal:
            return {
                "alert_generated": False,
                "alert_level": ALERT_LEVEL_NONE,
                "alert_status": ALERT_STATUS_NONE,
                "alert_status_text": ALERT_STATUS_TEXT_NONE,
                "alert_message": ALERT_MESSAGE_NONE,
                "alert_advice": ALERT_ADVICE_NONE,
            }

        if clipped_risk_score < self.risk_threshold_warning:
            return {
                "alert_generated": True,
                "alert_level": ALERT_LEVEL_LOW,
                "alert_status": ALERT_STATUS_UNHANDLED,
                "alert_status_text": ALERT_STATUS_TEXT_UNHANDLED,
                "alert_message": ALERT_MESSAGE_LOW,
                "alert_advice": ALERT_ADVICE_LOW,
            }

        if clipped_risk_score < self.risk_threshold_critical:
            return {
                "alert_generated": True,
                "alert_level": ALERT_LEVEL_MEDIUM,
                "alert_status": ALERT_STATUS_UNHANDLED,
                "alert_status_text": ALERT_STATUS_TEXT_UNHANDLED,
                "alert_message": ALERT_MESSAGE_MEDIUM,
                "alert_advice": ALERT_ADVICE_MEDIUM,
            }

        self.logger.info(
            "High risk alert generated",
            extra={
                "health_score": health_score,
                "health_level": health_level,
                "predicted_label": predicted_label,
            },
        )
        return {
            "alert_generated": True,
            "alert_level": ALERT_LEVEL_HIGH,
            "alert_status": ALERT_STATUS_UNHANDLED,
            "alert_status_text": ALERT_STATUS_TEXT_UNHANDLED,
            "alert_message": ALERT_MESSAGE_HIGH,
            "alert_advice": ALERT_ADVICE_HIGH,
        }

    def generate_range_alerts(
        self,
        prediction_records: list[Dict[str, Any]],
        lookback_minutes: int | None = None,
        range_start_time: Any = None,
        range_end_time: Any = None,
        inference_stride_seconds: int = 60,
    ) -> Dict[str, Any]:
        """为区间推理结果生成片段级告警，并按同设备同等级活跃告警做冷却抑制。"""
        effective_window_minutes = self._calculate_suppress_window_minutes(
            lookback_minutes=lookback_minutes,
            range_start_time=range_start_time,
            range_end_time=range_end_time,
        )
        evaluated_records = self._evaluate_prediction_records(prediction_records or [])
        alert_segments = self._build_alert_segments(
            evaluated_records,
            inference_stride_seconds=inference_stride_seconds,
        )

        alerts: list[Dict[str, Any]] = []
        new_alert_count = 0
        existing_alert_count = 0
        total_abnormal_points = sum(len(segment["points"]) for segment in alert_segments)
        segment_summaries: list[Dict[str, Any]] = []

        for segment in alert_segments:
            summary = self._build_segment_summary(segment)
            representative = self._select_representative_point(segment["points"])

            if representative is None or not representative.get("risk_result_id"):
                summary.update(
                    {
                        "representative_time": self._format_datetime(
                            self._get_record_time(representative or {})
                        ),
                        "representative_risk_result_id": None,
                        "suppressed": True,
                        "suppress_reason": "missing_risk_result_id",
                    }
                )
                segment_summaries.append(summary)
                continue

            representative_time = self._get_record_time(representative)
            representative_record = dict(representative)
            representative_record.update(
                {
                    "alert_generated": True,
                    "alert_level": segment["alert_level"],
                }
            )

            summary.update(
                {
                    "representative_time": self._format_datetime(representative_time),
                    "representative_risk_result_id": representative_record.get("risk_result_id"),
                }
            )

            existing_by_risk_id = AlertRepository.get_by_risk_result_id(
                int(representative_record["risk_result_id"])
            )
            if existing_by_risk_id:
                existing_alert_count += 1
                alerts.append({**existing_by_risk_id, "existing": True})
                summary.update(
                    {
                        "suppressed": True,
                        "suppress_reason": "risk_result_id_already_has_alert",
                        "alert_id": None,
                        "existing_alert_id": existing_by_risk_id.get("alert_id"),
                    }
                )
                segment_summaries.append(summary)
                continue

            recent_alert = self._find_recent_active_alert(
                representative_record=representative_record,
                representative_time=representative_time,
                suppress_window_minutes=effective_window_minutes,
            )
            if recent_alert:
                existing_alert_count += 1
                alerts.append({**recent_alert, "existing": True})
                summary.update(
                    {
                        "suppressed": True,
                        "suppress_reason": "same_device_level_active_alert_within_cooldown",
                        "alert_id": None,
                        "existing_alert_id": recent_alert.get("alert_id"),
                    }
                )
                segment_summaries.append(summary)
                continue

            alert_record = AlertRepository.create_from_prediction(representative_record)
            if alert_record:
                new_alert_count += 1
                alerts.append({**alert_record, "existing": False})
                summary.update(
                    {
                        "suppressed": False,
                        "suppress_reason": "",
                        "alert_id": alert_record.get("alert_id"),
                        "existing_alert_id": None,
                    }
                )
            else:
                summary.update(
                    {
                        "suppressed": True,
                        "suppress_reason": "alert_create_skipped",
                        "alert_id": None,
                        "existing_alert_id": None,
                    }
                )
            segment_summaries.append(summary)

        return {
            "generate_alert": True,
            "alert_suppress_window_minutes": effective_window_minutes,
            "alert_count": new_alert_count,
            "existing_alert_count": existing_alert_count,
            "suppressed_alert_count": max(total_abnormal_points - new_alert_count, 0),
            "alert_segment_count": len(alert_segments),
            "alerts": alerts,
            "alert_segments": segment_summaries,
        }

    def build_empty_range_alert_summary(
        self,
        generate_alert: bool,
        skip_reason: str,
        lookback_minutes: int | None = None,
        range_start_time: Any = None,
        range_end_time: Any = None,
    ) -> Dict[str, Any]:
        """构造未生成区间告警时的稳定返回结构。"""
        return {
            "generate_alert": generate_alert,
            "alert_generation_skipped": True,
            "alert_generation_skip_reason": skip_reason,
            "alert_suppress_window_minutes": self._calculate_suppress_window_minutes(
                lookback_minutes=lookback_minutes,
                range_start_time=range_start_time,
                range_end_time=range_end_time,
            ),
            "alert_count": 0,
            "existing_alert_count": 0,
            "suppressed_alert_count": 0,
            "alert_segment_count": 0,
            "alerts": [],
            "alert_segments": [],
        }

    def _evaluate_prediction_records(
        self,
        prediction_records: list[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        evaluated_records: list[Dict[str, Any]] = []
        for record in prediction_records:
            alert_result = self.evaluate(
                risk_score=record.get("risk_score"),
                health_score=record.get("health_score"),
                health_level=record.get("health_level"),
                predicted_label=record.get("predicted_label"),
            )
            evaluated_records.append({**record, **alert_result})
        return evaluated_records

    def _build_alert_segments(
        self,
        evaluated_records: list[Dict[str, Any]],
        inference_stride_seconds: int,
    ) -> list[Dict[str, Any]]:
        ordered_records = list(evaluated_records)
        if ordered_records and all(self._get_record_time(record) for record in ordered_records):
            ordered_records.sort(key=lambda record: self._get_record_time(record) or datetime.min)

        segments: list[Dict[str, Any]] = []
        current_points: list[Dict[str, Any]] = []
        current_level: str | None = None
        previous_alert_time: datetime | None = None
        max_gap_seconds = max(
            float(inference_stride_seconds) * 1.5,
            float(inference_stride_seconds) + 5.0,
        )

        for record in ordered_records:
            if not record.get("alert_generated"):
                if current_points:
                    segments.append(
                        {"alert_level": current_level, "points": current_points}
                    )
                current_points = []
                current_level = None
                previous_alert_time = None
                continue

            record_level = record.get("alert_level")
            record_time = self._get_record_time(record)
            has_time_gap = (
                previous_alert_time is not None
                and record_time is not None
                and abs((record_time - previous_alert_time).total_seconds()) > max_gap_seconds
            )
            should_split = (
                bool(current_points)
                and (record_level != current_level or has_time_gap)
            )
            if should_split:
                segments.append({"alert_level": current_level, "points": current_points})
                current_points = []

            current_points.append(record)
            current_level = record_level
            previous_alert_time = record_time

        if current_points:
            segments.append({"alert_level": current_level, "points": current_points})

        return segments

    def _build_segment_summary(self, segment: Dict[str, Any]) -> Dict[str, Any]:
        points = segment["points"]
        start_time = self._get_record_time(points[0])
        end_time = self._get_record_time(points[-1])
        risk_scores = [
            self._safe_float(point.get("risk_score"))
            for point in points
            if self._safe_float(point.get("risk_score")) is not None
        ]
        return {
            "device_code": points[0].get("device_code"),
            "alert_level": segment["alert_level"],
            "segment_start_time": self._format_datetime(start_time),
            "segment_end_time": self._format_datetime(end_time),
            "point_count": len(points),
            "max_risk_score": max(risk_scores) if risk_scores else None,
            "representative_time": None,
            "representative_risk_result_id": None,
            "suppressed": True,
            "suppress_reason": "",
            "alert_id": None,
            "existing_alert_id": None,
        }

    def _select_representative_point(
        self,
        points: list[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        candidates = [point for point in points if point.get("risk_result_id")]
        if not candidates:
            return None

        def sort_key(point: Dict[str, Any]) -> tuple[float, datetime]:
            risk_score = self._safe_float(point.get("risk_score"))
            point_time = self._get_record_time(point) or datetime.min
            return (risk_score if risk_score is not None else float("-inf"), point_time)

        return max(candidates, key=sort_key)

    def _find_recent_active_alert(
        self,
        representative_record: Dict[str, Any],
        representative_time: datetime | None,
        suppress_window_minutes: int,
    ) -> Optional[Dict[str, Any]]:
        device_code = representative_record.get("device_code")
        alert_level = representative_record.get("alert_level")
        if not device_code or not alert_level:
            return None

        if representative_time is not None:
            since_time = representative_time - timedelta(minutes=suppress_window_minutes)
            recent_alert = AlertRepository.find_recent_active_alert(
                device_code=device_code,
                alert_level=alert_level,
                since_time=since_time,
                until_time=representative_time,
            )
            if recent_alert:
                return recent_alert

        now = datetime.now()
        current_since_time = now - timedelta(minutes=suppress_window_minutes)
        return AlertRepository.find_recent_active_alert(
            device_code=device_code,
            alert_level=alert_level,
            since_time=current_since_time,
            until_time=now,
        )

    def _calculate_suppress_window_minutes(
        self,
        lookback_minutes: int | None = None,
        range_start_time: Any = None,
        range_end_time: Any = None,
    ) -> int:
        effective_range_minutes = self._safe_float(lookback_minutes)
        if effective_range_minutes is None and range_start_time and range_end_time:
            start_dt = self._parse_datetime(range_start_time)
            end_dt = self._parse_datetime(range_end_time)
            if start_dt and end_dt and end_dt > start_dt:
                effective_range_minutes = (end_dt - start_dt).total_seconds() / 60
        if effective_range_minutes is None or effective_range_minutes <= 0:
            effective_range_minutes = 60

        raw_window = effective_range_minutes * self.suppress_lookback_ratio
        return int(
            max(
                self.suppress_min_window_minutes,
                min(self.suppress_max_window_minutes, raw_window),
            )
        )

    @staticmethod
    def _get_record_time(record: Dict[str, Any]) -> datetime | None:
        for field in ("time", "window_end_time", "ts_end", "created_at"):
            value = record.get(field)
            parsed_value = AlertService._parse_datetime(value)
            if parsed_value:
                return parsed_value
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized_value = value.strip().replace("T", " ").removesuffix("Z")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    return datetime.strptime(normalized_value, fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _format_datetime(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or value == "" or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _parse_risk_score(self, risk_score: Any) -> float:
        if risk_score is None or risk_score == "":
            raise BusinessException(
                code=400,
                message="risk_score 不能为空",
                status_code=400,
            )
        if isinstance(risk_score, bool):
            raise BusinessException(
                code=400,
                message="risk_score 格式非法",
                status_code=400,
            )
        try:
            return float(risk_score)
        except (TypeError, ValueError) as exc:
            raise BusinessException(
                code=400,
                message="risk_score 格式非法",
                status_code=400,
            ) from exc

    def _clip_risk_score(self, risk_score: float) -> float:
        if risk_score < 0.0:
            self.logger.warning("risk_score below 0, clipped to 0 for alert evaluation")
            return 0.0
        if risk_score > 1.0:
            self.logger.warning("risk_score above 1, clipped to 1 for alert evaluation")
            return 1.0
        return risk_score

    @staticmethod
    def _parse_pagination(page_str: Any, size_str: Any) -> tuple[int, int]:
        """解析并校验分页参数"""
        try:
            page = int(page_str)
            size = int(size_str)
            if page <= 0:
                raise ValueError
            if size <= 0:
                raise ValueError
            return page, size
        except (ValueError, TypeError):
            raise BusinessException(code=400, message="page 和 size 必须为正整数", status_code=400)

    @staticmethod
    def get_alert_list(page_str: Any, size_str: Any, alert_status: Optional[str], alert_level: Optional[str], device_id_str: Optional[str]) -> Dict[str, Any]:
        page, size = AlertService._parse_pagination(page_str, size_str)

        try:
            normalized_status = AlertRepository._normalize_alert_status(alert_status)
            normalized_level = AlertRepository._normalize_alert_level(alert_level)
        except ValueError as exc:
            raise BusinessException(code=400, message=str(exc), status_code=400) from exc

        total, items = AlertRepository.query_alerts(
            page,
            size,
            normalized_status,
            normalized_level,
            device_id_str,
        )
        return AlertSchema.dump_page(items, total, page, size)

    @staticmethod
    def get_alert_detail(alert_id: int) -> Dict[str, Any]:
        record = AlertRepository.get_alert_by_id(alert_id)
        if not record:
            raise BusinessException(code=404, message=f"未找到告警ID为 {alert_id} 的告警记录", status_code=404)
        return AlertSchema.dump_detail(record)

    @staticmethod
    def get_alert_diagnosis(alert_id: int, context_seconds: Any = None) -> Dict[str, Any]:
        context = AlertService._parse_context_seconds(context_seconds)
        alert = AlertRepository.get_alert_by_id(alert_id)
        if not alert:
            raise BusinessException(code=404, message=f"未找到告警ID为 {alert_id} 的告警记录", status_code=404)

        representative_risk = AlertService._get_representative_risk(alert)
        run_record = AlertService._get_related_run_record(alert, representative_risk)
        event_time = AlertService._resolve_event_time(alert, representative_risk)
        context_start, context_end = AlertService._build_context_window(
            event_time=event_time,
            context_seconds=context,
            run_record=run_record,
        )

        risk_records = AlertService._query_risk_records(
            alert=alert,
            representative_risk=representative_risk,
            run_record=run_record,
            context_start=context_start,
            context_end=context_end,
        )
        risk_records = AlertService._dedupe_risk_records_by_time(risk_records)
        monitor_series = AlertService._query_monitor_series(
            alert=alert,
            representative_risk=representative_risk,
            run_record=run_record,
            context_start=context_start,
            context_end=context_end,
        )
        risk_series = AlertService._build_risk_series(risk_records)
        health_series = AlertService._build_health_series(risk_records)
        condition_segments = AlertService._build_condition_segments(monitor_series)
        if not condition_segments:
            condition_segments = AlertService._build_condition_segments(risk_series)
        diagnosis_summary = AlertService._build_diagnosis_summary(
            event_time=event_time,
            context_start=context_start,
            context_end=context_end,
            monitor_series=monitor_series,
            risk_records=risk_records,
            representative_risk=representative_risk,
            run_record=run_record,
        )

        return AlertSchema.dump_diagnosis(
            {
                "alert": alert,
                "run_record": run_record,
                "representative_risk": representative_risk,
                "monitor_series": monitor_series,
                "risk_series": risk_series,
                "health_series": health_series,
                "condition_segments": condition_segments,
                "diagnosis_summary": diagnosis_summary,
            }
        )

    @staticmethod
    def _parse_context_seconds(value: Any) -> int:
        if value is None or value == "":
            return 120
        if isinstance(value, bool):
            raise BusinessException(code=400, message="context_seconds 必须为正整数", status_code=400)
        try:
            context_seconds = int(value)
        except (TypeError, ValueError) as exc:
            raise BusinessException(code=400, message="context_seconds 必须为正整数", status_code=400) from exc
        if context_seconds <= 0:
            raise BusinessException(code=400, message="context_seconds 必须为正整数", status_code=400)
        return min(context_seconds, 1800)

    @staticmethod
    def _get_representative_risk(alert: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        risk_result_id = AlertService._safe_int(alert.get("risk_result_id"))
        if risk_result_id is None:
            return None
        return PredictionRepository.get_by_id(risk_result_id)

    @staticmethod
    def _get_related_run_record(
        alert: Dict[str, Any],
        representative_risk: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        run_record_id = AlertService._safe_int(alert.get("run_record_id"))
        if run_record_id is None and representative_risk:
            run_record_id = AlertService._safe_int(representative_risk.get("run_record_id"))
        if run_record_id is None:
            return None
        return RunRecordRepository.get_by_id(run_record_id)

    @staticmethod
    def _resolve_event_time(
        alert: Dict[str, Any],
        representative_risk: Optional[Dict[str, Any]],
    ) -> Optional[datetime]:
        for value in (
            (representative_risk or {}).get("window_end_time"),
            (representative_risk or {}).get("ts_end"),
            alert.get("target_time"),
            alert.get("alert_time"),
            alert.get("create_time"),
        ):
            parsed_value = AlertService._parse_datetime(value)
            if parsed_value:
                return parsed_value
        return None

    @staticmethod
    def _build_context_window(
        event_time: Optional[datetime],
        context_seconds: int,
        run_record: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        if run_record:
            start_dt = AlertService._parse_datetime(run_record.get("record_start_time"))
            end_dt = AlertService._parse_datetime(run_record.get("record_end_time"))
            if start_dt and end_dt and end_dt >= start_dt:
                return start_dt, end_dt
        if not event_time:
            return None, None
        return (
            event_time - timedelta(seconds=context_seconds),
            event_time + timedelta(seconds=context_seconds),
        )

    @staticmethod
    def _query_risk_records(
        alert: Dict[str, Any],
        representative_risk: Optional[Dict[str, Any]],
        run_record: Optional[Dict[str, Any]],
        context_start: Optional[datetime],
        context_end: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        run_record_id = AlertService._safe_int((run_record or {}).get("run_record_id"))
        if run_record_id is not None:
            return PredictionRepository.query_history_by_run_record_id(run_record_id)

        if not context_start or not context_end:
            return []

        device_value = (
            alert.get("device_code")
            or (representative_risk or {}).get("device_code")
            or alert.get("device_id")
        )
        if not device_value:
            return []
        return PredictionRepository.query_history_by_device_and_range(
            device_value,
            context_start,
            context_end,
        )

    @staticmethod
    def _dedupe_risk_records_by_time(risk_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        keyed_records: Dict[str, Dict[str, Any]] = {}
        no_time_records: List[Dict[str, Any]] = []

        for record in risk_records or []:
            record_time = AlertService._get_record_time(record)
            if not record_time:
                no_time_records.append(record)
                continue

            time_key = AlertService._format_datetime(record_time)
            existing_record = keyed_records.get(time_key)
            if existing_record is None or AlertService._should_replace_duplicate_risk_record(
                existing_record,
                record,
            ):
                keyed_records[time_key] = record

        deduped_records = sorted(
            keyed_records.values(),
            key=lambda record: AlertService._get_record_time(record) or datetime.max,
        )
        return [*deduped_records, *no_time_records]

    @staticmethod
    def _should_replace_duplicate_risk_record(
        existing_record: Dict[str, Any],
        candidate_record: Dict[str, Any],
    ) -> bool:
        existing_id = AlertService._safe_int(existing_record.get("risk_result_id"))
        candidate_id = AlertService._safe_int(candidate_record.get("risk_result_id"))
        if existing_id is None and candidate_id is None:
            return True
        if existing_id is None:
            return True
        if candidate_id is None:
            return False
        return candidate_id > existing_id

    @staticmethod
    def _query_monitor_series(
        alert: Dict[str, Any],
        representative_risk: Optional[Dict[str, Any]],
        run_record: Optional[Dict[str, Any]],
        context_start: Optional[datetime],
        context_end: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        try:
            if run_record:
                device_code = AlertService._clean_text(run_record.get("device_code"))
                source_segment = AlertService._clean_text(run_record.get("source_segment"))
                start_dt = AlertService._parse_datetime(run_record.get("record_start_time"))
                end_dt = AlertService._parse_datetime(run_record.get("record_end_time"))
                if device_code and source_segment and start_dt and end_dt:
                    return MonitorRepository.query_history_by_device_and_segment(
                        device_code=device_code,
                        source_segment=source_segment,
                        start_time=start_dt,
                        end_time=end_dt + timedelta(seconds=1),
                        limit=20000,
                        fields=list(MonitorRepository.FIELD_COLUMNS),
                    )

            device_code = AlertService._clean_text(
                alert.get("device_code") or (representative_risk or {}).get("device_code")
            )
            if not device_code or not context_start or not context_end:
                return []
            return MonitorRepository.query_history_by_device_and_range(
                device_code=device_code,
                start_dt=context_start,
                end_dt=context_end,
                fields=list(MonitorRepository.FIELD_COLUMNS),
                limit=20000,
            )
        except Exception:
            return []

    @staticmethod
    def _build_risk_series(risk_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        series = []
        for record in risk_records or []:
            series.append(
                {
                    "time": AlertService._format_datetime(AlertService._get_record_time(record)),
                    "risk_result_id": record.get("risk_result_id"),
                    "risk_score": AlertService._safe_float(record.get("risk_score")),
                    "risk_raw": AlertService._safe_float(record.get("risk_raw")),
                    "risk_std": AlertService._safe_float(record.get("risk_std")),
                    "threshold": AlertService._safe_float(record.get("threshold")),
                    "predicted_label": record.get("predicted_label"),
                    "condition_label": record.get("condition_label"),
                    "health_score": AlertService._safe_float(record.get("health_score")),
                    "health_level": record.get("health_level"),
                    "health_status": record.get("health_status"),
                    "window_start_time": record.get("window_start_time"),
                    "window_end_time": record.get("window_end_time"),
                    "ts_end": record.get("ts_end"),
                }
            )
        return series

    @staticmethod
    def _build_health_series(risk_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        series = []
        for record in risk_records or []:
            series.append(
                {
                    "time": AlertService._format_datetime(AlertService._get_record_time(record)),
                    "risk_result_id": record.get("risk_result_id"),
                    "health_score": AlertService._safe_float(record.get("health_score")),
                    "health_level": record.get("health_level"),
                    "health_status": record.get("health_status"),
                    "health_description": record.get("health_description"),
                    "risk_score": AlertService._safe_float(record.get("risk_score")),
                    "condition_label": record.get("condition_label"),
                }
            )
        return series

    @staticmethod
    def _build_condition_segments(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        points = []
        for row in rows or []:
            label = AlertService._clean_text(row.get("condition_label"))
            if not label:
                continue
            point_time = AlertService._get_series_time(row)
            if not point_time:
                continue
            points.append({"label": label, "time": point_time})

        points.sort(key=lambda item: item["time"])
        segments: List[Dict[str, Any]] = []
        for point in points:
            if not segments or segments[-1]["label"] != point["label"]:
                segments.append(
                    {
                        "label": point["label"],
                        "start_time": AlertService._format_datetime(point["time"]),
                        "end_time": AlertService._format_datetime(point["time"]),
                        "point_count": 1,
                    }
                )
                continue
            segments[-1]["end_time"] = AlertService._format_datetime(point["time"])
            segments[-1]["point_count"] += 1
        return segments

    @staticmethod
    def _build_diagnosis_summary(
        event_time: Optional[datetime],
        context_start: Optional[datetime],
        context_end: Optional[datetime],
        monitor_series: List[Dict[str, Any]],
        risk_records: List[Dict[str, Any]],
        representative_risk: Optional[Dict[str, Any]],
        run_record: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        risk_scores = [
            AlertService._safe_float(record.get("risk_score"))
            for record in risk_records or []
            if AlertService._safe_float(record.get("risk_score")) is not None
        ]
        health_scores = [
            AlertService._safe_float(record.get("health_score"))
            for record in risk_records or []
            if AlertService._safe_float(record.get("health_score")) is not None
        ]
        max_risk_score = max(risk_scores) if risk_scores else None
        min_health_score = min(health_scores) if health_scores else None

        evidence_parts = []
        if max_risk_score is not None and max_risk_score >= RISK_THRESHOLD_CRITICAL:
            evidence_parts.append("告警窗口内风险分数处于较高水平，建议结合制动速度、速度变化和工况状态进行复核。")
        if min_health_score is not None and min_health_score <= 60:
            evidence_parts.append("告警窗口内健康度下降明显，建议关注设备状态变化。")
        if monitor_series:
            evidence_parts.append("已关联告警前后运行监测数据，可用于检修研判。")
        else:
            evidence_parts.append("当前告警缺少可关联监测数据，建议检查运行记录或 InfluxDB 数据同步情况。")

        return {
            "event_time": AlertService._format_datetime(event_time),
            "context_start_time": AlertService._format_datetime(context_start),
            "context_end_time": AlertService._format_datetime(context_end),
            "monitor_point_count": len(monitor_series or []),
            "risk_point_count": len(risk_records or []),
            "max_risk_score": max_risk_score,
            "min_health_score": min_health_score,
            "representative_risk_result_id": (representative_risk or {}).get("risk_result_id"),
            "run_record_id": AlertService._resolve_summary_run_record_id(
                run_record,
                representative_risk,
            ),
            "source_segment": AlertService._resolve_summary_source_segment(
                run_record,
                representative_risk,
                monitor_series,
            ),
            "evidence_text": "".join(evidence_parts),
        }

    @staticmethod
    def _resolve_summary_run_record_id(
        run_record: Optional[Dict[str, Any]],
        representative_risk: Optional[Dict[str, Any]],
    ) -> Any:
        return (run_record or {}).get("run_record_id") or (representative_risk or {}).get("run_record_id")

    @staticmethod
    def _resolve_summary_source_segment(
        run_record: Optional[Dict[str, Any]],
        representative_risk: Optional[Dict[str, Any]],
        monitor_series: List[Dict[str, Any]],
    ) -> Optional[str]:
        first_monitor = monitor_series[0] if monitor_series and isinstance(monitor_series[0], dict) else {}
        for value in (
            (run_record or {}).get("source_segment"),
            (representative_risk or {}).get("segment_id"),
            (representative_risk or {}).get("segment_file"),
            first_monitor.get("source_segment"),
        ):
            text = AlertService._clean_text(value)
            if text:
                return text
        return None

    @staticmethod
    def _get_series_time(row: Dict[str, Any]) -> Optional[datetime]:
        for field in ("sample_time", "time", "window_end_time", "ts_end", "created_at"):
            parsed_value = AlertService._parse_datetime(row.get(field))
            if parsed_value:
                return parsed_value
        return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value is None or value == "" or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def update_alert_status(alert_id: int, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not payload or not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体不能为空", status_code=400)

        alert_status = payload.get("alert_status")
        if not alert_status:
            raise BusinessException(code=400, message="alert_status 不能为空", status_code=400)
        try:
            normalized_status = AlertRepository._normalize_alert_status(alert_status)
        except ValueError as exc:
            raise BusinessException(code=400, message=str(exc), status_code=400) from exc
        if normalized_status not in AlertService.VALID_ALERT_STATUSES:
            raise BusinessException(code=400, message="非法告警状态", status_code=400)

        handler_id = None
        if "handler_id" in payload:
            if isinstance(payload["handler_id"], bool):
                raise BusinessException(code=400, message="handler_id 必须为正整数", status_code=400)
            try:
                handler_id = int(payload["handler_id"])
            except (ValueError, TypeError):
                raise BusinessException(code=400, message="handler_id 必须为正整数", status_code=400)
            if handler_id <= 0:
                raise BusinessException(code=400, message="handler_id 必须为正整数", status_code=400)

        handle_note = None
        if "handle_note" in payload:
            handle_note = payload["handle_note"]
            if not isinstance(handle_note, str):
                raise BusinessException(code=400, message="handle_note 必须为字符串", status_code=400)

        handle_time = None
        if normalized_status in {"processing", "resolved"}:
            handle_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record = AlertRepository.update_alert_status(
            alert_id=alert_id,
            alert_status=normalized_status,
            handler_id=handler_id,
            handle_note=handle_note,
            handle_time=handle_time,
        )
        if not record:
            raise BusinessException(code=404, message=f"未找到告警ID为 {alert_id} 的告警记录", status_code=404)

        return AlertSchema.dump_detail(record)
