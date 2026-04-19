from werkzeug.exceptions import HTTPException

from app.core.response import error_response


class BusinessException(Exception):
    """通用业务异常。"""

    def __init__(
        self,
        code: int = 400,
        message: str = "business error",
        data=None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
        self.status_code = status_code


def handle_business_exception(error: BusinessException):
    return error_response(
        code=error.code,
        message=error.message,
        data=error.data,
        status_code=error.status_code,
    )


def handle_404_error(error):
    return error_response(code=404, message="not found", status_code=404)

def handle_405_error(e):
    return error_response(code=405, message="method not allowed", status_code=405)

def handle_500_error(error):
    return error_response(code=500, message="internal server error", status_code=500)


def handle_generic_exception(error):
    if isinstance(error, HTTPException):
        return error_response(
            code=error.code,
            message=error.description if error.description else error.name.lower(),
            status_code=error.code,
        )
    return error_response(code=500, message="internal server error", status_code=500)


def register_error_handlers(app):
    """注册全局异常处理器。"""
    app.register_error_handler(BusinessException, handle_business_exception)
    app.register_error_handler(404, handle_404_error)
    app.register_error_handler(405, handle_405_error)
    app.register_error_handler(500, handle_500_error)
    app.register_error_handler(Exception, handle_generic_exception)
