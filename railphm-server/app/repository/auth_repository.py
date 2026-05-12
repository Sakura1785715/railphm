from typing import Any, Dict, Optional

class AuthRepository:
    """
    身份认证数据访问层 (Repository)
    当前阶段使用 Mock 用户，后续可替换为数据库查询
    """

    _mock_users = [
        {
            "user_id": 1,
            "username": "ops",
            "password": "123456",
            "role": "OPS",
            "display_name": "运维用户",
            "token": "mock-token-ops"
        },
        {
            "user_id": 2,
            "username": "admin",
            "password": "123456",
            "role": "ADMIN",
            "display_name": "系统管理员",
            "token": "mock-token-admin"
        }
    ]

    @classmethod
    def find_by_username(cls, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名查找用户"""
        for user in cls._mock_users:
            if user["username"] == username:
                return user
        return None

    @classmethod
    def find_by_token(cls, token: str) -> Optional[Dict[str, Any]]:
        """根据 token 查找用户"""
        for user in cls._mock_users:
            if user["token"] == token:
                return user
        return None
