# 实现统一响应处理
from flask import jsonify
from typing import Any, Optional, Tuple

def success_response(data: Optional[Any] = None, message: str = "success", code: int = 200) -> Tuple[Any, int]:
    """
    统一成功响应结构封装
    :param data: 返回的具体业务数据
    :param message: 成功提示信息
    :param code: HTTP 状态码 / 业务状态码
    :return: Flask 可接受的响应元组 (json_response, status_code)
    """
    response_body = {
        "code": code,
        "message": message,
        "data": data
    }
    return jsonify(response_body), code

def error_response(
    message: str = "error",
    code: int = 400,
    data: Optional[Any] = None,
    status_code: Optional[int] = None,
) -> Tuple[Any, int]:
    """
    统一错误响应结构封装
    :param message: 错误提示信息
    :param code: 业务错误码或默认返回码
    :param data: 补充的错误详情或数据
    :param status_code: HTTP 状态码，未传时默认与 code 保持一致
    :return: Flask 可接受的响应元组 (json_response, status_code)
    """
    response_body = {
        "code": code,
        "message": message,
        "data": data
    }
    return jsonify(response_body), status_code or code
