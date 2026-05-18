from typing import Any, Dict

from app.repository.dashboard_repository import DashboardRepository
from app.schema.dashboard_schema import DashboardSchema


class DashboardService:
    """Dashboard 聚合业务层。"""

    @staticmethod
    def get_overview() -> Dict[str, Any]:
        kpi = DashboardRepository.get_kpi()
        risk_trend = DashboardRepository.get_risk_trend(limit=30)
        health_distribution = DashboardRepository.get_health_distribution()
        latest_alerts = DashboardRepository.get_latest_alerts(limit=5)
        key_devices = DashboardRepository.get_key_devices(limit=5)

        return DashboardSchema.dump_overview(
            {
                "kpi": kpi,
                "risk_trend": risk_trend,
                "health_distribution": health_distribution,
                "latest_alerts": latest_alerts,
                "key_devices": key_devices,
            }
        )
