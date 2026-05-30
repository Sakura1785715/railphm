import os
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class BaseConfig:
    """基础配置。"""

    APP_NAME: str = "railphm-ai"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", "5001"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "railphm-ai-dev-secret")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MODEL_VERSION: str = os.getenv("MODEL_VERSION", "bilstm_attention_h1_synthetic_v3_rule_anchor")
    AI_MODEL_DIR: str = os.getenv(
        "RAILPHM_AI_MODEL_DIR",
        "outputs/sequence_models/bilstm_attention_h1_synthetic_v3_rule_anchor",
    )
    AI_DATASET_DIR: str = os.getenv(
        "RAILPHM_AI_DATASET_DIR",
        "data/datasets/bilstm_attention_h1_synthetic_v3/scaled_window_w30_s1_h1",
    )
    AI_RUNTIME_DEVICE: str = os.getenv("RAILPHM_AI_RUNTIME_DEVICE", "auto")
    AI_DEFAULT_MC_SAMPLES: int = int(os.getenv("RAILPHM_AI_DEFAULT_MC_SAMPLES", "30"))
    AI_MAX_MC_SAMPLES: int = int(os.getenv("RAILPHM_AI_MAX_MC_SAMPLES", "1000"))
    AI_ENABLE_MOCK_FALLBACK: bool = _env_bool("RAILPHM_AI_ENABLE_MOCK_FALLBACK", True)
    AI_DEFAULT_RANGE_INFERENCE_STRIDE_SECONDS: int = int(
        os.getenv("RAILPHM_AI_DEFAULT_RANGE_INFERENCE_STRIDE_SECONDS", "60")
    )
    AI_DEFAULT_RANGE_MC_SAMPLES: int = int(
        os.getenv("RAILPHM_AI_DEFAULT_RANGE_MC_SAMPLES", "20")
    )
    AI_MAX_RANGE_POINTS: int = int(os.getenv("RAILPHM_AI_MAX_RANGE_POINTS", "5000"))
    AI_MAX_MONITOR_ROWS: int = int(os.getenv("RAILPHM_AI_MAX_MONITOR_ROWS", "20000"))
    AI_REQUIRE_CONTINUOUS_WINDOW: bool = _env_bool("RAILPHM_AI_REQUIRE_CONTINUOUS_WINDOW", True)
    AI_MAX_SAMPLE_GAP_SECONDS: int = int(os.getenv("RAILPHM_AI_MAX_SAMPLE_GAP_SECONDS", "2"))
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
