from flask import Blueprint, request
from app.core.response import success_response
from app.service.monitor_service import MonitorService

monitor_bp = Blueprint('monitor', __name__)

@monitor_bp.route('/series', methods=['GET'])
def get_monitor_series():
    """
    获取历史监测数据曲线
    """
    device_id = request.args.get('device_id')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')

    data = MonitorService.get_historical_series(device_id, start_time, end_time)
    
    return success_response(data=data)