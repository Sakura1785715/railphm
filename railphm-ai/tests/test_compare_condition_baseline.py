import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "compare_condition_baseline.py"


def _metrics_from_probs(y_true, y_prob):
    y_true = np.asarray(y_true, dtype=np.int64)
    y_prob = np.asarray(y_prob, dtype=np.float64)
    y_pred = (y_prob >= 0.5).astype(np.int64)

    accuracy = float((y_pred == y_true).mean())
    precision = float(((y_pred == 1) & (y_true == 1)).sum() / max((y_pred == 1).sum(), 1))
    recall = float(((y_pred == 1) & (y_true == 1)).sum() / max((y_true == 1).sum(), 1))
    f1 = 0.0 if precision + recall == 0 else float(2 * precision * recall / (precision + recall))
    brier = float(np.mean((y_prob - y_true) ** 2))

    return {
        "loss": brier,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auc": 0.6,
        "brier_score": brier,
    }


def _write_baseline_run(run_dir: Path, y_true, y_prob, x_shape, input_dim):
    run_dir.mkdir(parents=True, exist_ok=True)

    y_true = np.asarray(y_true, dtype=np.int64)
    y_prob = np.asarray(y_prob, dtype=np.float64)
    y_pred = (y_prob >= 0.5).astype(np.int64)

    metrics = _metrics_from_probs(y_true, y_prob)
    report = {
        "model": {
            "name": "BaselineMLP",
            "input_dim": input_dim,
        },
        "dataset": {
            "dataset_dir": "dataset",
            "X_shape": list(x_shape),
            "y_shape": [len(y_true)],
        },
        "training": {
            "best_epoch": 2,
            "best_metric": "val_auc",
            "best_metric_value": 0.6,
        },
        "train_metrics": metrics,
        "val_metrics": metrics,
        "test_metrics": metrics,
    }

    (run_dir / "baseline_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    history = pd.DataFrame(
        [
            {
                "epoch": 1,
                "train_loss": 0.7,
                "val_loss": 0.68,
                "val_f1": 0.2,
                "val_auc": 0.55,
                "val_brier_score": 0.24,
            },
            {
                "epoch": 2,
                "train_loss": 0.6,
                "val_loss": 0.62,
                "val_f1": 0.3,
                "val_auc": 0.6,
                "val_brier_score": 0.22,
            },
        ]
    )
    history.to_csv(run_dir / "metrics_history.csv", index=False)

    predictions = pd.DataFrame(
        {
            "sample_order": list(range(len(y_true))),
            "y_true": y_true,
            "y_prob": y_prob,
            "y_pred": y_pred,
        }
    )
    predictions.to_csv(run_dir / "test_predictions.csv", index=False)


def _write_dataset(
    dataset_dir: Path,
    feature_dim: int,
    feature_columns,
    condition_labels=None,
    test_indices=None,
):
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "splits").mkdir(parents=True, exist_ok=True)

    X = np.zeros((6, 4, feature_dim), dtype=np.float32)
    y = np.array([0, 0, 1, 1, 0, 1], dtype=np.int64)

    np.save(dataset_dir / "X.npy", X)
    np.save(dataset_dir / "y.npy", y)

    (dataset_dir / "feature_columns.json").write_text(
        json.dumps(feature_columns, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    train_indices = np.array([0, 1], dtype=np.int64)
    val_indices = np.array([2, 3], dtype=np.int64)
    if test_indices is None:
        test_indices = np.array([0, 1, 2, 3, 4, 5], dtype=np.int64)

    np.save(dataset_dir / "splits" / "train_indices.npy", train_indices)
    np.save(dataset_dir / "splits" / "val_indices.npy", val_indices)
    np.save(dataset_dir / "splits" / "test_indices.npy", test_indices)

    if condition_labels is not None:
        np.save(dataset_dir / "condition_labels.npy", np.asarray(condition_labels, dtype=np.int64))

        condition_summary = {
            "n_clusters": 3,
            "condition_label_mapping": {
                "0": "高速巡航",
                "1": "进站减速",
                "2": "出站加速",
            },
            "cluster_sample_count": {
                "0": 2,
                "1": 2,
                "2": 2,
            },
            "cluster_positive_ratio": {
                "0": 0.0,
                "1": 1.0,
                "2": 0.5,
            },
        }
        (dataset_dir / "condition_summary.json").write_text(
            json.dumps(condition_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _write_full_compare_fixture(tmp_path: Path):
    baseline_a = tmp_path / "baseline_a"
    baseline_b = tmp_path / "baseline_b"
    dataset_a = tmp_path / "dataset_a"
    dataset_b = tmp_path / "dataset_b"

    y_true = np.array([0, 0, 1, 1, 0, 1], dtype=np.int64)
    y_prob_a = np.array([0.4, 0.45, 0.55, 0.6, 0.5, 0.52], dtype=np.float64)
    y_prob_b = np.array([0.2, 0.25, 0.8, 0.85, 0.3, 0.75], dtype=np.float64)

    _write_baseline_run(baseline_a, y_true, y_prob_a, x_shape=[6, 4, 3], input_dim=12)
    _write_baseline_run(baseline_b, y_true, y_prob_b, x_shape=[6, 4, 6], input_dim=24)

    _write_dataset(
        dataset_a,
        feature_dim=3,
        feature_columns=["speed", "mileage", "distance"],
    )
    _write_dataset(
        dataset_b,
        feature_dim=6,
        feature_columns=["speed", "mileage", "distance", "condition_0", "condition_1", "condition_2"],
        condition_labels=np.array([0, 0, 1, 1, 2, 2], dtype=np.int64),
    )

    return baseline_a, baseline_b, dataset_a, dataset_b


def _run_script(baseline_a: Path, baseline_b: Path, dataset_a: Path, dataset_b: Path, output_dir: Path, *extra_args: str):
    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--baseline-a",
        str(baseline_a),
        "--baseline-b",
        str(baseline_b),
        "--dataset-a",
        str(dataset_a),
        "--dataset-b",
        str(dataset_b),
        "--output-dir",
        str(output_dir),
        *extra_args,
    ]

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_compare_condition_baseline_success(tmp_path):
    baseline_a, baseline_b, dataset_a, dataset_b = _write_full_compare_fixture(tmp_path)
    output_dir = tmp_path / "compare"

    result = _run_script(baseline_a, baseline_b, dataset_a, dataset_b, output_dir, "--overwrite")

    assert result.returncode == 0, result.stderr
    assert (output_dir / "condition_baseline_compare.json").exists()
    assert (output_dir / "condition_baseline_compare.md").exists()

    report = json.loads((output_dir / "condition_baseline_compare.json").read_text(encoding="utf-8"))

    assert "metric_delta" in report
    assert "per_condition_test_metrics" in report
    assert "judgement" in report
    assert "artifacts" in report


def test_compare_condition_baseline_y_true_mismatch(tmp_path):
    baseline_a, baseline_b, dataset_a, dataset_b = _write_full_compare_fixture(tmp_path)

    predictions_b = pd.read_csv(baseline_b / "test_predictions.csv")
    predictions_b.loc[0, "y_true"] = 1
    predictions_b.to_csv(baseline_b / "test_predictions.csv", index=False)

    output_dir = tmp_path / "compare"
    result = _run_script(baseline_a, baseline_b, dataset_a, dataset_b, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "y_true" in result.stderr or "无法对比" in result.stderr


def test_compare_condition_baseline_test_indices_mismatch(tmp_path):
    baseline_a, baseline_b, dataset_a, dataset_b = _write_full_compare_fixture(tmp_path)

    np.save(dataset_b / "splits" / "test_indices.npy", np.array([0, 1, 2, 3, 5, 4], dtype=np.int64))

    output_dir = tmp_path / "compare"
    result = _run_script(baseline_a, baseline_b, dataset_a, dataset_b, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "test_indices" in result.stderr or "无法做按工况对比" in result.stderr


def test_compare_condition_baseline_missing_condition_labels(tmp_path):
    baseline_a, baseline_b, dataset_a, dataset_b = _write_full_compare_fixture(tmp_path)
    (dataset_b / "condition_labels.npy").unlink()

    output_dir = tmp_path / "compare"
    result = _run_script(baseline_a, baseline_b, dataset_a, dataset_b, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "condition_labels" in result.stderr


def test_compare_condition_baseline_per_condition_metrics_generated(tmp_path):
    baseline_a, baseline_b, dataset_a, dataset_b = _write_full_compare_fixture(tmp_path)
    output_dir = tmp_path / "compare"

    result = _run_script(baseline_a, baseline_b, dataset_a, dataset_b, output_dir, "--overwrite")

    assert result.returncode == 0, result.stderr

    report = json.loads((output_dir / "condition_baseline_compare.json").read_text(encoding="utf-8"))
    per_condition = report["per_condition_test_metrics"]

    assert set(per_condition.keys()) == {"0", "1", "2"}

    for metrics in per_condition.values():
        assert "sample_count" in metrics
        assert "positive_ratio" in metrics
        assert "baseline_a" in metrics
        assert "baseline_b" in metrics
        assert "delta" in metrics


def test_compare_condition_baseline_brier_improvement_direction(tmp_path):
    baseline_a, baseline_b, dataset_a, dataset_b = _write_full_compare_fixture(tmp_path)
    output_dir = tmp_path / "compare"

    result = _run_script(baseline_a, baseline_b, dataset_a, dataset_b, output_dir, "--overwrite")

    assert result.returncode == 0, result.stderr

    report = json.loads((output_dir / "condition_baseline_compare.json").read_text(encoding="utf-8"))
    assert report["metric_delta"]["test"]["brier_improvement"] > 0


def test_compare_condition_baseline_refuses_existing_output_without_overwrite(tmp_path):
    baseline_a, baseline_b, dataset_a, dataset_b = _write_full_compare_fixture(tmp_path)
    output_dir = tmp_path / "compare"
    output_dir.mkdir(parents=True)

    result = _run_script(baseline_a, baseline_b, dataset_a, dataset_b, output_dir)

    assert result.returncode != 0
    assert "output_dir 已存在" in result.stderr or "overwrite" in result.stderr