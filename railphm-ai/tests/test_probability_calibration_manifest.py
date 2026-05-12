"""
概率校准 manifest 写入测试。

本测试只验证 calibration 字段写入逻辑，不依赖真实模型、不加载 best_model.pt，
不重新拟合校准器，也不修改真实训练产物。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.fit_probability_calibrator import update_manifest_calibration


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def touch(path: Path) -> None:
    path.write_text("placeholder", encoding="utf-8")


def make_model_dir(tmp_path: Path) -> Path:
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    write_json(
        model_dir / "model_artifact_manifest.json",
        {
            "model_version": "bilstm_attention_h1_full_features",
            "model_name": "bilstm_attention",
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
        },
    )

    touch(model_dir / "calibrator.pkl")
    touch(model_dir / "calibration_summary.json")
    touch(model_dir / "calibrated_val_predictions.csv")
    touch(model_dir / "calibrated_test_predictions.csv")

    return model_dir


def test_update_manifest_calibration_success(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)

    update_manifest_calibration(model_dir)

    manifest = json.loads(
        (model_dir / "model_artifact_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["model_version"] == "bilstm_attention_h1_full_features"
    assert manifest["model_name"] == "bilstm_attention"
    assert manifest["artifacts"]["model_weight"] == "best_model.pt"

    calibration = manifest["calibration"]
    assert calibration["enabled"] is True
    assert calibration["method"] == "isotonic_regression"
    assert calibration["calibrator"] == "calibrator.pkl"
    assert calibration["summary"] == "calibration_summary.json"
    assert calibration["fit_split"] == "val"
    assert calibration["calibrated_val_predictions"] == "calibrated_val_predictions.csv"
    assert calibration["calibrated_test_predictions"] == "calibrated_test_predictions.csv"


def test_update_manifest_calibration_fails_when_manifest_missing(tmp_path: Path) -> None:
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    touch(model_dir / "calibrator.pkl")
    touch(model_dir / "calibration_summary.json")
    touch(model_dir / "calibrated_val_predictions.csv")
    touch(model_dir / "calibrated_test_predictions.csv")

    with pytest.raises(FileNotFoundError, match="model_artifact_manifest.json"):
        update_manifest_calibration(model_dir)


def test_update_manifest_calibration_fails_when_calibrator_missing(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    (model_dir / "calibrator.pkl").unlink()

    with pytest.raises(FileNotFoundError, match="calibrator.pkl"):
        update_manifest_calibration(model_dir)


def test_update_manifest_calibration_fails_when_summary_missing(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    (model_dir / "calibration_summary.json").unlink()

    with pytest.raises(FileNotFoundError, match="calibration_summary.json"):
        update_manifest_calibration(model_dir)