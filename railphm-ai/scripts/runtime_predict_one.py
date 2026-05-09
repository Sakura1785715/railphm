"""
RailPHM 单窗口运行时预测调试脚本。

本脚本用于从已经构建好的窗口数据集 X.npy / y.npy 中抽取一个样本窗口，
加载默认模型目录中的 SequenceModelRuntime，并调用 predict_proba 完成一次
确定性风险预测。

当前脚本仅用于开发调试和阶段验收，不负责概率校准、MC-Dropout、不确定性估计、
Flask /infer 接入、数据库写入或训练产物修改。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.runtime.model_loader import SequenceModelRuntime  # noqa: E402


DEFAULT_MODEL_DIR = Path("outputs/sequence_models/bilstm_attention_h1_full_features")
DEFAULT_DATASET_DIR = Path(
    "data/datasets/bilstm_attention_h1_full_features/train_scaled_condition_k3"
)


TRACE_FIELDS = (
    "sample_id",
    "segment_id",
    "segment_file",
    "window_start_time",
    "window_end_time",
    "target_time",
    "label",
    "target_alarm_value",
    "target_label_value",
)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Run one RailPHM runtime prediction from an existing window dataset."
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help=(
            "模型输出目录，默认 "
            "outputs/sequence_models/bilstm_attention_h1_full_features"
        ),
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=(
            "窗口数据集目录，默认 "
            "data/datasets/bilstm_attention_h1_full_features/train_scaled_condition_k3"
        ),
    )
    parser.add_argument(
        "--sample-index",
        type=int,
        default=0,
        help="要预测的样本索引，默认 0",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=("auto", "cpu", "cuda", "mps"),
        help="运行设备，默认 auto",
    )
    parser.add_argument(
        "--show-manifest",
        action="store_true",
        help="输出 runtime.summary() 调试信息",
    )
    parser.add_argument(
        "--show-window-values",
        action="store_true",
        help="输出窗口前 3 行数值预览，默认不输出窗口数值",
    )
    return parser


def load_dataset_arrays(dataset_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    读取窗口数据集中的 X.npy 和 y.npy。

    同时检查 dataset_dir、X.npy、y.npy、feature_columns.json 是否存在。
    feature_columns.json 在本脚本中不直接读取，但它是运行时数据集一致性的重要标志。
    """
    dataset_dir = Path(dataset_dir)

    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset_dir 不存在: {dataset_dir}")

    if not dataset_dir.is_dir():
        raise NotADirectoryError(f"dataset_dir 不是目录: {dataset_dir}")

    x_path = dataset_dir / "X.npy"
    y_path = dataset_dir / "y.npy"
    feature_columns_path = dataset_dir / "feature_columns.json"

    if not x_path.exists():
        raise FileNotFoundError(f"缺少数据集文件: {x_path}")

    if not y_path.exists():
        raise FileNotFoundError(f"缺少数据集文件: {y_path}")

    if not feature_columns_path.exists():
        raise FileNotFoundError(f"缺少数据集文件: {feature_columns_path}")

    X = np.load(x_path, allow_pickle=False)
    y = np.load(y_path, allow_pickle=False)

    validate_dataset_arrays(X, y)

    return X, y


def validate_dataset_arrays(X: np.ndarray, y: np.ndarray) -> None:
    """校验 X.npy 和 y.npy 的基础形状一致性。"""
    if not isinstance(X, np.ndarray):
        raise ValueError("X must be a numpy.ndarray")

    if not isinstance(y, np.ndarray):
        raise ValueError("y must be a numpy.ndarray")

    if X.ndim != 3:
        raise ValueError(f"X must be 3D [num_samples, window_size, feature_dim], got {X.shape}")

    if y.ndim != 1:
        raise ValueError(f"y must be 1D [num_samples], got {y.shape}")

    if X.shape[0] != y.shape[0]:
        raise ValueError(
            f"X/y sample count mismatch: X={X.shape[0]}, y={y.shape[0]}"
        )


def validate_runtime_dataset_shape(
    X: np.ndarray,
    runtime: SequenceModelRuntime,
) -> None:
    """校验数据集窗口形状是否与运行时模型要求一致。"""
    if X.shape[1] != runtime.window_size:
        raise ValueError(
            "dataset window_size mismatch: "
            f"X.shape[1]={X.shape[1]}, runtime.window_size={runtime.window_size}"
        )

    if X.shape[2] != runtime.feature_dim:
        raise ValueError(
            "dataset feature_dim mismatch: "
            f"X.shape[2]={X.shape[2]}, runtime.feature_dim={runtime.feature_dim}"
        )


def validate_sample_index(sample_index: int, total_samples: int) -> None:
    """校验 sample_index 是否为合法样本索引。"""
    if isinstance(sample_index, bool) or not isinstance(sample_index, int):
        raise ValueError("sample_index must be an integer")

    if sample_index < 0:
        raise ValueError(f"sample_index must be non-negative, got {sample_index}")

    if sample_index >= total_samples:
        raise IndexError(
            f"sample_index out of range: sample_index={sample_index}, "
            f"total_samples={total_samples}"
        )


def extract_window_and_label(
    X: np.ndarray,
    y: np.ndarray,
    sample_index: int,
) -> tuple[np.ndarray, int]:
    """根据样本索引抽取单个窗口和真实标签。"""
    validate_sample_index(sample_index, X.shape[0])

    window = X[sample_index]

    if not np.isfinite(window).all():
        raise ValueError(f"X[{sample_index}] contains NaN or inf")

    try:
        y_true = int(y[sample_index])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"y[{sample_index}] cannot be converted to int") from exc

    return window, y_true


def load_manifest_row(dataset_dir: Path, sample_index: int) -> dict[str, str] | None:
    """
    读取 window_manifest.csv 中 sample_index 对应的追溯信息。

    如果 window_manifest.csv 不存在，返回 None。
    如果文件存在但行数不足 sample_index，返回带 warning 的字典。
    """
    manifest_path = Path(dataset_dir) / "window_manifest.csv"

    if not manifest_path.exists():
        return None

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_index, row in enumerate(reader):
            if row_index == sample_index:
                return {
                    field: row.get(field, "")
                    for field in TRACE_FIELDS
                    if field in row and row.get(field, "") != ""
                }

    return {
        "warning": (
            "window_manifest.csv exists but does not contain "
            f"sample_index={sample_index}"
        )
    }


def format_prediction_output(
    *,
    model_dir: Path,
    dataset_dir: Path,
    sample_index: int,
    X: np.ndarray,
    y: np.ndarray,
    window: np.ndarray,
    y_true: int,
    runtime: SequenceModelRuntime,
    prediction: dict[str, Any],
    trace_row: dict[str, str] | None,
    show_manifest: bool,
    show_window_values: bool,
) -> str:
    """格式化终端输出内容，便于复制到开发记录。"""
    correct = int(y_true) == int(prediction["predicted_label"])

    lines: list[str] = [
        "=" * 60,
        "RailPHM runtime single-window prediction",
        "=" * 60,
        f"model_dir: {model_dir}",
        f"dataset_dir: {dataset_dir}",
        f"sample_index: {sample_index}",
        "",
        "[Dataset]",
        f"X_shape: {tuple(X.shape)}",
        f"y_shape: {tuple(y.shape)}",
        f"window_shape: {tuple(window.shape)}",
        f"y_true: {y_true}",
        "",
        "[Manifest]",
        f"model_version: {runtime.model_version}",
        f"model_name: {runtime.model_name}",
        f"window_size: {runtime.window_size}",
        f"feature_dim: {runtime.feature_dim}",
        f"threshold: {runtime.threshold}",
        f"device: {runtime.device}",
    ]

    if show_manifest:
        lines.extend(
            [
                "",
                "[Runtime Summary]",
            ]
        )
        for key, value in runtime.summary().items():
            lines.append(f"{key}: {value}")

    lines.extend(
        [
            "",
            "[Prediction]",
            f"risk_raw: {prediction['risk_raw']:.6f}",
            f"risk_score: {prediction['risk_score']:.6f}",
            f"threshold: {prediction['threshold']}",
            f"predicted_label: {prediction['predicted_label']}",
            f"correct: {str(correct).lower()}",
            "",
            "[Window Trace]",
        ]
    )

    if trace_row is None:
        lines.append("window_manifest.csv not found, skipped.")
    elif "warning" in trace_row:
        lines.append(f"[WARN] {trace_row['warning']}")
    elif not trace_row:
        lines.append("window_manifest.csv row is empty, skipped.")
    else:
        for key in TRACE_FIELDS:
            if key in trace_row:
                lines.append(f"{key}: {trace_row[key]}")

    if show_window_values:
        preview_rows = min(3, window.shape[0])
        preview = np.array2string(
            window[:preview_rows],
            precision=6,
            suppress_small=True,
        )
        lines.extend(
            [
                "",
                "[Window Values Preview]",
                f"first_rows: {preview_rows}",
                preview,
            ]
        )

    lines.extend(
        [
            "",
            "Prediction finished.",
            "=" * 60,
        ]
    )

    return "\n".join(lines)


def main() -> int:
    """脚本入口。成功返回 0，失败返回 1。"""
    parser = build_parser()
    args = parser.parse_args()

    try:
        model_dir = Path(args.model_dir)
        dataset_dir = Path(args.dataset_dir)

        if not model_dir.exists():
            raise FileNotFoundError(f"model_dir 不存在: {model_dir}")

        if not model_dir.is_dir():
            raise NotADirectoryError(f"model_dir 不是目录: {model_dir}")

        if args.sample_index < 0:
            raise ValueError(
                f"sample_index must be non-negative, got {args.sample_index}"
            )

        runtime = SequenceModelRuntime.from_model_dir(
            model_dir=model_dir,
            device=args.device,
        )

        X, y = load_dataset_arrays(dataset_dir)
        validate_runtime_dataset_shape(X, runtime)

        window, y_true = extract_window_and_label(
            X=X,
            y=y,
            sample_index=args.sample_index,
        )

        prediction = runtime.predict_proba(window)
        trace_row = load_manifest_row(dataset_dir, args.sample_index)

        output = format_prediction_output(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
            sample_index=args.sample_index,
            X=X,
            y=y,
            window=window,
            y_true=y_true,
            runtime=runtime,
            prediction=prediction,
            trace_row=trace_row,
            show_manifest=args.show_manifest,
            show_window_values=args.show_window_values,
        )
        print(output)

        return 0

    except Exception as exc:
        print(f"runtime single-window prediction failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())