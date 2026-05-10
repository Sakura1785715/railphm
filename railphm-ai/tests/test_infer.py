# tests/test_infer.py
import pytest

from app.repository.infer_repository import InferRepository


def _mock_runtime_result(payload):
    return {
        "sample_index": payload["sample_index"],
        "y_true": 0,
        "risk_raw": 0.3812,
        "risk_score": 0.4278,
        "risk_raw_std": 0.0731,
        "risk_std": 0.0615,
        "threshold": 0.26,
        "predicted_label": 1,
        "model_version": "bilstm_attention_h1_full_features",
        "model_name": "bilstm_attention",
        "calibration_enabled": True,
        "calibration_method": "isotonic_regression",
        "uncertainty_enabled": True,
        "uncertainty_method": "mc_dropout",
        "mc_samples": payload["mc_samples"],
        "data_source": "local_window_dataset",
        "trace": {
            "sample_id": "sample-0",
            "segment_id": "segment-0",
            "label": 0,
        },
    }


@pytest.fixture
def patched_runtime_infer(monkeypatch):
    def fake_infer(payload):
        return _mock_runtime_result(payload)

    monkeypatch.setattr(InferRepository, "infer", staticmethod(fake_infer))


def test_infer_runtime_success_response(client, patched_runtime_infer):
    payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 12:00:00",
        "window_minutes": 30,
        "sample_index": 0,
        "mc_samples": 5,
    }

    response = client.post("/infer", json=payload)

    assert response.status_code == 200
    data = response.get_json()["data"]

    assert data["device_id"] == 1001
    assert data["ts_end"] == "2026-05-09 12:00:00"
    assert data["window_minutes"] == 30
    assert data["window_start_time"] == "2026-05-09 11:30:00"
    assert data["window_end_time"] == "2026-05-09 12:00:00"
    assert data["sample_index"] == 0

    for field in (
        "risk_raw",
        "risk_score",
        "risk_raw_std",
        "risk_std",
        "threshold",
        "predicted_label",
        "model_version",
        "calibration_enabled",
        "uncertainty_enabled",
        "mc_samples",
        "data_source",
    ):
        assert field in data

    assert data["mc_samples"] == 5
    assert data["data_source"] == "local_window_dataset"
    assert "health_score" not in data
    assert "alert_level" not in data


def test_infer_runtime_success_response_with_api_v1_alias(client, patched_runtime_infer):
    payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 12:00:00",
        "window_minutes": 30,
        "sample_index": 0,
        "mc_samples": 5,
    }

    response = client.post("/api/v1/infer", json=payload)

    assert response.status_code == 200
    assert response.get_json()["data"]["data_source"] == "local_window_dataset"


def test_infer_default_sample_index(client, patched_runtime_infer):
    payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 12:00:00",
        "window_minutes": 30,
        "mc_samples": 5,
    }

    response = client.post("/infer", json=payload)

    assert response.status_code == 200
    assert response.get_json()["data"]["sample_index"] == 0


def test_infer_default_mc_samples(client, patched_runtime_infer):
    payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 12:00:00",
        "window_minutes": 30,
        "sample_index": 0,
    }

    response = client.post("/infer", json=payload)

    assert response.status_code == 200
    assert response.get_json()["data"]["mc_samples"] == 30


def test_infer_time_calculation_cross_hour(client, patched_runtime_infer):
    payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 00:02:00",
        "window_minutes": 10,
        "sample_index": 0,
        "mc_samples": 5,
    }

    response = client.post("/infer", json=payload)

    assert response.status_code == 200
    assert response.get_json()["data"]["window_start_time"] == "2026-05-08 23:52:00"


def test_infer_empty_payload(client):
    response = client.post("/infer")

    assert response.status_code == 400
    assert "请求格式非法或为空" in response.get_json()["message"]


@pytest.mark.parametrize(
    "payload_mod, expected_msg",
    [
        ({"device_id": None}, "device_id 不能为空"),
        ({"device_id": "1"}, "必须为整数"),
        ({"device_id": 1.5}, "必须为整数"),
        ({"device_id": True}, "必须为整数"),
        ({"ts_end": None}, "ts_end 不能为空"),
        ({"ts_end": "2026-04-19"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),
        ({"ts_end": "2026/04/19 10:05:00"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),
        ({"ts_end": "2026-13-19 10:05:00"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),
        ({"ts_end": "2026-04-19 25:05:00"}, "ts_end 必须使用 YYYY-MM-DD HH:mm:ss 格式"),
        ({"window_minutes": None}, "window_minutes 不能为空"),
        ({"window_minutes": "5"}, "必须为正整数"),
        ({"window_minutes": 5.5}, "必须为正整数"),
        ({"window_minutes": 0}, "必须为正整数"),
        ({"window_minutes": -5}, "必须为正整数"),
        ({"window_minutes": True}, "必须为正整数"),
        ({"sample_index": -1}, "sample_index 必须为非负整数"),
        ({"sample_index": True}, "sample_index 必须为非负整数"),
        ({"sample_index": "0"}, "sample_index 必须为非负整数"),
        ({"mc_samples": 0}, "mc_samples 必须为正整数"),
        ({"mc_samples": True}, "mc_samples 必须为正整数"),
        ({"mc_samples": "5"}, "mc_samples 必须为正整数"),
        ({"mc_samples": 1001}, "mc_samples 不能超过 1000"),
    ],
)
def test_infer_parameter_validation_all_paths(
    client,
    patched_runtime_infer,
    payload_mod,
    expected_msg,
):
    base_payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 12:00:00",
        "window_minutes": 30,
        "sample_index": 0,
        "mc_samples": 5,
    }

    for key, value in payload_mod.items():
        if value is None:
            del base_payload[key]
        else:
            base_payload[key] = value

    response = client.post("/infer", json=base_payload)

    assert response.status_code == 400
    assert expected_msg in response.get_json()["message"]


def test_infer_mock_fallback_when_runtime_fails(client, monkeypatch):
    def fail_runtime(cls, payload):
        raise FileNotFoundError("model artifact missing for test")

    monkeypatch.setattr(
        InferRepository,
        "_infer_with_runtime",
        classmethod(fail_runtime),
    )

    payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 12:00:00",
        "window_minutes": 30,
        "sample_index": 0,
        "mc_samples": 5,
    }

    response = client.post("/infer", json=payload)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["data_source"] == "mock_fallback"
    assert data["model_version"] == "mock"
    assert data["model_name"] == "mock"
    assert data["risk_raw_std"] == 0.0
    assert data["risk_std"] == 0.0
    assert data["calibration_enabled"] is False
    assert data["uncertainty_enabled"] is False
    assert data["runtime_error"] == "model artifact missing for test"


def test_infer_sample_index_out_of_range_is_request_error(client, monkeypatch):
    def fail_runtime(cls, payload):
        raise IndexError("sample_index 越界: sample_index=999999")

    monkeypatch.setattr(
        InferRepository,
        "_infer_with_runtime",
        classmethod(fail_runtime),
    )

    payload = {
        "device_id": 1001,
        "ts_end": "2026-05-09 12:00:00",
        "window_minutes": 30,
        "sample_index": 999999,
        "mc_samples": 5,
    }

    response = client.post("/infer", json=payload)

    assert response.status_code == 400
    assert "sample_index 越界" in response.get_json()["message"]
