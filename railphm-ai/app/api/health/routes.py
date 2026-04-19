from flask import Blueprint

from app.core.response import success_response

health_bp = Blueprint("health", __name__)


@health_bp.route("", methods=["GET"])
def health_check():
    """最小健康检查接口。"""
    data = {
        "service": "railphm-ai",
        "status": "running",
        "version": "0.1.0",
    }
    return success_response(data=data)
