from flask import current_app
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from app.core.errors import BusinessException


def get_client() -> InfluxDBClient:
    """获取复用的 InfluxDB client。"""
    client = current_app.extensions.get("influxdb_client")
    if client is not None:
        return client

    url = current_app.config.get("INFLUXDB_URL")
    token = current_app.config.get("INFLUXDB_TOKEN")
    org = current_app.config.get("INFLUXDB_ORG")
    timeout = current_app.config.get("INFLUXDB_TIMEOUT", 10000)

    if not url:
        raise BusinessException(code=500, message="INFLUXDB_URL 未配置", status_code=500)
    if not token:
        raise BusinessException(code=500, message="INFLUXDB_TOKEN 未配置", status_code=500)
    if not org:
        raise BusinessException(code=500, message="INFLUXDB_ORG 未配置", status_code=500)

    client = InfluxDBClient(url=url, token=token, org=org, timeout=timeout)
    current_app.extensions["influxdb_client"] = client
    return client


def get_query_api():
    """获取 InfluxDB 查询 API。"""
    return get_client().query_api()


def get_write_api():
    """获取同步写入 API，供离线导入流程复用。"""
    return get_client().write_api(write_options=SYNCHRONOUS)
