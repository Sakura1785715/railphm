from typing import Any, Optional, Tuple

from flask import jsonify


def success_response(
    data: Optional[Any] = None,
    message: str = "success",
    code: int = 200,
) -> Tuple[Any, int]:
    response_body = {
        "code": code,
        "message": message,
        "data": data,
    }
    return jsonify(response_body), code


def error_response(
    message: str = "error",
    code: int = 400,
    data: Optional[Any] = None,
    status_code: Optional[int] = None,
) -> Tuple[Any, int]:
    response_body = {
        "code": code,
        "message": message,
        "data": data,
    }
    return jsonify(response_body), status_code or code
