def test_system_ping(client):
    """
    测试系统连通性 ping 接口
    验证:
      1. 接口是否存在并返回 200
      2. 是否正确返回指定的 system-ping 键值对
    """
    response = client.get('/api/v1/system/ping')
    
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data is not None
    assert json_data["code"] == 200
    assert json_data["message"] == "success"
    
    payload = json_data.get("data", {})
    assert payload.get("system-ping") == "system-pong"