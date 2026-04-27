from functools import wraps

from flask import g, request

from app.core.errors import BusinessException
from app.repository.auth_repository import AuthRepository


AUTH_ERROR_MESSAGE = "未登录或登录状态无效"
FORBIDDEN_ERROR_MESSAGE = "权限不足"


def _raise_auth_error():
    raise BusinessException(code=401, message=AUTH_ERROR_MESSAGE, status_code=401)


def parse_bearer_token(auth_header: str) -> str:
    """从 Authorization 请求头中解析 Bearer token。"""
    if not auth_header or not isinstance(auth_header, str):
        _raise_auth_error()

    normalized_header = auth_header.strip()
    prefix = "Bearer "

    if not normalized_header.startswith(prefix):
        _raise_auth_error()

    token = normalized_header[len(prefix):].strip()
    if not token:
        _raise_auth_error()

    return token


def get_current_user():
    """基于 mock token 获取当前用户内部字典。"""
    token = parse_bearer_token(request.headers.get("Authorization", ""))
    user = AuthRepository.find_by_token(token)

    if not user:
        _raise_auth_error()

    return user


def require_login(view_func):
    """要求接口必须携带有效登录态。"""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        g.current_user = get_current_user()
        return view_func(*args, **kwargs)

    return wrapper


def require_roles(*roles):
    """要求当前用户具备任一指定角色。"""
    allowed_roles = set(roles)

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            g.current_user = user

            if user.get("role") not in allowed_roles:
                raise BusinessException(
                    code=403,
                    message=FORBIDDEN_ERROR_MESSAGE,
                    status_code=403
                )

            return view_func(*args, **kwargs)

        return wrapper

    return decorator
