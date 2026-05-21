import math
from typing import Any, Dict, List, Optional


class HealthCurveService:
    """基于已落库预测结果构建展示层风险/健康度曲线。"""

    DEFAULT_ALPHA = 0.3
    CURVE_TYPE = "ema_from_persisted_prediction_results"
    CARRY_FIELDS = (
        "risk_result_id",
        "device_id",
        "device_code",
        "time",
        "window_start_time",
        "window_end_time",
        "ts_end",
        "created_at",
        "risk_std",
        "threshold",
        "predicted_label",
        "health_level",
        "health_status",
        "health_description",
        "condition_label",
        "model_version",
    )

    @classmethod
    def build_curve(
        cls,
        records: List[Dict[str, Any]],
        *,
        device_id: Any,
        start_time: str,
        end_time: str,
        alpha: float = DEFAULT_ALPHA,
    ) -> Dict[str, Any]:
        normalized_items = []
        skipped_count = 0

        for record in records or []:
            time_value = cls._get_point_time(record)
            risk_score = cls._parse_risk_score(record.get("risk_score"))

            if time_value is None or risk_score is None:
                skipped_count += 1
                continue

            normalized_items.append(
                {
                    **cls._pick_fields(record),
                    "time": time_value,
                    "risk_score_raw": round(cls._clip_risk_score(risk_score), 6),
                }
            )

        normalized_items.sort(key=lambda item: item["time"])

        items = []
        previous_smoothed_risk: Optional[float] = None
        for item in normalized_items:
            risk_score_raw = item["risk_score_raw"]
            if previous_smoothed_risk is None:
                risk_score_smoothed = risk_score_raw
            else:
                risk_score_smoothed = alpha * risk_score_raw + (1 - alpha) * previous_smoothed_risk
            previous_smoothed_risk = risk_score_smoothed

            rounded_smoothed_risk = round(risk_score_smoothed, 6)
            items.append(
                {
                    **item,
                    "risk_score_smoothed": rounded_smoothed_risk,
                    "health_score_raw": cls._to_health_score(risk_score_raw),
                    "health_score_smoothed": cls._to_health_score(rounded_smoothed_risk),
                }
            )

        return {
            "device_id": device_id,
            "start_time": start_time,
            "end_time": end_time,
            "alpha": alpha,
            "curve_type": cls.CURVE_TYPE,
            "point_count": len(items),
            "skipped_count": skipped_count,
            "items": items,
            "summary": cls._build_summary(items),
        }

    @classmethod
    def _build_summary(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not items:
            return {
                "empty": True,
                "message": "指定时间范围内暂无预测结果",
            }

        raw_risks = [item["risk_score_raw"] for item in items]
        smoothed_risks = [item["risk_score_smoothed"] for item in items]
        raw_health_scores = [item["health_score_raw"] for item in items]
        smoothed_health_scores = [item["health_score_smoothed"] for item in items]
        latest_item = items[-1]

        return {
            "latest_time": latest_item["time"],
            "latest_risk_score_raw": latest_item["risk_score_raw"],
            "latest_risk_score_smoothed": latest_item["risk_score_smoothed"],
            "latest_health_score_raw": latest_item["health_score_raw"],
            "latest_health_score_smoothed": latest_item["health_score_smoothed"],
            "max_risk_score_raw": max(raw_risks),
            "max_risk_score_smoothed": max(smoothed_risks),
            "min_health_score_raw": min(raw_health_scores),
            "min_health_score_smoothed": min(smoothed_health_scores),
            "avg_risk_score_raw": round(sum(raw_risks) / len(raw_risks), 6),
            "avg_risk_score_smoothed": round(sum(smoothed_risks) / len(smoothed_risks), 6),
            "abnormal_point_count": sum(1 for item in items if item.get("predicted_label") == 1),
            "empty": False,
            "message": None,
        }

    @classmethod
    def _pick_fields(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        return {field: record.get(field) for field in cls.CARRY_FIELDS if field != "time"}

    @staticmethod
    def _get_point_time(record: Dict[str, Any]) -> Optional[str]:
        return record.get("window_end_time") or record.get("ts_end") or record.get("created_at")

    @staticmethod
    def _parse_risk_score(value: Any) -> Optional[float]:
        if value is None or value == "" or isinstance(value, bool):
            return None
        try:
            risk_score = float(value)
        except (TypeError, ValueError):
            return None
        return risk_score if math.isfinite(risk_score) else None

    @staticmethod
    def _clip_risk_score(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _to_health_score(risk_score: float) -> float:
        return round(100 * (1 - risk_score), 2)
