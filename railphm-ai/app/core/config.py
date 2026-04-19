import os
from typing import Any


class BaseConfig:
    """基础配置。"""

    APP_NAME: str = "railphm-ai"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", "5001"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "railphm-ai-dev-secret")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MODEL_VERSION: str = os.getenv("MODEL_VERSION", "mock-bilstm-attention-v1")
    TESTING: bool = False


class TestingConfig(BaseConfig):
    TESTING = True


def get_config(config_name: str = "default") -> Any:
    """配置工厂。"""
    config_map = {
        "default": BaseConfig,
        "testing": TestingConfig,
    }
    return config_map.get(config_name, BaseConfig)
