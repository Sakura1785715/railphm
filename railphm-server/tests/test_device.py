
def test_get_devices_success(client):
    """测试获取设备列表成功与分页结构"""
    response = client.get('/api/v1/devices')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data["code"] == 200
    assert json_data["message"] == "success"
    
    data = json_data.get("data", {})
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    
    # 验证列表中有数据
    items = data["items"]
    assert isinstance(items, list)
    assert len(items) > 0
    assert "device_id" in items[0]

def test_get_device_detail_success(client):
    """测试获取单个设备成功"""
    response = client.get('/api/v1/devices/1')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data["code"] == 200
    assert json_data["message"] == "success"
    
    data = json_data.get("data", {})
    assert data["device_id"] == 1
    assert data["car_no"] == "CR400AF-0201" # Mock的第一条数据

def test_get_device_detail_not_found(client):
    """测试获取不存在的设备，验证全局异常链路和统一 JSON 返回"""
    response = client.get('/api/v1/devices/999999')
    
    # 断言 HTTP 层面返回合理的 404，而不是 Flask 默认 HTML 404
    assert response.status_code == 404
    
    # 断言业务封装格式为 JSON，走的是业务异常拦截
    json_data = response.get_json()
    assert json_data is not None
    assert json_data["code"] == 404
    assert "未找到设备ID为" in json_data["message"]