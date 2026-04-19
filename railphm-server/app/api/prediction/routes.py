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


@prediction_bp.route('/infer', methods=['POST'])
def infer_prediction():
    """
    触发一次即时推理。
    当前通过独立 railphm-ai mock 服务打通链路，后续真实模型接入优先替换 AIClient。
    当前阶段健康度与告警级别属于 server 侧业务解释规则，不直接信任 AI 原始返回。
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    data = PredictionService.infer_prediction(
        payload.get('device_id'),
        payload.get('ts_end'),
        payload.get('window_minutes'),
    )
    return success_response(data=data)
