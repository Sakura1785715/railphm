
def test_get_alerts_success(client):
    """场景1：测试默认列表查询与完整结构"""
    response = client.get('/api/v1/alerts')
    assert response.status_code == 200
    data = response.get_json()["data"]
    
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0

def test_get_alerts_pagination_success(client):
    """场景2：测试分页切片"""
    response = client.get('/api/v1/alerts?page=1&size=2')
    assert response.status_code == 200
    data = response.get_json()["data"]
    
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["size"] == 2
    assert data["total"] >= 2

def test_get_alerts_filter_success(client):
    """场景3：测试筛选条件"""
    response = client.get('/api/v1/alerts?alert_level=HIGH&alert_status=PENDING')
    assert response.status_code == 200
    data = response.get_json()["data"]
    
    for item in data["items"]:
        assert item["alert_level"] == "HIGH"
        assert item["alert_status"] == "PENDING"

def test_get_alerts_empty_result(client):
    """场景4：测试合法过滤条件但无数据时的稳定结构"""
    response = client.get('/api/v1/alerts?device_id=9999')
    assert response.status_code == 200
    data = response.get_json()["data"]
    
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1

def test_get_alert_detail_success(client):
    """场景5：测试详情查询"""
    response = client.get('/api/v1/alerts/1001')
    assert response.status_code == 200
    data = response.get_json()["data"]
    
    assert data["alert_id"] == 1001
    assert "alert_source" in data
    assert "handle_time" in data

def test_get_alert_detail_not_found(client):
    """场景6：测试不存在的记录，拦截 404"""
    response = client.get('/api/v1/alerts/999999')
    assert response.status_code == 404
    assert response.get_json()["code"] == 404
    assert "未找到" in response.get_json()["message"]

def test_get_alerts_invalid_page(client):
    """场景7：测试分页参数异常 page <= 0"""
    response = client.get('/api/v1/alerts?page=0')
    assert response.status_code == 400
    assert "正整数" in response.get_json()["message"]

def test_get_alerts_invalid_size(client):
    """场景8：测试分页参数异常 size 不是数字"""
    response = client.get('/api/v1/alerts?size=abc')
    assert response.status_code == 400
    assert "正整数" in response.get_json()["message"]