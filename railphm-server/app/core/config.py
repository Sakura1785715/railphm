import os
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional_int(name: str, default: int | None) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip().lower() in {"", "none", "null"}:
        return default
    return int(raw_value)


class BaseConfig:
    """基础配置。"""

    APP_NAME: str = "railphm-server"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", "5000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "railphm-dev-secret")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    MYSQL_URL: str = os.getenv("MYSQL_URL", "")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "mdgq04l08y11x")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "railphm")
    MYSQL_CHARSET: str = os.getenv("MYSQL_CHARSET", "utf8mb4")
    INFLUXDB_URL: str = os.getenv("INFLUXDB_URL", "")

    AI_SERVICE_BASE_URL: str = os.getenv("AI_SERVICE_BASE_URL", "http://127.0.0.1:5001")
    AI_INFER_PATH: str = os.getenv("AI_INFER_PATH", "/infer")
    AI_REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "5"))
    AI_ENABLE_FALLBACK: bool = os.getenv("AI_ENABLE_FALLBACK", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    AI_DEFAULT_THRESHOLD: float = float(os.getenv("AI_DEFAULT_THRESHOLD", "0.5"))
    RISK_THRESHOLD_NORMAL: float = float(os.getenv("RISK_THRESHOLD_NORMAL", "0.3"))
    RISK_THRESHOLD_WARNING: float = float(os.getenv("RISK_THRESHOLD_WARNING", "0.58"))
    RISK_THRESHOLD_CRITICAL: float = float(os.getenv("RISK_THRESHOLD_CRITICAL", "0.8"))
    HEALTH_SCORE_DECIMALS: int = int(os.getenv("HEALTH_SCORE_DECIMALS", "2"))

    REALTIME_STREAM_ID: str = os.getenv("REALTIME_STREAM_ID", "default")
    REALTIME_DEFAULT_DEVICE_ID: str = os.getenv("REALTIME_DEFAULT_DEVICE_ID", "ATP001")
    REALTIME_DEFAULT_START_SAMPLE_INDEX: int = int(
        os.getenv("REALTIME_DEFAULT_START_SAMPLE_INDEX", "0")
    )
    REALTIME_DEFAULT_END_SAMPLE_INDEX: int | None = _env_optional_int(
        "REALTIME_DEFAULT_END_SAMPLE_INDEX",
        None,
    )
    REALTIME_DEFAULT_STEP: int = int(os.getenv("REALTIME_DEFAULT_STEP", "1"))
    REALTIME_DEFAULT_WINDOW_MINUTES: int = int(
        os.getenv("REALTIME_DEFAULT_WINDOW_MINUTES", "30")
    )
    REALTIME_DEFAULT_MC_SAMPLES: int = int(os.getenv("REALTIME_DEFAULT_MC_SAMPLES", "20"))
    REALTIME_DEFAULT_AUTO_WRAP: bool = _env_bool("REALTIME_DEFAULT_AUTO_WRAP", False)
    REALTIME_DEFAULT_TS_START: str = os.getenv(
        "REALTIME_DEFAULT_TS_START",
        "2026-05-01 10:00:00",
    )
    REALTIME_TS_STEP_SECONDS: int = int(os.getenv("REALTIME_TS_STEP_SECONDS", "1"))
    # 兼容旧配置名，后续调用统一优先使用 AI_REQUEST_TIMEOUT_SECONDS。
    AI_SERVICE_TIMEOUT: float = float(
        os.getenv("AI_SERVICE_TIMEOUT", str(AI_REQUEST_TIMEOUT_SECONDS))
    )

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
