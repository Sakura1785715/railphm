import pytest

from app.clients import ai_client as ai_client_module
from app.clients.ai_client import AIClient
from app.core.errors import BusinessException


class FakeResponse:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def build_ai_data():
    return {
        "device_id": 1,
        "ts_end": "2026-04-19 10:05:00",
        "window_minutes": 5,
        "window_start_time": "2026-04-19 10:00:00",
        "window_end_time": "2026-04-19 10:05:00",
        "condition_label": "abnormal-trend",
        "risk_score": 0.82,
        "risk_std": 0.07,
        "model_version": "mock-bilstm-attention-v1",
    }


def mock_ai_response(monkeypatch, data):
    def fake_post(url, json, timeout):
        return FakeResponse({"code": 200, "message": "success", "data": data})

    monkeypatch.setattr(ai_client_module.requests, "post", fake_post)


def test_ai_client_does_not_require_health_score_or_alert_level(monkeypatch):
    data = build_ai_data()
    mock_ai_response(monkeypatch, data)

    result = AIClient(base_url="http://railphm-ai.test").infer(
        device_id=1,
        ts_end="2026-04-19 10:05:00",
        window_minutes=5,
    )

    assert result["risk_score"] == 0.82
    assert result["risk_std"] == 0.07
    assert "health_score" not in result
    assert "alert_level" not in result


@pytest.mark.parametrize("missing_field", ["risk_score", "risk_std", "condition_label"])
def test_ai_client_requires_model_output_fields(monkeypatch, missing_field):
    data = build_ai_data()
    data.pop(missing_field)
    mock_ai_response(monkeypatch, data)

    with pytest.raises(BusinessException) as exc_info:
        AIClient(base_url="http://railphm-ai.test").infer(
            device_id=1,
            ts_end="2026-04-19 10:05:00",
            window_minutes=5,
        )

    assert exc_info.value.status_code == 502
    assert "缺少必要字段" in exc_info.value.message
