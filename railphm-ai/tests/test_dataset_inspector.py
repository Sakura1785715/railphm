# tests/test_dataset_inspector.py

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.dataset.dataset_inspector import DatasetInspector


def _write_valid_dataset(dataset_dir: Path) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)

    X = np.array(
        [
            [[0.0, 0.1], [0.2, 0.3], [0.4, 0.5]],
            [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            [[0.2, 0.3], [0.4, 0.5], [0.6, 0.7]],
            [[0.3, 0.4], [0.5, 0.6], [0.7, 0.8]],
        ],
        dtype=np.float32,
    )
    y = np.array([0, 1, 0, 1], dtype=np.int64)

    np.save(dataset_dir / "X.npy", X)
    np.save(dataset_dir / "y.npy", y)

    (dataset_dir / "feature_columns.json").write_text(
        json.dumps(["速度", "里程"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = pd.DataFrame(
        [
            {
                "sample_id": "s1_000000_000003",
                "segment_id": "segment_000001",
                "segment_file": "segment_000001.csv",
                "window_start_row": 0,
                "window_end_row": 2,
                "target_row": 3,
                "window_start_time": "2015-01-09 11:23:05",
                "window_end_time": "2015-01-09 11:23:07",
                "target_time": "2015-01-09 11:23:08",
                "label": 0,
                "target_label_value": "",
            },
            {
                "sample_id": "s1_000001_000004",
                "segment_id": "segment_000001",
                "segment_file": "segment_000001.csv",
                "window_start_row": 1,
                "window_end_row": 3,
                "target_row": 4,
                "window_start_time": "2015-01-09 11:23:06",
                "window_end_time": "2015-01-09 11:23:08",
                "target_time": "2015-01-09 11:23:09",
                "label": 1,
                "target_label_value": "车载主机",
            },
            {
                "sample_id": "s2_000000_000003",
                "segment_id": "segment_000002",
                "segment_file": "segment_000002.csv",
                "window_start_row": 0,
                "window_end_row": 2,
                "target_row": 3,
                "window_start_time": "2015-01-09 11:24:05",
                "window_end_time": "2015-01-09 11:24:07",
                "target_time": "2015-01-09 11:24:08",
                "label": 0,
                "target_label_value": "",
            },
            {
                "sample_id": "s2_000001_000004",
                "segment_id": "segment_000002",
                "segment_file": "segment_000002.csv",
                "window_start_row": 1,
                "window_end_row": 3,
                "target_row": 4,
                "window_start_time": "2015-01-09 11:24:06",
                "window_end_time": "2015-01-09 11:24:08",
                "target_time": "2015-01-09 11:24:09",
                "label": 1,
                "target_label_value": "车载主机",
            },
        ]
    )
    manifest.to_csv(dataset_dir / "window_manifest.csv", index=False, encoding="utf-8-sig")

    build_summary = {
        "total_windows": 4,
        "positive_count": 2,
        "negative_count": 2,
        "X_shape": [4, 3, 2],
        "y_shape": [4],
        "used_segment_count": 2,
        "skipped_segment_count": 0,
    }

    (dataset_dir / "dataset_summary.json").write_text(
        json.dumps(build_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_dataset_inspector_valid_dataset(tmp_path):
    dataset_dir = tmp_path / "dataset"
    output_file = tmp_path / "inspection_summary.json"
    _write_valid_dataset(dataset_dir)

    result = DatasetInspector().inspect(dataset_dir, output_file=output_file)

    assert result.is_valid is True
    assert result.errors == []
    assert result.summary["X_shape"] == [4, 3, 2]
    assert result.summary["y_shape"] == [4]
    assert result.summary["manifest_rows"] == 4
    assert result.summary["unique_y"] == [0, 1]
    assert result.summary["positive_count"] == 2
    assert result.summary["negative_count"] == 2
    assert result.summary["segment_count"] == 2
    assert output_file.exists()


def test_dataset_inspector_detects_shape_mismatch(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_valid_dataset(dataset_dir)

    # 覆盖 y，让 y 样本数和 X 不一致。
    np.save(dataset_dir / "y.npy", np.array([0, 1], dtype=np.int64))

    result = DatasetInspector().inspect(dataset_dir)

    assert result.is_valid is False
    assert any("X 样本数与 y 样本数不一致" in error for error in result.errors)


def test_dataset_inspector_detects_invalid_labels(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_valid_dataset(dataset_dir)

    np.save(dataset_dir / "y.npy", np.array([0, 1, 2, 1], dtype=np.int64))

    result = DatasetInspector().inspect(dataset_dir)

    assert result.is_valid is False
    assert any("y 只能包含 0/1 标签" in error for error in result.errors)


def test_dataset_inspector_detects_nan(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_valid_dataset(dataset_dir)

    X = np.load(dataset_dir / "X.npy")
    X[0, 0, 0] = np.nan
    np.save(dataset_dir / "X.npy", X)

    result = DatasetInspector().inspect(dataset_dir)

    assert result.is_valid is False
    assert "X 中存在 NaN" in result.errors


def test_dataset_inspector_detects_sensitive_manifest_columns(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_valid_dataset(dataset_dir)

    manifest = pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig")
    manifest["target_司机手机号"] = "13800000000"
    manifest.to_csv(dataset_dir / "window_manifest.csv", index=False, encoding="utf-8-sig")

    result = DatasetInspector().inspect(dataset_dir)

    assert result.is_valid is False
    assert any("manifest 不应包含敏感字段" in error for error in result.errors)