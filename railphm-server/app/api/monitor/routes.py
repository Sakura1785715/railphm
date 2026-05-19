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
    device_code = request.args.get('device_code')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    limit = request.args.get('limit')
    condition_label = request.args.get('condition_label')

    data = MonitorService.get_historical_series(
        device_value=device_id,
        device_code=device_code,
        start_str=start_time,
        end_str=end_time,
        limit_value=limit,
        condition_label=condition_label,
    )

    return success_response(data=data)


@monitor_bp.route('/history', methods=['GET'])
def get_monitor_history():
    """
    获取 InfluxDB 历史监测数据
    """
    data = MonitorService.get_historical_series(
        device_value=request.args.get('device_id'),
        device_code=request.args.get('device_code'),
        start_str=request.args.get('start_time'),
        end_str=request.args.get('end_time'),
        limit_value=request.args.get('limit'),
        condition_label=request.args.get('condition_label'),
    )

    return success_response(data=data)
