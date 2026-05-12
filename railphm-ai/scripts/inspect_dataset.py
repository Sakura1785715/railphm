# scripts/inspect_dataset.py

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.dataset.dataset_inspector import DatasetInspector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect RailPHM window dataset consistency and quality."
    )

    parser.add_argument(
        "--dataset-dir",
        required=True,
        type=Path,
        help="窗口数据集目录，例如 data/datasets/window_w30_s1_h1",
    )

    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="检查结果输出文件，默认写入 dataset_dir/inspection_summary.json",
    )

    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="如果存在 warnings，也以非 0 状态码退出",
    )

    return parser.parse_args()


def print_result(result) -> None:
    summary = result.summary

    print()
    print("RailPHM dataset inspection finished.")
    print("-" * 72)
    print(f"dataset_dir          : {summary.get('dataset_dir')}")
    print(f"is_valid             : {result.is_valid}")
    print(f"X_shape              : {summary.get('X_shape')}")
    print(f"y_shape              : {summary.get('y_shape')}")
    print(f"manifest_rows        : {summary.get('manifest_rows')}")
    print(f"feature_dim          : {summary.get('feature_dim')}")
    print(f"feature_column_count : {summary.get('feature_column_count')}")
    print(f"unique_y             : {summary.get('unique_y')}")
    print(f"positive_count       : {summary.get('positive_count')}")
    print(f"negative_count       : {summary.get('negative_count')}")

    positive_ratio = summary.get("positive_ratio", 0.0)
    try:
        positive_ratio_text = f"{float(positive_ratio):.6f}"
    except (TypeError, ValueError):
        positive_ratio_text = str(positive_ratio)

    print(f"positive_ratio       : {positive_ratio_text}")
    print(f"X_min                : {summary.get('X_min')}")
    print(f"X_max                : {summary.get('X_max')}")
    print(f"has_nan              : {summary.get('has_nan')}")
    print(f"has_inf              : {summary.get('has_inf')}")
    print(f"segment_count        : {summary.get('segment_count')}")
    print(f"samples_per_seg_min  : {summary.get('samples_per_segment_min')}")
    print(f"samples_per_seg_max  : {summary.get('samples_per_segment_max')}")
    print(f"samples_per_seg_mean : {summary.get('samples_per_segment_mean')}")
    print("-" * 72)

    if result.errors:
        print()
        print("Errors:")
        for error in result.errors:
            print(f"- {error}")

    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


def main() -> int:
    args = parse_args()

    dataset_dir = args.dataset_dir
    output_file = args.output_file or dataset_dir / "inspection_summary.json"

    try:
        result = DatasetInspector().inspect(
            dataset_dir=dataset_dir,
            output_file=output_file,
        )
    except Exception as exc:
        print(f"[ERROR] 数据集检查失败: {exc}", file=sys.stderr)
        return 1

    print_result(result)
    print()
    print(f"inspection_summary saved to: {output_file}")

    if not result.is_valid:
        return 1

    if args.fail_on_warning and result.warnings:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())