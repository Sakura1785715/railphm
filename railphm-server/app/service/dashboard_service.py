from typing import Any, Dict, List

from app.repository.dashboard_repository import DashboardRepository
from app.schema.dashboard_schema import DashboardSchema


class DashboardService:
    """Dashboard 聚合业务层。"""

    @staticmethod
    def get_overview() -> Dict[str, Any]:
        device_status_cards = DashboardRepository.get_device_status_overview()
        kpi = DashboardService._build_kpi(device_status_cards)
        health_distribution = DashboardService._build_health_distribution(device_status_cards)
        latest_alerts = DashboardRepository.get_latest_alerts(limit=5)
        key_devices = DashboardService._build_key_devices(device_status_cards, limit=5)

        return DashboardSchema.dump_overview(
            {
                "kpi": kpi,
                "device_status_cards": device_status_cards,
                "risk_trend": [],
                "health_distribution": health_distribution,
                "latest_alerts": latest_alerts,
                "key_devices": key_devices,
            }
        )

    @staticmethod
    def _build_kpi(device_status_cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "device_total": len(device_status_cards),
            "normal_device_count": sum(1 for item in device_status_cards if item.get("current_status") == 1),
            "attention_device_count": sum(1 for item in device_status_cards if item.get("current_status") == 2),
            "warning_device_count": sum(1 for item in device_status_cards if item.get("current_status") in (3, 4)),
            "warning_only_device_count": sum(1 for item in device_status_cards if item.get("current_status") == 3),
            "critical_device_count": sum(1 for item in device_status_cards if item.get("current_status") == 4),
            "unhandled_alert_count": sum(
                DashboardService._to_int(item.get("active_alert_count"))
                for item in device_status_cards
            ),
        }

    @staticmethod
    def _build_health_distribution(device_status_cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for item in device_status_cards:
            current_status = DashboardService._to_int(item.get("current_status"))
            if current_status in counts:
                counts[current_status] += 1

        return [
            {"level": "normal", "label": "正常", "status": 1, "count": counts[1]},
            {"level": "attention", "label": "关注", "status": 2, "count": counts[2]},
            {"level": "warning", "label": "预警", "status": 3, "count": counts[3]},
            {"level": "critical", "label": "告警", "status": 4, "count": counts[4]},
        ]

    @staticmethod
    def _build_key_devices(device_status_cards: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        return sorted(
            device_status_cards,
            key=DashboardService._key_device_sort_key,
            reverse=True,
        )[:limit]

    @staticmethod
    def _key_device_sort_key(item: Dict[str, Any]) -> tuple:
        return (
            DashboardService._to_int(item.get("current_status")),
            1 if DashboardService._to_int(item.get("active_alert_count")) > 0 else 0,
            DashboardService._to_float(item.get("risk_score")),
            DashboardService._sort_time(item.get("latest_prediction_time") or item.get("updated_at")),
        )

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _sort_time(value: Any) -> str:
        return str(value or "")
