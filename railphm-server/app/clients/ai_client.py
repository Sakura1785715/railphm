import logging
from typing import Any, Dict

import requests
from flask import current_app, has_app_context

from app.core.errors import BusinessException


class AIClient:
    """
    railphm-server 访问独立 railphm-ai 服务的唯一入口。
    当前阶段调用的是 mock inference service，后续接入真实模型时优先替换这里。
    """

    REQUIRED_FIELDS = (
        "device_id",
        "ts_end",
        "window_minutes",
        "window_start_time",
        "window_end_time",
        "condition_label",
        "risk_score",
        "risk_std",
        "model_version",
    )
    # health_score / alert_level 即使由 AI 返回，也不会作为最终业务解释结果直接对外透传。
    # 本阶段优先保持规则稳定落在 server 侧，后续接入真实模型或概率校准时仅替换风险分数来源。

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        config = current_app.config if has_app_context() else {}
        self.base_url = (base_url or config.get("AI_SERVICE_BASE_URL", "http://127.0.0.1:5001")).rstrip("/")
        self.timeout = timeout or config.get("AI_SERVICE_TIMEOUT", 3)
        self.logger = current_app.logger if has_app_context() else logging.getLogger(__name__)

    def infer(self, device_id: int, ts_end: str, window_minutes: int) -> Dict[str, Any]:
        payload = {
            "device_id": device_id,
            "ts_end": ts_end,
            "window_minutes": window_minutes,
        }
        url = f"{self.base_url}/infer"

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.Timeout:
            self.logger.warning("AI infer request timed out", extra={"url": url, "payload": payload})
            raise BusinessException(code=504, message="AI 推理服务请求超时", status_code=504)
        except requests.ConnectionError:
            self.logger.warning("AI infer service unavailable", extra={"url": url, "payload": payload})
            raise BusinessException(code=502, message="AI 推理服务不可用", status_code=502)
        except requests.RequestException:
            self.logger.exception("AI infer request failed", extra={"url": url, "payload": payload})
            raise BusinessException(code=502, message="AI 推理服务返回异常状态", status_code=502)

        if response.status_code != 200:
            self.logger.warning(
                "AI infer response status error",
                extra={"url": url, "status_code": response.status_code, "payload": payload},
            )
            raise BusinessException(code=502, message="AI 推理服务返回异常状态", status_code=502)

        try:
            response_body = response.json()
        except ValueError:
            self.logger.warning("AI infer response is not valid JSON", extra={"url": url, "payload": payload})
            raise BusinessException(code=502, message="AI 推理服务返回数据格式非法", status_code=502)

        if not isinstance(response_body, dict):
            self.logger.warning("AI infer response JSON is not an object", extra={"url": url, "payload": payload})
            raise BusinessException(code=502, message="AI 推理服务返回数据格式非法", status_code=502)

        if response_body.get("code") != 200:
            self.logger.warning(
                "AI infer response business code error",
                extra={"url": url, "payload": payload, "response_body": response_body},
            )
            raise BusinessException(code=502, message="AI 推理服务返回异常状态", status_code=502)

        data = response_body.get("data")
        if not isinstance(data, dict):
            self.logger.warning(
                "AI infer response data is invalid",
                extra={"url": url, "payload": payload, "response_body": response_body},
            )
            raise BusinessException(code=502, message="AI 推理服务返回数据格式非法", status_code=502)

        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing_fields:
            self.logger.warning(
                "AI infer response missing required fields",
                extra={"url": url, "payload": payload, "missing_fields": missing_fields},
            )
            raise BusinessException(code=502, message="AI 推理服务返回缺少必要字段", status_code=502)

        return data
