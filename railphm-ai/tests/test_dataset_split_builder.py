# tests/test_dataset_split_builder.py

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.dataset.split_builder import DatasetSplitBuilder


def _write_dataset_for_split(dataset_dir: Path) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # 6 个 segment，每个 4 个样本，总共 24 个样本。
    y_values = []
    manifest_records = []

    sample_index = 0
    for segment_idx in range(6):
        segment_id = f"segment_{segment_idx:06d}"
        for local_idx in range(4):
            label = 1 if (segment_idx + local_idx) % 2 == 0 else 0
            y_values.append(label)
            manifest_records.append(
                {
                    "sample_id": f"{segment_id}_{local_idx:06d}",
                    "segment_id": segment_id,
                    "segment_file": f"{segment_id}.csv",
                    "label": label,
                    "target_time": f"2015-01-09 11:23:{sample_index:02d}",
                }
            )
            sample_index += 1

    y = np.array(y_values, dtype=np.int64)
    np.save(dataset_dir / "y.npy", y)

    manifest = pd.DataFrame(manifest_records)
    manifest.to_csv(dataset_dir / "window_manifest.csv", index=False, encoding="utf-8-sig")


def test_split_builder_splits_by_segment_id(tmp_path):
    dataset_dir = tmp_path / "dataset"
    output_dir = dataset_dir / "splits"
    _write_dataset_for_split(dataset_dir)

    result = DatasetSplitBuilder().split(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        train_ratio=0.5,
        val_ratio=0.25,
        test_ratio=0.25,
        seed=42,
        overwrite=False,
    )

    assert (output_dir / "train_indices.npy").exists()
    assert (output_dir / "val_indices.npy").exists()
    assert (output_dir / "test_indices.npy").exists()
    assert (output_dir / "split_summary.json").exists()

    train_indices = np.load(output_dir / "train_indices.npy")
    val_indices = np.load(output_dir / "val_indices.npy")
    test_indices = np.load(output_dir / "test_indices.npy")

    assert np.array_equal(train_indices, result.train_indices)
    assert np.array_equal(val_indices, result.val_indices)
    assert np.array_equal(test_indices, result.test_indices)

    all_indices = np.concatenate([train_indices, val_indices, test_indices])
    assert sorted(all_indices.tolist()) == list(range(24))

    manifest = pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig")

    train_segments = set(manifest.iloc[train_indices]["segment_id"])
    val_segments = set(manifest.iloc[val_indices]["segment_id"])
    test_segments = set(manifest.iloc[test_indices]["segment_id"])

    assert train_segments.isdisjoint(val_segments)
    assert train_segments.isdisjoint(test_segments)
    assert val_segments.isdisjoint(test_segments)

    summary = json.loads((output_dir / "split_summary.json").read_text(encoding="utf-8"))
    assert summary["split_strategy"] == "segment_id"
    assert summary["total_samples"] == 24
    assert summary["total_segments"] == 6
    assert summary["leakage_check"]["has_segment_leakage"] is False


def test_split_builder_refuses_invalid_ratios(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_dataset_for_split(dataset_dir)

    with pytest.raises(ValueError, match="必须等于 1"):
        DatasetSplitBuilder().split(
            dataset_dir=dataset_dir,
            train_ratio=0.8,
            val_ratio=0.1,
            test_ratio=0.2,
        )


def test_split_builder_refuses_existing_output_without_overwrite(tmp_path):
    dataset_dir = tmp_path / "dataset"
    output_dir = dataset_dir / "splits"
    _write_dataset_for_split(dataset_dir)
    output_dir.mkdir()

    with pytest.raises(FileExistsError, match="划分输出目录已存在"):
        DatasetSplitBuilder().split(
            dataset_dir=dataset_dir,
            output_dir=output_dir,
            overwrite=False,
        )


def test_split_builder_can_overwrite_existing_output(tmp_path):
    dataset_dir = tmp_path / "dataset"
    output_dir = dataset_dir / "splits"
    _write_dataset_for_split(dataset_dir)
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old", encoding="utf-8")

    result = DatasetSplitBuilder().split(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        overwrite=True,
    )

    assert not (output_dir / "old.txt").exists()
    assert result.summary["leakage_check"]["has_segment_leakage"] is False