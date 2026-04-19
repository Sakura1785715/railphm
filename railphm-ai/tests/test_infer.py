# tests/test_infer.py
import pytest

# ==========================================
# 1. 业务逻辑分支覆盖测试 (核心 Mock 规则与时间计算)
# ==========================================
@pytest.mark.parametrize("device_id, expected_level, expected_label, expected_score", [
    (1, "HIGH", "abnormal-trend", 0.82),     # 取模 1
    (4, "HIGH", "abnormal-trend", 0.82),     # 取模 1
    (2, "MEDIUM", "normal-cruise", 0.52),    # 取模 2
    (5, "MEDIUM", "normal-cruise", 0.52),    # 取模 2
    (3, "LOW", "stable", 0.21),              # 取模 0
    (6, "LOW", "stable", 0.21),              # 取模 0
])
def test_infer_business_mock_branches(client, device_id, expected_level, expected_label, expected_score):
    """全覆盖测试：设备ID的取模分支逻辑"""
    payload = {
        "device_id": device_id,
        "ts_end": "2026-04-19 10:05:00",
        "window_minutes": 5
    }
    response = client.post('/infer', json=payload)
    assert response.status_code == 200
    data = response.get_json()["data"]
    
    assert data["device_id"] == device_id
    assert data["alert_level"] == expected_level
    assert data["condition_label"] == expected_label
    assert data["risk_score"] == expected_score

def test_infer_time_calculation_cross_hour(client):
    """全覆盖测试：时间跨小时/跨天的窗口倒推逻辑计算"""
    payload = {
        "device_id": 1,
        "ts_end": "2026-04-19 00:02:00",
        "window_minutes": 10
    }
    response = client.post('/infer', json=payload)
    assert response.status_code == 200
    data = response.get_json()["data"]
    # 00:02:00 往前推 10 分钟应该是前一天的 23:52:00
    assert data["window_start_time"] == "2026-04-18 23:52:00"

# ==========================================
# 2. 请求载荷与外层异常覆盖测试
# ==========================================
def test_infer_empty_payload(client):
    """测试：完全空的请求体或非 JSON 请求"""
    # 发生空 POST
    response = client.post('/infer')
    assert response.status_code == 400
    assert "请求格式非法或为空" in response.get_json()["message"]

# ==========================================
# 3. 参数级边界约束全覆盖测试 (Validation)
# ==========================================
@pytest.mark.parametrize("payload_mod, expected_msg", [
    # device_id 异常场景
    ({"device_id": None}, "device_id 不能为空"),
    ({"device_id": "1"}, "必须为整数"),
    ({"device_id": 1.5}, "必须为整数"),
    
    # ts_end 异常场景
    ({"ts_end": None}, "ts_end 不能为空"),
    ({"ts_end": "2026-04-19"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),           # 缺时间
    ({"ts_end": "2026/04/19 10:05:00"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),  # 斜杠格式
    ({"ts_end": "2026-13-19 10:05:00"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),  # 非法月份
    ({"ts_end": "2026-04-19 25:05:00"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),  # 非法小时
    
    # window_minutes 异常场景
    ({"window_minutes": None}, "window_minutes 不能为空"),
    ({"window_minutes": "5"}, "必须为正整数"),
    ({"window_minutes": 5.5}, "必须为正整数"),
    ({"window_minutes": 0}, "必须为正整数"),
    ({"window_minutes": -5}, "必须为正整数"),
])
def test_infer_parameter_validation_all_paths(client, payload_mod, expected_msg):
    """全覆盖测试：使用参数化覆盖所有参数校验失败的边界条件"""
    # 基础合法载荷
    base_payload = {
        "device_id": 1,
        "ts_end": "2026-04-19 10:05:00",
        "window_minutes": 5
    }
    
    # 针对某个被测试字段进行篡改 (如果值为 None，代表直接不传该字段)
    for key, value in payload_mod.items():
        if value is None:
            del base_payload[key]
        else:
            base_payload[key] = value

    response = client.post('/infer', json=base_payload)
    
    # 统一断言：状态码必定为 400 且错误信息包含预期关键词
    assert response.status_code == 400
    json_data = response.get_json()
    assert expected_msg in json_data["message"]