import pymysql
from flask import current_app


def get_connection():
    """创建 MySQL 连接。

    调用方负责在使用后关闭连接；涉及写操作时应显式 commit 或 rollback。
    """
    return pymysql.connect(
        host=current_app.config["MYSQL_HOST"],
        port=current_app.config["MYSQL_PORT"],
        user=current_app.config["MYSQL_USER"],
        password=current_app.config["MYSQL_PASSWORD"],
        database=current_app.config["MYSQL_DATABASE"],
        charset=current_app.config.get("MYSQL_CHARSET", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
