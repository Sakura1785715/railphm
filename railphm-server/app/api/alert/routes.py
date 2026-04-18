from flask import Blueprint, request
from app.core.response import success_response
from app.service.alert_service import AlertService

alert_bp = Blueprint('alert', __name__)

@alert_bp.route('', methods=['GET'])
def get_alerts():
    """获取告警列表（带分页与筛选）"""
    page = request.args.get('page', 1)
    size = request.args.get('size', 10)
    alert_status = request.args.get('alert_status')
    alert_level = request.args.get('alert_level')
    device_id = request.args.get('device_id')
    
    data = AlertService.get_alert_list(page, size, alert_status, alert_level, device_id)
    return success_response(data=data)

@alert_bp.route('/<int:alert_id>', methods=['GET'])
def get_alert_detail(alert_id):
    """获取单条告警详情"""
    data = AlertService.get_alert_detail(alert_id)
    return success_response(data=data)