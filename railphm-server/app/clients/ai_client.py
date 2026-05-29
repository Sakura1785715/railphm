import logging
from typing import Any, Dict
from urllib.parse import urljoin

import requests
from flask import current_app, has_app_context

from app.core.errors import BusinessException


class AIServiceError(BusinessException):
    """AI 推理服务调用失败的基础异常。"""

    def __init__(self, message: str = "AI 推理服务调用失败", code: int = 502, status_code: int = 502):
        super().__init__(code=code, message=message, status_code=status_code)


class AIServiceUnavailableError(AIServiceError):
    """AI 服务不可用、连接失败或超时。"""

    def __init__(self, message: str = "AI 推理服务不可用", code: int = 502, status_code: int = 502):
        super().__init__(message=message, code=code, status_code=status_code)


class AIResponseFormatError(AIServiceError):
    """AI 服务返回结构不符合 server 侧推理接入规范。"""

    def __init__(self, message: str = "AI 推理服务返回数据格式非法"):
        super().__init__(message=message, code=502, status_code=502)


class AIClient:
    """
    railphm-server 访问独立 railphm-ai 服务的唯一入口。
    本阶段只负责 HTTP 调用、响应壳解析和关键字段校验。
    """

    REQUIRED_FIELDS = ("risk_score",)
    NORMAL_SUCCESS_CODES = {0, 200}

    def __init__(
        self,
        base_url: str | None = None,
        infer_path: str | None = None,
        range_infer_path: str | None = None,
        timeout: int | float | None = None,
        range_timeout: int | float | None = None,
    ):
        config = current_app.config if has_app_context() else {}
        self.base_url = (base_url or config.get("AI_SERVICE_BASE_URL", "http://127.0.0.1:5001")).rstrip("/")
        self.infer_path = infer_path or config.get("AI_INFER_PATH", "/infer")
        self.range_infer_path = range_infer_path or config.get("AI_RANGE_INFER_PATH", "/infer/range")
        self.timeout = timeout or config.get(
            "AI_REQUEST_TIMEOUT_SECONDS",
            config.get("AI_SERVICE_TIMEOUT", 5),
        )
        self.range_timeout = range_timeout or config.get(
            "AI_RANGE_REQUEST_TIMEOUT_SECONDS",
            self.timeout,
        )
        self.logger = current_app.logger if has_app_context() else logging.getLogger(__name__)

    @property
    def infer_url(self) -> str:
        return urljoin(f"{self.base_url}/", self.infer_path.lstrip("/"))

    @property
    def range_infer_url(self) -> str:
        return urljoin(f"{self.base_url}/", self.range_infer_path.lstrip("/"))

    @staticmethod
    def _extract_error_message(response: requests.Response, fallback: str) -> str:
        try:
            response_body = response.json()
        except ValueError:
            return fallback

        if not isinstance(response_body, dict):
            return fallback

        message = response_body.get("message")
        return message if isinstance(message, str) and message.strip() else fallback

    def infer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise AIResponseFormatError("AI 推理请求参数格式非法")

        url = self.infer_url

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.Timeout:
            self.logger.warning(
                "AI infer request timed out",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIServiceUnavailableError(
                code=504,
                message="AI 推理服务请求超时",
                status_code=504,
            )
        except requests.ConnectionError:
            self.logger.warning(
                "AI infer service unavailable",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIServiceUnavailableError()
        except requests.RequestException:
            self.logger.exception(
                "AI infer request failed",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIServiceError("AI 推理服务返回异常状态")

        if response.status_code < 200 or response.status_code >= 300:
            self.logger.warning(
                "AI infer response status error",
                extra={
                    "url": url,
                    "status_code": response.status_code,
                    "payload_keys": list(payload.keys()),
                },
            )
            raise AIServiceError("AI 推理服务返回异常状态")

        try:
            response_body = response.json()
        except ValueError:
            self.logger.warning(
                "AI infer response is not valid JSON",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIResponseFormatError()

        if not isinstance(response_body, dict):
            self.logger.warning(
                "AI infer response JSON is not an object",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIResponseFormatError()

        if response_body.get("success") is False:
            self.logger.warning(
                "AI infer response success=false",
                extra={"url": url, "response_code": response_body.get("code")},
            )
            raise AIServiceError("AI 推理服务返回失败状态")

        response_code = response_body.get("code")
        if response_code is not None and response_code not in self.NORMAL_SUCCESS_CODES:
            self.logger.warning(
                "AI infer response business code error",
                extra={"url": url, "response_code": response_code},
            )
            raise AIServiceError("AI 推理服务返回异常状态")

        data = self._extract_data(response_body)
        self._validate_required_fields(data, url=url, payload=payload)
        return data

    def infer_range(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise AIResponseFormatError("AI 区间推理请求参数格式非法")

        url = self.range_infer_url

        try:
            response = requests.post(url, json=payload, timeout=self.range_timeout)
        except requests.Timeout:
            self.logger.warning(
                "AI range infer request timed out",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIServiceUnavailableError(
                code=504,
                message="AI 区间推理服务请求超时",
                status_code=504,
            )
        except requests.ConnectionError:
            self.logger.warning(
                "AI range infer service unavailable",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIServiceUnavailableError("AI 区间推理服务不可用")
        except requests.RequestException:
            self.logger.exception(
                "AI range infer request failed",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIServiceError("AI 区间推理服务返回异常状态")

        if response.status_code < 200 or response.status_code >= 300:
            error_message = self._extract_error_message(response, "AI range infer response status error")
            self.logger.warning(
                error_message,
                extra={
                    "url": url,
                    "status_code": response.status_code,
                    "payload_keys": list(payload.keys()),
                },
            )
            raise AIServiceError(error_message)

        try:
            response_body = response.json()
        except ValueError:
            self.logger.warning(
                "AI range infer response is not valid JSON",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIResponseFormatError()

        if not isinstance(response_body, dict):
            self.logger.warning(
                "AI range infer response JSON is not an object",
                extra={"url": url, "payload_keys": list(payload.keys())},
            )
            raise AIResponseFormatError()

        if response_body.get("success") is False:
            self.logger.warning(
                "AI range infer response success=false",
                extra={"url": url, "response_code": response_body.get("code")},
            )
            raise AIServiceError("AI 区间推理服务返回失败状态")

        response_code = response_body.get("code")
        if response_code is not None and response_code not in self.NORMAL_SUCCESS_CODES:
            self.logger.warning(
                "AI range infer response business code error",
                extra={"url": url, "response_code": response_code},
            )
            raise AIServiceError("AI 区间推理服务返回异常状态")

        data = self._extract_data(response_body)
        if not isinstance(data.get("results"), list):
            self.logger.warning(
                "AI range infer response results is invalid",
                extra={"url": url},
            )
            raise AIResponseFormatError("AI 区间推理服务返回缺少 results 列表")
        return data

    def _extract_data(self, response_body: Dict[str, Any]) -> Dict[str, Any]:
        if "data" not in response_body:
            return response_body

        data = response_body.get("data")
        if not isinstance(data, dict):
            self.logger.warning(
                "AI infer response data is invalid",
                extra={"response_body": response_body},
            )
            raise AIResponseFormatError()

        return data

    def _validate_required_fields(
        self,
        data: Dict[str, Any],
        *,
        url: str,
        payload: Dict[str, Any],
    ) -> None:
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing_fields:
            self.logger.warning(
                "AI infer response missing required fields",
                extra={"url": url, "missing_fields": missing_fields},
            )
            raise AIResponseFormatError(
                f"AI 推理服务返回缺少必要字段: {', '.join(missing_fields)}"
            )
