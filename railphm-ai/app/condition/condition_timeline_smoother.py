from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.condition.rule_condition import RuleConditionClassifier


@dataclass(frozen=True)
class _ConditionSegment:
    label: str | None
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


class ConditionTimelineSmoother:
    """把逐点工况标签整理为稳定的主运行阶段时间轴。"""

    CRUISE_LABEL = RuleConditionClassifier.CRUISE_LABEL
    TRANSIENT_CRUISE_BREAK_LABELS = {
        RuleConditionClassifier.ACCEL_LABEL,
        RuleConditionClassifier.DECEL_LABEL,
    }

    def __init__(self, *, min_confirm_points: int = 5, min_segment_points: int = 5) -> None:
        self.min_confirm_points = max(1, int(min_confirm_points))
        self.min_segment_points = max(1, int(min_segment_points))

    def smooth(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not results:
            return results

        raw_labels = [self._extract_label(result) for result in results]
        absorbed_labels, absorbed_reasons = self._absorb_short_segments(raw_labels)
        smoothed_labels, confirm_reasons = self._apply_confirmed_transitions(absorbed_labels)

        smoothed_results: list[dict[str, Any]] = []
        config = {
            "min_confirm_points": self.min_confirm_points,
            "min_segment_points": self.min_segment_points,
        }

        for index, result in enumerate(results):
            if not isinstance(result, dict):
                smoothed_results.append(result)
                continue

            raw_label = raw_labels[index]
            smoothed_label = smoothed_labels[index]
            smooth_applied = raw_label != smoothed_label
            reason = self._pick_reason(
                raw_label=raw_label,
                absorbed_label=absorbed_labels[index],
                smoothed_label=smoothed_label,
                absorbed_reason=absorbed_reasons[index],
                confirm_reason=confirm_reasons[index],
            )

            trace = result.get("trace") if isinstance(result.get("trace"), dict) else {}
            smoothed_result = {
                **result,
                "condition_label": smoothed_label,
                "trace": {
                    **trace,
                    "raw_condition_label_before_smooth": raw_label,
                    "smoothed_condition_label": smoothed_label,
                    "condition_smooth_applied": smooth_applied,
                    "condition_smooth_reason": reason,
                    "condition_smooth_config": dict(config),
                },
            }
            smoothed_results.append(smoothed_result)

        return smoothed_results

    def _absorb_short_segments(
        self,
        labels: list[str | None],
    ) -> tuple[list[str | None], list[str]]:
        smoothed_labels = list(labels)
        reasons = ["unchanged"] * len(labels)
        segments = self._build_segments(labels)

        for index in range(1, len(segments) - 1):
            segment = segments[index]
            previous_segment = segments[index - 1]
            next_segment = segments[index + 1]
            if not self._is_valid_label(segment.label):
                continue
            if not self._is_valid_label(previous_segment.label) or previous_segment.label != next_segment.label:
                continue
            if segment.label == previous_segment.label or segment.length >= self.min_segment_points:
                continue

            reason = self._absorb_reason(previous_segment.label, segment.label)
            for point_index in range(segment.start, segment.end):
                smoothed_labels[point_index] = previous_segment.label
                reasons[point_index] = reason

        return smoothed_labels, reasons

    def _apply_confirmed_transitions(
        self,
        labels: list[str | None],
    ) -> tuple[list[str | None], list[str]]:
        smoothed_labels = list(labels)
        reasons = ["unchanged"] * len(labels)
        segments = self._build_segments(labels)
        current_label: str | None = None

        for index, segment in enumerate(segments):
            if not self._is_valid_label(segment.label):
                current_label = None
                continue

            if current_label is None:
                current_label = segment.label
                continue

            if segment.label == current_label:
                continue

            if segment.length >= self.min_confirm_points:
                current_label = segment.label
                for point_index in range(segment.start, segment.end):
                    reasons[point_index] = "confirmed_transition"
                continue

            next_label = self._next_valid_label(segments, index)
            if next_label is None:
                current_label = segment.label
                for point_index in range(segment.start, segment.end):
                    reasons[point_index] = "terminal_segment_preserved"
                continue

            reason = self._absorb_reason(current_label, segment.label)
            for point_index in range(segment.start, segment.end):
                smoothed_labels[point_index] = current_label
                reasons[point_index] = reason

        return smoothed_labels, reasons

    @staticmethod
    def _extract_label(result: Any) -> str | None:
        if not isinstance(result, dict):
            return None
        label = result.get("condition_label")
        if label is None:
            return None
        label_text = str(label).strip()
        return label_text or None

    @staticmethod
    def _is_valid_label(label: str | None) -> bool:
        return isinstance(label, str) and bool(label.strip())

    @staticmethod
    def _build_segments(labels: list[str | None]) -> list[_ConditionSegment]:
        if not labels:
            return []

        segments: list[_ConditionSegment] = []
        start = 0
        active_label = labels[0]

        for index, label in enumerate(labels[1:], start=1):
            if label == active_label:
                continue
            segments.append(_ConditionSegment(label=active_label, start=start, end=index))
            start = index
            active_label = label

        segments.append(_ConditionSegment(label=active_label, start=start, end=len(labels)))
        return segments

    def _next_valid_label(self, segments: list[_ConditionSegment], index: int) -> str | None:
        for segment in segments[index + 1 :]:
            if self._is_valid_label(segment.label):
                return segment.label
            return None
        return None

    def _absorb_reason(self, stable_label: str | None, transient_label: str | None) -> str:
        if (
            stable_label == self.CRUISE_LABEL
            and transient_label in self.TRANSIENT_CRUISE_BREAK_LABELS
        ):
            return "cruise_sandwich_guard"
        return "short_segment_absorbed"

    @staticmethod
    def _pick_reason(
        *,
        raw_label: str | None,
        absorbed_label: str | None,
        smoothed_label: str | None,
        absorbed_reason: str,
        confirm_reason: str,
    ) -> str:
        if raw_label != absorbed_label and absorbed_reason != "unchanged":
            return absorbed_reason
        if absorbed_label != smoothed_label and confirm_reason != "unchanged":
            return confirm_reason
        return confirm_reason if confirm_reason != "unchanged" else "unchanged"
