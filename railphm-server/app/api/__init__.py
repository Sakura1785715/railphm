from flask import Flask
from app.api.health import health_bp
from app.api.system import system_bp

def register_blueprints(app: Flask) -> None:
    """
    统一在app/__init__.py中注册 API 蓝图
    """
    # 注册健康检查模块，指定前缀
    app.register_blueprint(health_bp, url_prefix='/api/v1/health')
    app.register_blueprint(system_bp, url_prefix='/api/v1/system')