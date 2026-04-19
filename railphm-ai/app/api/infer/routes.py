from flask import Blueprint, request
from app.core.response import success_response
from app.service.infer_service import InferService
from app.core.errors import BusinessException

infer_bp = Blueprint("infer", __name__)


@infer_bp.route("", methods=["POST"])
def infer():
    """最小 mock 推理接口。"""

    payload = request.get_json(silent=True)
    if payload is None:
        raise BusinessException(code=400, message="请求格式非法或为空，必须为 JSON")
        
    data = InferService.infer(payload)
    return success_response(data=data)
