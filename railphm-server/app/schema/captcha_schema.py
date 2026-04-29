from typing import Dict


class CaptchaSchema:
    """图片验证码响应 DTO。"""

    @staticmethod
    def dump(
        captcha_id: str,
        captcha_image: str,
        captcha_code: str = "",
        include_code: bool = False,
    ) -> Dict[str, str]:
        data = {
            "captcha_id": captcha_id,
            "captcha_image": captcha_image
        }

        if include_code:
            data["captcha_code"] = captcha_code

        return data
