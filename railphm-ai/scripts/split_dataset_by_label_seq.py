#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def parse_label_seq_list(value: str) -> list[str]:
    if value is None:
        return []

    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("label_seq 列表不能为空")

    return items


def save_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def choose_sort_col(manifest: pd.DataFrame) -> str | None:
    """
    选择 segment 内标签序列排序字段。
    优先 target_row，因为它最能表示样本预测目标点的顺序。
    """
    for col in ["target_row", "window_start_row", "target_time", "window_start_time"]:
        if col in manifest.columns:
            return col
    return None


def build_segment_label_sequences(manifest: pd.DataFrame) -> pd.DataFrame:
    """
    按 segment_id 聚合每个 segment 的 label_seq。
    输出字段：
    - segment_id
    - label_seq
    - sample_count
    - positive_count
    - positive_ratio
    """
    if "segment_id" not in manifest.columns:
        raise ValueError("window_manifest.csv 缺少 segment_id 字段")

    if "label" not in manifest.columns:
        raise ValueError("window_manifest.csv 缺少 label 字段")

    sort_col = choose_sort_col(manifest)

    working = manifest.copy()
    working["_original_index"] = np.arange(len(working))

    if sort_col is not None:
        working = working.sort_values(["segment_id", sort_col, "_original_index"])
    else:
        working = working.sort_values(["segment_id", "_original_index"])

    seq_df = working.groupby("segment_id").agg(
        label_seq=("label", lambda s: "".join(str(int(x)) for x in s.tolist())),
        sample_count=("label", "count"),
        positive_count=("label", "sum"),
        positive_ratio=("label", "mean"),
    ).reset_index()

    return seq_df


def validate_label_seq_groups(
    existing_label_seqs: set[str],
    train_label_seqs: list[str],
    val_label_seqs: list[str],
    test_label_seqs: list[str],
) -> None:
    train_set = set(train_label_seqs)
    val_set = set(val_label_seqs)
    test_set = set(test_label_seqs)

    overlap_train_val = train_set & val_set
    overlap_train_test = train_set & test_set
    overlap_val_test = val_set & test_set

    if overlap_train_val or overlap_train_test or overlap_val_test:
        raise ValueError(
            "label_seq 分组存在重叠: "
            f"train_val={sorted(overlap_train_val)}, "
            f"train_test={sorted(overlap_train_test)}, "
            f"val_test={sorted(overlap_val_test)}"
        )

    configured = train_set | val_set | test_set

    unknown = configured - existing_label_seqs
    if unknown:
        raise ValueError(
            "指定的 label_seq 在当前数据集中不存在: "
            f"{sorted(unknown)}; 当前存在: {sorted(existing_label_seqs)}"
        )

    missing = existing_label_seqs - configured
    if missing:
        raise ValueError(
            "还有 label_seq 没有被分配到 train/val/test: "
            f"{sorted(missing)}; 请补充到参数中"
        )


def assign_split_by_label_seq(
    seq_df: pd.DataFrame,
    train_label_seqs: list[str],
    val_label_seqs: list[str],
    test_label_seqs: list[str],
) -> pd.DataFrame:
    train_set = set(train_label_seqs)
    val_set = set(val_label_seqs)
    test_set = set(test_label_seqs)

    def choose_split(label_seq: str) -> str:
        if label_seq in train_set:
            return "train"
        if label_seq in val_set:
            return "val"
        if label_seq in test_set:
            return "test"
        raise ValueError(f"未分配的 label_seq: {label_seq}")

    result = seq_df.copy()
    result["split"] = result["label_seq"].apply(choose_split)
    return result


def validate_indices(
    train_indices: np.ndarray,
    val_indices: np.ndarray,
    test_indices: np.ndarray,
    total_samples: int,
) -> dict[str, Any]:
    train_set = set(train_indices.tolist())
    val_set = set(val_indices.tolist())
    test_set = set(test_indices.tolist())

    train_val_overlap = train_set & val_set
    train_test_overlap = train_set & test_set
    val_test_overlap = val_set & test_set

    all_indices = np.concatenate([train_indices, val_indices, test_indices])
    unique_indices = np.unique(all_indices)

    has_overlap = bool(train_val_overlap or train_test_overlap or val_test_overlap)
    has_missing_or_duplicate = (
        len(all_indices) != total_samples
        or len(unique_indices) != total_samples
    )

    if len(all_indices) > 0:
        min_index = int(all_indices.min())
        max_index = int(all_indices.max())
    else:
        min_index = None
        max_index = None

    index_out_of_range = (
        min_index is None
        or max_index is None
        or min_index < 0
        or max_index >= total_samples
    )

    return {
        "train_val_index_overlap": len(train_val_overlap),
        "train_test_index_overlap": len(train_test_overlap),
        "val_test_index_overlap": len(val_test_overlap),
        "has_index_overlap": has_overlap,
        "all_indices_count": int(len(all_indices)),
        "unique_indices_count": int(len(unique_indices)),
        "total_samples": int(total_samples),
        "has_duplicate_or_missing_index": bool(has_missing_or_duplicate),
        "min_index": min_index,
        "max_index": max_index,
        "index_out_of_range": bool(index_out_of_range),
    }


def build_split_summary(
    *,
    dataset_dir: Path,
    output_dir: Path,
    manifest: pd.DataFrame,
    seq_df: pd.DataFrame,
    train_indices: np.ndarray,
    val_indices: np.ndarray,
    test_indices: np.ndarray,
    index_check: dict[str, Any],
) -> dict[str, Any]:
    def part_summary(name: str, indices: np.ndarray) -> dict[str, Any]:
        subset = manifest.iloc[indices]
        segment_ids = set(subset["segment_id"].dropna().astype(str).tolist())

        y_part = subset["label"].astype(int).to_numpy()
        sample_count = int(len(indices))
        positive_count = int(y_part.sum()) if sample_count > 0 else 0
        negative_count = sample_count - positive_count
        positive_ratio = positive_count / sample_count if sample_count > 0 else 0.0

        label_seq_counts = (
            seq_df[seq_df["split"] == name]["label_seq"]
            .value_counts()
            .to_dict()
        )

        return {
            "name": name,
            "sample_count": sample_count,
            "segment_count": int(len(segment_ids)),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "positive_ratio": positive_ratio,
            "label_seq_count": {
                str(k): int(v) for k, v in label_seq_counts.items()
            },
            "indices_file": f"{name}_indices.npy",
        }

    cross = pd.crosstab(seq_df["label_seq"], seq_df["split"])

    label_seq_leakage = {}
    for label_seq, row in cross.iterrows():
        appeared_splits = [split for split, count in row.items() if int(count) > 0]
        label_seq_leakage[str(label_seq)] = appeared_splits

    has_label_seq_leakage = any(
        len(splits) > 1 for splits in label_seq_leakage.values()
    )

    return {
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "split_strategy": "label_seq",
        "total_samples": int(len(manifest)),
        "total_segments": int(seq_df["segment_id"].nunique()),
        "total_label_seq_patterns": int(seq_df["label_seq"].nunique()),
        "train": part_summary("train", train_indices),
        "val": part_summary("val", val_indices),
        "test": part_summary("test", test_indices),
        "label_seq_distribution": (
            seq_df.groupby(["label_seq", "split"])
            .size()
            .reset_index(name="segment_count")
            .to_dict(orient="records")
        ),
        "label_seq_leakage_check": {
            "has_label_seq_leakage": bool(has_label_seq_leakage),
            "label_seq_to_splits": label_seq_leakage,
        },
        "index_check": index_check,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split RailPHM dataset by segment label sequence for leakage diagnosis."
    )

    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="窗口数据集目录，例如 data/datasets/window_w60_s20_h100_raw",
    )
    parser.add_argument(
        "--train-label-seqs",
        type=parse_label_seq_list,
        required=True,
        help="分配到 train 的 label_seq，用逗号分隔，例如 000000,1111111,010101",
    )
    parser.add_argument(
        "--val-label-seqs",
        type=parse_label_seq_list,
        required=True,
        help="分配到 val 的 label_seq，用逗号分隔，例如 0000000,1001100",
    )
    parser.add_argument(
        "--test-label-seqs",
        type=parse_label_seq_list,
        required=True,
        help="分配到 test 的 label_seq，用逗号分隔，例如 111110",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="如果 dataset_dir/splits 已存在，则覆盖旧划分文件",
    )

    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    output_dir = dataset_dir / "splits"

    manifest_path = dataset_dir / "window_manifest.csv"
    y_path = dataset_dir / "y.npy"

    if not dataset_dir.exists():
        raise FileNotFoundError(f"数据集目录不存在: {dataset_dir}")

    if not manifest_path.exists():
        raise FileNotFoundError(f"缺少 window_manifest.csv: {manifest_path}")

    if not y_path.exists():
        raise FileNotFoundError(f"缺少 y.npy: {y_path}")

    manifest = pd.read_csv(manifest_path, encoding="utf-8-sig")
    y = np.load(y_path)

    if len(manifest) != len(y):
        raise ValueError(
            f"manifest 行数与 y 样本数不一致: manifest={len(manifest)}, y={len(y)}"
        )

    if "label" not in manifest.columns:
        raise ValueError("window_manifest.csv 缺少 label 字段")

    manifest_label = manifest["label"].astype(int).to_numpy()
    if not np.array_equal(manifest_label, y.astype(int)):
        raise ValueError("manifest 中的 label 与 y.npy 不一致，请先修复数据集")

    seq_df = build_segment_label_sequences(manifest)
    existing_label_seqs = set(seq_df["label_seq"].astype(str).tolist())

    validate_label_seq_groups(
        existing_label_seqs=existing_label_seqs,
        train_label_seqs=args.train_label_seqs,
        val_label_seqs=args.val_label_seqs,
        test_label_seqs=args.test_label_seqs,
    )

    seq_df = assign_split_by_label_seq(
        seq_df=seq_df,
        train_label_seqs=args.train_label_seqs,
        val_label_seqs=args.val_label_seqs,
        test_label_seqs=args.test_label_seqs,
    )

    segment_to_split = dict(zip(seq_df["segment_id"], seq_df["split"]))

    manifest_with_split = manifest.copy()
    manifest_with_split["split"] = manifest_with_split["segment_id"].map(segment_to_split)

    if manifest_with_split["split"].isna().any():
        missing_count = int(manifest_with_split["split"].isna().sum())
        raise ValueError(f"存在未能分配 split 的样本: {missing_count}")

    train_indices = np.flatnonzero(manifest_with_split["split"].to_numpy() == "train").astype(np.int64)
    val_indices = np.flatnonzero(manifest_with_split["split"].to_numpy() == "val").astype(np.int64)
    test_indices = np.flatnonzero(manifest_with_split["split"].to_numpy() == "test").astype(np.int64)

    index_check = validate_indices(
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
        total_samples=len(manifest),
    )

    if index_check["has_index_overlap"]:
        raise ValueError(f"划分索引存在重叠: {index_check}")

    if index_check["has_duplicate_or_missing_index"]:
        raise ValueError(f"划分索引存在重复或遗漏: {index_check}")

    if index_check["index_out_of_range"]:
        raise ValueError(f"划分索引越界: {index_check}")

    if output_dir.exists():
        if not args.overwrite:
            raise FileExistsError(
                f"划分输出目录已存在: {output_dir}。如需覆盖，请添加 --overwrite"
            )
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    np.save(output_dir / "train_indices.npy", train_indices)
    np.save(output_dir / "val_indices.npy", val_indices)
    np.save(output_dir / "test_indices.npy", test_indices)

    seq_df.to_csv(output_dir / "segment_label_sequences.csv", index=False, encoding="utf-8-sig")

    summary = build_split_summary(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        manifest=manifest_with_split,
        seq_df=seq_df,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
        index_check=index_check,
    )

    save_json(output_dir / "split_summary.json", summary)

    print()
    print("RailPHM label_seq split finished.")
    print("-" * 72)
    print(f"dataset_dir: {dataset_dir}")
    print(f"output_dir : {output_dir}")
    print(f"total_samples: {summary['total_samples']}")
    print(f"total_segments: {summary['total_segments']}")
    print(f"total_label_seq_patterns: {summary['total_label_seq_patterns']}")
    print()
    print("train:")
    print(f"  sample_count: {summary['train']['sample_count']}")
    print(f"  segment_count: {summary['train']['segment_count']}")
    print(f"  positive_ratio: {summary['train']['positive_ratio']:.6f}")
    print(f"  label_seq_count: {summary['train']['label_seq_count']}")
    print()
    print("val:")
    print(f"  sample_count: {summary['val']['sample_count']}")
    print(f"  segment_count: {summary['val']['segment_count']}")
    print(f"  positive_ratio: {summary['val']['positive_ratio']:.6f}")
    print(f"  label_seq_count: {summary['val']['label_seq_count']}")
    print()
    print("test:")
    print(f"  sample_count: {summary['test']['sample_count']}")
    print(f"  segment_count: {summary['test']['segment_count']}")
    print(f"  positive_ratio: {summary['test']['positive_ratio']:.6f}")
    print(f"  label_seq_count: {summary['test']['label_seq_count']}")
    print()
    print("label_seq leakage:")
    print(f"  has_label_seq_leakage: {summary['label_seq_leakage_check']['has_label_seq_leakage']}")
    print()
    print("Output files:")
    print(f"- {output_dir / 'train_indices.npy'}")
    print(f"- {output_dir / 'val_indices.npy'}")
    print(f"- {output_dir / 'test_indices.npy'}")
    print(f"- {output_dir / 'segment_label_sequences.csv'}")
    print(f"- {output_dir / 'split_summary.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
