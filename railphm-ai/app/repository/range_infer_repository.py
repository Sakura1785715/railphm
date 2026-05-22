from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np

from flask import current_app

from app.core.errors import BusinessException
from app.dataset.feature_processor import FeatureProcessor
from app.repository.infer_repository import InferRepository
from app.runtime.monitor_feature_adapter import MonitorFeatureAdapter
from app.runtime.online_scaler import OnlineScalerLoader


class RangeInferRepository:
    """基于 monitor_rows 的在线区间推理访问层。"""

    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def infer_range(cls, payload: dict[str, Any]) -> dict[str, Any]:
        runtime = InferRepository._get_runtime()
        scaler = OnlineScalerLoader.load_for_runtime(runtime)

        monitor_rows = cls._normalize_monitor_rows(payload["monitor_rows"])
        candidate_times = cls._build_candidate_times(
            start_dt=payload["start_dt"],
            end_dt=payload["end_dt"],
            stride_seconds=payload["inference_stride_seconds"],
        )

        adapter = MonitorFeatureAdapter()
        feature_processor = FeatureProcessor(feature_columns=runtime.feature_columns)
        results: list[dict[str, Any]] = []
        skipped_windows: list[dict[str, Any]] = []

        for prediction_dt in candidate_times:
            window_rows = cls._select_window_rows(
                monitor_rows=monitor_rows,
                prediction_dt=prediction_dt,
                window_size=runtime.window_size,
            )

            if len(window_rows) < runtime.window_size:
                skipped_windows.append(
                    cls._build_skip_record(
                        prediction_dt=prediction_dt,
                        reason="insufficient_monitor_points",
                        raw_window_points=len(window_rows),
                        required_window_size=runtime.window_size,
                    )
                )
                continue

            continuity_error = cls._validate_window_continuity(window_rows, prediction_dt)
            if continuity_error is not None:
                skipped_windows.append(
                    cls._build_skip_record(
                        prediction_dt=prediction_dt,
                        reason=continuity_error["reason"],
                        raw_window_points=len(window_rows),
                        required_window_size=runtime.window_size,
                        detail=continuity_error,
                    )
                )
                continue

            feature_df = adapter.to_feature_dataframe(window_rows)
            feature_result = feature_processor.transform(feature_df)
            feature_matrix = feature_result.feature_matrix

            if feature_matrix.shape != (runtime.window_size, runtime.feature_dim):
                raise BusinessException(
                    code=500,
                    message=(
                        "在线窗口特征矩阵 shape 与模型运行时不一致: "
                        f"actual={feature_matrix.shape}, "
                        f"expected={(runtime.window_size, runtime.feature_dim)}"
                    ),
                    status_code=500,
                )

            window = scaler.transform(feature_matrix)
            if not np.isfinite(window).all():
                raise BusinessException(code=500, message="在线窗口标准化后存在非法数值", status_code=500)

            prediction = runtime.predict_with_uncertainty(
                window,
                mc_samples=payload["mc_samples"],
            )

            first_sample_dt = window_rows[0]["_sample_dt"]
            last_sample_dt = window_rows[-1]["_sample_dt"]
            window_end_dt = prediction_dt if last_sample_dt == prediction_dt else last_sample_dt

            trace = {
                "source": "monitor_rows",
                "runtime_window_size": runtime.window_size,
                "runtime_feature_dim": runtime.feature_dim,
                "inference_stride_seconds": payload["inference_stride_seconds"],
                "raw_window_points": len(window_rows),
                "window_selection_method": "latest_n_points_before_prediction_time",
                "feature_adapter": "monitor_rows_to_feature_processor",
                "missing_feature_columns": feature_result.missing_feature_columns,
                "all_nan_feature_columns": feature_result.all_nan_feature_columns,
                "condition_label_method": "last_non_empty_condition_label_in_window",
                **scaler.trace(),
            }

            results.append(
                {
                    "time": cls._format_datetime(prediction_dt),
                    "window_start_time": cls._format_datetime(first_sample_dt),
                    "window_end_time": cls._format_datetime(window_end_dt),
                    "risk_raw": prediction["risk_raw"],
                    "risk_score": prediction["risk_score"],
                    "risk_raw_std": prediction["risk_raw_std"],
                    "risk_std": prediction["risk_std"],
                    "threshold": prediction["threshold"],
                    "predicted_label": prediction["predicted_label"],
                    "model_name": prediction["model_name"],
                    "model_version": prediction["model_version"],
                    "calibration_enabled": prediction["calibration_enabled"],
                    "calibration_method": prediction.get("calibration_method"),
                    "uncertainty_enabled": prediction.get("uncertainty_enabled", False),
                    "uncertainty_method": prediction.get("uncertainty_method"),
                    "mc_samples": prediction["mc_samples"],
                    "condition_label": cls._pick_condition_label(window_rows),
                    "data_source": "influxdb_online_range",
                    "trace": trace,
                }
            )

        return {
            "device_id": payload["device_id"],
            "device_code": payload["device_code"],
            "start_time": payload["start_time"],
            "end_time": payload["end_time"],
            "inference_stride_seconds": payload["inference_stride_seconds"],
            "monitor_point_count": len(monitor_rows),
            "total_candidate_points": payload["total_candidate_points"],
            "result_count": len(results),
            "skipped_window_count": len(skipped_windows),
            "model_name": runtime.model_name,
            "model_version": runtime.model_version,
            "calibration_enabled": runtime.calibration_enabled,
            "calibration_method": runtime.calibration_method,
            "uncertainty_enabled": runtime.uncertainty_enabled,
            "uncertainty_method": runtime.uncertainty_method,
            "results": results,
            "skipped_windows": skipped_windows,
        }

    @classmethod
    def _normalize_monitor_rows(cls, monitor_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_rows: list[dict[str, Any]] = []

        for index, row in enumerate(monitor_rows):
            sample_time = row.get("sample_time")
            if not isinstance(sample_time, str) or not sample_time.strip():
                raise BusinessException(
                    code=400,
                    message=f"monitor_rows[{index}].sample_time 不能为空",
                    status_code=400,
                )

            try:
                sample_dt = datetime.strptime(sample_time.strip(), cls.DATETIME_FORMAT)
            except ValueError as exc:
                raise BusinessException(
                    code=400,
                    message=(
                        f"monitor_rows[{index}].sample_time 必须使用 "
                        "YYYY-MM-DD HH:mm:ss 格式"
                    ),
                    status_code=400,
                ) from exc

            normalized_rows.append({**row, "_sample_dt": sample_dt})

        normalized_rows.sort(key=lambda item: item["_sample_dt"])
        return normalized_rows

    @staticmethod
    def _build_candidate_times(
        *,
        start_dt: datetime,
        end_dt: datetime,
        stride_seconds: int,
    ) -> list[datetime]:
        candidate_times: list[datetime] = []
        current_dt = start_dt
        step = timedelta(seconds=stride_seconds)
        while current_dt <= end_dt:
            candidate_times.append(current_dt)
            current_dt += step
        return candidate_times

    @staticmethod
    def _select_window_rows(
        *,
        monitor_rows: list[dict[str, Any]],
        prediction_dt: datetime,
        window_size: int,
    ) -> list[dict[str, Any]]:
        eligible_rows = [row for row in monitor_rows if row["_sample_dt"] <= prediction_dt]
        return eligible_rows[-window_size:]

    @classmethod
    def _validate_window_continuity(
        cls,
        window_rows: list[dict[str, Any]],
        prediction_dt: datetime,
    ) -> dict[str, Any] | None:
        if not current_app.config.get("AI_REQUIRE_CONTINUOUS_WINDOW", True):
            return None

        max_gap_seconds = int(current_app.config.get("AI_MAX_SAMPLE_GAP_SECONDS", 2))
        sample_times = [row["_sample_dt"] for row in window_rows]

        for previous_dt, current_dt in zip(sample_times, sample_times[1:]):
            gap_seconds = (current_dt - previous_dt).total_seconds()
            if gap_seconds > max_gap_seconds:
                return {
                    "reason": "sample_gap_exceeds_limit",
                    "max_allowed_gap_seconds": max_gap_seconds,
                    "actual_gap_seconds": gap_seconds,
                    "gap_start_time": cls._format_datetime(previous_dt),
                    "gap_end_time": cls._format_datetime(current_dt),
                }

        tail_gap_seconds = (prediction_dt - sample_times[-1]).total_seconds()
        if tail_gap_seconds > max_gap_seconds:
            return {
                "reason": "prediction_time_gap_exceeds_limit",
                "max_allowed_gap_seconds": max_gap_seconds,
                "actual_gap_seconds": tail_gap_seconds,
                "last_sample_time": cls._format_datetime(sample_times[-1]),
                "prediction_time": cls._format_datetime(prediction_dt),
            }

        return None

    @classmethod
    def _build_skip_record(
        cls,
        *,
        prediction_dt: datetime,
        reason: str,
        raw_window_points: int,
        required_window_size: int,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "time": cls._format_datetime(prediction_dt),
            "reason": reason,
            "raw_window_points": raw_window_points,
            "required_window_size": required_window_size,
            "detail": detail or {},
        }

    @staticmethod
    def _pick_condition_label(window_rows: list[dict[str, Any]]) -> Any:
        for row in reversed(window_rows):
            condition_label = row.get("condition_label")
            if condition_label is not None and str(condition_label).strip():
                return condition_label
        return None

    @classmethod
    def _format_datetime(cls, value: datetime) -> str:
        return value.strftime(cls.DATETIME_FORMAT)
