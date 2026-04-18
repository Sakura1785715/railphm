# 实现日志记录统一配置
import logging
from flask import Flask

def init_logging(app: Flask) -> None:
    """
    统一日志初始化配置
    :param app: Flask 应用实例
    """
    # 1. 获取配置项中的日志级别，默认 INFO
    log_level_name = app.config.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    
    # 2. 避免 Flask 在 Debug/Reload 模式下重复添加 Handler 导致日志打印多次
    if app.logger.hasHandlers():
        app.logger.handlers.clear()

    # 3. 设置日志输出格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(module)s:%(lineno)d] %(message)s'
    )

    # 4. 创建并配置控制台 Handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    
    # 5. 将配置应用到 Flask 内置的 logger 上
    app.logger.setLevel(log_level)
    app.logger.addHandler(stream_handler)
    
    # 关闭日志向上冒泡，防止被外层默认配置的 root logger 再次打印
    app.logger.propagate = False

    app.logger.info(f"Logging initialized successfully with level: {log_level_name}")