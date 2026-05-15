#!/usr/bin/env python3
"""
K-means 工况划分命令行脚本。

从标准化后的窗口数据集里读取 X.npy、y.npy、feature_columns.json、window_manifest.csv 和 splits，
提取每个窗口的工况统计特征，
只用训练集样本拟合 K-means，
再给全部样本预测 condition_id，
最后生成 condition_labels.npy、condition_manifest.csv、condition_summary.json、condition_model.pkl。
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.condition import ConditionClusterConfig, ConditionFeatureExtractor, ConditionKMeansClusterer


OUTPUT_FILENAMES = [
    "condition_labels.npy", # 每个窗口样本对应的工况编号，shape = [num_samples]
    "condition_manifest.csv", # 每个窗口样本的工况追溯表，包括 sample_id、segment_id、时间、label、condition_id、condition_label、工况统计特征等
    "condition_summary.json", # 工况聚类摘要，包括每类工况样本数、训练/验证/测试分布、正样本比例、聚类中心解释等
    "condition_model.pkl", # 保存工况聚类相关模型信息，例如聚类配置、工况特征名、标签映射、聚类中心、summary
]

# 定义命令行参数
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cluster RailPHM window samples into operating conditions by K-means."
    )

    parser.add_argument("--dataset-dir", type=Path, required=True, help="窗口数据集目录")
    parser.add_argument("--n-clusters", type=int, default=3, help="K-means 聚类数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--max-iter", type=int, default=300, help="KMeans 最大迭代次数")
    parser.add_argument("--n-init", type=int, default=10, help="KMeans 初始化次数")
    parser.add_argument("--output-dir", type=Path, default=None, help="工况划分结果输出目录")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出文件")
    parser.add_argument("--verbose", action="store_true", help="打印更详细的工况划分信息")

    return parser


# 检查输入数据集目录
def validate_dataset_dir(dataset_dir: Path) -> None:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"数据集目录不存在: {dataset_dir}")

    if not dataset_dir.is_dir():
        raise NotADirectoryError(f"dataset_dir 必须是目录: {dataset_dir}")

    dataset_files = [
        "X.npy",
        "y.npy",
        "feature_columns.json",
        "window_manifest.csv",
    ]
    split_files = [
        "train_indices.npy",
        "val_indices.npy",
        "test_indices.npy",
    ]

    for filename in dataset_files:
        path = dataset_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少数据集文件：{filename}")

    for filename in split_files:
        path = dataset_dir / "splits" / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少划分文件：splits/{filename}")


def check_output_paths(output_dir: Path, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_files = [
        filename for filename in OUTPUT_FILENAMES
        if (output_dir / filename).exists()
    ]

    if existing_files and not overwrite:
        existing_text = "、".join(existing_files)
        raise FileExistsError(
            f"输出文件已存在：{existing_text}。如需覆盖，请使用 --overwrite"
        )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# 读取工况聚类需要的全部输入
def load_dataset_inputs(dataset_dir: Path) -> dict[str, Any]:
    return {
        "X": np.load(dataset_dir / "X.npy", allow_pickle=False),
        "y": np.load(dataset_dir / "y.npy", allow_pickle=False),
        "feature_columns": load_json(dataset_dir / "feature_columns.json"),
        "window_manifest": pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig"),
        "train_indices": np.load(dataset_dir / "splits" / "train_indices.npy", allow_pickle=False),
        "val_indices": np.load(dataset_dir / "splits" / "val_indices.npy", allow_pickle=False),
        "test_indices": np.load(dataset_dir / "splits" / "test_indices.npy", allow_pickle=False),
    }


def validate_loaded_inputs(
    X: np.ndarray,
    y: np.ndarray,
    feature_columns: list[str],
    window_manifest: pd.DataFrame,
    train_indices: np.ndarray,
    val_indices: np.ndarray,
    test_indices: np.ndarray,
) -> None:
    if X.ndim != 3:
        raise ValueError("X 必须为三维数组 [num_samples, window_size, feature_dim]")

    if y.ndim != 1:
        raise ValueError("y 必须为一维数组")

    if X.shape[0] != y.shape[0]:
        raise ValueError("X 与 y 样本数不一致")

    if not isinstance(feature_columns, list) or not all(isinstance(item, str) for item in feature_columns):
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

    sample_count = int(X.shape[0])
    train_indices = _validate_split_indices(train_indices, sample_count, "train_indices")
    val_indices = _validate_split_indices(val_indices, sample_count, "val_indices")
    test_indices = _validate_split_indices(test_indices, sample_count, "test_indices")

    all_indices = np.concatenate([train_indices, val_indices, test_indices])

    if np.unique(all_indices).shape[0] != all_indices.shape[0]:
        raise ValueError("train/val/test 划分索引存在重复")

    expected_indices = np.arange(sample_count, dtype=np.int64)
    if not np.array_equal(np.sort(all_indices), expected_indices):
        raise ValueError("train/val/test 划分索引未覆盖全部样本")


def _validate_split_indices(indices: np.ndarray, sample_count: int, name: str) -> np.ndarray:
    if not isinstance(indices, np.ndarray):
        raise ValueError(f"{name} 必须是 numpy.ndarray")

    if indices.ndim != 1:
        raise ValueError(f"{name} 必须是一维整数数组")

    if not np.issubdtype(indices.dtype, np.integer):
        raise ValueError(f"{name} 必须是一维整数数组")

    normalized = indices.astype(np.int64, copy=False)

    if normalized.size > 0 and (normalized.min() < 0 or normalized.max() >= sample_count):
        raise ValueError(f"{name} 存在越界索引")

    return normalized


# 生成工况追溯表
def build_condition_manifest(
    window_manifest: pd.DataFrame,
    condition_ids: np.ndarray,
    condition_labels: list[str],
    condition_feature_matrix: np.ndarray,
    condition_feature_names: list[str],
) -> pd.DataFrame:
    sample_count = int(condition_ids.shape[0])
    result = pd.DataFrame({"sample_index": np.arange(sample_count, dtype=np.int64)})

    required_columns = [
        "sample_id",
        "segment_id",
        "segment_file",
        "window_start_time",
        "window_end_time",
        "target_time",
        "label",
    ]

    for column in required_columns:
        if column in window_manifest.columns:
            result[column] = window_manifest[column].values
        else:
            result[column] = ""

    result["condition_id"] = condition_ids.astype(np.int64)
    result["condition_label"] = condition_labels

    for feature_index, feature_name in enumerate(condition_feature_names):
        result[feature_name] = condition_feature_matrix[:, feature_index].astype(np.float32)

    return result


def build_enriched_summary(
    dataset_dir: Path,
    output_dir: Path,
    config: ConditionClusterConfig,
    feature_columns: list[str],
    y: np.ndarray,
    train_indices: np.ndarray,
    val_indices: np.ndarray,
    test_indices: np.ndarray,
    condition_ids: np.ndarray,
    condition_feature_names: list[str],
    cluster_summary: dict,
    warnings: list[str],
) -> dict[str, Any]:
    n_clusters = int(config.n_clusters)

    cluster_positive_ratio = {
        str(cluster_id): _positive_ratio_for_cluster(y, condition_ids, cluster_id)
        for cluster_id in range(n_clusters)
    }

    cluster_split_distribution = {
        "train": _count_split_distribution(condition_ids, train_indices, n_clusters),
        "val": _count_split_distribution(condition_ids, val_indices, n_clusters),
        "test": _count_split_distribution(condition_ids, test_indices, n_clusters),
    }

    return {
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "n_clusters": n_clusters,
        "seed": int(config.seed),
        "max_iter": int(config.max_iter),
        "n_init": int(config.n_init),
        "fit_scope": "train_split_only",
        "sample_count": int(condition_ids.shape[0]),
        "train_sample_count": int(train_indices.shape[0]),
        "val_sample_count": int(val_indices.shape[0]),
        "test_sample_count": int(test_indices.shape[0]),
        "feature_names": list(feature_columns),
        "condition_feature_names": list(condition_feature_names),
        "condition_label_mapping": cluster_summary.get("condition_label_mapping", {}),
        "cluster_sample_count": cluster_summary.get("cluster_sample_count", {}),
        "cluster_train_sample_count": cluster_summary.get("cluster_train_sample_count", {}),
        "cluster_positive_ratio": cluster_positive_ratio,
        "cluster_split_distribution": cluster_split_distribution,
        "cluster_feature_summary": cluster_summary.get("cluster_feature_summary", {}),
        "warnings": warnings,
    }


def _positive_ratio_for_cluster(
    y: np.ndarray,
    condition_ids: np.ndarray,
    cluster_id: int,
) -> float:
    mask = condition_ids == cluster_id
    if not mask.any():
        return 0.0

    return float(y[mask].sum() / mask.sum())


def _count_split_distribution(
    condition_ids: np.ndarray,
    indices: np.ndarray,
    n_clusters: int,
) -> dict[str, int]:
    split_condition_ids = condition_ids[indices]
    return {
        str(cluster_id): int((split_condition_ids == cluster_id).sum())
        for cluster_id in range(n_clusters)
    }


def save_condition_outputs(
    output_dir: Path,
    condition_ids: np.ndarray,
    condition_manifest: pd.DataFrame,
    condition_summary: dict,
    model_info: dict,
) -> None:
    np.save(output_dir / "condition_labels.npy", condition_ids.astype(np.int64, copy=False))

    condition_manifest.to_csv(
        output_dir / "condition_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )

    save_json(output_dir / "condition_summary.json", condition_summary)

    with (output_dir / "condition_model.pkl").open("wb") as file:
        pickle.dump(model_info, file)


def build_model_info(
    config: ConditionClusterConfig,
    condition_feature_names: list[str],
    cluster_result,
    condition_summary: dict,
) -> dict[str, Any]:
    return {
        "config": {
            "n_clusters": int(config.n_clusters),
            "seed": int(config.seed),
            "max_iter": int(config.max_iter),
            "n_init": int(config.n_init),
            "auto_label": bool(config.auto_label),
        },
        "condition_feature_names": list(condition_feature_names),
        "condition_label_mapping": dict(cluster_result.condition_label_mapping),
        "cluster_centers": cluster_result.cluster_centers,
        "cluster_centers_original_scale": cluster_result.cluster_centers_original_scale,
        "summary": condition_summary,
    }


def print_summary(summary: dict, output_dir: Path, verbose: bool = False) -> None:
    print()
    print("RailPHM condition clustering finished.")
    print(f"dataset_dir: {summary['dataset_dir']}")
    print(f"output_dir: {summary['output_dir']}")
    print(f"n_clusters: {summary['n_clusters']}")
    print(f"sample_count: {summary['sample_count']}")
    print(f"train_sample_count: {summary['train_sample_count']}")
    print(f"val_sample_count: {summary['val_sample_count']}")
    print(f"test_sample_count: {summary['test_sample_count']}")

    print()
    print("condition distribution:")
    for cluster_id in range(int(summary["n_clusters"])):
        key = str(cluster_id)
        label = summary["condition_label_mapping"].get(key, f"工况{cluster_id}")
        sample_count = summary["cluster_sample_count"].get(key, 0)
        positive_ratio = summary["cluster_positive_ratio"].get(key, 0.0)
        print(
            f"- condition_id={cluster_id}, "
            f"label={label}, "
            f"sample_count={sample_count}, "
            f"positive_ratio={positive_ratio:.6f}"
        )

    print()
    print("Output files:")
    for filename in OUTPUT_FILENAMES:
        print(f"- {output_dir / filename}")

    if not verbose:
        return

    print()
    print("condition_feature_names:")
    for feature_name in summary["condition_feature_names"]:
        print(f"- {feature_name}")

    print()
    print("cluster_feature_summary:")
    print(json.dumps(summary["cluster_feature_summary"], ensure_ascii=False, indent=2))

    warnings = summary.get("warnings") or []
    if warnings:
        print()
        print("warnings:")
        for warning in warnings:
            print(f"- {warning}")


def run(args: argparse.Namespace) -> dict[str, Any]:
    dataset_dir = args.dataset_dir
    output_dir = args.output_dir or dataset_dir

    validate_dataset_dir(dataset_dir)
    check_output_paths(output_dir, overwrite=args.overwrite)

    inputs = load_dataset_inputs(dataset_dir)

    X = inputs["X"]
    y = inputs["y"]
    feature_columns = inputs["feature_columns"]
    window_manifest = inputs["window_manifest"]
    train_indices = inputs["train_indices"]
    val_indices = inputs["val_indices"]
    test_indices = inputs["test_indices"]

    validate_loaded_inputs(
        X=X,
        y=y,
        feature_columns=feature_columns,
        window_manifest=window_manifest,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
    )

    feature_result = ConditionFeatureExtractor().extract(X, feature_columns)

    config = ConditionClusterConfig(
        n_clusters=args.n_clusters,
        seed=args.seed,
        max_iter=args.max_iter,
        n_init=args.n_init,
    )

    cluster_result = ConditionKMeansClusterer().fit_predict(
        feature_matrix=feature_result.feature_matrix,
        feature_names=feature_result.feature_names,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
        config=config,
    )

    warnings = list(feature_result.warnings) + list(cluster_result.warnings)

    condition_manifest = build_condition_manifest(
        window_manifest=window_manifest,
        condition_ids=cluster_result.condition_ids,
        condition_labels=cluster_result.condition_labels,
        condition_feature_matrix=feature_result.feature_matrix,
        condition_feature_names=feature_result.feature_names,
    )

    condition_summary = build_enriched_summary(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        config=config,
        feature_columns=feature_columns,
        y=y,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
        condition_ids=cluster_result.condition_ids,
        condition_feature_names=feature_result.feature_names,
        cluster_summary=cluster_result.summary,
        warnings=warnings,
    )

    model_info = build_model_info(
        config=config,
        condition_feature_names=feature_result.feature_names,
        cluster_result=cluster_result,
        condition_summary=condition_summary,
    )

    save_condition_outputs(
        output_dir=output_dir,
        condition_ids=cluster_result.condition_ids,
        condition_manifest=condition_manifest,
        condition_summary=condition_summary,
        model_info=model_info,
    )

    print_summary(condition_summary, output_dir=output_dir, verbose=args.verbose)

    return condition_summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        run(args)
        return 0
    except Exception as exc:
        print(f"工况划分失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())