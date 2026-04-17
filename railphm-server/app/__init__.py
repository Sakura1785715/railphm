from flask import Flask
from .core.config import get_config
from app.core.response import success_response
from app.core.errors import BusinessException
from app.core import register_error_handlers
from app.api import register_blueprints

def create_app(config_name="default") -> Flask:
    """
    Flask Application Factory
    创建并返回一个基础的 Flask 应用实例
    """
    app = Flask(__name__)

    # 加载配置
    config_obj = get_config()
    app.config.from_object(config_obj)

    # 注册蓝图
    register_blueprints(app)
    register_error_handlers(app)

    # 临时测试接口
    @app.route('/__probe/business-error')
    def probe_business_error():
        raise BusinessException(code=4001, message="demo business error")

    @app.route('/__probe/runtime-error')
    def probe_runtime_error():
        raise Exception("This is a simulated runtime error")


    # TODO: 后续任务 - 在此处初始化第三方扩展 (Extensions, 例如 SQLAlchemy, Marshmallow 等)


    return app
