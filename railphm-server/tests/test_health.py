def test_health_check(client):
    """
    测试健康检查探针接口
    验证:
      1. HTTP 状态码是否为 200
      2. 业务 code 是否为 200，message 是否为 success
      3. data 载荷中是否包含核心的 service 和 status 信息
    """
    response = client.get('/api/v1/health')
    
    # 断言 HTTP 层面正常
    assert response.status_code == 200
    
    # 解析统一响应 JSON
    json_data = response.get_json()
    assert json_data is not None
    
    # 断言业务封装格式
    assert json_data["code"] == 200
    assert json_data["message"] == "success"
    
    # 断言具体业务数据
    payload = json_data.get("data", {})
    assert payload.get("service") == "railphm-server"
    assert payload.get("status") == "running"
    assert "version" in payload