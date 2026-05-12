from typing import Any, Dict

class AuthSchema:
    """
    身份认证序列化层 (Schema/DTO)
    控制对外返回的用户字段，避免泄露密码等内部字段
    """

    @staticmethod
    def dump_user(user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"],
            "display_name": user["display_name"]
        }

    @staticmethod
    def dump_login_result(user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "token": user["token"],
            "user": AuthSchema.dump_user(user)
        }
