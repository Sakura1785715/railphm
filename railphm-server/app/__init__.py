from flask import Flask
from .core.config import get_config
from app.core.response import success_response
from app.core.errors import BusinessException
from app.core import register_error_handlers
from app.api import register_blueprints
from app.core.logging import init_logging
from app.extensions import init_extensions

def create_app(config_name="default") -> Flask:
    """
    Flask Application Factory
    创建并返回一个基础的 Flask 应用实例
    """
    app = Flask(__name__)

    # 加载配置
    config_obj = get_config()
    app.config.from_object(config_obj)

    # 初始化日志，以便后续过程可以使用规范的 logger
    init_logging(app)
    app.logger.info(f"App starting with environment: {app.config.get('APP_ENV', 'development')}")

    # 初始化第三方扩展 (Extensions)
    init_extensions(app)

    # 注册蓝图与全局异常
    register_blueprints(app)
    register_error_handlers(app)
    app.logger.info("Blueprints and error handlers registered.")

    # 临时测试接口
    @app.route('/__probe/business-error')
    def probe_business_error():
        raise BusinessException(code=4001, message="demo business error")

    @app.route('/__probe/runtime-error')
    def probe_runtime_error():
        raise Exception("This is a simulated runtime error")


    app.logger.info("Flask application initialized successfully.")
    return app
