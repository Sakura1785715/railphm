"""
fit_probability_calibrator.py 脚本轻量测试。

本测试使用 tmp_path 构造临时模型目录和预测 CSV，不依赖真实 outputs 目录，
不依赖真实 best_model.pt，也不修改真实训练产物。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from scripts.fit_probability_calibrator import run


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_prediction_csv(path: Path) -> None:
    df = pd.DataFrame(
        {
            "sample_order": [0, 1, 2, 3, 4, 5],
            "y_true": [0, 0, 0, 1, 1, 1],
            "y_prob": [0.05, 0.20, 0.35, 0.55, 0.75, 0.90],
            "y_pred_05": [0, 0, 0, 1, 1, 1],
        }
    )
    df.to_csv(path, index=False, encoding="utf-8-sig")


def make_args(model_dir: Path, *, update_manifest: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        model_dir=model_dir,
        val_predictions=None,
        test_predictions=None,
        output_dir=None,
        overwrite=True,
        update_manifest=update_manifest,
    )


def test_fit_probability_calibrator_generates_outputs(tmp_path: Path) -> None:
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    write_prediction_csv(model_dir / "val_predictions.csv")
    write_prediction_csv(model_dir / "test_predictions.csv")

    write_json(
        model_dir / "threshold_summary.json",
        {
            "best_threshold": 0.26,
            "search_on": "val",
            "metric": "f1",
        },
    )

    summary = run(make_args(model_dir))

    assert (model_dir / "calibrator.pkl").exists()
    assert (model_dir / "calibration_summary.json").exists()
    assert (model_dir / "calibrated_val_predictions.csv").exists()
    assert (model_dir / "calibrated_test_predictions.csv").exists()

    assert summary["calibration_method"] == "isotonic_regression"
    assert summary["fit_split"] == "val"
    assert "brier_score" in summary["val_before"]
    assert "brier_score" in summary["val_after"]
    assert "auc" in summary["test_before"]
    assert "auc" in summary["test_after"]

    calibrated_val = pd.read_csv(model_dir / "calibrated_val_predictions.csv")
    assert "y_prob_raw" in calibrated_val.columns
    assert "y_prob_calibrated" in calibrated_val.columns


def test_fit_probability_calibrator_updates_manifest(tmp_path: Path) -> None:
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    write_prediction_csv(model_dir / "val_predictions.csv")
    write_prediction_csv(model_dir / "test_predictions.csv")
    write_json(model_dir / "threshold_summary.json", {"best_threshold": 0.26})

    write_json(
        model_dir / "model_artifact_manifest.json",
        {
            "model_version": "bilstm_attention_h1_full_features",
            "artifacts": {
                "model_weight": "best_model.pt",
            },
        },
    )

    run(make_args(model_dir, update_manifest=True))

    manifest = json.loads(
        (model_dir / "model_artifact_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["calibration"]["enabled"] is True
    assert manifest["calibration"]["method"] == "isotonic_regression"
    assert manifest["calibration"]["calibrator"] == "calibrator.pkl"
    assert manifest["calibration"]["summary"] == "calibration_summary.json"
    assert manifest["artifacts"]["model_weight"] == "best_model.pt"