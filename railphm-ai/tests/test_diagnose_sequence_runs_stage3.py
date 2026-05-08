import importlib.util
import json
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _load_diagnose_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_sequence_runs.py"
    spec = importlib.util.spec_from_file_location("diagnose_sequence_runs", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_dataset(dataset_dir: Path):
    dataset_dir.mkdir(parents=True, exist_ok=True)
    splits_dir = dataset_dir / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)

    X = np.random.default_rng(42).normal(size=(30, 6, 4)).astype(np.float32)

    y = np.array(
        [
            1, 0, 1, 0, 0, 1, 0, 0, 1, 0,
            1, 1, 0, 0, 0, 1, 0, 1, 0, 0,
            1, 0, 0, 1, 0, 1, 0, 0, 1, 0,
        ],
        dtype=np.int64,
    )

    train_indices = np.arange(0, 12, dtype=np.int64)
    val_indices = np.arange(12, 20, dtype=np.int64)
    test_indices = np.arange(20, 30, dtype=np.int64)

    condition_labels = np.array(
        [
            0, 0, 1, 1, 2, 2, 0, 1, 2, 0,
            0, 1, 1, 2, 2, 0, 0, 1, 2, 2,
            0, 0, 0, 1, 1, 1, 2, 2, 2, 2,
        ],
        dtype=np.int64,
    )

    np.save(dataset_dir / "X.npy", X)
    np.save(dataset_dir / "y.npy", y)
    np.save(splits_dir / "train_indices.npy", train_indices)
    np.save(splits_dir / "val_indices.npy", val_indices)
    np.save(splits_dir / "test_indices.npy", test_indices)
    np.save(dataset_dir / "condition_labels.npy", condition_labels)

    condition_summary = {
        "condition_label_mapping": {
            "0": "高速巡航",
            "1": "进站减速",
            "2": "出站加速",
        }
    }
    (dataset_dir / "condition_summary.json").write_text(
        json.dumps(condition_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = pd.DataFrame(
        {
            "sample_id": np.arange(30),
            "segment_id": [
                "seg_a", "seg_a", "seg_a", "seg_a", "seg_b", "seg_b",
                "seg_b", "seg_b", "seg_c", "seg_c", "seg_c", "seg_c",
                "seg_d", "seg_d", "seg_d", "seg_d", "seg_e", "seg_e",
                "seg_e", "seg_e", "seg_fp", "seg_fp", "seg_fp", "seg_fp",
                "seg_x", "seg_x", "seg_y", "seg_y", "seg_y", "seg_y",
            ],
        }
    )
    manifest.to_csv(dataset_dir / "window_manifest.csv", index=False)

    return {
        "X": X,
        "y": y,
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
        "condition_labels": condition_labels,
    }


def _write_predictions(output_dir: Path):
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)

    val_df = pd.DataFrame(
        {
            "sample_order": list(range(8)),
            "sample_index": list(range(12, 20)),
            "y_true": [0, 0, 0, 1, 0, 1, 0, 0],
            "y_prob": [0.10, 0.20, 0.30, 0.70, 0.40, 0.80, 0.25, 0.35],
        }
    )
    val_df["y_pred_05"] = (val_df["y_prob"] >= 0.5).astype(int)

    test_df = pd.DataFrame(
        {
            "sample_order": list(range(10)),
            "sample_index": list(range(20, 30)),
            "y_true": [1, 0, 0, 1, 0, 1, 0, 0, 1, 0],
            "y_prob": [0.80, 0.45, 0.40, 0.70, 0.20, 0.65, 0.35, 0.32, 0.60, 0.15],
        }
    )
    test_df["y_pred_05"] = (test_df["y_prob"] >= 0.5).astype(int)

    for prefix in ["lstm", "bilstm", "lstm_attention", "bilstm_attention"]:
        val_df.to_csv(predictions_dir / f"{prefix}_val_predictions.csv", index=False)
        test_df.to_csv(predictions_dir / f"{prefix}_test_predictions.csv", index=False)


def _args(dataset_dir: Path, output_dir: Path, save=False, save_detail=False, thresholds=None):
    return Namespace(
        stage="distribution",
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        lstm_run=None,
        bilstm_run=None,
        lstm_attention_run=None,
        bilstm_attention_run=None,
        threshold_step=0.01,
        thresholds=thresholds or "lstm=0.30,bilstm=0.30,lstm_attention=0.30,bilstm_attention=0.30",
        device="cpu",
        save=save,
        save_detail=save_detail,
        verbose=True,
    )


def test_distribution_terminal_mode_does_not_generate_files(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_dataset(dataset_dir)
    _write_predictions(output_dir)

    module.run_distribution_analysis(_args(dataset_dir, output_dir, save=False))

    assert not (output_dir / "distribution_diagnosis_summary.json").exists()
    assert not (output_dir / "distribution_diagnosis_summary.md").exists()
    assert not (output_dir / "split_label_distribution.csv").exists()
    assert not (output_dir / "condition_distribution.csv").exists()
    assert not (output_dir / "per_condition_error_analysis.csv").exists()
    assert not (output_dir / "probability_distribution_summary.csv").exists()
    assert not (output_dir / "top_fp_segments.csv").exists()


def test_distribution_terminal_output_contains_core_sections(tmp_path, capsys):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_dataset(dataset_dir)
    _write_predictions(output_dir)

    module.run_distribution_analysis(_args(dataset_dir, output_dir))

    stdout = capsys.readouterr().out

    assert "Split Label Distribution" in stdout
    assert "Condition Distribution" in stdout
    assert "Test Confusion Matrix" in stdout
    assert "Per-condition Error Analysis" in stdout
    assert "Probability Distribution" in stdout
    assert "Global Diagnosis" in stdout


def test_split_label_distribution_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    data = _write_dataset(dataset_dir)

    rows = module.compute_split_label_distribution(
        y=data["y"],
        split_indices={
            "train": data["train_indices"],
            "val": data["val_indices"],
            "test": data["test_indices"],
        },
    )

    train_row = next(row for row in rows if row["split"] == "train")
    assert train_row["sample_count"] == 12
    assert train_row["positive_count"] == int((data["y"][data["train_indices"]] == 1).sum())
    assert train_row["positive_ratio"] == pytest.approx(
        train_row["positive_count"] / train_row["sample_count"]
    )


def test_condition_distribution_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    data = _write_dataset(dataset_dir)

    rows = module.compute_condition_distribution(
        y=data["y"],
        condition_labels=data["condition_labels"],
        split_indices={
            "train": data["train_indices"],
            "val": data["val_indices"],
            "test": data["test_indices"],
        },
        condition_mapping={0: "高速巡航", 1: "进站减速", 2: "出站加速"},
    )

    test_condition_0 = next(
        row for row in rows if row["split"] == "test" and row["condition_id"] == 0
    )

    assert test_condition_0["sample_count"] == 3
    assert test_condition_0["positive_count"] == 1
    assert test_condition_0["positive_ratio"] == pytest.approx(1 / 3)


def test_per_condition_fp_statistics_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    data = _write_dataset(dataset_dir)
    _write_predictions(output_dir)

    predictions = module.load_stage1_predictions(output_dir)
    rows = module.compute_per_condition_errors(
        predictions=predictions,
        condition_labels=data["condition_labels"],
        thresholds={
            "lstm": 0.30,
            "bilstm": 0.30,
            "lstm_attention": 0.30,
            "bilstm_attention": 0.30,
        },
        condition_mapping={0: "高速巡航", 1: "进站减速", 2: "出站加速"},
    )

    lstm_condition_0 = next(
        row for row in rows
        if row["model_key"] == "lstm" and row["condition_id"] == 0
    )

    assert lstm_condition_0["fp"] == 2


def test_probability_distribution_is_correct(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"

    _write_predictions(output_dir)
    predictions = module.load_stage1_predictions(output_dir)

    rows = module.compute_probability_distribution(predictions)
    lstm_row = next(row for row in rows if row["model_key"] == "lstm")

    df = predictions["lstm"]["test"]
    pos_mean = df[df["y_true"] == 1]["y_prob"].mean()
    neg_mean = df[df["y_true"] == 0]["y_prob"].mean()

    assert lstm_row["pos_mean"] == pytest.approx(pos_mean)
    assert lstm_row["neg_mean"] == pytest.approx(neg_mean)
    assert lstm_row["mean_gap"] == pytest.approx(pos_mean - neg_mean)


def test_top_fp_segment_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    data = _write_dataset(dataset_dir)
    _write_predictions(output_dir)

    predictions = module.load_stage1_predictions(output_dir)
    manifest = pd.read_csv(dataset_dir / "window_manifest.csv")

    top_segments, warnings = module.compute_top_fp_segments(
        predictions=predictions,
        thresholds={
            "lstm": 0.30,
            "bilstm": 0.30,
            "lstm_attention": 0.30,
            "bilstm_attention": 0.30,
        },
        window_manifest=manifest,
        y=data["y"],
    )

    assert warnings == []
    assert top_segments["lstm"][0]["segment_id"] == "seg_fp"


def test_missing_condition_labels_raises_error(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"

    _write_dataset(dataset_dir)
    (dataset_dir / "condition_labels.npy").unlink()

    with pytest.raises(FileNotFoundError):
        module.load_dataset_distribution_inputs(dataset_dir)


def test_missing_window_manifest_only_warns(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_dataset(dataset_dir)
    _write_predictions(output_dir)
    (dataset_dir / "window_manifest.csv").unlink()

    result = module.run_distribution_analysis(_args(dataset_dir, output_dir))

    assert any("window_manifest.csv" in warning for warning in result["warnings"])


def test_missing_thresholds_raises_error(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"

    with pytest.raises(ValueError, match="缺少 best_val_threshold"):
        module.parse_thresholds(None, output_dir=output_dir)


def test_save_mode_generates_summary_json(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_dataset(dataset_dir)
    _write_predictions(output_dir)

    module.run_distribution_analysis(_args(dataset_dir, output_dir, save=True))

    assert (output_dir / "distribution_diagnosis_summary.json").exists()