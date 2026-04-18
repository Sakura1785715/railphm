from flask import Blueprint, request
from app.core.response import success_response
from app.service.prediction_service import PredictionService

prediction_bp = Blueprint('prediction', __name__)

@prediction_bp.route('/latest', methods=['GET'])
def get_latest():
    """获取最新一次风险分析结果"""
    device_id = request.args.get('device_id')
    data = PredictionService.get_latest_prediction(device_id)
    return success_response(data=data)

@prediction_bp.route('/history', methods=['GET'])
def get_history():
    """获取历史风险结果序列"""
    device_id = request.args.get('device_id')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    
    data = PredictionService.get_prediction_history(device_id, start_time, end_time)
    return success_response(data=data)