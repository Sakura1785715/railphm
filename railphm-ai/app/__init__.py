from flask import Flask

from app.api import register_blueprints
from app.core import register_error_handlers
from app.core.config import get_config
from app.core.logging import init_logging


def create_app(config_name: str = "default") -> Flask:
    """
    Flask application factory.
    当前仅保留 AI mock 服务启动所需的最小初始化逻辑。
    """
    app = Flask(__name__)
    app.json.ensure_ascii = False

    config_obj = get_config(config_name)
    app.config.from_object(config_obj)

    print("AI_MODEL_DIR =", app.config.get("AI_MODEL_DIR"))
    print("AI_DATASET_DIR =", app.config.get("AI_DATASET_DIR"))
    print("AI_ENABLE_MOCK_FALLBACK =", app.config.get("AI_ENABLE_MOCK_FALLBACK"))

    init_logging(app)
    register_blueprints(app)
    register_error_handlers(app)

    app.logger.info(
        "railphm-ai initialized with env=%s",
        app.config.get("APP_ENV", "development"),
    )
    return app
