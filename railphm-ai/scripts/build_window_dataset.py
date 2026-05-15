"""
CSV segment
   ↓
1. build_window_dataset.py
   ↓
原始窗口数据集
   ↓
2. split_dataset.py
   ↓
按 segment_id 划分 train / val / test
   ↓
3. scale_window_dataset.py
   ↓
基于训练集统计量标准化后的窗口数据集
   ↓
4. cluster_conditions.py
   ↓
K-means 工况划分结果
   ↓
5. build_condition_augmented_dataset.py
   ↓
拼接 condition one-hot 后的增强数据集
   ↓
6. train_sequence_model.py
   ↓
训练 Bi-LSTM+Attention 等时序模型
   ↓
7. build_model_artifact_manifest.py
   ↓
生成 model_artifact_manifest.json，供在线推理加载

作用： CSV segment → 窗口数据集的命令行入口
WindowDatasetBuilder 是窗口数据集构建主逻辑
"""
import argparse
import sys
from pathlib import Path
# 从项目根目录正确导入 app 包
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.dataset.dataset_builder import WindowDatasetBuilder # 导入核心对象
# 导入默认窗口配置参数
from app.dataset.feature_config import (
    DEFAULT_PREDICTION_HORIZON,
    DEFAULT_STRIDE,
    DEFAULT_WINDOW_SIZE,
)
from app.dataset.feature_processor import FeatureProcessor
from app.dataset.feature_profiles import get_feature_profile, list_feature_profiles
from app.dataset.segment_loader import SegmentLoader

def parse_args() -> argparse.Namespace:
    """
    解析窗口数据集构建命令行参数。
    python scripts/build_window_dataset.py \
        --segments-dir data/processed/atp_segments \
        --output-dir data/datasets/window_w30_s1_h1 \
        --feature-profile full_features \
        --window-size 30 \
        --stride 1 \
        --horizon 1 \
        --overwrite
    """

    parser = argparse.ArgumentParser(
        description="Build RailPHM ATP sliding-window dataset from segment CSV files."
    )

    # --feature-profile参数，决定本次构建数据集时使用哪一组特征
    parser.add_argument(
        "--feature-profile",
        type=str,
        default="full_features",
        choices=list_feature_profiles(),
        help="特征消融配置：full_features / remove_id_like_features / continuous_only_features",
    )

    # --segments-dir：输入目录，存放切分后的segment.csv
    parser.add_argument(
        "--segments-dir",
        required=True,
        type=Path,
        help="已切分的 ATP segment CSV 文件目录，例如 data/processed/atp_segments",
    )

    # 输出目录 包括X.npy y.npy feature_columns.json window_manifest.csv dataset_summary.json
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="窗口数据集输出目录，例如 data/datasets/window_w30_s1_h1",
    )

    # --window-size：窗口长度
    parser.add_argument(
        "--window-size",
        type=int,
        default=DEFAULT_WINDOW_SIZE,
        help=f"滑动窗口长度，默认 {DEFAULT_WINDOW_SIZE}",
    )

    # --stride：步长
    parser.add_argument(
        "--stride",
        type=int,
        default=DEFAULT_STRIDE,
        help=f"滑动窗口步长，默认 {DEFAULT_STRIDE}",
    )


    parser.add_argument(
        "--horizon",
        "--prediction-horizon",
        dest="prediction_horizon",
        type=int,
        default=DEFAULT_PREDICTION_HORIZON,
        help=f"预测步长，默认 {DEFAULT_PREDICTION_HORIZON}",
    )

    # 如果输出目录存在，默认报错，加上--overwrite会删除旧输出目录并重新构建
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="如果输出目录已存在，则删除后重新构建",
    )

    parser.add_argument(
        "--skip-invalid-segments",
        dest="skip_invalid_segments",
        action="store_true",
        default=True,
        help="跳过无法读取、时间不连续或无法生成窗口的 segment，默认开启",
    )

    parser.add_argument(
        "--no-skip-invalid-segments",
        dest="skip_invalid_segments",
        action="store_false",
        help="遇到异常 segment 时直接终止构建",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出更详细的构建结果，包括跳过文件和缺失特征字段",
    )

    return parser.parse_args()



def resolve_existing_feature_columns(segments_dir: Path, requested_columns: list[str]) -> tuple[list[str], list[str]]:
    """
    校验工作：
    根据 feature_profile 期望使用的字段
    去真实 CSV 里看哪些字段实际存在
    只保留实际存在的字段进入 FeatureProcessor
    """
    segment_files = sorted(Path(segments_dir).glob("segment_*.csv"))
    if not segment_files:
        raise FileNotFoundError(f"segments_dir 下未找到 segment_*.csv: {segments_dir}")

    loader = SegmentLoader()
    last_error = None

    for file_path in segment_files:
        try:
            segment_data = loader.load_segment(file_path)
            available_columns = set(segment_data.df.columns)
            actual_columns = [column for column in requested_columns if column in available_columns]
            missing_columns = [column for column in requested_columns if column not in available_columns]

            if not actual_columns:
                raise ValueError(
                    f"feature_profile 中没有任何字段存在于首个可读 segment: {file_path.name}"
                )

            return actual_columns, missing_columns
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"无法读取任何 segment 文件以解析字段，最后一次错误: {last_error}")


# 终端输出构建摘要
def print_summary(summary: dict, verbose: bool = False) -> None:
    """
    将 WindowDatasetBuilder 返回的 summary 打印到终端。

    summary 同时会写入 output_dir/dataset_summary.json。
    """

    print()
    print("RailPHM window dataset build finished.")
    print("-" * 72)
    # 打印基本信息
    print(f"segments_dir          : {summary.get('segments_dir')}")
    print(f"output_dir            : {summary.get('output_dir')}")
    print(f"window_size           : {summary.get('window_size')}")
    print(f"stride                : {summary.get('stride')}")
    print(f"prediction_horizon    : {summary.get('prediction_horizon')}")
    print(f"feature_profile       : {summary.get('feature_profile', 'full_features')}")
    # 打印 segment 使用情况
    print(f"total_segment_files   : {summary.get('total_segment_files')}")
    print(f"used_segment_count    : {summary.get('used_segment_count')}")
    print(f"skipped_segment_count : {summary.get('skipped_segment_count')}")
    # 打印窗口样本统计
    print(f"total_windows         : {summary.get('total_windows')}")
    print(f"positive_count        : {summary.get('positive_count')}")
    print(f"negative_count        : {summary.get('negative_count')}")
    # 格式化 positive_ratio
    positive_ratio = summary.get("positive_ratio", 0.0)
    try:
        positive_ratio_text = f"{float(positive_ratio):.6f}"
    except (TypeError, ValueError):
        positive_ratio_text = str(positive_ratio)
    # 打印特征维度
    print(f"positive_ratio        : {positive_ratio_text}")
    print(f"feature_dim           : {summary.get('feature_dim')}")
    actual_feature_columns = summary.get("actual_feature_columns") or summary.get("feature_columns") or []
    requested_feature_columns = summary.get("requested_feature_columns") or []
    missing_profile_columns = summary.get("missing_profile_columns") or []
    # 打印输出文件
    print(f"requested_feature_dim : {len(requested_feature_columns)}")
    print(f"actual_feature_dim    : {len(actual_feature_columns)}")
    print(f"X_shape               : {summary.get('X_shape')}")
    print(f"y_shape               : {summary.get('y_shape')}")
    print("-" * 72)

    output_dir = Path(str(summary.get("output_dir")))

    print("Output files:")
    print(f"- {output_dir / 'X.npy'}")
    print(f"- {output_dir / 'y.npy'}")
    print(f"- {output_dir / 'feature_columns.json'}")
    print(f"- {output_dir / 'window_manifest.csv'}")
    print(f"- {output_dir / 'dataset_summary.json'}")

    # 加了--verbose，会继续打印详细信息
    if not verbose:
        return
    
    if requested_feature_columns:
        print()
        print("requested_feature_columns:")
    for column in requested_feature_columns:
        print(f"- {column}")

    if actual_feature_columns:
        print()
        print("actual_feature_columns:")
        for column in actual_feature_columns:
            print(f"- {column}")

    if missing_profile_columns:
        print()
        print("missing_profile_columns:")
        for column in missing_profile_columns:
            print(f"- {column}")

    print()
    print("Verbose details:")
    print("-" * 72)

    missing_feature_columns = summary.get("missing_feature_columns") or []
    all_nan_feature_columns = summary.get("all_nan_feature_columns") or []
    skipped_segments = summary.get("skipped_segments") or []

    print(f"missing_feature_columns count : {len(missing_feature_columns)}")
    print(f"all_nan_feature_columns count : {len(all_nan_feature_columns)}")

    if missing_feature_columns:
        print()
        print("missing_feature_columns:")
        for column in missing_feature_columns:
            print(f"- {column}")

    if all_nan_feature_columns:
        print()
        print("all_nan_feature_columns:")
        for column in all_nan_feature_columns:
            print(f"- {column}")

    if skipped_segments:
        print()
        print("skipped_segments preview:")
        for item in skipped_segments[:20]:
            print(f"- {item.get('segment_file')}: {item.get('reason')}")

        if len(skipped_segments) > 20:
            print(f"... and {len(skipped_segments) - 20} more skipped segments")

# 脚本流程
def main() -> int:
    args = parse_args()

    requested_feature_columns = get_feature_profile(args.feature_profile)
    actual_feature_columns, missing_profile_columns = resolve_existing_feature_columns(
        segments_dir=args.segments_dir,
        requested_columns=requested_feature_columns,
    )

    feature_processor = FeatureProcessor(feature_columns=actual_feature_columns)
    builder = WindowDatasetBuilder(feature_processor=feature_processor)

    try:
        summary = builder.build(
            segments_dir=args.segments_dir,
            output_dir=args.output_dir,
            window_size=args.window_size,
            stride=args.stride,
            prediction_horizon=args.prediction_horizon,
            overwrite=args.overwrite,
            skip_invalid_segments=args.skip_invalid_segments,
        )
        summary["feature_profile"] = args.feature_profile
        summary["requested_feature_columns"] = requested_feature_columns
        summary["actual_feature_columns"] = actual_feature_columns
        summary["missing_profile_columns"] = missing_profile_columns

        summary_path = args.output_dir / "dataset_summary.json"
        summary_path.write_text(
            __import__("json").dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[ERROR] 数据集构建失败: {exc}", file=sys.stderr)
        return 1
    

    

    print_summary(summary, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())