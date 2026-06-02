from datetime import datetime, timedelta

from app.clients.ai_client import AIClient, AIServiceUnavailableError
from app.repository.monitor_repository import MonitorRepository
from app.repository.prediction_repository import PredictionRepository


OPS_HEADERS = {
    "Authorization": "Bearer mock-token-ops"
}


def _build_monitor_rows(count=91):
    base_dt = datetime(2026, 5, 18, 8, 59, 30)
    return [
        {
            "sample_time": (base_dt + timedelta(seconds=index)).strftime("%Y-%m-%d %H:%M:%S"),
            "device_code": "ATP001",
            "speed": 120,
            "mileage": 900 + index,
        }
        for index in range(count)
    ]


def _build_ai_range_result():
    return {
        "monitor_point_count": 91,
        "total_candidate_points": 2,
        "skipped_window_count": 0,
        "model_name": "bilstm_attention",
        "model_version": "bilstm_attention_h1_full_features",
        "calibration_enabled": True,
        "calibration_method": "isotonic_regression",
        "uncertainty_enabled": True,
        "uncertainty_method": "mc_dropout",
        "results": [
            {
                "time": "2026-05-18 09:00:00",
                "window_start_time": "2026-05-18 08:59:31",
                "window_end_time": "2026-05-18 09:00:00",
                "risk_raw": 0.31,
                "risk_score": 0.28,
                "risk_raw_std": 0.02,
                "risk_std": 0.015,
                "threshold": 0.58,
                "predicted_label": 0,
                "model_name": "bilstm_attention",
                "model_version": "bilstm_attention_h1_full_features",
                "calibration_enabled": True,
                "calibration_method": "isotonic_regression",
                "uncertainty_enabled": True,
                "uncertainty_method": "mc_dropout",
                "mc_samples": 20,
                "condition_label": "stable",
                "data_source": "influxdb_online_range",
                "trace": {},
            },
            {
                "time": "2026-05-18 09:01:00",
                "window_start_time": "2026-05-18 09:00:31",
                "window_end_time": "2026-05-18 09:01:00",
                "risk_raw": 0.6,
                "risk_score": 0.61,
                "risk_raw_std": 0.03,
                "risk_std": 0.02,
                "threshold": 0.58,
                "predicted_label": 1,
                "model_name": "bilstm_attention",
                "model_version": "bilstm_attention_h1_full_features",
                "calibration_enabled": True,
                "calibration_method": "isotonic_regression",
                "uncertainty_enabled": True,
                "uncertainty_method": "mc_dropout",
                "mc_samples": 20,
                "condition_label": "stable",
                "data_source": "influxdb_online_range",
                "trace": {},
            },
        ],
        "skipped_windows": [],
    }


def test_prediction_range_infer_success_and_persist(client, monkeypatch):
    captured = {}

    def fake_query(cls, **kwargs):
        captured["fields"] = kwargs["fields"]
        captured["start_dt"] = kwargs["start_dt"]
        captured["end_dt"] = kwargs["end_dt"]
        return _build_monitor_rows()

    def fake_infer_range(self, payload):
        captured["ai_payload"] = payload
        return _build_ai_range_result()

    monkeypatch.setattr(MonitorRepository, "query_history_by_device_and_range", classmethod(fake_query))
    monkeypatch.setattr(AIClient, "infer_range", fake_infer_range)
    monkeypatch.setattr(
        PredictionRepository,
        "get_existing_by_device_window",
        classmethod(lambda cls, *args, **kwargs: None),
    )
    monkeypatch.setattr(
        PredictionRepository,
        "save_infer_result",
        classmethod(
            lambda cls, record: {
                "risk_result_id": 1000 if record["window_end_time"].endswith("00:00") else 1001,
                "device_id": 1,
                "device_code": record["device_code"],
            }
        ),
    )

    response = client.post(
        "/api/v1/predictions/range-infer",
        headers=OPS_HEADERS,
        json={
            "device_code": "ATP001",
            "start_time": "2026-05-18 09:00:00",
            "end_time": "2026-05-18 09:01:00",
            "inference_stride_seconds": 60,
            "mc_samples": 20,
            "persist": True,
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert captured["fields"] == list(MonitorRepository.FIELD_COLUMNS)
    assert captured["start_dt"].strftime("%Y-%m-%d %H:%M:%S") == "2026-05-18 08:59:30"
    assert captured["end_dt"].strftime("%Y-%m-%d %H:%M:%S") == "2026-05-18 09:01:01"
    assert captured["ai_payload"]["device_id"] == 1
    assert len(captured["ai_payload"]["monitor_rows"]) == 91
    assert data["result_count"] == 2
    assert data["saved_count"] == 2
    assert data["skipped_existing_count"] == 0
    assert data["risk_series"][0]["risk_result_id"] == 1000
    assert data["risk_series"][0]["health_score"] == 72.0
    assert data["health_series"][1]["health_level"] == "warning"


def test_prediction_range_infer_skips_existing_rows(client, monkeypatch):
    monkeypatch.setattr(
        MonitorRepository,
        "query_history_by_device_and_range",
        classmethod(lambda cls, **kwargs: _build_monitor_rows()),
    )
    monkeypatch.setattr(AIClient, "infer_range", lambda self, payload: _build_ai_range_result())
    monkeypatch.setattr(
        PredictionRepository,
        "get_existing_by_device_window",
        classmethod(lambda cls, *args, **kwargs: {"risk_result_id": 123}),
    )
    monkeypatch.setattr(
        PredictionRepository,
        "save_infer_result",
        classmethod(lambda cls, record: (_ for _ in ()).throw(AssertionError("should not save"))),
    )

    response = client.post(
        "/api/v1/predictions/range-infer",
        headers=OPS_HEADERS,
        json={
            "device_code": "ATP001",
            "start_time": "2026-05-18 09:00:00",
            "end_time": "2026-05-18 09:01:00",
            "persist": True,
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["saved_count"] == 0
    assert data["skipped_existing_count"] == 2
    assert data["risk_series"][0]["risk_result_id"] == 123
    assert data["risk_series"][0]["persist_status"] == "skipped_existing"


def test_prediction_range_infer_boundaries(client):
    response = client.post(
        "/api/v1/predictions/range-infer",
        headers=OPS_HEADERS,
        json={
            "device_code": "ATP001",
            "start_time": "2026-05-18 10:00:00",
            "end_time": "2026-05-18 10:00:00",
        },
    )
    assert response.status_code == 400
    assert "start_time 必须早于 end_time" in response.get_json()["message"]

    response = client.post(
        "/api/v1/predictions/range-infer",
        headers=OPS_HEADERS,
        json={
            "device_code": "ATP001",
            "end_time": "2026-05-18 10:00:00",
            "lookback_minutes": 181,
        },
    )
    assert response.status_code == 400
    assert "lookback_minutes 不能超过" in response.get_json()["message"]


def test_prediction_range_infer_ai_unavailable(client, monkeypatch):
    monkeypatch.setattr(
        MonitorRepository,
        "query_history_by_device_and_range",
        classmethod(lambda cls, **kwargs: _build_monitor_rows()),
    )
    monkeypatch.setattr(
        AIClient,
        "infer_range",
        lambda self, payload: (_ for _ in ()).throw(AIServiceUnavailableError()),
    )

    response = client.post(
        "/api/v1/predictions/range-infer",
        headers=OPS_HEADERS,
        json={
            "device_code": "ATP001",
            "end_time": "2026-05-18 10:00:00",
            "lookback_minutes": 60,
        },
    )

    assert response.status_code == 502
    assert response.get_json()["message"] == "AI 推理服务不可用"
