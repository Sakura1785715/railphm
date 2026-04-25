import os
from typing import Any


class BaseConfig:
    """基础配置。"""

    APP_NAME: str = "railphm-server"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", "5000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "railphm-dev-secret")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    MYSQL_URL: str = os.getenv("MYSQL_URL", "")
    INFLUXDB_URL: str = os.getenv("INFLUXDB_URL", "")

    AI_SERVICE_BASE_URL: str = os.getenv("AI_SERVICE_BASE_URL", "http://127.0.0.1:5001")
    AI_SERVICE_TIMEOUT: int = int(os.getenv("AI_SERVICE_TIMEOUT", "3"))

    TESTING: bool = False


class TestingConfig(BaseConfig):
    TESTING = True


def get_config(config_name: str = "default") -> Any:
    """配置工厂。"""
    config_map = {
        "default": BaseConfig,
        "development": BaseConfig,
        "testing": TestingConfig,
    }
    return config_map.get(config_name, BaseConfig)
