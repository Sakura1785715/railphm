import pytest
from app import create_app

@pytest.fixture
def app():
    """
    创建并配置测试用的 Flask App 实例。
    得益于 Task 7 的软初始化，这里不会真实连接数据库。
    """
    app = create_app()
    # 开启 Flask 测试模式，能够向外抛出未处理的异常而不是仅仅返回 500
    app.config.update({
        "TESTING": True,
    })
    
    yield app

@pytest.fixture
def client(app):
    """
    提供统一的 Flask 测试客户端，供各测试用例发起 HTTP 请求。
    """
    return app.test_client()