# 实现健康检查相关接口
from flask import Blueprint
from app.core.response import success_response

# 定义健康检查蓝图
health_bp = Blueprint('health', __name__)

@health_bp.route('', methods=['GET'])
def health_check():
    """
    标准健康检查接口
    响应路径: GET /api/v1/health
    """
    data = {
        "service": "railphm-server",
        "status": "running",
        "version": "0.1.0"
    }
    return success_response(data=data)