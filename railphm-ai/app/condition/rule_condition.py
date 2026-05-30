"""物理规则锚定的三类固定工况判断。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class RuleConditionResult:
    condition_id: int | None
    condition_label: str | None
    confidence: float
    reason: str
    stats: dict[str, Any]
    is_high_confidence: bool


class RuleConditionClassifier:
    """基于原始尺度窗口判断出站加速、高速巡航、进站减速。"""

    ACCEL_LABEL = "出站加速"
    CRUISE_LABEL = "高速巡航"
    DECEL_LABEL = "进站减速"
    FIXED_LABELS = (ACCEL_LABEL, CRUISE_LABEL, DECEL_LABEL)

    SPEED_ALIASES = ("速度", "speed")
    BRAKE_ALIASES = ("制动信息", "brake_info", "brake")
    SERVICE_BRAKE_ALIASES = ("常用制动速度", "service_brake_speed")
    EMERGENCY_BRAKE_ALIASES = ("紧急制动速度", "emergency_brake_speed")

    def __init__(
        self,
        condition_label_mapping: dict[int, str] | None = None,
        *,
        high_confidence_threshold: float = 0.75,
    ) -> None:
        self.condition_label_mapping = dict(condition_label_mapping or {})
        self.high_confidence_threshold = float(high_confidence_threshold)

    def classify(
        self,
        raw_window: np.ndarray,
        feature_columns: list[str],
        *,
        kmeans_condition_id: int | None = None,
        kmeans_condition_label: str | None = None,
    ) -> RuleConditionResult:
        stats = self._build_stats(raw_window, feature_columns)
        if not stats:
            return self._result(
                label=None,
                confidence=0.0,
                reason="missing_or_invalid_raw_window",
                stats={},
                kmeans_condition_id=kmeans_condition_id,
                kmeans_condition_label=kmeans_condition_label,
            )

        cruise_guard = self._classify_cruise_anomaly(stats)
        if cruise_guard is not None:
            return self._result(
                label=self.CRUISE_LABEL,
                confidence=cruise_guard[0],
                reason=cruise_guard[1],
                stats=stats,
                kmeans_condition_id=kmeans_condition_id,
                kmeans_condition_label=kmeans_condition_label,
            )

        decel = self._classify_deceleration(stats)
        if decel is not None:
            return self._result(
                label=self.DECEL_LABEL,
                confidence=decel[0],
                reason=decel[1],
                stats=stats,
                kmeans_condition_id=kmeans_condition_id,
                kmeans_condition_label=kmeans_condition_label,
            )

        accel = self._classify_acceleration(stats)
        if accel is not None:
            return self._result(
                label=self.ACCEL_LABEL,
                confidence=accel[0],
                reason=accel[1],
                stats=stats,
                kmeans_condition_id=kmeans_condition_id,
                kmeans_condition_label=kmeans_condition_label,
            )

        cruise = self._classify_steady_cruise(stats)
        if cruise is not None:
            return self._result(
                label=self.CRUISE_LABEL,
                confidence=cruise[0],
                reason=cruise[1],
                stats=stats,
                kmeans_condition_id=kmeans_condition_id,
                kmeans_condition_label=kmeans_condition_label,
            )

        return self._result(
            label=None,
            confidence=0.0,
            reason="rule_uncertain",
            stats=stats,
            kmeans_condition_id=kmeans_condition_id,
            kmeans_condition_label=kmeans_condition_label,
        )

    def _build_stats(self, raw_window: np.ndarray, feature_columns: list[str]) -> dict[str, Any]:
        if not isinstance(raw_window, np.ndarray) or raw_window.ndim != 2:
            return {}
        if not isinstance(feature_columns, list) or len(feature_columns) != raw_window.shape[1]:
            return {}
        if raw_window.shape[0] == 0 or not np.isfinite(raw_window).all():
            return {}

        speed_index = self._find_column(feature_columns, self.SPEED_ALIASES)
        if speed_index is None:
            return {}

        speed = raw_window[:, speed_index].astype(np.float32, copy=False)
        n = int(speed.shape[0])
        first, middle, last = self._third_arrays(speed)
        speed_diff = np.diff(speed) if n >= 2 else np.asarray([], dtype=np.float32)
        clipped_diff = self._clip_diff(speed_diff)
        abs_diff = np.abs(speed_diff) if speed_diff.size else np.asarray([], dtype=np.float32)

        brake_index = self._find_column(feature_columns, self.BRAKE_ALIASES)
        if brake_index is None:
            brake = np.zeros(n, dtype=np.float32)
        else:
            brake = raw_window[:, brake_index].astype(np.float32, copy=False)
        service_index = self._find_column(feature_columns, self.SERVICE_BRAKE_ALIASES)
        emergency_index = self._find_column(feature_columns, self.EMERGENCY_BRAKE_ALIASES)
        service_margin = None
        emergency_margin = None
        if service_index is not None:
            service_margin = raw_window[:, service_index].astype(np.float32, copy=False) - speed
        if emergency_index is not None:
            emergency_margin = raw_window[:, emergency_index].astype(np.float32, copy=False) - speed

        delta_last_30 = self._tail_delta(speed, 30)
        delta_last_60 = self._tail_delta(speed, 60)
        delta_whole = float(speed[-1] - speed[0]) if n >= 2 else 0.0
        speed_delta_robust = float(np.median(last) - np.median(first))
        early_delta = float(np.median(middle) - np.median(first))
        recent_delta = float(np.median(last) - np.median(middle))
        clipped_mean = float(np.mean(clipped_diff)) if clipped_diff.size else 0.0

        positive_ratio = float(np.mean(clipped_diff > 0.05)) if clipped_diff.size else 0.0
        negative_ratio = float(np.mean(clipped_diff < -0.05)) if clipped_diff.size else 0.0
        speed_diff_abs_p95 = float(np.percentile(abs_diff, 95)) if abs_diff.size else 0.0

        return {
            "window_size": n,
            "speed_mean": float(np.mean(speed)),
            "speed_median": float(np.median(speed)),
            "speed_start_median": float(np.median(first)),
            "speed_middle_median": float(np.median(middle)),
            "speed_end_median": float(np.median(last)),
            "speed_delta": delta_whole,
            "speed_delta_robust": speed_delta_robust,
            "early_delta": early_delta,
            "recent_delta": recent_delta,
            "delta_last_30": delta_last_30,
            "delta_last_60": delta_last_60,
            "speed_diff_clipped_mean": clipped_mean,
            "speed_diff_clipped_std": float(np.std(clipped_diff)) if clipped_diff.size else 0.0,
            "positive_diff_ratio": positive_ratio,
            "negative_diff_ratio": negative_ratio,
            "speed_volatility": float(np.percentile(speed, 95) - np.percentile(speed, 5)),
            "large_jump_count": int(np.sum(abs_diff > 20.0)) if abs_diff.size else 0,
            "freeze_ratio": float(np.mean(abs_diff <= 0.05)) if abs_diff.size else 0.0,
            "speed_diff_abs_p95": speed_diff_abs_p95,
            "brake_mean": float(np.mean(brake)),
            "brake_max": float(np.max(brake)) if brake.size else 0.0,
            "brake_active_ratio": float(np.mean(brake > 0)) if brake.size else 0.0,
            "service_margin_min": float(np.min(service_margin)) if service_margin is not None else 0.0,
            "emergency_margin_min": float(np.min(emergency_margin)) if emergency_margin is not None else 0.0,
        }

    def _classify_cruise_anomaly(self, stats: dict[str, Any]) -> tuple[float, str] | None:
        high_speed = stats["speed_median"] >= 240.0
        anomaly_present = (
            stats["large_jump_count"] >= 1
            or stats["freeze_ratio"] >= 0.20
            or stats["speed_diff_abs_p95"] >= 12.0
        )
        net_trend_bounded = (
            abs(stats["speed_delta_robust"]) <= 15.0
            and abs(stats["speed_diff_clipped_mean"]) <= 2.2
        )
        if high_speed and anomaly_present and net_trend_bounded:
            return 0.88, "high_speed_cruise_anomaly_guard"
        if high_speed and abs(stats["speed_delta_robust"]) <= 15.0 and abs(stats["speed_diff_clipped_mean"]) <= 1.0:
            return 0.84, "high_speed_bounded_trend_guard"
        return None

    def _classify_deceleration(self, stats: dict[str, Any]) -> tuple[float, str] | None:
        brake_active = stats["brake_active_ratio"]
        strong_negative_trend = (
            stats["speed_delta_robust"] <= -22.0
            or stats["delta_last_30"] <= -20.0
            or stats["delta_last_60"] <= -30.0
            or stats["early_delta"] <= -18.0
        )
        sustained_negative = (
            stats["negative_diff_ratio"] >= 0.55
            and stats["speed_diff_clipped_mean"] <= -0.6
        )
        brake_insufficient_guard = (
            brake_active >= 0.25
            and stats["speed_median"] >= 160.0
            and stats["speed_median"] < 240.0
            and stats["speed_delta_robust"] <= 12.0
        )
        if strong_negative_trend and (sustained_negative or brake_active >= 0.10):
            return 0.90, "negative_speed_trend_with_brake_context"
        if strong_negative_trend and stats["speed_delta_robust"] <= -35.0:
            return 0.86, "strong_negative_speed_trend"
        if brake_insufficient_guard:
            return 0.84, "brake_active_deceleration_guard"
        return None

    def _classify_acceleration(self, stats: dict[str, Any]) -> tuple[float, str] | None:
        low_brake = stats["brake_active_ratio"] < 0.30
        positive_trend = (
            stats["speed_delta_robust"] >= 22.0
            or stats["delta_last_30"] >= 20.0
            or stats["delta_last_60"] >= 30.0
        )
        sustained_positive = (
            stats["positive_diff_ratio"] >= 0.55
            and stats["speed_diff_clipped_mean"] >= 0.6
        )
        not_high_stable_cruise = (
            stats["speed_median"] < 240.0
            or stats["speed_delta_robust"] >= 35.0
        )
        departure_response_guard = (
            stats["speed_median"] < 180.0
            and stats["speed_delta_robust"] >= -10.0
            and stats["service_margin_min"] > 0.0
            and (
                stats["large_jump_count"] >= 3
                or stats["speed_diff_abs_p95"] >= 15.0
            )
        )
        if positive_trend and sustained_positive and low_brake and not_high_stable_cruise:
            return 0.90, "positive_speed_trend_low_brake"
        if stats["speed_delta_robust"] >= 35.0 and low_brake:
            return 0.82, "strong_positive_speed_trend"
        if departure_response_guard:
            return 0.82, "low_mid_speed_departure_response_guard"
        return None

    def _classify_steady_cruise(self, stats: dict[str, Any]) -> tuple[float, str] | None:
        high_speed = stats["speed_median"] >= 160.0
        trend_near_zero = (
            abs(stats["speed_delta_robust"]) <= 22.0
            and abs(stats["speed_diff_clipped_mean"]) <= 1.0
        )
        low_or_mid_brake = stats["brake_active_ratio"] < 0.30
        if high_speed and trend_near_zero and low_or_mid_brake:
            return 0.86, "high_speed_near_zero_trend"
        if stats["speed_median"] >= 220.0 and abs(stats["speed_delta_robust"]) <= 40.0:
            return 0.78, "high_speed_bounded_trend"
        return None

    def _result(
        self,
        *,
        label: str | None,
        confidence: float,
        reason: str,
        stats: dict[str, Any],
        kmeans_condition_id: int | None,
        kmeans_condition_label: str | None,
    ) -> RuleConditionResult:
        if label is not None and label not in self.FIXED_LABELS:
            label = None
            confidence = 0.0
            reason = "invalid_rule_label"

        condition_id = self._condition_id_for_label(
            label=label,
            kmeans_condition_id=kmeans_condition_id,
            kmeans_condition_label=kmeans_condition_label,
        )
        is_high_confidence = (
            label is not None
            and condition_id is not None
            and confidence >= self.high_confidence_threshold
        )
        return RuleConditionResult(
            condition_id=condition_id,
            condition_label=label,
            confidence=float(confidence),
            reason=reason,
            stats=stats,
            is_high_confidence=bool(is_high_confidence),
        )

    def _condition_id_for_label(
        self,
        *,
        label: str | None,
        kmeans_condition_id: int | None,
        kmeans_condition_label: str | None,
    ) -> int | None:
        if label is None:
            return None
        for condition_id, mapped_label in self.condition_label_mapping.items():
            if mapped_label == label:
                return int(condition_id)
        if kmeans_condition_label == label and kmeans_condition_id is not None:
            return int(kmeans_condition_id)
        return None

    @staticmethod
    def _find_column(feature_columns: list[str], aliases: tuple[str, ...]) -> int | None:
        for alias in aliases:
            if alias in feature_columns:
                return feature_columns.index(alias)
        lowered = {column.lower(): index for index, column in enumerate(feature_columns)}
        for alias in aliases:
            index = lowered.get(alias.lower())
            if index is not None:
                return index
        return None

    @staticmethod
    def _third_arrays(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = int(values.shape[0])
        third = max(1, n // 3)
        first = values[:third]
        middle = values[third : n - third]
        if middle.size == 0:
            middle = values[:]
        last = values[n - third :]
        return first, middle, last

    @staticmethod
    def _tail_delta(values: np.ndarray, tail_size: int) -> float:
        if values.shape[0] < 2:
            return 0.0
        tail = values[-min(int(tail_size), int(values.shape[0])) :]
        return float(tail[-1] - tail[0]) if tail.shape[0] >= 2 else 0.0

    @staticmethod
    def _clip_diff(diff: np.ndarray) -> np.ndarray:
        if diff.size == 0:
            return diff.astype(np.float32, copy=False)
        lower = np.percentile(diff, 5)
        upper = np.percentile(diff, 95)
        return np.clip(diff, lower, upper).astype(np.float32, copy=False)
