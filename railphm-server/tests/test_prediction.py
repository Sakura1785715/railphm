# tests/test_prediction.py

def test_get_latest_prediction_success(client):
    """测试获取最新结果成功"""
    response = client.get('/api/v1/predictions/latest?device_id=1')
    assert response.status_code == 200
    data = response.get_json()["data"]
    
    assert data["device_id"] == 1
    assert "risk_score" in data
    assert "health_score" in data
    assert "model_version" in data
    assert "window_start_time" in data
    # 断言确实取到了时间上最新的一条
    assert data["window_start_time"] == "2026-04-01 10:00:00"

def test_get_latest_prediction_missing_device_id(client):
    """测试缺少 device_id 触发异常"""
    response = client.get('/api/v1/predictions/latest')
    assert response.status_code == 400
    assert "不能为空" in response.get_json()["message"]

def test_get_latest_prediction_empty_result(client):
    """测试设备合法但无结果"""
    response = client.get('/api/v1/predictions/latest?device_id=999')
    assert response.status_code == 200
    # 按照设计语义，查不到时明确返回 null
    assert response.get_json()["data"] is None

def test_get_prediction_history_success(client):
    """测试获取历史趋势成功"""
    params = {"device_id": "1", "start_time": "2026-04-01 08:00:00", "end_time": "2026-04-01 09:30:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    assert response.status_code == 200
    
    data = response.get_json()["data"]
    assert data["device_id"] == 1
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2
    assert "risk_score" in data["items"][0]

def test_get_prediction_history_items_sorted(client):
    """测试历史结果是否按升序排列"""
    params = {"device_id": "1", "start_time": "2026-04-01 08:00:00", "end_time": "2026-04-01 11:00:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    items = response.get_json()["data"]["items"]
    # 验证升序 (前一个的时间应该小于或等于后一个的时间)
    for i in range(len(items) - 1):
        assert items[i]["window_start_time"] <= items[i+1]["window_start_time"]

def test_get_prediction_history_missing_device_id(client):
    params = {"start_time": "2026-04-01 08:00:00", "end_time": "2026-04-01 09:30:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    assert response.status_code == 400

def test_get_prediction_history_missing_start_time(client):
    params = {"device_id": "1", "end_time": "2026-04-01 09:30:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    assert response.status_code == 400

def test_get_prediction_history_missing_end_time(client):
    params = {"device_id": "1", "start_time": "2026-04-01 08:00:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    assert response.status_code == 400

def test_get_prediction_history_invalid_time_format(client):
    params = {"device_id": "1", "start_time": "2026/04/01 08:00:00", "end_time": "2026-04-01 09:30:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    assert response.status_code == 400
    assert "时间格式非法" in response.get_json()["message"]

def test_get_prediction_history_invalid_time_range(client):
    params = {"device_id": "1", "start_time": "2026-04-01 10:00:00", "end_time": "2026-04-01 09:30:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    assert response.status_code == 400
    assert "早于结束时间" in response.get_json()["message"]

def test_get_prediction_history_empty_result(client):
    """测试合法参数无数据时稳定结构返回"""
    params = {"device_id": "999", "start_time": "2026-04-01 08:00:00", "end_time": "2026-04-01 09:30:00"}
    response = client.get('/api/v1/predictions/history', query_string=params)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["items"] == [] 