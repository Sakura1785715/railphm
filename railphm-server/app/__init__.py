from flask import Flask
from .core.config import get_config

def create_app() -> Flask:
    """
    Flask Application Factory
    创建并返回一个基础的 Flask 应用实例
    """
    app = Flask(__name__)

    # 加载配置
    config_obj = get_config()
    app.config.from_object(config_obj)

    # TODO: 后续任务 - 在此处初始化第三方扩展 (Extensions, 例如 SQLAlchemy, Marshmallow 等)

    # TODO: 后续任务 - 在此处注册路由蓝图 (Blueprints)

    # TODO: 后续任务 - 在此处注册全局异常处理器 (Error Handlers)

    return app