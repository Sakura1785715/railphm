from flask import Flask
from app.api.health import health_bp
from app.api.system import system_bp
from app.api.device import device_bp
from app.api.monitor import monitor_bp
from app.api.prediction import prediction_bp
from app.api.alert import alert_bp

def register_blueprints(app: Flask) -> None:
    """
    统一在app/__init__.py中注册 API 蓝图
    """
    # 注册蓝图
    app.register_blueprint(health_bp, url_prefix='/api/v1/health')
    app.register_blueprint(system_bp, url_prefix='/api/v1/system')
    app.register_blueprint(device_bp, url_prefix='/api/v1/devices')
    app.register_blueprint(monitor_bp, url_prefix='/api/v1/monitor')
    app.register_blueprint(prediction_bp, url_prefix='/api/v1/predictions')
    app.register_blueprint(alert_bp, url_prefix='/api/v1/alerts')