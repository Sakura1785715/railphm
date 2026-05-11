import pytest

from app.service.prediction_service import PredictionService
from app.api.realtime.routes import realtime_stream_service


def build_prediction_result(request_data):
    return {
        "device_id": request_data["device_id"],
        "sample_index": request_data["sample_index"],
        "risk_raw": 0.41,
        "risk_score": 0.41,
        "risk_std": 0.03,
        "threshold": 0.26,
        "predicted_label": 1,
        "model_version": "test-model",
        "window_start_time": "2026-05-01 09:59:30",
        "window_end_time": request_data["ts_end"],
        "data_source": "model_runtime",
        "uncertainty_method": "mc_dropout",
        "health_score": 59.0,
        "health_level": "attention",
        "health_status": "关注",
        "health_description": "设备风险开始升高，建议持续关注",
        "alert_generated": True,
        "alert_level": "low",
        "alert_status": "unhandled",
        "alert_status_text": "未处理",
        "alert_message": "设备风险开始升高，建议关注",
        "alert_advice": "建议持续观察设备风险变化趋势",
    }


@pytest.fixture(autouse=True)
def reset_realtime_route_state():
    realtime_stream_service.reset_for_tests()
    yield
    realtime_stream_service.reset_for_tests()


def test_realtime_start_route(client):
    response = client.post("/api/v1/realtime/start", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == 200
    assert payload["data"]["running"] is True
    assert payload["data"]["device_id"] == "ATP001"


def test_realtime_state_route(client):
    client.post(
        "/api/v1/realtime/start",
        json={
            "device_id": "ATP001",
            "start_sample_index": 4,
        },
    )

    response = client.get("/api/v1/realtime/state")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["running"] is True
    assert data["current_sample_index"] == 4
    assert data["last_result"] is None


def test_realtime_next_route(client, monkeypatch):
    calls = []

    def fake_infer(request_data):
        calls.append(request_data)
        return build_prediction_result(request_data)

    monkeypatch.setattr(PredictionService, "infer_prediction", staticmethod(fake_infer))
    client.post(
        "/api/v1/realtime/start",
        json={
            "device_id": "ATP001",
            "start_sample_index": 2,
            "step": 1,
        },
    )

    response = client.get("/api/v1/realtime/next")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["stream_id"] == "default"
    assert data["sample_index"] == 2
    assert data["next_sample_index"] == 3
    assert data["risk_score"] == 0.41
    assert data["health_score"] == 59.0
    assert data["alert_level"] == "low"
    assert data["stream_state"]["current_sample_index"] == 3
    assert calls[0]["sample_index"] == 2


def test_realtime_stop_route(client):
    client.post("/api/v1/realtime/start", json={})

    response = client.post("/api/v1/realtime/stop")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["running"] is False


def test_realtime_reset_route(client):
    client.post("/api/v1/realtime/start", json={"start_sample_index": 10})

    response = client.post("/api/v1/realtime/reset", json={"sample_index": 12})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["running"] is False
    assert data["current_sample_index"] == 12


def test_realtime_start_invalid_param(client):
    response = client.post(
        "/api/v1/realtime/start",
        json={
            "start_sample_index": 2,
            "end_sample_index": 1,
        },
    )

    assert response.status_code == 400
    assert "end_sample_index" in response.get_json()["message"]


def test_realtime_start_non_json_body(client):
    response = client.post(
        "/api/v1/realtime/start",
        data="not-json",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert "JSON 对象" in response.get_json()["message"]


def test_realtime_next_when_not_started(client):
    response = client.get("/api/v1/realtime/next")

    assert response.status_code == 400
    assert "未启动" in response.get_json()["message"]
