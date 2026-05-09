from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_model_artifact_manifest import (  # noqa: E402
    ManifestBuildError,
    build_manifest,
    save_manifest,
)


FEATURE_COLUMNS_23 = [
    "速度",
    "里程",
    "运行距离",
    "行别",
    "线路编号",
    "应答器编号",
    "应答器里程",
    "行别.1",
    "线路编号.1",
    "信号机ID",
    "信号机里程",
    "行别.2",
    "线路编号.2",
    "信号机ID.1",
    "信号机里程.1",
    "行别.3",
    "线路编号.3",
    "运行方向",
    "室外温度",
    "湿度",
    "condition_0",
    "condition_1",
    "condition_2",
]


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_model_dir(
    tmp_path: Path,
    *,
    feature_columns: list[str] | None = None,
    threshold: float = 0.26,
    include_feature_columns: bool = True,
) -> Path:
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    (model_dir / "best_model.pt").write_bytes(b"")

    write_json(
        model_dir / "training_config.json",
        {
            "dataset_dir": "data/datasets/bilstm_attention_h1_full_features/train_scaled_condition_k3",
            "output_dir": "outputs/sequence_models/bilstm_attention_h1_full_features",
            "model": "bilstm_attention",
            "window_size": 30,
            "feature_dim": 23,
            "input_dim": 23,
            "hidden_dim": 64,
            "num_layers": 1,
            "dropout": 0.3,
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
            "best_threshold": threshold,
            "search_on": "val",
            "metric": "f1",
        },
    )

    write_json(
        model_dir / "evaluation_summary.json",
        {
            "task": "test_evaluation",
        },
    )

    if include_feature_columns:
        write_json(
            model_dir / "feature_columns.json",
            feature_columns if feature_columns is not None else FEATURE_COLUMNS_23,
        )

    return model_dir


def test_build_manifest_success(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)

    manifest = build_manifest(model_dir)

    assert manifest["model_version"] == "bilstm_attention_h1_full_features"
    assert manifest["model_name"] == "bilstm_attention"
    assert manifest["model_class"] == "BiLSTMAttentionClassifier"
    assert manifest["window_size"] == 30
    assert manifest["feature_dim"] == 23
    assert manifest["input_dim"] == 23
    assert manifest["hidden_dim"] == 64
    assert manifest["num_layers"] == 1
    assert manifest["dropout"] == 0.3
    assert manifest["threshold"] == 0.26
    assert manifest["threshold_source"] == "validation_best_f1"
    assert manifest["feature_columns_count"] == 23
    assert manifest["condition_feature_columns"] == [
        "condition_0",
        "condition_1",
        "condition_2",
    ]
    assert manifest["checks"]["required_files_exist"] is True
    assert manifest["checks"]["feature_dim_matches_feature_columns"] is True
    assert manifest["checks"]["threshold_in_valid_range"] is True


def test_build_manifest_fails_when_feature_columns_missing(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path, include_feature_columns=False)

    with pytest.raises(ManifestBuildError, match="feature_columns.json"):
        build_manifest(model_dir)


def test_build_manifest_fails_when_feature_count_mismatch(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path, feature_columns=FEATURE_COLUMNS_23[:-1])

    with pytest.raises(ManifestBuildError, match="feature_columns 数量"):
        build_manifest(model_dir)


def test_build_manifest_fails_when_threshold_invalid(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path, threshold=1.2)

    with pytest.raises(ManifestBuildError, match="threshold"):
        build_manifest(model_dir)


def test_save_manifest_fails_without_overwrite_when_file_exists(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    manifest = build_manifest(model_dir)

    manifest_path = model_dir / "model_artifact_manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ManifestBuildError, match="已存在"):
        save_manifest(manifest_path, manifest, overwrite=False)