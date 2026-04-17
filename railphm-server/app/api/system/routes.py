# 实现系统管理相关接口
from flask import Blueprint
from app.core.response import success_response

system_bp = Blueprint('system', __name__)

@system_bp.route('', methods=['GET'])
def ping():
    return success_response(data={"system-ping" : "system-pong"})