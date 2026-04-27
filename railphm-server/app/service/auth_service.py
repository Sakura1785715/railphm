from typing import Any, Dict, Optional
from app.core.errors import BusinessException
from app.repository.auth_repository import AuthRepository
from app.schema.auth_schema import AuthSchema

class AuthService:
    """
    身份认证业务层 (Service)
    负责登录校验、token 解析和用户 DTO 转换
    """

    INVALID_LOGIN_MESSAGE = "用户名或密码错误"
    INVALID_AUTH_MESSAGE = "未登录或登录状态无效"

    @staticmethod
    def login(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not payload or not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体不能为空", status_code=400)

        username = payload.get("username")
        password = payload.get("password")

        if not isinstance(username, str) or not username.strip():
            raise BusinessException(code=400, message="username 不能为空", status_code=400)

        if not isinstance(password, str) or not password.strip():
            raise BusinessException(code=400, message="password 不能为空", status_code=400)

        user = AuthRepository.find_by_username(username.strip())
        if not user or user["password"] != password:
            raise BusinessException(code=401, message=AuthService.INVALID_LOGIN_MESSAGE, status_code=401)

        return AuthSchema.dump_login_result(user)

    @staticmethod
    def get_current_user_from_header(auth_header: str) -> Dict[str, Any]:
        if not auth_header:
            raise BusinessException(code=401, message=AuthService.INVALID_AUTH_MESSAGE, status_code=401)

        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
            raise BusinessException(code=401, message=AuthService.INVALID_AUTH_MESSAGE, status_code=401)

        user = AuthRepository.find_by_token(parts[1])
        if not user:
            raise BusinessException(code=401, message=AuthService.INVALID_AUTH_MESSAGE, status_code=401)

        return AuthSchema.dump_user(user)

    @staticmethod
    def logout() -> Dict[str, bool]:
        return {"logged_out": True}
