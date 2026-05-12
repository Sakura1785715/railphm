"""
MLP baseline 训练流程 smoke test。

本测试使用 tmp_path 构造极小 toy dataset，不依赖真实 data 目录。
测试目标是验证 Task 4-4 的训练主流程能够在 CPU 上跑通，并生成必要产物：

- baseline_report.json
- metrics_history.csv
- training_config.json
- best_model.pt
- test_predictions.csv
"""

import json

import numpy as np
import pandas as pd
import pytest

from app.training.train_baseline import BaselineTrainConfig, train_baseline


def _write_toy_window_dataset(dataset_dir):
    splits_dir = dataset_dir / "splits"
    splits_dir.mkdir(parents=True)

    rng = np.random.default_rng(42)
    X = rng.random((60, 4, 3), dtype=np.float32)

    # 构造一个简单可学习模式：第 0 个特征在窗口内的均值超过 0.5 则为正类。
    y = (X[:, :, 0].mean(axis=1) > 0.5).astype(np.int64)

    train_indices = np.arange(0, 40, dtype=np.int64)
    val_indices = np.arange(40, 50, dtype=np.int64)
    test_indices = np.arange(50, 60, dtype=np.int64)

    np.save(dataset_dir / "X.npy", X)
    np.save(dataset_dir / "y.npy", y)
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


def _build_smoke_config(tmp_path, epochs=2, overwrite=True):
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "outputs" / "baseline_mlp_toy"

    _write_toy_window_dataset(dataset_dir)

    return BaselineTrainConfig(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        model="mlp",
        epochs=epochs,
        batch_size=8,
        lr=0.001,
        seed=42,
        device="cpu",
        threshold=0.5,
        hidden_dims=(16, 8),
        dropout=0.1,
        num_workers=0,
        overwrite=overwrite,
        best_metric="val_f1",
    )


def test_train_baseline_smoke_success(tmp_path):
    config = _build_smoke_config(tmp_path, epochs=2, overwrite=True)

    report = train_baseline(config)

    assert isinstance(report, dict)
    assert config.output_dir.exists()
    assert (config.output_dir / "baseline_report.json").exists()
    assert (config.output_dir / "metrics_history.csv").exists()
    assert (config.output_dir / "training_config.json").exists()
    assert (config.output_dir / "best_model.pt").exists()
    assert (config.output_dir / "test_predictions.csv").exists()


def test_train_baseline_report_contains_required_keys(tmp_path):
    config = _build_smoke_config(tmp_path, epochs=1, overwrite=True)

    train_baseline(config)

    with (config.output_dir / "baseline_report.json").open("r", encoding="utf-8") as file:
        report = json.load(file)

    required_keys = {
        "task",
        "model",
        "dataset",
        "training",
        "train_metrics",
        "val_metrics",
        "test_metrics",
        "artifacts",
    }

    assert required_keys.issubset(report.keys())


def test_metrics_history_has_epoch_rows(tmp_path):
    epochs = 2
    config = _build_smoke_config(tmp_path, epochs=epochs, overwrite=True)

    train_baseline(config)

    history = pd.read_csv(config.output_dir / "metrics_history.csv")

    assert len(history) == epochs

    required_columns = {
        "epoch",
        "train_loss",
        "val_loss",
        "val_accuracy",
        "val_precision",
        "val_recall",
        "val_f1",
        "val_auc",
        "val_brier_score",
    }

    assert required_columns.issubset(history.columns)


def test_test_predictions_has_required_columns(tmp_path):
    config = _build_smoke_config(tmp_path, epochs=1, overwrite=True)

    train_baseline(config)

    predictions = pd.read_csv(config.output_dir / "test_predictions.csv")

    required_columns = {
        "sample_order",
        "y_true",
        "y_prob",
        "y_pred",
    }

    assert required_columns.issubset(predictions.columns)
    assert len(predictions) == 10


def test_train_baseline_reject_existing_output_without_overwrite(tmp_path):
    config = _build_smoke_config(tmp_path, epochs=1, overwrite=False)
    config.output_dir.mkdir(parents=True)

    with pytest.raises(FileExistsError, match="输出目录已存在"):
        train_baseline(config)


def test_train_baseline_invalid_model(tmp_path):
    config = _build_smoke_config(tmp_path, epochs=1, overwrite=True)
    config.model = "unknown"

    with pytest.raises(ValueError, match="当前 baseline 训练仅支持 model='mlp'"):
        train_baseline(config)