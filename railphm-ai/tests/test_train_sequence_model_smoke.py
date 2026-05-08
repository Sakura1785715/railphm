import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.training.train_sequence_model import SequenceTrainConfig, train_sequence_model


def _write_toy_sequence_dataset(root_dir: Path) -> dict:
    splits_dir = root_dir / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)

    num_samples = 48
    window_size = 10
    feature_dim = 6

    rng = np.random.default_rng(42)
    X = rng.normal(size=(num_samples, window_size, feature_dim)).astype(np.float32)

    # 构造同时包含 0/1 的简单标签，保证 train/val/test 中均有两类样本。
    y = np.array([index % 2 for index in range(num_samples)], dtype=np.int64)

    train_indices = np.arange(0, 32, dtype=np.int64)
    val_indices = np.arange(32, 40, dtype=np.int64)
    test_indices = np.arange(40, 48, dtype=np.int64)

    np.save(root_dir / "X.npy", X)
    np.save(root_dir / "y.npy", y)
    np.save(splits_dir / "train_indices.npy", train_indices)
    np.save(splits_dir / "val_indices.npy", val_indices)
    np.save(splits_dir / "test_indices.npy", test_indices)

    return {
        "X": X,
        "y": y,
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
    }


@pytest.mark.parametrize(
    "model_name",
    [
        "lstm",
        "bilstm",
        "lstm_attention",
        "bilstm_attention",
    ],
)
def test_train_sequence_model_smoke_for_all_models(tmp_path, model_name):
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / f"outputs_{model_name}"
    dataset_dir.mkdir(parents=True)

    expected = _write_toy_sequence_dataset(dataset_dir)

    config = SequenceTrainConfig(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        model=model_name,
        epochs=1,
        batch_size=8,
        lr=0.001,
        seed=42,
        device="cpu",
        threshold=0.5,
        hidden_dim=8,
        num_layers=1,
        dropout=0.1,
        num_workers=0,
        overwrite=True,
        best_metric="val_auc",
    )

    report = train_sequence_model(config)

    expected_files = [
        "best_model.pt",
        "metrics_history.csv",
        "test_predictions.csv",
        "training_config.json",
        "sequence_model_report.json",
    ]
    for filename in expected_files:
        assert (output_dir / filename).exists()

    report_path = output_dir / "sequence_model_report.json"
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["task"] == "sequence_model_training"
    assert saved_report["task"] == "sequence_model_training"
    assert saved_report["model"]["name"]
    assert saved_report["dataset"]["X_shape"] == [int(value) for value in expected["X"].shape]
    assert saved_report["dataset"]["y_shape"] == [int(value) for value in expected["y"].shape]
    assert saved_report["dataset"]["window_size"] == 10
    assert saved_report["dataset"]["feature_dim"] == 6

    assert "train_metrics" in saved_report
    assert "val_metrics" in saved_report
    assert "test_metrics" in saved_report

    predictions = pd.read_csv(output_dir / "test_predictions.csv")
    assert {"sample_order", "y_true", "y_prob", "y_pred"}.issubset(predictions.columns)
    assert len(predictions) == len(expected["test_indices"])

    history = pd.read_csv(output_dir / "metrics_history.csv")
    assert {"epoch", "train_loss", "val_loss", "val_f1", "val_auc"}.issubset(history.columns)
    assert len(history) == 1


@pytest.mark.parametrize(
    "field_name, bad_value, expected_message",
    [
        ("model", "unknown", "model"),
        ("epochs", 0, "epochs"),
        ("batch_size", 0, "batch_size"),
        ("hidden_dim", 0, "hidden_dim"),
        ("dropout", 1.0, "dropout"),
        ("threshold", 1.0, "threshold"),
        ("best_metric", "bad_metric", "best_metric"),
    ],
)
def test_train_sequence_model_rejects_invalid_config(
    tmp_path,
    field_name,
    bad_value,
    expected_message,
):
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "outputs"
    dataset_dir.mkdir(parents=True)
    _write_toy_sequence_dataset(dataset_dir)

    kwargs = {
        "dataset_dir": dataset_dir,
        "output_dir": output_dir,
        "model": "lstm",
        "epochs": 1,
        "batch_size": 8,
        "lr": 0.001,
        "seed": 42,
        "device": "cpu",
        "threshold": 0.5,
        "hidden_dim": 8,
        "num_layers": 1,
        "dropout": 0.1,
        "num_workers": 0,
        "overwrite": True,
        "best_metric": "val_auc",
    }
    kwargs[field_name] = bad_value

    with pytest.raises(ValueError, match=expected_message):
        train_sequence_model(SequenceTrainConfig(**kwargs))