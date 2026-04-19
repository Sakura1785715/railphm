from app.clients.ai_client import AIClient
from app.core.errors import BusinessException


def test_prediction_infer_backend_overrides_health_and_alert(client, monkeypatch):
    def fake_infer(self, device_id, ts_end, window_minutes):
        return {
            "device_id": device_id,
            "ts_end": ts_end,
            "window_minutes": window_minutes,
            "window_start_time": "2026-04-19 10:00:00",
            "window_end_time": "2026-04-19 10:05:00",
            "condition_label": "abnormal-trend",
            "risk_score": 0.82,
            "risk_std": 0.07,
            "health_score": 999,
            "alert_level": "LOW",
            "model_version": "mock-bilstm-attention-v1",
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == 200
    assert payload["message"] == "success"
    assert payload["data"]["device_id"] == 1
    assert payload["data"]["risk_score"] == 0.82
    assert payload["data"]["risk_std"] == 0.07
    assert payload["data"]["health_score"] == 18.0
    assert payload["data"]["alert_level"] == "HIGH"
    assert payload["data"]["model_version"] == "mock-bilstm-attention-v1"


def test_prediction_infer_medium_case(client, monkeypatch):
    def fake_infer(self, device_id, ts_end, window_minutes):
        return {
            "device_id": device_id,
            "ts_end": ts_end,
            "window_minutes": window_minutes,
            "window_start_time": "2026-04-19 10:00:00",
            "window_end_time": "2026-04-19 10:05:00",
            "condition_label": "abnormal-trend",
            "risk_score": 0.52,
            "risk_std": 0.05,
            "model_version": "mock-bilstm-attention-v1",
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["risk_score"] == 0.52
    assert payload["data"]["health_score"] == 48.0
    assert payload["data"]["alert_level"] == "MEDIUM"


def test_prediction_infer_low_case(client, monkeypatch):
    def fake_infer(self, device_id, ts_end, window_minutes):
        return {
            "device_id": device_id,
            "ts_end": ts_end,
            "window_minutes": window_minutes,
            "window_start_time": "2026-04-19 10:00:00",
            "window_end_time": "2026-04-19 10:05:00",
            "condition_label": "abnormal-trend",
            "risk_score": 0.21,
            "risk_std": 0.03,
            "model_version": "mock-bilstm-attention-v1",
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["risk_score"] == 0.21
    assert payload["data"]["health_score"] == 79.0
    assert payload["data"]["alert_level"] == "LOW"


def test_prediction_infer_missing_device_id(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 400
    assert "device_id 不能为空" in response.get_json()["message"]


def test_prediction_infer_invalid_device_id(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "abc",
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 400
    assert "device_id 必须为整数" in response.get_json()["message"]


def test_prediction_infer_missing_ts_end(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "window_minutes": 5,
        },
    )

    assert response.status_code == 400
    assert "ts_end 不能为空" in response.get_json()["message"]


def test_prediction_infer_invalid_ts_end_format(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026/04/19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 400
    assert "YYYY-MM-DD HH:mm:ss" in response.get_json()["message"]


def test_prediction_infer_missing_window_minutes(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
        },
    )

    assert response.status_code == 400
    assert "window_minutes 不能为空" in response.get_json()["message"]


def test_prediction_infer_invalid_window_minutes(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 0,
        },
    )
    assert response.status_code == 400
    assert "window_minutes 必须为正整数" in response.get_json()["message"]

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": "abc",
        },
    )
    assert response.status_code == 400
    assert "window_minutes 必须为正整数" in response.get_json()["message"]


def test_prediction_infer_ai_unavailable(client, monkeypatch):
    def fake_infer(self, device_id, ts_end, window_minutes):
        raise BusinessException(code=502, message="AI 推理服务不可用", status_code=502)

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["code"] == 502
    assert payload["message"] == "AI 推理服务不可用"


def test_prediction_infer_ai_timeout(client, monkeypatch):
    def fake_infer(self, device_id, ts_end, window_minutes):
        raise BusinessException(code=504, message="AI 推理服务请求超时", status_code=504)

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 504
    payload = response.get_json()
    assert payload["code"] == 504
    assert payload["message"] == "AI 推理服务请求超时"


def test_prediction_infer_ai_bad_payload(client, monkeypatch):
    def fake_infer(self, device_id, ts_end, window_minutes):
        return {
            "device_id": device_id,
            "ts_end": ts_end,
            "window_minutes": window_minutes,
            "window_start_time": "2026-04-19 10:00:00",
            "window_end_time": "2026-04-19 10:05:00",
            "condition_label": "abnormal-trend",
            "risk_std": 0.07,
            "model_version": "mock-bilstm-attention-v1",
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": 1,
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 5,
        },
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["code"] == 502
    assert "缺少必要字段" in payload["message"]
