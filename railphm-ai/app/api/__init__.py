from flask import Flask

from app.api.health import health_bp
from app.api.infer import infer_bp


def register_blueprints(app: Flask) -> None:
    """统一注册 API 蓝图。"""
    app.register_blueprint(health_bp, url_prefix="/health")
    app.register_blueprint(infer_bp, url_prefix="/infer")
