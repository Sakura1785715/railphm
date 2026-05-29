import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.repository.infer_repository import InferRepository
from app.runtime.online_scaler import OnlineScalerLoader


def _build_monitor_rows(count=90):
    base_dt = datetime(2026, 5, 18, 8, 59, 31)
    rows = []
    for index in range(count):
        sample_dt = base_dt + timedelta(seconds=index)
        rows.append(
            {
                "sample_time": sample_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "device_code": "ATP001",
                "speed": 120 + index % 3,
                "mileage": 900 + index,
                "line_id": 3008,
                "direction": 2,
                "balise_id": 1316 + index,
                "balise_mileage": 1548 + index,
                "signal_id": 1482 + index,
                "signal_mileage": 1548 + index,
                "outdoor_temperature": 21.5,
                "humidity": 45,
                "condition_label": "stable",
            }
        )
    return rows


def _patch_fake_runtime(monkeypatch):
    runtime_feature_columns = json.loads(
        Path("outputs/sequence_models/bilstm_attention_h1_synthetic_v3/feature_columns.json")
        .read_text(encoding="utf-8")
    )
    dataset_dir = str(
        Path("data/datasets/bilstm_attention_h1_synthetic_v3/scaled_window_w30_s1_h1")
        .resolve()
    )

    class FakeRuntime:
        window_size = 30
        feature_dim = len(runtime_feature_columns)
        feature_columns = runtime_feature_columns
        model_name = "bilstm_attention"
        model_version = "fake-version"
        calibration_enabled = True
        calibration_method = "isotonic_regression"
        uncertainty_enabled = True
        uncertainty_method = "mc_dropout"
        manifest = SimpleNamespace(dataset_dir=dataset_dir, model_dir=Path("."))

        def predict_with_uncertainty(self, window, mc_samples=20):
            assert window.shape == (30, len(runtime_feature_columns))
            return {
                "risk_raw": 0.31,
                "risk_score": 0.28,
                "risk_raw_std": 0.02,
                "risk_std": 0.015,
                "threshold": 0.58,
                "predicted_label": 0,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "calibration_enabled": self.calibration_enabled,
                "calibration_method": self.calibration_method,
                "uncertainty_enabled": self.uncertainty_enabled,
                "uncertainty_method": self.uncertainty_method,
                "mc_samples": mc_samples,
            }

    OnlineScalerLoader._cache.clear()
    monkeypatch.setattr(InferRepository, "_get_runtime", classmethod(lambda cls: FakeRuntime()))


def test_range_infer_builds_online_windows_and_uses_feature_processor(client, monkeypatch):
    _patch_fake_runtime(monkeypatch)

    response = client.post(
        "/infer/range",
        json={
            "device_id": 1,
            "device_code": "ATP001",
            "start_time": "2026-05-18 09:00:00",
            "end_time": "2026-05-18 09:01:00",
            "inference_stride_seconds": 60,
            "mc_samples": 2,
            "monitor_rows": _build_monitor_rows(),
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["result_count"] == 2
    assert data["skipped_window_count"] == 0
    first_result = data["results"][0]
    assert first_result["window_start_time"] == "2026-05-18 08:59:31"
    assert first_result["window_end_time"] == "2026-05-18 09:00:00"
    assert first_result["risk_score"] == 0.28
    assert first_result["trace"]["feature_adapter"] == "monitor_rows_to_feature_processor"
    assert first_result["trace"]["scaler_applied"] is True
    assert first_result["trace"]["scaler_mode"] == "partial"
    assert "condition_0" in first_result["trace"]["missing_feature_columns"]


def test_range_infer_skips_insufficient_window(client, monkeypatch):
    _patch_fake_runtime(monkeypatch)

    response = client.post(
        "/infer/range",
        json={
            "device_id": 1,
            "device_code": "ATP001",
            "start_time": "2026-05-18 09:00:00",
            "end_time": "2026-05-18 09:00:00",
            "monitor_rows": _build_monitor_rows(count=10),
        },
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["result_count"] == 0
    assert data["skipped_window_count"] == 1
    assert data["skipped_windows"][0]["reason"] == "insufficient_monitor_points"
