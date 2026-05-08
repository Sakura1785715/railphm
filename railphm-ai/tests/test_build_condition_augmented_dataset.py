import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.dataset.dataset_inspector import DatasetInspector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_condition_augmented_dataset.py"


def _write_minimal_input_dataset(
    input_dir: Path,
    condition_labels: np.ndarray | None = None,
) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "splits").mkdir(parents=True, exist_ok=True)

    X = np.array(
        [
            [[10.0, 100.0, 0.0], [11.0, 101.0, 10.0], [12.0, 102.0, 20.0], [13.0, 103.0, 30.0]],
            [[20.0, 200.0, 0.0], [21.0, 201.0, 10.0], [22.0, 202.0, 20.0], [23.0, 203.0, 30.0]],
            [[30.0, 300.0, 0.0], [31.0, 301.0, 10.0], [32.0, 302.0, 20.0], [33.0, 303.0, 30.0]],
            [[40.0, 400.0, 0.0], [41.0, 401.0, 10.0], [42.0, 402.0, 20.0], [43.0, 403.0, 30.0]],
            [[50.0, 500.0, 0.0], [51.0, 501.0, 10.0], [52.0, 502.0, 20.0], [53.0, 503.0, 30.0]],
            [[60.0, 600.0, 0.0], [61.0, 601.0, 10.0], [62.0, 602.0, 20.0], [63.0, 603.0, 30.0]],
        ],
        dtype=np.float32,
    )
    y = np.array([0, 1, 0, 1, 0, 1], dtype=np.int64)
    feature_columns = ["速度", "里程", "运行距离"]

    np.save(input_dir / "X.npy", X)
    np.save(input_dir / "y.npy", y)

    (input_dir / "feature_columns.json").write_text(
        json.dumps(feature_columns, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = pd.DataFrame(
        [
            {
                "sample_id": f"sample_{index:03d}",
                "segment_id": f"segment_{index // 2:03d}",
                "segment_file": f"segment_{index // 2:03d}.csv",
                "window_start_row": 0,
                "window_end_row": 3,
                "target_row": 4,
                "window_start_time": f"2026-04-01 10:0{index}:00",
                "window_end_time": f"2026-04-01 10:0{index}:03",
                "target_time": f"2026-04-01 10:0{index}:04",
                "label": int(y[index]),
                "target_label_value": "车载主机" if y[index] == 1 else "",
            }
            for index in range(6)
        ]
    )
    manifest.to_csv(input_dir / "window_manifest.csv", index=False, encoding="utf-8-sig")

    dataset_summary = {
        "X_shape": [6, 4, 3],
        "y_shape": [6],
        "feature_dim": 3,
        "feature_columns": feature_columns,
        "total_windows": 6,
        "positive_count": 3,
        "negative_count": 3,
        "window_size": 4,
        "stride": 1,
        "prediction_horizon": 1,
    }
    (input_dir / "dataset_summary.json").write_text(
        json.dumps(dataset_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    train_indices = np.array([0, 1, 2], dtype=np.int64)
    val_indices = np.array([3, 4], dtype=np.int64)
    test_indices = np.array([5], dtype=np.int64)

    np.save(input_dir / "splits" / "train_indices.npy", train_indices)
    np.save(input_dir / "splits" / "val_indices.npy", val_indices)
    np.save(input_dir / "splits" / "test_indices.npy", test_indices)

    split_summary = {
        "split_strategy": "segment_id",
        "train": {"sample_count": 3},
        "val": {"sample_count": 2},
        "test": {"sample_count": 1},
    }
    (input_dir / "splits" / "split_summary.json").write_text(
        json.dumps(split_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    labels = condition_labels
    if labels is None:
        labels = np.array([0, 1, 2, 0, 1, 2], dtype=np.int64)

    np.save(input_dir / "condition_labels.npy", labels)

    condition_summary = {
        "n_clusters": 3,
        "fit_scope": "train_split_only",
        "condition_label_mapping": {
            "0": "高速巡航",
            "1": "进站减速",
            "2": "出站加速",
        },
    }
    (input_dir / "condition_summary.json").write_text(
        json.dumps(condition_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    condition_manifest = pd.DataFrame(
    {
        "sample_index": list(range(len(labels))),
        "condition_id": labels.tolist(),
    }
)
    condition_manifest.to_csv(input_dir / "condition_manifest.csv", index=False, encoding="utf-8-sig")


def _run_script(input_dir: Path, output_dir: Path, *extra_args: str):
    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(output_dir),
        *extra_args,
    ]

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_build_condition_augmented_dataset_success(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(input_dir)

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode == 0, result.stderr

    assert (output_dir / "X.npy").exists()
    assert (output_dir / "y.npy").exists()
    assert (output_dir / "feature_columns.json").exists()
    assert (output_dir / "dataset_summary.json").exists()
    assert (output_dir / "condition_augmented_summary.json").exists()

    X_aug = np.load(output_dir / "X.npy")
    feature_columns = json.loads((output_dir / "feature_columns.json").read_text(encoding="utf-8"))

    assert X_aug.shape == (6, 4, 6)
    assert feature_columns[-3:] == ["condition_0", "condition_1", "condition_2"]

    assert np.array_equal(X_aug[0, :, -3:], np.tile(np.array([1.0, 0.0, 0.0], dtype=np.float32), (4, 1)))
    assert np.array_equal(X_aug[1, :, -3:], np.tile(np.array([0.0, 1.0, 0.0], dtype=np.float32), (4, 1)))
    assert np.array_equal(X_aug[2, :, -3:], np.tile(np.array([0.0, 0.0, 1.0], dtype=np.float32), (4, 1)))


def test_build_condition_augmented_dataset_keeps_y_and_splits_unchanged(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(input_dir)

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode == 0, result.stderr

    assert np.array_equal(np.load(output_dir / "y.npy"), np.load(input_dir / "y.npy"))
    assert np.array_equal(
        np.load(output_dir / "splits" / "train_indices.npy"),
        np.load(input_dir / "splits" / "train_indices.npy"),
    )
    assert np.array_equal(
        np.load(output_dir / "splits" / "val_indices.npy"),
        np.load(input_dir / "splits" / "val_indices.npy"),
    )
    assert np.array_equal(
        np.load(output_dir / "splits" / "test_indices.npy"),
        np.load(input_dir / "splits" / "test_indices.npy"),
    )


def test_build_condition_augmented_dataset_condition_label_count_mismatch(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(
        input_dir,
        condition_labels=np.array([0, 1, 2, 0, 1], dtype=np.int64),
    )

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "condition_labels" in result.stderr or "样本数不一致" in result.stderr


def test_build_condition_augmented_dataset_rejects_negative_condition_label(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(
        input_dir,
        condition_labels=np.array([0, 1, -1, 0, 1, 2], dtype=np.int64),
    )

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "condition_labels" in result.stderr or "不能包含负数" in result.stderr


def test_build_condition_augmented_dataset_rejects_condition_label_out_of_clusters(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(
        input_dir,
        condition_labels=np.array([0, 1, 3, 0, 1, 2], dtype=np.int64),
    )

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "n_clusters" in result.stderr or "越界" in result.stderr


def test_build_condition_augmented_dataset_refuses_existing_output_without_overwrite(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(input_dir)
    output_dir.mkdir(parents=True)

    result = _run_script(input_dir, output_dir)

    assert result.returncode != 0
    assert "output_dir 已存在" in result.stderr or "overwrite" in result.stderr


def test_build_condition_augmented_dataset_missing_required_file(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(input_dir)
    (input_dir / "X.npy").unlink()

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "缺少数据集文件" in result.stderr


def test_build_condition_augmented_dataset_missing_condition_labels_file(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(input_dir)
    (input_dir / "condition_labels.npy").unlink()

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode != 0
    assert "缺少工况标签文件" in result.stderr


def test_build_condition_augmented_dataset_can_be_inspected(tmp_path):
    input_dir = tmp_path / "input_dataset"
    output_dir = tmp_path / "output_dataset"
    _write_minimal_input_dataset(input_dir)

    result = _run_script(input_dir, output_dir, "--overwrite")

    assert result.returncode == 0, result.stderr

    inspection = DatasetInspector().inspect(output_dir)

    assert inspection.is_valid is True
    assert inspection.errors == []