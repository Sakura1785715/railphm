from flask import Blueprint, request
from app.core.response import success_response
from app.service.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    payload = request.get_json(silent=True)
    data = AuthService.login(payload)
    return success_response(data=data)

@auth_bp.route('/me', methods=['GET'])
def me():
    """获取当前登录用户"""
    auth_header = request.headers.get('Authorization', '')
    data = AuthService.get_current_user_from_header(auth_header)
    return success_response(data=data)

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """退出登录"""
    data = AuthService.logout()
    return success_response(data=data)
