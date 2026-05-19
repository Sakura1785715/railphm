from flask import Blueprint

from app.core.response import success_response
from app.service.dashboard_service import DashboardService


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/overview", methods=["GET"])
def get_dashboard_overview():
    """获取首页 Dashboard 聚合数据。"""
    data = DashboardService.get_overview()
    return success_response(data=data)
