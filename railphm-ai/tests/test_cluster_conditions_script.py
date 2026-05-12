import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "cluster_conditions.py"


def _make_window(speed_values, mileage_start, run_distance_start):
    rows = []
    for index, speed in enumerate(speed_values):
        rows.append(
            [
                float(speed),
                float(mileage_start + index),
                float(run_distance_start + index * 10),
            ]
        )
    return rows


def _write_minimal_dataset(
    dataset_dir: Path,
    manifest_rows: int = 12,
    duplicate_split_index: bool = False,
) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "splits").mkdir(parents=True, exist_ok=True)

    windows = []

    cruise_patterns = [
        [250, 252, 251, 253],
        [248, 251, 250, 252],
        [255, 254, 256, 255],
        [245, 247, 246, 248],
    ]
    decel_patterns = [
        [180, 150, 120, 90],
        [175, 148, 118, 88],
        [185, 152, 122, 92],
        [170, 145, 115, 85],
    ]
    accel_patterns = [
        [60, 90, 120, 150],
        [65, 95, 125, 155],
        [55, 85, 115, 145],
        [70, 100, 130, 160],
    ]

    for i, pattern in enumerate(cruise_patterns):
        windows.append(_make_window(pattern, mileage_start=1000 + i * 10, run_distance_start=i * 100))

    for i, pattern in enumerate(decel_patterns):
        windows.append(_make_window(pattern, mileage_start=2000 + i * 10, run_distance_start=500 + i * 100))

    for i, pattern in enumerate(accel_patterns):
        windows.append(_make_window(pattern, mileage_start=3000 + i * 10, run_distance_start=900 + i * 100))

    X = np.asarray(windows, dtype=np.float32)
    y = np.asarray([0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1], dtype=np.int64)

    np.save(dataset_dir / "X.npy", X)
    np.save(dataset_dir / "y.npy", y)

    feature_columns = ["速度", "里程", "运行距离"]
    (dataset_dir / "feature_columns.json").write_text(
        json.dumps(feature_columns, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = pd.DataFrame(
        [
            {
                "sample_id": f"sample_{index:03d}",
                "segment_id": f"segment_{index // 4:03d}",
                "segment_file": f"segment_{index // 4:03d}.csv",
                "window_start_time": f"2026-04-01 10:{index:02d}:00",
                "window_end_time": f"2026-04-01 10:{index:02d}:03",
                "target_time": f"2026-04-01 10:{index:02d}:04",
                "label": int(y[index]) if index < len(y) else 0,
            }
            for index in range(manifest_rows)
        ]
    )
    manifest.to_csv(dataset_dir / "window_manifest.csv", index=False, encoding="utf-8-sig")

    if duplicate_split_index:
        train_indices = np.array([0, 1, 1, 4, 5, 8], dtype=np.int64)
    else:
        train_indices = np.array([0, 1, 4, 5, 8, 9], dtype=np.int64)

    val_indices = np.array([2, 6, 10], dtype=np.int64)
    test_indices = np.array([3, 7, 11], dtype=np.int64)

    np.save(dataset_dir / "splits" / "train_indices.npy", train_indices)
    np.save(dataset_dir / "splits" / "val_indices.npy", val_indices)
    np.save(dataset_dir / "splits" / "test_indices.npy", test_indices)


def _run_script(dataset_dir: Path, *extra_args: str):
    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--dataset-dir",
        str(dataset_dir),
        "--n-clusters",
        "3",
        "--seed",
        "42",
        *extra_args,
    ]

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cluster_conditions_script_success(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_minimal_dataset(dataset_dir)

    result = _run_script(dataset_dir, "--overwrite")

    assert result.returncode == 0, result.stderr

    labels_path = dataset_dir / "condition_labels.npy"
    manifest_path = dataset_dir / "condition_manifest.csv"
    summary_path = dataset_dir / "condition_summary.json"
    model_path = dataset_dir / "condition_model.pkl"

    assert labels_path.exists()
    assert manifest_path.exists()
    assert summary_path.exists()
    assert model_path.exists()

    condition_labels = np.load(labels_path)
    condition_manifest = pd.read_csv(manifest_path, encoding="utf-8-sig")
    condition_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert condition_labels.shape == (12,)
    assert condition_labels.dtype == np.int64
    assert len(condition_manifest) == 12
    assert condition_summary["n_clusters"] == 3
    assert condition_summary["fit_scope"] == "train_split_only"
    assert "cluster_positive_ratio" in condition_summary
    assert "cluster_split_distribution" in condition_summary


def test_cluster_conditions_script_missing_required_file(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_minimal_dataset(dataset_dir)
    (dataset_dir / "X.npy").unlink()

    result = _run_script(dataset_dir, "--overwrite")

    assert result.returncode != 0
    assert "缺少数据集文件" in result.stderr


def test_cluster_conditions_script_missing_split_file(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_minimal_dataset(dataset_dir)
    (dataset_dir / "splits" / "train_indices.npy").unlink()

    result = _run_script(dataset_dir, "--overwrite")

    assert result.returncode != 0
    assert "缺少划分文件" in result.stderr


def test_cluster_conditions_script_refuses_overwrite_without_flag(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_minimal_dataset(dataset_dir)

    first_result = _run_script(dataset_dir, "--overwrite")
    assert first_result.returncode == 0, first_result.stderr

    second_result = _run_script(dataset_dir)

    assert second_result.returncode != 0
    assert "输出文件已存在" in second_result.stderr or "overwrite" in second_result.stderr


def test_cluster_conditions_script_manifest_row_mismatch(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_minimal_dataset(dataset_dir, manifest_rows=10)

    result = _run_script(dataset_dir, "--overwrite")

    assert result.returncode != 0
    assert "manifest" in result.stderr or "样本数不一致" in result.stderr


def test_cluster_conditions_script_split_indices_duplicate_or_not_cover_all_samples(tmp_path):
    dataset_dir = tmp_path / "dataset"
    _write_minimal_dataset(dataset_dir, duplicate_split_index=True)

    result = _run_script(dataset_dir, "--overwrite")

    assert result.returncode != 0
    assert "重复" in result.stderr or "覆盖全部样本" in result.stderr or "划分索引" in result.stderr