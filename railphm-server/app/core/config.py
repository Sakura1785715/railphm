# 实现配置管理逻辑
import os
from typing import Any


class BaseConfig:
    """
    基础配置类
    使用标准库 os.getenv 获取环境变量，如果获取不到，就使用提供的默认值
    """
    # 应用基础配置
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", 5000))
    
    # 安全配置 (Flask 会自动读取 SECRET_KEY)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "railphm-dev-secret")
    
    # 日志配置 (预留项，供后续任务使用)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # 数据库配置 (预留项，供后续任务使用)
    MYSQL_URL: str = os.getenv("MYSQL_URL", "")
    INFLUXDB_URL: str = os.getenv("INFLUXDB_URL", "")

    # 独立 AI mock 服务配置。
    # 默认端口 5001 需与 railphm-ai 的启动端口保持一致。
    AI_SERVICE_BASE_URL: str = os.getenv("AI_SERVICE_BASE_URL", "http://127.0.0.1:5001")
    AI_SERVICE_TIMEOUT: int = int(os.getenv("AI_SERVICE_TIMEOUT", 3))


def get_config() -> Any:
    """
    配置工厂函数
    目前返回 BaseConfig 实例，后续可根据 APP_ENV 返回不同的子类
    """
    return BaseConfig
