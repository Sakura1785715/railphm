import base64
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

from app.core.errors import BusinessException
from app.repository.captcha_repository import CaptchaRepository
from app.schema.captcha_schema import CaptchaSchema


class CaptchaService:
    """图片验证码业务层。"""

    CAPTCHA_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    CAPTCHA_LENGTH = 4
    CAPTCHA_EXPIRE_MINUTES = 5
    IMAGE_WIDTH = 128
    IMAGE_HEIGHT = 48

    @staticmethod
    def generate_captcha(include_code: bool = False) -> Dict[str, str]:
        now = datetime.now(timezone.utc)
        CaptchaRepository.cleanup_expired(now)

        captcha_id = str(uuid.uuid4())
        code = CaptchaService._generate_code()
        captcha_image = CaptchaService._generate_image_data_url(code)
        expire_at = now + timedelta(minutes=CaptchaService.CAPTCHA_EXPIRE_MINUTES)

        CaptchaRepository.save(captcha_id, code, expire_at)

        return CaptchaSchema.dump(
            captcha_id=captcha_id,
            captcha_image=captcha_image,
            captcha_code=code,
            include_code=include_code,
        )

    @staticmethod
    def validate_captcha(captcha_id: str, captcha_code: str) -> None:
        if not isinstance(captcha_id, str) or not captcha_id.strip():
            raise BusinessException(code=400, message="captcha_id 不能为空", status_code=400)

        if not isinstance(captcha_code, str) or not captcha_code.strip():
            raise BusinessException(code=400, message="captcha_code 不能为空", status_code=400)

        now = datetime.now(timezone.utc)
        captcha = CaptchaRepository.get(captcha_id.strip())

        if not captcha:
            raise BusinessException(code=400, message="验证码不存在或已失效", status_code=400)

        if captcha["expire_at"] <= now:
            CaptchaRepository.delete(captcha_id.strip())
            raise BusinessException(code=400, message="验证码已过期，请重新获取", status_code=400)

        if captcha["code"].upper() != captcha_code.strip().upper():
            raise BusinessException(code=400, message="验证码错误", status_code=400)

        CaptchaRepository.delete(captcha_id.strip())

    @staticmethod
    def _generate_code() -> str:
        return "".join(
            secrets.choice(CaptchaService.CAPTCHA_CHARS)
            for _ in range(CaptchaService.CAPTCHA_LENGTH)
        )

    @staticmethod
    def _generate_image_data_url(code: str) -> str:
        image = Image.new(
            "RGB",
            (CaptchaService.IMAGE_WIDTH, CaptchaService.IMAGE_HEIGHT),
            color=(244, 248, 252),
        )
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        for _ in range(5):
            start = (
                secrets.randbelow(CaptchaService.IMAGE_WIDTH),
                secrets.randbelow(CaptchaService.IMAGE_HEIGHT),
            )
            end = (
                secrets.randbelow(CaptchaService.IMAGE_WIDTH),
                secrets.randbelow(CaptchaService.IMAGE_HEIGHT),
            )
            color = (
                120 + secrets.randbelow(80),
                140 + secrets.randbelow(70),
                160 + secrets.randbelow(60),
            )
            draw.line([start, end], fill=color, width=1)

        char_gap = CaptchaService.IMAGE_WIDTH // (CaptchaService.CAPTCHA_LENGTH + 1)
        for index, char in enumerate(code):
            x = 18 + index * char_gap + secrets.randbelow(6)
            y = 14 + secrets.randbelow(8)
            color = (
                20 + secrets.randbelow(50),
                55 + secrets.randbelow(80),
                105 + secrets.randbelow(80),
            )
            draw.text((x, y), char, font=font, fill=color)

        for _ in range(26):
            point = (
                secrets.randbelow(CaptchaService.IMAGE_WIDTH),
                secrets.randbelow(CaptchaService.IMAGE_HEIGHT),
            )
            color = (
                120 + secrets.randbelow(90),
                140 + secrets.randbelow(80),
                160 + secrets.randbelow(70),
            )
            draw.point(point, fill=color)

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
