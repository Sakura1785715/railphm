from datetime import datetime
from typing import Any, Dict, Optional


class CaptchaRepository:
    """
    图片验证码内存仓储。
    当前阶段不接 Redis / 数据库，后续生产部署可替换为 Redis 实现。
    """

    _captcha_store: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def save(cls, captcha_id: str, code: str, expire_at: datetime) -> None:
        cls._captcha_store[captcha_id] = {
            "code": code,
            "expire_at": expire_at
        }

    @classmethod
    def get(cls, captcha_id: str) -> Optional[Dict[str, Any]]:
        return cls._captcha_store.get(captcha_id)

    @classmethod
    def delete(cls, captcha_id: str) -> None:
        cls._captcha_store.pop(captcha_id, None)

    @classmethod
    def cleanup_expired(cls, now: datetime) -> None:
        expired_ids = [
            captcha_id
            for captcha_id, captcha in cls._captcha_store.items()
            if captcha["expire_at"] <= now
        ]
        for captcha_id in expired_ids:
            cls.delete(captcha_id)
