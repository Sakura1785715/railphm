
def test_get_monitor_series_success(client):
    """测试完整合法参数下的成功查询，使用真实的2015年Mock范围"""
    params = {
        "device_id": "1",
        "start_time": "2015-01-09 10:20:00",
        "end_time": "2015-01-09 10:25:00"
    }
    response = client.get('/api/v1/monitor/series', query_string=params)
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data["code"] == 200
    data = json_data["data"]
    assert data["device_id"] == 1
    
    # 验证提取了 speed, mileage, run_distance 3 条曲线
    assert len(data["series"]) == 3
    assert data["series"][0]["metric"] == "speed"
    # 该区间内应含有 CSV 中的部分真实模拟数据
    assert len(data["series"][0]["points"]) > 0
    assert "time" in data["series"][0]["points"][0]
    assert "value" in data["series"][0]["points"][0]

def test_get_monitor_series_missing_device_id(client):
    """测试缺少 device_id 参数"""
    params = {"start_time": "2015-01-09 10:20:00", "end_time": "2015-01-09 10:25:00"}
    response = client.get('/api/v1/monitor/series', query_string=params)
    assert response.status_code == 400
    assert "device_id 不能为空" in response.get_json()["message"]

def test_get_monitor_series_missing_start_time(client):
    """测试缺少 start_time 参数"""
    params = {"device_id": "1", "end_time": "2015-01-09 10:25:00"}
    response = client.get('/api/v1/monitor/series', query_string=params)
    assert response.status_code == 400
    assert "start_time 不能为空" in response.get_json()["message"]

def test_get_monitor_series_missing_end_time(client):
    """测试缺少 end_time 参数"""
    params = {"device_id": "1", "start_time": "2015-01-09 10:20:00"}
    response = client.get('/api/v1/monitor/series', query_string=params)
    assert response.status_code == 400
    assert "end_time 不能为空" in response.get_json()["message"]

def test_get_monitor_series_invalid_time_format(client):
    """测试传入非法时间格式"""
    params = {
        "device_id": "1",
        "start_time": "2015/01/09", 
        "end_time": "2015-01-09 10:25:00"
    }
    response = client.get('/api/v1/monitor/series', query_string=params)
    assert response.status_code == 400
    assert "时间格式非法" in response.get_json()["message"]

def test_get_monitor_series_invalid_time_range(client):
    """测试时间范围倒置"""
    params = {
        "device_id": "1",
        "start_time": "2015-01-09 10:30:00",
        "end_time": "2015-01-09 10:20:00"
    }
    response = client.get('/api/v1/monitor/series', query_string=params)
    assert response.status_code == 400
    assert "早于结束时间" in response.get_json()["message"]

def test_get_monitor_series_empty_result(client):
    """测试设备存在但该时段无数据"""
    params = {
        "device_id": "1",
        "start_time": "2010-01-01 10:00:00",
        "end_time": "2010-01-01 11:00:00"
    }
    response = client.get('/api/v1/monitor/series', query_string=params)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert len(data["series"]) == 3
    # 断言结构稳定存在，但点位数组为空
    assert data["series"][0]["points"] == []