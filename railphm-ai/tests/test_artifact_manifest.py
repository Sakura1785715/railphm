from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.runtime.artifact_manifest import ArtifactManifest


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_manifest_data(**overrides):
    data = {
        "model_version": "bilstm_attention_h1_full_features",
        "model_name": "bilstm_attention",
        "model_class": "BiLSTMAttentionClassifier",
        "window_size": 30,
        "feature_dim": 23,
        "input_dim": 23,
        "hidden_dim": 64,
        "num_layers": 1,
        "dropout": 0.3,
        "threshold": 0.26,
        "dataset_dir": "data/datasets/bilstm_attention_h1_full_features/train_scaled_condition_k3",
        "output_dir": "outputs/sequence_models/bilstm_attention_h1_full_features",
        "feature_columns_count": 23,
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

    data.update(overrides)
    return data


def make_model_dir(
    tmp_path: Path,
    *,
    manifest_data: dict | None = None,
    write_manifest: bool = True,
    missing_files: set[str] | None = None,
) -> Path:
    missing_files = missing_files or set()
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    files = [
        "best_model.pt",
        "training_config.json",
        "sequence_model_report.json",
        "threshold_summary.json",
        "feature_columns.json",
    ]

    for file_name in files:
        if file_name in missing_files:
            continue

        path = model_dir / file_name
        if file_name.endswith(".pt"):
            path.write_bytes(b"")
        else:
            write_json(path, {})

    if write_manifest:
        write_json(
            model_dir / "model_artifact_manifest.json",
            manifest_data if manifest_data is not None else make_manifest_data(),
        )

    return model_dir


def test_load_manifest_success(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)

    manifest = ArtifactManifest.load(model_dir)

    assert manifest.model_version == "bilstm_attention_h1_full_features"
    assert manifest.model_name == "bilstm_attention"
    assert manifest.model_class == "BiLSTMAttentionClassifier"
    assert manifest.window_size == 30
    assert manifest.feature_dim == 23
    assert manifest.input_dim == 23
    assert manifest.hidden_dim == 64
    assert manifest.num_layers == 1
    assert manifest.dropout == 0.3
    assert manifest.threshold == 0.26
    assert manifest.feature_columns_count == 23


def test_get_path_success(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    manifest = ArtifactManifest.load(model_dir)

    assert manifest.get_path("model_weight").name == "best_model.pt"
    assert manifest.get_path("feature_columns").name == "feature_columns.json"


def test_summary_contains_key_paths(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    manifest = ArtifactManifest.load(model_dir)

    summary = manifest.summary()

    assert summary["model_version"] == "bilstm_attention_h1_full_features"
    assert summary["model_name"] == "bilstm_attention"
    assert summary["model_class"] == "BiLSTMAttentionClassifier"
    assert summary["window_size"] == 30
    assert summary["feature_dim"] == 23
    assert summary["threshold"] == 0.26
    assert summary["model_weight_path"].endswith("best_model.pt")
    assert summary["feature_columns_path"].endswith("feature_columns.json")


def test_load_fails_when_manifest_missing(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path, write_manifest=False)

    with pytest.raises(FileNotFoundError, match="model_artifact_manifest.json"):
        ArtifactManifest.load(model_dir)


def test_load_fails_when_required_field_missing(tmp_path: Path) -> None:
    data = make_manifest_data()
    data.pop("model_name")

    model_dir = make_model_dir(tmp_path, manifest_data=data)

    with pytest.raises(ValueError, match="model_name"):
        ArtifactManifest.load(model_dir)


def test_load_fails_when_feature_columns_count_mismatch(tmp_path: Path) -> None:
    data = make_manifest_data(feature_columns_count=22)

    model_dir = make_model_dir(tmp_path, manifest_data=data)

    with pytest.raises(ValueError, match="feature_columns_count"):
        ArtifactManifest.load(model_dir)


def test_load_fails_when_threshold_invalid(tmp_path: Path) -> None:
    data = make_manifest_data(threshold=1.5)

    model_dir = make_model_dir(tmp_path, manifest_data=data)

    with pytest.raises(ValueError, match="threshold"):
        ArtifactManifest.load(model_dir)


def test_load_fails_when_required_artifact_key_missing(tmp_path: Path) -> None:
    data = make_manifest_data()
    data["artifacts"].pop("model_weight")

    model_dir = make_model_dir(tmp_path, manifest_data=data)

    with pytest.raises(ValueError, match="model_weight"):
        ArtifactManifest.load(model_dir)


def test_load_fails_when_required_artifact_file_missing(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path, missing_files={"best_model.pt"})

    with pytest.raises(FileNotFoundError, match="best_model.pt"):
        ArtifactManifest.load(model_dir)


def test_get_path_fails_when_key_missing(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    manifest = ArtifactManifest.load(model_dir)

    with pytest.raises(KeyError, match="unknown"):
        manifest.get_path("unknown")


def test_load_fails_when_model_dir_missing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing_model_dir"

    with pytest.raises(FileNotFoundError, match="model_dir"):
        ArtifactManifest.load(missing_dir)


def test_load_fails_when_model_dir_is_not_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "not_a_dir"
    file_path.write_text("not directory", encoding="utf-8")

    with pytest.raises(NotADirectoryError, match="model_dir"):
        ArtifactManifest.load(file_path)


def test_to_dict_returns_raw_manifest(tmp_path: Path) -> None:
    model_dir = make_model_dir(tmp_path)
    manifest = ArtifactManifest.load(model_dir)

    raw = manifest.to_dict()

    assert raw["model_name"] == "bilstm_attention"
    assert raw["model_class"] == "BiLSTMAttentionClassifier"