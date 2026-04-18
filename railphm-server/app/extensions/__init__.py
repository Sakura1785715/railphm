# 扩展组件初始化统一入口（当前仅作占位）
from flask import Flask

def init_mysql(app: Flask) -> None:
    """MySQL 初始化占位"""
    mysql_url = app.config.get("MYSQL_URL")
    if not mysql_url:
        app.logger.warning("MYSQL_URL not configured. MySQL initialization skipped (Placeholder).")
    else:
        app.logger.info("MYSQL_URL detected. MySQL connection placeholder ready.")
    
    # 将客户端挂载到 Flask 标准 extensions 字典中（目前为 None）
    app.extensions["mysql_client"] = None

def init_influxdb(app: Flask) -> None:
    """InfluxDB 初始化占位"""
    influx_url = app.config.get("INFLUXDB_URL")
    if not influx_url:
        app.logger.warning("INFLUXDB_URL not configured. InfluxDB initialization skipped (Placeholder).")
    else:
        app.logger.info("INFLUXDB_URL detected. InfluxDB connection placeholder ready.")
    
    # 将客户端挂载到 Flask 标准 extensions 字典中（目前为 None）
    app.extensions["influxdb_client"] = None

def init_extensions(app: Flask) -> None:
    """
    统一扩展初始化入口
    后续任务接入真实数据库或其他三方件时，直接在此处拓展
    """
    # 确保 extensions 字典存在
    if not hasattr(app, "extensions"):
        app.extensions = {}
        
    # 执行各组件占位初始化
    init_mysql(app)
    init_influxdb(app)
    
    app.logger.info("Extensions placeholders initialization completed.")