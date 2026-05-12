import pytest

from app.clients import ai_client as ai_client_module
from app.clients.ai_client import AIClient, AIResponseFormatError, AIServiceUnavailableError


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def json(self):
        return self._body


def build_ai_data():
    return {
        "device_id": "ATP001",
        "sample_index": 100,
        "risk_raw": 0.39,
        "risk_score": 0.41,
        "window_start_time": "2026-04-19 10:00:00",
        "window_end_time": "2026-04-19 10:05:00",
        "risk_std": 0.03,
        "threshold": 0.26,
        "predicted_label": 1,
        "model_version": "bilstm_attention_h1_full_features",
        "data_source": "model_runtime",
        "uncertainty_method": "mc_dropout",
    }


def mock_ai_response(monkeypatch, body):
    def fake_post(url, json, timeout):
        return FakeResponse(body)

    monkeypatch.setattr(ai_client_module.requests, "post", fake_post)


def test_ai_client_extracts_wrapped_ai_response(monkeypatch):
    data = build_ai_data()
    mock_ai_response(monkeypatch, {"code": 0, "message": "success", "data": data})

    result = AIClient(base_url="http://railphm-ai.test").infer({
        "device_id": "ATP001",
        "ts_end": "2026-04-19 10:05:00",
        "window_minutes": 30,
        "sample_index": 100,
        "mc_samples": 20,
    })

    assert result["risk_score"] == 0.41
    assert result["threshold"] == 0.26
    assert "health_score" not in result
    assert "alert_level" not in result


def test_ai_client_accepts_direct_ai_response(monkeypatch):
    data = build_ai_data()
    mock_ai_response(monkeypatch, data)

    result = AIClient(base_url="http://railphm-ai.test").infer({
        "device_id": "ATP001",
        "ts_end": "2026-04-19 10:05:00",
        "window_minutes": 30,
        "sample_index": 100,
        "mc_samples": 20,
    })

    assert result["risk_score"] == 0.41


def test_ai_client_requires_risk_score(monkeypatch):
    data = build_ai_data()
    data.pop("risk_score")
    mock_ai_response(monkeypatch, {"code": 200, "message": "success", "data": data})

    with pytest.raises(AIResponseFormatError) as exc_info:
        AIClient(base_url="http://railphm-ai.test").infer({
            "device_id": "ATP001",
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 30,
            "sample_index": 100,
            "mc_samples": 20,
        })

    assert exc_info.value.status_code == 502
    assert "缺少必要字段" in exc_info.value.message


def test_ai_client_timeout(monkeypatch):
    def fake_post(url, json, timeout):
        raise ai_client_module.requests.Timeout()

    monkeypatch.setattr(ai_client_module.requests, "post", fake_post)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        AIClient(base_url="http://railphm-ai.test").infer({
            "device_id": "ATP001",
            "ts_end": "2026-04-19 10:05:00",
            "window_minutes": 30,
            "sample_index": 100,
            "mc_samples": 20,
        })

    assert exc_info.value.status_code == 504
