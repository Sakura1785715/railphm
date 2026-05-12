from app.clients.ai_client import AIClient, AIServiceUnavailableError


def build_ai_result():
    return {
        "device_id": "ATP001",
        "sample_index": 100,
        "risk_raw": 0.39,
        "risk_score": 0.41,
        "risk_std": 0.03,
        "threshold": 0.26,
        "predicted_label": 1,
        "model_version": "bilstm_attention_h1_full_features",
        "window_start_time": "2026-05-01 10:00:00",
        "window_end_time": "2026-05-01 10:00:30",
        "data_source": "model_runtime",
        "uncertainty_method": "mc_dropout",
    }


def test_prediction_infer_success(client, monkeypatch):
    def fake_infer(self, payload):
        assert payload == {
            "device_id": 1,
            "ts_end": "2026-05-01 10:00:30",
            "window_minutes": 30,
            "sample_index": 100,
            "mc_samples": 20,
        }
        return build_ai_result()

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
            "window_minutes": 30,
            "sample_index": 100,
            "mc_samples": 20,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == 200
    assert payload["message"] == "success"
    assert payload["data"]["device_id"] == "ATP001"
    assert payload["data"]["risk_score"] == 0.41
    assert payload["data"]["threshold"] == 0.26
    assert payload["data"]["predicted_label"] == 1
    assert payload["data"]["model_version"] == "bilstm_attention_h1_full_features"
    assert payload["data"]["health_score"] == 59.0
    assert payload["data"]["health_level"] == "attention"
    assert payload["data"]["health_status"] == "关注"
    assert payload["data"]["health_description"] == "设备风险开始升高，建议持续关注"
    assert payload["data"]["alert_generated"] is True
    assert payload["data"]["alert_level"] == "low"
    assert payload["data"]["alert_status"] == "unhandled"
    assert payload["data"]["alert_status_text"] == "未处理"
    assert payload["data"]["alert_message"] == "设备风险开始升高，建议关注"
    assert payload["data"]["alert_advice"] == "建议持续观察设备风险变化趋势"
    assert "alert_id" not in payload["data"]
    assert "handler_id" not in payload["data"]
    assert "handle_time" not in payload["data"]


def test_prediction_infer_defaults_optional_params(client, monkeypatch):
    def fake_infer(self, payload):
        assert payload["window_minutes"] == 30
        assert payload["sample_index"] == 0
        assert payload["mc_samples"] == 20
        assert payload["device_id"] == 1
        return {
            "risk_score": 0.2,
            "window_end_time": payload["ts_end"],
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["sample_index"] == 0
    assert data["risk_raw"] == 0.2
    assert data["risk_std"] == 0.0
    assert data["threshold"] == 0.26
    assert data["predicted_label"] == 0
    assert data["model_version"] == "unknown"
    assert data["window_start_time"] is None
    assert data["window_end_time"] == "2026-05-01 10:00:30"
    assert data["data_source"] == "ai_service"
    assert data["uncertainty_method"] == "unknown"
    assert data["health_score"] == 80.0
    assert data["health_level"] == "normal"
    assert data["alert_generated"] is False
    assert data["alert_level"] == "none"
    assert data["alert_status"] == "none"
    assert data["alert_message"] == "当前设备状态正常，暂未生成告警"


def test_prediction_infer_missing_device_id(client, monkeypatch):
    called = {"value": False}

    def fake_infer(self, payload):
        called["value"] = True
        return build_ai_result()

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "ts_end": "2026-05-01 10:00:30",
        },
    )

    assert response.status_code == 400
    assert "device_id 不能为空" in response.get_json()["message"]
    assert called["value"] is False


def test_prediction_infer_missing_ts_end(client, monkeypatch):
    called = {"value": False}

    def fake_infer(self, payload):
        called["value"] = True
        return build_ai_result()

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
        },
    )

    assert response.status_code == 400
    assert "ts_end 不能为空" in response.get_json()["message"]
    assert called["value"] is False


def test_prediction_infer_invalid_window_minutes(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
            "window_minutes": 0,
        },
    )

    assert response.status_code == 400
    assert "window_minutes 必须为正整数" in response.get_json()["message"]


def test_prediction_infer_invalid_sample_index(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
            "sample_index": "100",
        },
    )

    assert response.status_code == 400
    assert "sample_index 必须为非负整数" in response.get_json()["message"]

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
            "sample_index": -1,
        },
    )

    assert response.status_code == 400
    assert "sample_index 必须为非负整数" in response.get_json()["message"]


def test_prediction_infer_invalid_mc_samples(client):
    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
            "mc_samples": 0,
        },
    )

    assert response.status_code == 400
    assert "mc_samples 必须为正整数" in response.get_json()["message"]


def test_prediction_infer_ai_unavailable(client, monkeypatch):
    def fake_infer(self, payload):
        raise AIServiceUnavailableError()

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
        },
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["code"] == 502
    assert payload["message"] == "AI 推理服务不可用"
    assert "Traceback" not in payload["message"]


def test_prediction_infer_ai_missing_risk_score(client, monkeypatch):
    def fake_infer(self, payload):
        return {
            "threshold": 0.26,
            "model_version": "bilstm_attention_h1_full_features",
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
        },
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["code"] == 502
    assert "risk_score" in payload["message"]


def test_prediction_infer_non_json_body(client):
    response = client.post(
        "/api/v1/predictions/infer",
        data="not-json",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert "请求体必须为 JSON 对象" in response.get_json()["message"]


def test_prediction_infer_fallback_when_enabled(client, app, monkeypatch):
    app.config["AI_ENABLE_FALLBACK"] = True

    def fake_infer(self, payload):
        raise AIServiceUnavailableError()

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
            "sample_index": 1,
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["data_source"] == "mock_fallback"
    assert data["risk_score"] == 0.52
    assert data["model_version"] == "mock"
    assert data["health_score"] == 48.0
    assert data["health_level"] == "warning"
    assert data["alert_generated"] is True
    assert data["alert_level"] == "medium"
    assert data["alert_status"] == "unhandled"


def test_prediction_infer_medium_alert(client, monkeypatch):
    def fake_infer(self, payload):
        return {
            **build_ai_result(),
            "risk_raw": 0.52,
            "risk_score": 0.52,
            "risk_std": 0.04,
            "predicted_label": 1,
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["health_level"] == "warning"
    assert data["alert_generated"] is True
    assert data["alert_level"] == "medium"
    assert data["alert_message"] == "设备存在异常风险，建议检查"


def test_prediction_infer_high_alert(client, monkeypatch):
    def fake_infer(self, payload):
        return {
            **build_ai_result(),
            "risk_raw": 0.72,
            "risk_score": 0.72,
            "risk_std": 0.06,
            "predicted_label": 1,
        }

    monkeypatch.setattr(AIClient, "infer", fake_infer)

    response = client.post(
        "/api/v1/predictions/infer",
        json={
            "device_id": "ATP001",
            "ts_end": "2026-05-01 10:00:30",
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["health_level"] == "critical"
    assert data["alert_generated"] is True
    assert data["alert_level"] == "high"
    assert data["alert_message"] == "设备处于高风险状态，请及时处理"
