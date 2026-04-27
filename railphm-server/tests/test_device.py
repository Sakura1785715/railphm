
ADMIN_HEADERS = {
    "Authorization": "Bearer mock-token-admin"
}

OPS_HEADERS = {
    "Authorization": "Bearer mock-token-ops"
}


def build_device_payload(car_no="CR400AF-AUTH-01"):
    return {
        "car_no": car_no,
        "atp_type": "CTCS-3",
        "attach_bureau": "北京局",
        "device_status": 1
    }


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

def test_get_devices_with_filters_success(client):
    """测试设备列表最小筛选能力"""
    response = client.get('/api/v1/devices?device_id=1&car_no=0201&device_status=1')
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data["code"] == 200

    data = json_data.get("data", {})
    items = data["items"]
    assert data["total"] == 1
    assert len(items) == 1
    assert items[0]["device_id"] == 1
    assert items[0]["car_no"] == "CR400AF-0201"

def test_get_devices_with_filters_empty_result(client):
    """测试设备筛选无结果时仍返回统一结构"""
    response = client.get('/api/v1/devices?car_no=NOT-EXISTS')
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data["code"] == 200

    data = json_data.get("data", {})
    assert data["total"] == 0
    assert data["items"] == []

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

def test_create_device_success(client):
    """测试新增设备成功"""
    response = client.post('/api/v1/devices', headers=ADMIN_HEADERS, json={
        "car_no": "CR400AF-TEST29",
        "atp_type": "CTCS-3",
        "attach_bureau": "北京局",
        "device_status": 1
    })

    json_data = response.get_json()
    data = json_data["data"]

    assert response.status_code == 200
    assert json_data["code"] == 200
    assert data["device_id"]
    assert data["car_no"] == "CR400AF-TEST29"
    assert data["atp_type"] == "CTCS-3"
    assert data["attach_bureau"] == "北京局"
    assert data["device_status"] == 1

def test_update_device_success(client):
    """测试编辑自己新增的设备成功"""
    create_response = client.post('/api/v1/devices', headers=ADMIN_HEADERS, json={
        "car_no": "CR400AF-TEST29-NEW",
        "atp_type": "CTCS-3",
        "attach_bureau": "北京局",
        "device_status": 1
    })
    device_id = create_response.get_json()["data"]["device_id"]

    response = client.put(f'/api/v1/devices/{device_id}', headers=ADMIN_HEADERS, json={
        "car_no": "CR400AF-TEST29-UPDATED",
        "atp_type": "CTCS-2",
        "attach_bureau": "上海局",
        "device_status": 0
    })

    json_data = response.get_json()
    data = json_data["data"]

    assert response.status_code == 200
    assert json_data["code"] == 200
    assert data["device_id"] == device_id
    assert data["car_no"] == "CR400AF-TEST29-UPDATED"
    assert data["atp_type"] == "CTCS-2"
    assert data["attach_bureau"] == "上海局"
    assert data["device_status"] == 0

def test_create_device_missing_required_field(client):
    """测试新增设备缺少必填字段"""
    response = client.post('/api/v1/devices', headers=ADMIN_HEADERS, json={
        "car_no": "CR400AF-MISSING",
        "atp_type": "CTCS-3",
        "device_status": 1
    })
    json_data = response.get_json()

    assert response.status_code == 400
    assert json_data["code"] == 400
    assert "attach_bureau" in json_data["message"] or "配属铁路局" in json_data["message"]

def test_create_device_invalid_status(client):
    """测试新增设备状态非法"""
    response = client.post('/api/v1/devices', headers=ADMIN_HEADERS, json={
        "car_no": "CR400AF-INVALID",
        "atp_type": "CTCS-3",
        "attach_bureau": "北京局",
        "device_status": 9
    })
    json_data = response.get_json()

    assert response.status_code == 400
    assert json_data["code"] == 400
    assert "0" in json_data["message"] or "1" in json_data["message"] or "非法" in json_data["message"]

def test_update_device_not_found(client):
    """测试编辑不存在的设备"""
    response = client.put('/api/v1/devices/999999', headers=ADMIN_HEADERS, json={
        "car_no": "CR400AF-NOTFOUND",
        "atp_type": "CTCS-3",
        "attach_bureau": "北京局",
        "device_status": 1
    })
    json_data = response.get_json()

    assert response.status_code == 404
    assert json_data["code"] == 404
    assert "未找到设备ID为" in json_data["message"]

def test_update_device_missing_required_field(client):
    """测试编辑设备缺少有效必填字段"""
    response = client.put('/api/v1/devices/1', headers=ADMIN_HEADERS, json={
        "car_no": "CR400AF-BAD",
        "atp_type": "CTCS-3",
        "attach_bureau": ""
    })
    json_data = response.get_json()

    assert response.status_code == 400
    assert json_data["code"] == 400

def test_create_device_requires_login(client):
    """测试未登录不能新增设备"""
    response = client.post('/api/v1/devices', json=build_device_payload("CR400AF-AUTH-01"))
    json_data = response.get_json()

    assert response.status_code == 401
    assert json_data["code"] == 401
    assert "未登录" in json_data["message"] or "无效" in json_data["message"]

def test_create_device_forbidden_for_ops(client):
    """测试运维用户不能新增设备"""
    response = client.post(
        '/api/v1/devices',
        headers=OPS_HEADERS,
        json=build_device_payload("CR400AF-AUTH-02")
    )
    json_data = response.get_json()

    assert response.status_code == 403
    assert json_data["code"] == 403
    assert "权限不足" in json_data["message"]

def test_update_device_requires_login(client):
    """测试未登录不能编辑设备"""
    response = client.put('/api/v1/devices/1', json=build_device_payload("CR400AF-AUTH-03"))
    json_data = response.get_json()

    assert response.status_code == 401
    assert json_data["code"] == 401

def test_update_device_forbidden_for_ops(client):
    """测试运维用户不能编辑设备"""
    response = client.put(
        '/api/v1/devices/1',
        headers=OPS_HEADERS,
        json=build_device_payload("CR400AF-AUTH-04")
    )
    json_data = response.get_json()

    assert response.status_code == 403
    assert json_data["code"] == 403
    assert "权限不足" in json_data["message"]
