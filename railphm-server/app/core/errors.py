# 实现全局异常处理
from werkzeug.exceptions import HTTPException
from app.core.response import error_response

class BusinessException(Exception):
    """通用业务异常类"""
    def __init__(self, code=400, message="business error", data=None):
        super().__init__()
        self.code = code
        self.message = message
        self.data = data

def handle_business_exception(e):
    # 捕获主动抛出的业务异常
    return error_response(code=e.code, message=e.message, data=e.data, status_code=400)

def handle_404_error(e):
    # 捕获 404 路由不存在的情况
    return error_response(code=404, message="not found", status_code=404)

def handle_500_error(e):
    # 捕获内部服务器 500 错误
    return error_response(code=500, message="internal server error", status_code=500)

def handle_generic_exception(e):
    # 兜底捕获未预料到的其他运行时 Exception
    if isinstance(e, HTTPException):
        return error_response(code=e.code, message=e.name.lower(), status_code=e.code)
    return error_response(code=500, message="internal server error", status_code=500)

def register_error_handlers(app):
    """
    注册全局异常处理器（使用最稳妥的显式注册方式）
    """
    app.register_error_handler(BusinessException, handle_business_exception)
    app.register_error_handler(404, handle_404_error)
    app.register_error_handler(500, handle_500_error)
    app.register_error_handler(Exception, handle_generic_exception)
