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
    MODEL_VERSION: str = os.getenv("MODEL_VERSION", "mock-bilstm-attention-v1")
    AI_MODEL_DIR: str = os.getenv(
        "RAILPHM_AI_MODEL_DIR",
        "outputs/sequence_models/bilstm_attention_h1_full_features",
    )
    AI_DATASET_DIR: str = os.getenv(
        "RAILPHM_AI_DATASET_DIR",
        "data/datasets/bilstm_attention_h1_full_features/train_scaled_condition_k3",
    )
    AI_RUNTIME_DEVICE: str = os.getenv("RAILPHM_AI_RUNTIME_DEVICE", "auto")
    AI_DEFAULT_MC_SAMPLES: int = int(os.getenv("RAILPHM_AI_DEFAULT_MC_SAMPLES", "30"))
    AI_MAX_MC_SAMPLES: int = int(os.getenv("RAILPHM_AI_MAX_MC_SAMPLES", "1000"))
    AI_ENABLE_MOCK_FALLBACK: bool = _env_bool("RAILPHM_AI_ENABLE_MOCK_FALLBACK", True)
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
