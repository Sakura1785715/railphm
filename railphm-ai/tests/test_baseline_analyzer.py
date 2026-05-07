"""
BaselineAnalyzer 单元测试。

本测试使用 tmp_path 构造假的 baseline 训练输出目录和数据集统计目录，
不依赖真实 data 目录，不重新训练模型，也不加载 best_model.pt。
"""

import json

import pandas as pd
import pytest

from app.training.baseline_analyzer import BaselineAnalysisConfig, BaselineAnalyzer


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_fake_dataset_dir(dataset_dir):
    _write_json(
        dataset_dir / "dataset_summary.json",
        {
            "X_shape": [60, 4, 3],
            "y_shape": [60],
            "total_windows": 60,
            "positive_count": 30,
            "negative_count": 30,
            "positive_ratio": 0.5,
            "feature_dim": 3,
            "used_segment_count": 6,
            "skipped_segment_count": 0,
        },
    )

    _write_json(
        dataset_dir / "inspection_summary.json",
        {
            "is_valid": True,
            "errors": [],
            "warnings": ["不同 segment 的窗口样本数差异较大"],
        },
    )

    _write_json(
        dataset_dir / "splits" / "split_summary.json",
        {
            "train": {
                "sample_count": 40,
                "segment_count": 4,
                "positive_count": 20,
                "negative_count": 20,
                "positive_ratio": 0.5,
            },
            "val": {
                "sample_count": 10,
                "segment_count": 1,
                "positive_count": 5,
                "negative_count": 5,
                "positive_ratio": 0.5,
            },
            "test": {
                "sample_count": 10,
                "segment_count": 1,
                "positive_count": 5,
                "negative_count": 5,
                "positive_ratio": 0.5,
            },
            "leakage_check": {
                "has_segment_leakage": False,
            },
        },
    )


def _write_fake_run_dir(
    run_dir,
    dataset_dir,
    val_auc=0.75,
    val_f1=0.60,
    val_recall=0.60,
    test_auc=0.73,
    test_f1=0.58,
    test_recall=0.56,
    first_train_loss=0.70,
    last_train_loss=0.50,
):
    run_dir.mkdir(parents=True, exist_ok=True)

    baseline_report = {
        "task": "baseline_trainability_check",
        "model": {
            "name": "BaselineMLP",
            "input_dim": 12,
            "hidden_dims": [16, 8],
            "dropout": 0.1,
        },
        "dataset": {
            "dataset_dir": str(dataset_dir),
            "X_shape": [60, 4, 3],
            "y_shape": [60],
            "train_samples": 40,
            "val_samples": 10,
            "test_samples": 10,
        },
        "training": {
            "epochs": 2,
            "batch_size": 8,
            "lr": 0.001,
            "seed": 42,
            "device": "cpu",
            "threshold": 0.5,
            "best_epoch": 2,
            "best_metric": "val_f1",
            "best_metric_value": val_f1,
        },
        "train_metrics": {
            "loss": 0.45,
            "accuracy": 0.80,
            "precision": 0.80,
            "recall": 0.80,
            "f1": 0.80,
            "auc": 0.82,
            "brier_score": 0.18,
            "threshold": 0.5,
            "positive_count": 20,
            "negative_count": 20,
            "predicted_positive_count": 20,
            "predicted_negative_count": 20,
            "confusion_matrix": {"tn": 16, "fp": 4, "fn": 4, "tp": 16},
            "warnings": [],
        },
        "val_metrics": {
            "loss": 0.50,
            "accuracy": 0.70,
            "precision": 0.70,
            "recall": val_recall,
            "f1": val_f1,
            "auc": val_auc,
            "brier_score": 0.20,
            "threshold": 0.5,
            "positive_count": 5,
            "negative_count": 5,
            "predicted_positive_count": 5,
            "predicted_negative_count": 5,
            "confusion_matrix": {"tn": 4, "fp": 1, "fn": 2, "tp": 3},
            "warnings": [],
        },
        "test_metrics": {
            "loss": 0.52,
            "accuracy": 0.70,
            "precision": 0.70,
            "recall": test_recall,
            "f1": test_f1,
            "auc": test_auc,
            "brier_score": 0.21,
            "threshold": 0.5,
            "positive_count": 5,
            "negative_count": 5,
            "predicted_positive_count": 5,
            "predicted_negative_count": 5,
            "confusion_matrix": {"tn": 4, "fp": 1, "fn": 2, "tp": 3},
            "warnings": [],
        },
        "artifacts": {
            "best_model": "best_model.pt",
            "metrics_history": "metrics_history.csv",
            "test_predictions": "test_predictions.csv",
            "training_config": "training_config.json",
        },
        "notes": [],
    }

    _write_json(run_dir / "baseline_report.json", baseline_report)

    pd.DataFrame(
        [
            {
                "epoch": 1,
                "train_loss": first_train_loss,
                "val_loss": 0.60,
                "val_accuracy": 0.60,
                "val_precision": 0.60,
                "val_recall": max(val_recall - 0.1, 0.0),
                "val_f1": max(val_f1 - 0.1, 0.0),
                "val_auc": max(val_auc - 0.05, 0.0) if val_auc is not None else None,
                "val_brier_score": 0.24,
            },
            {
                "epoch": 2,
                "train_loss": last_train_loss,
                "val_loss": 0.50,
                "val_accuracy": 0.70,
                "val_precision": 0.70,
                "val_recall": val_recall,
                "val_f1": val_f1,
                "val_auc": val_auc,
                "val_brier_score": 0.20,
            },
        ]
    ).to_csv(run_dir / "metrics_history.csv", index=False)

    pd.DataFrame(
        {
            "sample_order": list(range(10)),
            "y_true": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
            "y_prob": [0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4, 0.9, 0.2, 0.8],
            "y_pred": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        }
    ).to_csv(run_dir / "test_predictions.csv", index=False)


def _prepare_case(tmp_path, **kwargs):
    dataset_dir = tmp_path / "dataset"
    run_dir = tmp_path / "outputs" / "baseline_mlp_toy"

    _write_fake_dataset_dir(dataset_dir)
    _write_fake_run_dir(run_dir, dataset_dir, **kwargs)

    return run_dir, dataset_dir


def test_analyze_baseline_success(tmp_path):
    run_dir, dataset_dir = _prepare_case(tmp_path)

    config = BaselineAnalysisConfig(
        run_dir=run_dir,
        dataset_dir=dataset_dir,
        overwrite=True,
    )

    analysis = BaselineAnalyzer().analyze(config)

    assert isinstance(analysis, dict)
    assert (run_dir / "baseline_analysis.json").exists()
    assert (run_dir / "baseline_analysis.md").exists()
    assert "trainability_judgement" in analysis
    assert "final_metrics" in analysis
    assert "dataset_summary" in analysis


def test_analyzer_generates_markdown_sections(tmp_path):
    run_dir, dataset_dir = _prepare_case(tmp_path)

    BaselineAnalyzer().analyze(
        BaselineAnalysisConfig(
            run_dir=run_dir,
            dataset_dir=dataset_dir,
            overwrite=True,
        )
    )

    content = (run_dir / "baseline_analysis.md").read_text(encoding="utf-8")

    assert "RailPHM Baseline 可训练性分析报告" in content
    assert "数据集概况" in content
    assert "数据划分情况" in content
    assert "最终评估指标" in content
    assert "可训练性结论" in content
    assert "风险与后续建议" in content


def test_trainability_pass(tmp_path):
    run_dir, dataset_dir = _prepare_case(
        tmp_path,
        val_auc=0.75,
        val_f1=0.60,
        test_auc=0.73,
        test_f1=0.58,
    )

    analysis = BaselineAnalyzer().analyze(
        BaselineAnalysisConfig(run_dir=run_dir, dataset_dir=dataset_dir)
    )

    judgement = analysis["trainability_judgement"]
    assert judgement["level"] == "pass"
    assert judgement["is_trainable"] is True


def test_trainability_weak_pass(tmp_path):
    run_dir, dataset_dir = _prepare_case(
        tmp_path,
        val_auc=0.62,
        val_f1=0.20,
        val_recall=0.15,
        test_auc=0.61,
        test_f1=0.20,
        test_recall=0.15,
    )

    analysis = BaselineAnalyzer().analyze(
        BaselineAnalysisConfig(run_dir=run_dir, dataset_dir=dataset_dir)
    )

    judgement = analysis["trainability_judgement"]
    assert judgement["level"] == "weak_pass"
    assert judgement["is_trainable"] is True
    assert any("F1" in risk or "Recall" in risk for risk in judgement["risks"])


def test_trainability_fail(tmp_path):
    run_dir, dataset_dir = _prepare_case(
        tmp_path,
        val_auc=0.50,
        val_f1=0.02,
        val_recall=0.0,
        test_auc=0.50,
        test_f1=0.02,
        test_recall=0.0,
        first_train_loss=0.60,
        last_train_loss=0.60,
    )

    analysis = BaselineAnalyzer().analyze(
        BaselineAnalysisConfig(run_dir=run_dir, dataset_dir=dataset_dir)
    )

    judgement = analysis["trainability_judgement"]
    assert judgement["level"] == "fail"
    assert judgement["is_trainable"] is False


def test_missing_required_run_file(tmp_path):
    run_dir, dataset_dir = _prepare_case(tmp_path)
    (run_dir / "baseline_report.json").unlink()

    with pytest.raises(FileNotFoundError, match="缺少训练结果文件: baseline_report.json"):
        BaselineAnalyzer().analyze(
            BaselineAnalysisConfig(run_dir=run_dir, dataset_dir=dataset_dir)
        )


def test_missing_metrics_history_file(tmp_path):
    run_dir, dataset_dir = _prepare_case(tmp_path)
    (run_dir / "metrics_history.csv").unlink()

    with pytest.raises(FileNotFoundError, match="缺少训练结果文件: metrics_history.csv"):
        BaselineAnalyzer().analyze(
            BaselineAnalysisConfig(run_dir=run_dir, dataset_dir=dataset_dir)
        )


def test_dataset_dir_from_report(tmp_path):
    run_dir, dataset_dir = _prepare_case(tmp_path)

    analysis = BaselineAnalyzer().analyze(
        BaselineAnalysisConfig(run_dir=run_dir, dataset_dir=None)
    )

    assert analysis["dataset_dir"] == str(dataset_dir)


def test_overwrite_false_reject_existing_outputs(tmp_path):
    run_dir, dataset_dir = _prepare_case(tmp_path)
    (run_dir / "baseline_analysis.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError, match="输出文件已存在"):
        BaselineAnalyzer().analyze(
            BaselineAnalysisConfig(
                run_dir=run_dir,
                dataset_dir=dataset_dir,
                overwrite=False,
            )
        )


def test_prediction_summary(tmp_path):
    run_dir, dataset_dir = _prepare_case(tmp_path)

    analysis = BaselineAnalyzer().analyze(
        BaselineAnalysisConfig(run_dir=run_dir, dataset_dir=dataset_dir)
    )

    summary = analysis["prediction_summary"]

    assert summary["test_prediction_rows"] == 10
    assert summary["y_prob_min"] == pytest.approx(0.1)
    assert summary["y_prob_max"] == pytest.approx(0.9)
    assert summary["y_prob_mean"] == pytest.approx(0.5)
    assert summary["predicted_positive_ratio"] == pytest.approx(0.5)