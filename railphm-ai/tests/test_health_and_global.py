
def test_health_success(client):
    """测试健康检查探针成功响应"""
    response = client.get('/health')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data["code"] == 200
    assert json_data["message"] == "success"
    
    payload = json_data["data"]
    assert payload["service"] == "railphm-ai"
    assert payload["status"] == "running"
    assert "version" in payload

def test_health_method_not_allowed(client):
    """测试不支持的 HTTP 方法，验证全局异常兜底是否转为 JSON"""
    response = client.post('/health')
    assert response.status_code == 405
    json_data = response.get_json()
    assert json_data["code"] == 405
    assert "method not allowed" in json_data["message"].lower()

def test_global_404_not_found(client):
    """测试不存在的路由，验证全局 404 捕获是否转为 JSON"""
    response = client.get('/some_not_exist_route')
    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data["code"] == 404
    assert "not found" in json_data["message"].lower()