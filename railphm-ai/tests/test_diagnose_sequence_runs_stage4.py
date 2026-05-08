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


def _write_stage4_dataset(dataset_dir: Path):
    dataset_dir.mkdir(parents=True, exist_ok=True)
    splits_dir = dataset_dir / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)

    X = np.random.default_rng(42).normal(size=(40, 6, 4)).astype(np.float32)
    y = np.zeros(40, dtype=np.int64)

    # test indices: 20..39
    # seg_fp: 20..29, positives at 23, 26
    # seg_other: 30..39, positives at 34, 38
    y[23] = 1
    y[26] = 1
    y[34] = 1
    y[38] = 1

    test_indices = np.arange(20, 40, dtype=np.int64)

    np.save(dataset_dir / "X.npy", X)
    np.save(dataset_dir / "y.npy", y)
    np.save(splits_dir / "test_indices.npy", test_indices)

    segment_ids = []
    segment_files = []
    target_times = []

    base_time = pd.Timestamp("2026-01-01 00:00:00")

    for index in range(40):
        if 20 <= index <= 29:
            segment_ids.append("seg_fp")
            segment_files.append("segment_fp.csv")
        elif 30 <= index <= 39:
            segment_ids.append("seg_other")
            segment_files.append("segment_other.csv")
        else:
            segment_ids.append("seg_train")
            segment_files.append("segment_train.csv")

        target_times.append((base_time + pd.Timedelta(seconds=index)).strftime("%Y-%m-%d %H:%M:%S"))

    manifest = pd.DataFrame(
        {
            "sample_id": np.arange(40),
            "segment_id": segment_ids,
            "segment_file": segment_files,
            "target_time": target_times,
            "label": y,
        }
    )
    manifest.to_csv(dataset_dir / "window_manifest.csv", index=False)

    return {
        "X": X,
        "y": y,
        "test_indices": test_indices,
        "manifest": manifest,
    }


def _write_stage4_predictions(output_dir: Path):
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)

    test_sample_index = list(range(20, 40))
    y_true = [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0]

    # seg_fp 内 20,21,22,24,25,27,28,29 多为 FP；
    # seg_other 内 FP 较少。
    y_prob = [
        0.80, 0.75, 0.70, 0.90, 0.72, 0.68, 0.88, 0.65, 0.64, 0.63,
        0.10, 0.20, 0.25, 0.15, 0.80, 0.10, 0.12, 0.14, 0.85, 0.10,
    ]

    test_df = pd.DataFrame(
        {
            "sample_order": list(range(20)),
            "sample_index": test_sample_index,
            "y_true": y_true,
            "y_prob": y_prob,
        }
    )
    test_df["y_pred_05"] = (test_df["y_prob"] >= 0.5).astype(int)

    val_df = pd.DataFrame(
        {
            "sample_order": list(range(5)),
            "sample_index": [20, 21, 22, 23, 24],
            "y_true": [0, 0, 0, 1, 0],
            "y_prob": [0.2, 0.3, 0.4, 0.9, 0.2],
        }
    )
    val_df["y_pred_05"] = (val_df["y_prob"] >= 0.5).astype(int)

    for prefix in ["lstm", "bilstm", "lstm_attention", "bilstm_attention"]:
        test_df.to_csv(predictions_dir / f"{prefix}_test_predictions.csv", index=False)
        val_df.to_csv(predictions_dir / f"{prefix}_val_predictions.csv", index=False)


def _args(dataset_dir: Path, output_dir: Path, save=False, save_detail=False, thresholds=None):
    return Namespace(
        stage="segment",
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        lstm_run=None,
        bilstm_run=None,
        lstm_attention_run=None,
        bilstm_attention_run=None,
        threshold_step=0.01,
        thresholds=thresholds or "lstm=0.50,bilstm=0.50,lstm_attention=0.50,bilstm_attention=0.50",
        top_k_segments=10,
        horizon_seconds="5,10,30",
        device="cpu",
        save=save,
        save_detail=save_detail,
        verbose=True,
    )


def test_segment_terminal_mode_does_not_generate_files(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    module.run_segment_label_analysis(_args(dataset_dir, output_dir, save=False))

    assert not (output_dir / "segment_label_diagnosis_summary.json").exists()
    assert not (output_dir / "segment_label_diagnosis_summary.md").exists()
    assert not (output_dir / "high_fp_segment_files.csv").exists()
    assert not (output_dir / "top_fp_segments.csv").exists()
    assert not (output_dir / "common_high_fp_segments.csv").exists()
    assert not (output_dir / "label_continuity_top_fp_segments.csv").exists()
    assert not (output_dir / "fp_distance_to_nearest_positive.csv").exists()
    assert not (output_dir / "future_horizon_label_potential.csv").exists()
    assert not (output_dir / "future_horizon_top_fp_segments.csv").exists()


def test_segment_terminal_output_contains_core_sections(tmp_path, capsys):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    module.run_segment_label_analysis(_args(dataset_dir, output_dir))

    stdout = capsys.readouterr().out

    assert "High-FP Segment Files" in stdout
    assert "Top FP Segments" in stdout
    assert "Common High-FP Segments" in stdout
    assert "Label Continuity" in stdout
    assert "FP Distance" in stdout
    assert "Future-horizon" in stdout
    assert "Global Diagnosis" in stdout


def test_top_fp_segment_statistics_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    predictions = module.load_stage1_predictions(output_dir)
    inputs = module.load_stage4_dataset_inputs(dataset_dir)
    thresholds = module.parse_thresholds("lstm=0.50,bilstm=0.50,lstm_attention=0.50,bilstm_attention=0.50")

    predictions_with_manifest = module.build_predictions_with_manifest(
        predictions=predictions,
        thresholds=thresholds,
        window_manifest=inputs["window_manifest"],
    )

    top_segments = module.compute_stage4_top_fp_segments(
        predictions_with_manifest=predictions_with_manifest,
        top_k=10,
    )

    assert top_segments["lstm"][0]["segment_id"] == "seg_fp"
    assert top_segments["lstm"][0]["fp"] == 8


def test_segment_file_is_preserved(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    result = module.run_segment_label_analysis(_args(dataset_dir, output_dir))

    assert result["high_fp_segments"]["lstm"][0]["segment_file"] == "segment_fp.csv"


def test_label_continuity_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    result = module.run_segment_label_analysis(_args(dataset_dir, output_dir))
    row = next(
        item for item in result["label_continuity"]
        if item["model_key"] == "lstm" and item["segment_id"] == "seg_fp"
    )

    # seg_fp test labels: positives at 23 and 26, both isolated.
    assert row["positive_count"] == 2
    assert row["positive_run_count"] == 2
    assert row["isolated_positive_count"] == 2


def test_fp_distance_to_nearest_positive_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    result = module.run_segment_label_analysis(_args(dataset_dir, output_dir))
    row = next(
        item for item in result["fp_distance_to_positive"]
        if item["model_key"] == "lstm" and item["segment_id"] == "seg_fp"
    )

    assert row["fp_count"] == 8
    assert row["fp_within_5s_count"] == 8
    assert row["median_distance_to_nearest_positive"] == pytest.approx(1.5)
    assert row["mean_distance_to_nearest_positive"] == pytest.approx(1.75)


def test_future_horizon_convertible_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    result = module.run_segment_label_analysis(_args(dataset_dir, output_dir))

    row = next(
        item for item in result["future_horizon_overall"]
        if item["model_key"] == "lstm" and item["horizon"] == 5
    )

    # seg_fp 内 20,21,22 后 5 秒内会遇到 23；24,25 后 5 秒内会遇到 26；
    # 27,28,29 后面没有正样本。共 5 个 convertible。
    assert row["fp_convertible_count"] == 5


def test_common_high_fp_segment_is_correct(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    result = module.run_segment_label_analysis(_args(dataset_dir, output_dir))

    common = result["common_high_fp_segments"]
    seg_fp = next(row for row in common if row["segment_id"] == "seg_fp")

    assert seg_fp["appear_count"] == 4


def test_missing_window_manifest_raises_error(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"

    _write_stage4_dataset(dataset_dir)
    (dataset_dir / "window_manifest.csv").unlink()

    with pytest.raises(FileNotFoundError, match="window_manifest.csv"):
        module.load_stage4_dataset_inputs(dataset_dir)


def test_missing_thresholds_raises_error(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"

    with pytest.raises(ValueError, match="缺少 best_val_threshold"):
        module.parse_thresholds(None, output_dir=output_dir)


def test_save_mode_generates_summary_json(tmp_path):
    module = _load_diagnose_module()
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "diagnosis"

    _write_stage4_dataset(dataset_dir)
    _write_stage4_predictions(output_dir)

    module.run_segment_label_analysis(_args(dataset_dir, output_dir, save=True))

    assert (output_dir / "segment_label_diagnosis_summary.json").exists()