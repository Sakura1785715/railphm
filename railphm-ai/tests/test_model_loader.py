from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from app.models import build_sequence_model
from app.runtime.model_loader import (
    SequenceModelRuntime,
    load_feature_columns,
    resolve_runtime_device,
)


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_feature_columns(count: int = 23) -> list[str]:
    if count < 3:
        return [f"feature_{index}" for index in range(count)]

    base_count = count - 3
    return [f"feature_{index}" for index in range(base_count)] + [
        "condition_0",
        "condition_1",
        "condition_2",
    ]


def make_manifest_data(
    *,
    model_dir_name: str,
    hidden_dim: int = 8,
    dropout: float = 0.1,
    feature_dim: int = 23,
    feature_columns_count: int = 23,
    threshold: float = 0.26,
) -> dict:
    return {
        "model_version": model_dir_name,
        "model_name": "bilstm_attention",
        "model_class": "BiLSTMAttentionClassifier",
        "window_size": 30,
        "feature_dim": feature_dim,
        "input_dim": feature_dim,
        "hidden_dim": hidden_dim,
        "num_layers": 1,
        "dropout": dropout,
        "threshold": threshold,
        "dataset_dir": "data/datasets/test_dataset",
        "output_dir": f"outputs/sequence_models/{model_dir_name}",
        "feature_columns_count": feature_columns_count,
        "artifacts": {
            "model_weight": "best_model.pt",
            "training_config": "training_config.json",
            "sequence_model_report": "sequence_model_report.json",
            "threshold_summary": "threshold_summary.json",
            "evaluation_summary": "evaluation_summary.json",
            "metrics_history": "metrics_history.csv",
            "val_predictions": "val_predictions.csv",
            "test_predictions": "test_predictions.csv",
            "feature_columns": "feature_columns.json",
        },
        "checks": {
            "required_files_exist": True,
            "feature_dim_matches_feature_columns": True,
            "threshold_in_valid_range": True,
        },
    }


def make_model_dir(
    tmp_path: Path,
    *,
    hidden_dim: int = 8,
    dropout: float = 0.1,
    feature_dim: int = 23,
    feature_columns: list[str] | None = None,
    checkpoint: dict | None = None,
) -> Path:
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    feature_columns = (
        feature_columns
        if feature_columns is not None
        else make_feature_columns(feature_dim)
    )

    write_json(
        model_dir / "training_config.json",
        {
            "model": "bilstm_attention",
            "dataset_dir": "data/datasets/test_dataset",
            "output_dir": f"outputs/sequence_models/{model_dir.name}",
            "window_size": 30,
            "feature_dim": feature_dim,
            "input_dim": feature_dim,
            "hidden_dim": hidden_dim,
            "num_layers": 1,
            "dropout": dropout,
            "model_config": {
                "name": "BiLSTMAttentionClassifier",
            },
        },
    )

    write_json(
        model_dir / "sequence_model_report.json",
        {
            "model": {
                "name": "BiLSTMAttentionClassifier",
            }
        },
    )

    write_json(
        model_dir / "threshold_summary.json",
        {
            "best_threshold": 0.26,
            "search_on": "val",
            "metric": "f1",
        },
    )

    write_json(model_dir / "evaluation_summary.json", {"task": "evaluation"})
    write_json(model_dir / "feature_columns.json", feature_columns)

    write_json(
        model_dir / "model_artifact_manifest.json",
        make_manifest_data(
            model_dir_name=model_dir.name,
            hidden_dim=hidden_dim,
            dropout=dropout,
            feature_dim=feature_dim,
            feature_columns_count=feature_dim,
        ),
    )

    if checkpoint is None:
        model = build_sequence_model(
            model_name="bilstm_attention",
            input_dim=feature_dim,
            hidden_dim=hidden_dim,
            num_layers=1,
            dropout=dropout,
        )
        checkpoint = {
            "model_state_dict": model.state_dict(),
            "model_config": model.get_config(),
            "epoch": 1,
            "best_metric": "val_auc",
            "best_metric_value": 0.5,
        }

    torch.save(checkpoint, model_dir / "best_model.pt")

    return model_dir


def test_resolve_runtime_device_cpu() -> None:
    device = resolve_runtime_device("cpu")

    assert device == torch.device("cpu")


def test_resolve_runtime_device_invalid() -> None:
    with pytest.raises(ValueError, match="device"):
        resolve_runtime_device("bad-device")


def test_load_feature_columns_success(tmp_path: Path) -> None:
    path = tmp_path / "feature_columns.json"
    write_json(path, ["速度", "里程", "condition_0"])

    cols = load_feature_columns(path)

    assert cols == ["速度", "里程", "condition_0"]


def test_load_feature_columns_invalid_type(tmp_path: Path) -> None:
    path = tmp_path / "feature_columns.json"
    write_json(path, {"bad": "value"})

    with pytest.raises(ValueError, match="feature_columns"):
        load_feature_columns(path)


def test_sequence_model_runtime_load_success(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)

    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    assert runtime.model_version == model_dir.name
    assert runtime.model_name == "bilstm_attention"
    assert runtime.model_class == "BiLSTMAttentionClassifier"
    assert runtime.window_size == 30
    assert runtime.feature_dim == 23
    assert runtime.threshold == 0.26
    assert len(runtime.feature_columns) == 23
    assert runtime.device == torch.device("cpu")
    assert runtime.model.training is False

    summary = runtime.summary()
    assert summary["model_version"] == model_dir.name
    assert summary["model_name"] == "bilstm_attention"
    assert summary["model_class"] == "BiLSTMAttentionClassifier"
    assert summary["window_size"] == 30
    assert summary["feature_dim"] == 23
    assert summary["threshold"] == 0.26
    assert summary["device"] == "cpu"
    assert summary["feature_columns_count"] == 23


def test_sequence_model_runtime_missing_state_dict(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path, checkpoint={"bad": "value"})

    with pytest.raises(ValueError, match="model_state_dict"):
        SequenceModelRuntime.from_model_dir(model_dir, device="cpu")


def test_sequence_model_runtime_feature_columns_mismatch(tmp_path: Path) -> None:
    model_dir = make_model_dir(
        tmp_path,
        feature_dim=23,
        feature_columns=make_feature_columns(22),
    )

    with pytest.raises(ValueError, match="feature_columns"):
        SequenceModelRuntime.from_model_dir(model_dir, device="cpu")


def test_predict_proba_success(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.random.randn(30, 23).astype("float32")

    result = runtime.predict_proba(window)

    assert 0 <= result["risk_raw"] <= 1
    assert 0 <= result["risk_score"] <= 1
    assert result["risk_score"] == result["risk_raw"]
    assert result["threshold"] == 0.26
    assert result["predicted_label"] in {0, 1}
    assert result["model_version"] == runtime.model_version
    assert result["model_name"] == runtime.model_name
    assert result["window_size"] == 30
    assert result["feature_dim"] == 23
    assert runtime.model.training is False


def test_predict_proba_rejects_non_numpy(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    with pytest.raises(ValueError, match="numpy.ndarray"):
        runtime.predict_proba([[0.0] * 23 for _ in range(30)])


def test_predict_proba_rejects_wrong_ndim(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((1, 30, 23), dtype=np.float32)

    with pytest.raises(ValueError, match="2D"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_wrong_window_size(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((20, 23), dtype=np.float32)

    with pytest.raises(ValueError, match="shape mismatch"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_wrong_feature_dim(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((30, 22), dtype=np.float32)

    with pytest.raises(ValueError, match="shape mismatch"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_nan(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((30, 23), dtype=np.float32)
    window[0, 0] = np.nan

    with pytest.raises(ValueError, match="NaN or inf"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_inf(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((30, 23), dtype=np.float32)
    window[0, 0] = np.inf

    with pytest.raises(ValueError, match="NaN or inf"):
        runtime.predict_proba(window)