"""
runtime_predict_one.py 调试脚本的轻量测试。

本测试只覆盖脚本中的纯函数和轻量文件读取逻辑，不依赖真实 best_model.pt，
不加载真实模型，不执行真实预测。
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from scripts.runtime_predict_one import (
    extract_window_and_label,
    load_manifest_row,
    validate_dataset_arrays,
    validate_sample_index,
)


def test_validate_dataset_arrays_success() -> None:
    X = np.zeros((5, 30, 23), dtype=np.float32)
    y = np.zeros((5,), dtype=np.int64)

    validate_dataset_arrays(X, y)


def test_validate_dataset_arrays_rejects_x_not_3d() -> None:
    X = np.zeros((30, 23), dtype=np.float32)
    y = np.zeros((5,), dtype=np.int64)

    with pytest.raises(ValueError, match="3D"):
        validate_dataset_arrays(X, y)


def test_validate_dataset_arrays_rejects_y_not_1d() -> None:
    X = np.zeros((5, 30, 23), dtype=np.float32)
    y = np.zeros((5, 1), dtype=np.int64)

    with pytest.raises(ValueError, match="1D"):
        validate_dataset_arrays(X, y)


def test_validate_dataset_arrays_rejects_sample_count_mismatch() -> None:
    X = np.zeros((5, 30, 23), dtype=np.float32)
    y = np.zeros((4,), dtype=np.int64)

    with pytest.raises(ValueError, match="sample count mismatch"):
        validate_dataset_arrays(X, y)


def test_validate_sample_index_success() -> None:
    validate_sample_index(0, total_samples=5)
    validate_sample_index(4, total_samples=5)


def test_validate_sample_index_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        validate_sample_index(-1, total_samples=5)


def test_validate_sample_index_rejects_out_of_range() -> None:
    with pytest.raises(IndexError, match="out of range"):
        validate_sample_index(5, total_samples=5)


def test_extract_window_and_label_success() -> None:
    X = np.zeros((5, 30, 23), dtype=np.float32)
    y = np.array([0, 1, 0, 1, 0], dtype=np.int64)

    window, y_true = extract_window_and_label(X, y, sample_index=1)

    assert window.shape == (30, 23)
    assert y_true == 1


def test_extract_window_and_label_rejects_nan() -> None:
    X = np.zeros((5, 30, 23), dtype=np.float32)
    y = np.zeros((5,), dtype=np.int64)
    X[2, 0, 0] = np.nan

    with pytest.raises(ValueError, match="NaN or inf"):
        extract_window_and_label(X, y, sample_index=2)


def test_extract_window_and_label_rejects_inf() -> None:
    X = np.zeros((5, 30, 23), dtype=np.float32)
    y = np.zeros((5,), dtype=np.int64)
    X[2, 0, 0] = np.inf

    with pytest.raises(ValueError, match="NaN or inf"):
        extract_window_and_label(X, y, sample_index=2)


def test_load_manifest_row_returns_none_when_missing(tmp_path: Path) -> None:
    row = load_manifest_row(tmp_path, sample_index=0)

    assert row is None


def test_load_manifest_row_success(tmp_path: Path) -> None:
    manifest_path = tmp_path / "window_manifest.csv"

    with manifest_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "sample_id",
                "segment_id",
                "segment_file",
                "window_start_time",
                "window_end_time",
                "target_time",
                "label",
                "target_label_value",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "sample_id": "segment_001_000000_000030",
                "segment_id": "segment_001",
                "segment_file": "segment_001.csv",
                "window_start_time": "2026-01-01 00:00:00",
                "window_end_time": "2026-01-01 00:00:29",
                "target_time": "2026-01-01 00:00:30",
                "label": "1",
                "target_label_value": "ATP报警",
            }
        )

    row = load_manifest_row(tmp_path, sample_index=0)

    assert row is not None
    assert row["sample_id"] == "segment_001_000000_000030"
    assert row["segment_id"] == "segment_001"
    assert row["label"] == "1"
    assert row["target_label_value"] == "ATP报警"


def test_load_manifest_row_returns_warning_when_row_missing(tmp_path: Path) -> None:
    manifest_path = tmp_path / "window_manifest.csv"

    with manifest_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["sample_id", "segment_id"])
        writer.writeheader()
        writer.writerow({"sample_id": "sample_0", "segment_id": "segment_0"})

    row = load_manifest_row(tmp_path, sample_index=5)

    assert row is not None
    assert "warning" in row