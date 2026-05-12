#!/usr/bin/env python3
"""
工况 one-hot 增强数据集构造脚本。

该脚本读取已经完成工况划分的窗口数据集，将每个样本的 condition_id 转换为 one-hot 特征，
并在每个时间步重复拼接到 X.npy 的最后一个特征维度，生成可直接用于现有检查和 baseline 训练流程的增强数据集。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_DATASET_FILES = [
    "X.npy",
    "y.npy",
    "feature_columns.json",
    "window_manifest.csv",
    "dataset_summary.json",
]

REQUIRED_SPLIT_FILES = [
    "train_indices.npy",
    "val_indices.npy",
    "test_indices.npy",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build RailPHM condition one-hot augmented window dataset."
    )

    parser.add_argument("--input-dir", type=Path, required=True, help="已完成工况划分的窗口数据集目录")
    parser.add_argument("--output-dir", type=Path, required=True, help="增强数据集输出目录")
    parser.add_argument("--condition-labels-file", type=Path, default=None, help="condition_labels.npy 路径")
    parser.add_argument("--condition-summary-file", type=Path, default=None, help="condition_summary.json 路径")
    parser.add_argument("--condition-manifest-file", type=Path, default=None, help="condition_manifest.csv 路径")
    parser.add_argument("--overwrite", action="store_true", help="如果输出目录已存在，则删除后重建")
    parser.add_argument("--verbose", action="store_true", help="打印更详细的增强数据集信息")

    return parser


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_input_dir(
    input_dir: Path,
    condition_labels_file: Path,
    condition_summary_file: Path,
) -> None:
    if not input_dir.exists():
        raise FileNotFoundError(f"输入数据集目录不存在: {input_dir}")

    if not input_dir.is_dir():
        raise NotADirectoryError(f"input_dir 必须是目录: {input_dir}")

    for filename in REQUIRED_DATASET_FILES:
        path = input_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少数据集文件：{filename}")

    for filename in REQUIRED_SPLIT_FILES:
        path = input_dir / "splits" / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少划分文件：splits/{filename}")

    if not condition_labels_file.exists():
        raise FileNotFoundError(f"缺少工况标签文件：{condition_labels_file}")

    if not condition_summary_file.exists():
        raise FileNotFoundError(f"缺少工况统计文件：{condition_summary_file}")


def prepare_output_dir(input_dir: Path, output_dir: Path, overwrite: bool) -> None:
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("output_dir 不能与 input_dir 相同，避免覆盖原始数据集")

    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"output_dir 已存在: {output_dir}，如需覆盖请使用 --overwrite")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "splits").mkdir(parents=True, exist_ok=True)


def load_inputs(
    input_dir: Path,
    condition_labels_file: Path,
    condition_summary_file: Path,
) -> dict[str, Any]:
    return {
        "X": np.load(input_dir / "X.npy", allow_pickle=False),
        "y": np.load(input_dir / "y.npy", allow_pickle=False),
        "feature_columns": load_json(input_dir / "feature_columns.json"),
        "window_manifest": pd.read_csv(input_dir / "window_manifest.csv", encoding="utf-8-sig"),
        "dataset_summary": load_json(input_dir / "dataset_summary.json"),
        "train_indices": np.load(input_dir / "splits" / "train_indices.npy", allow_pickle=False),
        "val_indices": np.load(input_dir / "splits" / "val_indices.npy", allow_pickle=False),
        "test_indices": np.load(input_dir / "splits" / "test_indices.npy", allow_pickle=False),
        "condition_labels": np.load(condition_labels_file, allow_pickle=False),
        "condition_summary": load_json(condition_summary_file),
    }


def validate_inputs(
    X: np.ndarray,
    y: np.ndarray,
    feature_columns: list[str],
    window_manifest: pd.DataFrame,
    condition_labels: np.ndarray,
    n_clusters: int,
    train_indices: np.ndarray,
    val_indices: np.ndarray,
    test_indices: np.ndarray,
) -> np.ndarray:
    if not isinstance(X, np.ndarray) or X.ndim != 3:
        raise ValueError("X 必须为三维 numpy 数组 [num_samples, window_size, feature_dim]")

    if not isinstance(y, np.ndarray) or y.ndim != 1:
        raise ValueError("y 必须为一维 numpy 数组")

    if X.shape[0] != y.shape[0]:
        raise ValueError("X 与 y 样本数不一致")

    if not isinstance(feature_columns, list) or not all(isinstance(column, str) for column in feature_columns):
        raise ValueError("feature_columns 必须是 list[str]")

    if len(feature_columns) != X.shape[2]:
        raise ValueError("feature_columns 数量必须等于 X.shape[2]")

    if len(window_manifest) != X.shape[0]:
        raise ValueError(
            f"window_manifest.csv 行数与样本数不一致: manifest={len(window_manifest)}, samples={X.shape[0]}"
        )

    if not np.isfinite(X).all():
        raise ValueError("X 中存在 NaN 或 inf")

    if not np.isin(y, [0, 1]).all():
        raise ValueError("y 只能包含 0/1 标签")

    normalized_condition_labels = normalize_condition_labels(condition_labels)

    if normalized_condition_labels.shape[0] != X.shape[0]:
        raise ValueError(
            "condition_labels 样本数不一致: "
            f"condition_labels={normalized_condition_labels.shape[0]}, samples={X.shape[0]}"
        )

    if normalized_condition_labels.size > 0 and normalized_condition_labels.min() < 0:
        raise ValueError("condition_labels 不能包含负数")

    if normalized_condition_labels.size > 0 and normalized_condition_labels.max() >= n_clusters:
        raise ValueError(
            "condition_labels 存在越界工况编号: "
            f"max_label={int(normalized_condition_labels.max())}, n_clusters={n_clusters}"
        )

    sample_count = int(X.shape[0])
    validate_split_indices(train_indices, sample_count, "train_indices")
    validate_split_indices(val_indices, sample_count, "val_indices")
    validate_split_indices(test_indices, sample_count, "test_indices")

    return normalized_condition_labels


def normalize_condition_labels(condition_labels: np.ndarray) -> np.ndarray:
    if not isinstance(condition_labels, np.ndarray):
        raise ValueError("condition_labels 必须是 numpy.ndarray")

    if condition_labels.ndim != 1:
        raise ValueError("condition_labels 必须是一维数组")

    if np.issubdtype(condition_labels.dtype, np.integer):
        return condition_labels.astype(np.int64, copy=False)

    try:
        as_float = condition_labels.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("condition_labels 必须是整数类型，或能安全转换为整数") from exc

    if not np.isfinite(as_float).all():
        raise ValueError("condition_labels 中存在 NaN 或 inf")

    rounded = np.rint(as_float)
    if not np.allclose(as_float, rounded):
        raise ValueError("condition_labels 必须是整数类型，或能安全转换为整数")

    return rounded.astype(np.int64)


def validate_split_indices(indices: np.ndarray, sample_count: int, name: str) -> None:
    if not isinstance(indices, np.ndarray):
        raise ValueError(f"{name} 必须是 numpy.ndarray")

    if indices.ndim != 1:
        raise ValueError(f"{name} 必须是一维整数数组")

    if not np.issubdtype(indices.dtype, np.integer):
        raise ValueError(f"{name} 必须是一维整数数组")

    if indices.size > 0 and (indices.min() < 0 or indices.max() >= sample_count):
        raise ValueError(f"{name} 存在越界索引")


def infer_n_clusters(condition_labels: np.ndarray, condition_summary: dict, warnings: list[str]) -> int:
    raw_n_clusters = condition_summary.get("n_clusters")

    if raw_n_clusters is not None:
        if isinstance(raw_n_clusters, bool) or not isinstance(raw_n_clusters, int) or raw_n_clusters <= 0:
            raise ValueError("condition_summary.json 中的 n_clusters 必须为正整数")
        return int(raw_n_clusters)

    unique_count = int(np.unique(condition_labels).shape[0])
    if unique_count <= 0:
        raise ValueError("无法从 condition_labels 推断 n_clusters")

    warnings.append("condition_summary.json 中缺少 n_clusters，已根据 condition_labels 唯一值数量推断")
    return unique_count


def append_condition_coverage_warning(
    condition_labels: np.ndarray,
    n_clusters: int,
    warnings: list[str],
) -> None:
    expected_labels = set(range(n_clusters))
    actual_labels = set(int(value) for value in np.unique(condition_labels).tolist())
    missing_labels = sorted(expected_labels - actual_labels)

    if missing_labels:
        warnings.append(f"condition_labels 未覆盖全部工况，缺失工况: {missing_labels}")


def build_condition_onehot(condition_labels: np.ndarray, n_clusters: int) -> np.ndarray:
    onehot = np.zeros((condition_labels.shape[0], n_clusters), dtype=np.float32)
    onehot[np.arange(condition_labels.shape[0]), condition_labels.astype(np.int64)] = 1.0
    return onehot


def append_condition_features(X: np.ndarray, condition_onehot: np.ndarray) -> np.ndarray:
    condition_onehot_seq = np.repeat(
        condition_onehot[:, None, :],
        repeats=X.shape[1],
        axis=1,
    ).astype(np.float32, copy=False)

    X_aug = np.concatenate(
        [X.astype(np.float32, copy=False), condition_onehot_seq],
        axis=2,
    ).astype(np.float32, copy=False)

    if not np.isfinite(X_aug).all():
        raise ValueError("增强后的 X_aug 中存在 NaN 或 inf")

    return X_aug


def build_augmented_feature_columns(feature_columns: list[str], n_clusters: int) -> list[str]:
    condition_feature_columns = [f"condition_{cluster_id}" for cluster_id in range(n_clusters)]
    return list(feature_columns) + condition_feature_columns


def copy_metadata_files(
    input_dir: Path,
    output_dir: Path,
    condition_labels_file: Path,
    condition_summary_file: Path,
    condition_manifest_file: Path | None,
    warnings: list[str],
) -> list[str]:
    copied_files: list[str] = []

    direct_files = [
        "y.npy",
        "window_manifest.csv",
    ]

    for filename in direct_files:
        shutil.copy2(input_dir / filename, output_dir / filename)
        copied_files.append(filename)

    for filename in REQUIRED_SPLIT_FILES:
        shutil.copy2(input_dir / "splits" / filename, output_dir / "splits" / filename)
        copied_files.append(f"splits/{filename}")

    split_summary_path = input_dir / "splits" / "split_summary.json"
    if split_summary_path.exists():
        shutil.copy2(split_summary_path, output_dir / "splits" / "split_summary.json")
        copied_files.append("splits/split_summary.json")

    shutil.copy2(condition_labels_file, output_dir / "condition_labels.npy")
    copied_files.append("condition_labels.npy")

    shutil.copy2(condition_summary_file, output_dir / "condition_summary.json")
    copied_files.append("condition_summary.json")

    if condition_manifest_file is not None and condition_manifest_file.exists():
        shutil.copy2(condition_manifest_file, output_dir / "condition_manifest.csv")
        copied_files.append("condition_manifest.csv")
    else:
        warnings.append("condition_manifest.csv 不存在，已跳过复制")

    condition_model_path = input_dir / "condition_model.pkl"
    if condition_model_path.exists():
        shutil.copy2(condition_model_path, output_dir / "condition_model.pkl")
        copied_files.append("condition_model.pkl")

    return copied_files


def build_dataset_summary(
    original_summary: dict,
    input_dir: Path,
    X_aug: np.ndarray,
    y: np.ndarray,
    feature_columns_aug: list[str],
    condition_labels_file: Path,
    condition_summary_file: Path,
    n_clusters: int,
) -> dict[str, Any]:
    original_feature_dim = int(original_summary.get("feature_dim", X_aug.shape[2] - n_clusters))
    condition_feature_columns = [f"condition_{cluster_id}" for cluster_id in range(n_clusters)]

    summary = dict(original_summary)
    summary["X_shape"] = [int(value) for value in X_aug.shape]
    summary["y_shape"] = [int(value) for value in y.shape]
    summary["feature_dim"] = int(X_aug.shape[2])
    summary["feature_columns"] = list(feature_columns_aug)
    summary["condition_augmentation"] = {
        "enabled": True,
        "source_dataset_dir": str(input_dir),
        "condition_labels_file": str(condition_labels_file),
        "condition_summary_file": str(condition_summary_file),
        "n_clusters": int(n_clusters),
        "condition_feature_columns": condition_feature_columns,
        "append_strategy": "repeat_onehot_per_timestep",
        "original_feature_dim": original_feature_dim,
        "augmented_feature_dim": int(X_aug.shape[2]),
        "notes": [
            "Condition one-hot features are repeated at each timestep of the window.",
            "Original y.npy and splits are kept unchanged.",
        ],
    }

    return summary


def build_condition_augmented_summary(
    input_dir: Path,
    output_dir: Path,
    X: np.ndarray,
    X_aug: np.ndarray,
    y: np.ndarray,
    condition_labels: np.ndarray,
    n_clusters: int,
    copied_files: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "task": "condition_augmented_dataset",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "sample_count": int(X.shape[0]),
        "window_size": int(X.shape[1]),
        "original_feature_dim": int(X.shape[2]),
        "augmented_feature_dim": int(X_aug.shape[2]),
        "n_clusters": int(n_clusters),
        "condition_feature_columns": [f"condition_{cluster_id}" for cluster_id in range(n_clusters)],
        "X_shape_before": [int(value) for value in X.shape],
        "X_shape_after": [int(value) for value in X_aug.shape],
        "y_shape": [int(value) for value in y.shape],
        "condition_labels_shape": [int(value) for value in condition_labels.shape],
        "condition_label_distribution": build_condition_label_distribution(condition_labels, n_clusters),
        "copied_files": copied_files,
        "warnings": warnings,
    }


def build_condition_label_distribution(condition_labels: np.ndarray, n_clusters: int) -> dict[str, int]:
    return {
        str(cluster_id): int((condition_labels == cluster_id).sum())
        for cluster_id in range(n_clusters)
    }


def print_summary(summary: dict, verbose: bool = False) -> None:
    print()
    print("RailPHM condition augmented dataset created.")
    print(f"input_dir: {summary['input_dir']}")
    print(f"output_dir: {summary['output_dir']}")
    print(f"sample_count: {summary['sample_count']}")
    print(f"window_size: {summary['window_size']}")
    print(f"original_feature_dim: {summary['original_feature_dim']}")
    print(f"augmented_feature_dim: {summary['augmented_feature_dim']}")
    print(f"n_clusters: {summary['n_clusters']}")
    print(f"X_shape_before: {summary['X_shape_before']}")
    print(f"X_shape_after: {summary['X_shape_after']}")

    print()
    print("condition label distribution:")
    for cluster_id in range(int(summary["n_clusters"])):
        key = str(cluster_id)
        count = summary["condition_label_distribution"].get(key, 0)
        print(f"- condition_{cluster_id}: {count}")

    print()
    print("Output files:")
    output_dir = Path(summary["output_dir"])
    output_files = [
        "X.npy",
        "y.npy",
        "feature_columns.json",
        "window_manifest.csv",
        "dataset_summary.json",
        "condition_labels.npy",
        "condition_summary.json",
        "condition_augmented_summary.json",
        "splits/train_indices.npy",
        "splits/val_indices.npy",
        "splits/test_indices.npy",
    ]

    for filename in output_files:
        print(f"- {output_dir / filename}")

    if not verbose:
        return

    print()
    print("condition_feature_columns:")
    for column in summary["condition_feature_columns"]:
        print(f"- {column}")

    warnings = summary.get("warnings") or []
    if warnings:
        print()
        print("warnings:")
        for warning in warnings:
            print(f"- {warning}")

    copied_files = summary.get("copied_files") or []
    if copied_files:
        print()
        print("copied_files:")
        for filename in copied_files:
            print(f"- {filename}")


def run(args: argparse.Namespace) -> dict[str, Any]:
    input_dir = args.input_dir
    output_dir = args.output_dir

    condition_labels_file = args.condition_labels_file or input_dir / "condition_labels.npy"
    condition_summary_file = args.condition_summary_file or input_dir / "condition_summary.json"
    condition_manifest_file = args.condition_manifest_file or input_dir / "condition_manifest.csv"

    warnings: list[str] = []

    validate_input_dir(
        input_dir=input_dir,
        condition_labels_file=condition_labels_file,
        condition_summary_file=condition_summary_file,
    )
    prepare_output_dir(input_dir=input_dir, output_dir=output_dir, overwrite=args.overwrite)

    inputs = load_inputs(
        input_dir=input_dir,
        condition_labels_file=condition_labels_file,
        condition_summary_file=condition_summary_file,
    )

    X = inputs["X"]
    y = inputs["y"]
    feature_columns = inputs["feature_columns"]
    window_manifest = inputs["window_manifest"]
    dataset_summary = inputs["dataset_summary"]
    train_indices = inputs["train_indices"]
    val_indices = inputs["val_indices"]
    test_indices = inputs["test_indices"]
    condition_summary = inputs["condition_summary"]

    n_clusters = infer_n_clusters(
        condition_labels=inputs["condition_labels"],
        condition_summary=condition_summary,
        warnings=warnings,
    )

    condition_labels = validate_inputs(
        X=X,
        y=y,
        feature_columns=feature_columns,
        window_manifest=window_manifest,
        condition_labels=inputs["condition_labels"],
        n_clusters=n_clusters,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
    )

    append_condition_coverage_warning(
        condition_labels=condition_labels,
        n_clusters=n_clusters,
        warnings=warnings,
    )

    condition_onehot = build_condition_onehot(
        condition_labels=condition_labels,
        n_clusters=n_clusters,
    )
    X_aug = append_condition_features(X=X, condition_onehot=condition_onehot)
    feature_columns_aug = build_augmented_feature_columns(
        feature_columns=feature_columns,
        n_clusters=n_clusters,
    )

    copied_files = copy_metadata_files(
        input_dir=input_dir,
        output_dir=output_dir,
        condition_labels_file=condition_labels_file,
        condition_summary_file=condition_summary_file,
        condition_manifest_file=condition_manifest_file,
        warnings=warnings,
    )

    np.save(output_dir / "X.npy", X_aug)
    save_json(output_dir / "feature_columns.json", feature_columns_aug)

    augmented_dataset_summary = build_dataset_summary(
        original_summary=dataset_summary,
        input_dir=input_dir,
        X_aug=X_aug,
        y=y,
        feature_columns_aug=feature_columns_aug,
        condition_labels_file=condition_labels_file,
        condition_summary_file=condition_summary_file,
        n_clusters=n_clusters,
    )
    save_json(output_dir / "dataset_summary.json", augmented_dataset_summary)

    condition_augmented_summary = build_condition_augmented_summary(
        input_dir=input_dir,
        output_dir=output_dir,
        X=X,
        X_aug=X_aug,
        y=y,
        condition_labels=condition_labels,
        n_clusters=n_clusters,
        copied_files=copied_files,
        warnings=warnings,
    )
    save_json(output_dir / "condition_augmented_summary.json", condition_augmented_summary)

    print_summary(condition_augmented_summary, verbose=args.verbose)

    return condition_augmented_summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        run(args)
        return 0
    except Exception as exc:
        print(f"增强数据集构建失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())