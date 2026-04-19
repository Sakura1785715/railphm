import logging

from flask import Flask


def init_logging(app: Flask) -> None:
    """初始化基础日志配置。"""
    log_level_name = app.config.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    if app.logger.hasHandlers():
        app.logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(module)s:%(lineno)d] %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    app.logger.setLevel(log_level)
    app.logger.addHandler(handler)
    app.logger.propagate = False
