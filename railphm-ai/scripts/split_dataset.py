# scripts/split_dataset.py

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.dataset.split_builder import DatasetSplitBuilder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split RailPHM window dataset by segment_id to avoid leakage."
    )

    parser.add_argument(
        "--dataset-dir",
        required=True,
        type=Path,
        help="窗口数据集目录，例如 data/datasets/window_w30_s1_h1",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="划分结果输出目录，默认写入 dataset_dir/splits",
    )

    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="训练集 segment 比例，默认 0.7",
    )

    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.15,
        help="验证集 segment 比例，默认 0.15",
    )

    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="测试集 segment 比例，默认 0.15",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子，默认 42",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="如果输出目录已存在，则覆盖其中旧划分文件",
    )

    return parser.parse_args()


def print_split_summary(summary: dict) -> None:
    print()
    print("RailPHM dataset split finished.")
    print("-" * 72)
    print(f"dataset_dir     : {summary.get('dataset_dir')}")
    print(f"output_dir      : {summary.get('output_dir')}")
    print(f"split_strategy  : {summary.get('split_strategy')}")
    print(f"train_ratio     : {summary.get('train_ratio')}")
    print(f"val_ratio       : {summary.get('val_ratio')}")
    print(f"test_ratio      : {summary.get('test_ratio')}")
    print(f"seed            : {summary.get('seed')}")
    print(f"total_samples   : {summary.get('total_samples')}")
    print(f"total_segments  : {summary.get('total_segments')}")
    print("-" * 72)

    for part_name in ["train", "val", "test"]:
        part = summary.get(part_name, {})
        print(f"{part_name}:")
        print(f"  sample_count   : {part.get('sample_count')}")
        print(f"  segment_count  : {part.get('segment_count')}")
        print(f"  positive_count : {part.get('positive_count')}")
        print(f"  negative_count : {part.get('negative_count')}")

        positive_ratio = part.get("positive_ratio", 0.0)
        try:
            positive_ratio_text = f"{float(positive_ratio):.6f}"
        except (TypeError, ValueError):
            positive_ratio_text = str(positive_ratio)

        print(f"  positive_ratio : {positive_ratio_text}")
        print(f"  indices_file   : {part.get('indices_file')}")
        print()

    leakage_check = summary.get("leakage_check", {})
    print("leakage_check:")
    print(f"  train_val_overlap_count  : {leakage_check.get('train_val_overlap_count')}")
    print(f"  train_test_overlap_count : {leakage_check.get('train_test_overlap_count')}")
    print(f"  val_test_overlap_count   : {leakage_check.get('val_test_overlap_count')}")
    print(f"  has_segment_leakage      : {leakage_check.get('has_segment_leakage')}")


def main() -> int:
    args = parse_args()

    output_dir = args.output_dir or args.dataset_dir / "splits"

    try:
        result = DatasetSplitBuilder().split(
            dataset_dir=args.dataset_dir,
            output_dir=output_dir,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(f"[ERROR] 数据集划分失败: {exc}", file=sys.stderr)
        return 1

    print_split_summary(result.summary)

    print()
    print("Output files:")
    print(f"- {output_dir / 'train_indices.npy'}")
    print(f"- {output_dir / 'val_indices.npy'}")
    print(f"- {output_dir / 'test_indices.npy'}")
    print(f"- {output_dir / 'split_summary.json'}")

    leakage_check = result.summary.get("leakage_check", {})
    if leakage_check.get("has_segment_leakage"):
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())