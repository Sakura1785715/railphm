"""
RailPHM 概率校准器拟合脚本。

本脚本使用默认模型输出目录中的 val_predictions.csv 拟合保序回归概率校准器，
并使用 val/test 预测文件评估校准前后的 Brier Score 和 AUC。

严格边界：
1. 只使用 val_predictions.csv 拟合校准器；
2. test_predictions.csv 只用于校准后评估；
3. 不修改模型结构；
4. 不重训模型；
5. 不修改 best_model.pt；
6. 不接入 /infer；
7. 不做 MC-Dropout。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.calibration import IsotonicRiskCalibrator  # noqa: E402


DEFAULT_MODEL_DIR = Path("outputs/sequence_models/bilstm_attention_h1_full_features")

OUTPUT_FILENAMES = {
    "calibrator": "calibrator.pkl",
    "summary": "calibration_summary.json",
    "calibrated_val": "calibrated_val_predictions.csv",
    "calibrated_test": "calibrated_test_predictions.csv",
}


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Fit RailPHM isotonic probability calibrator from validation predictions."
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="模型输出目录，默认 outputs/sequence_models/bilstm_attention_h1_full_features",
    )
    parser.add_argument(
        "--val-predictions",
        type=Path,
        default=None,
        help="验证集预测文件，默认使用 model_dir/val_predictions.csv",
    )
    parser.add_argument(
        "--test-predictions",
        type=Path,
        default=None,
        help="测试集预测文件，默认使用 model_dir/test_predictions.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="校准产物输出目录，默认使用 model_dir",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="允许覆盖已有校准产物",
    )
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="将 calibration 字段写入 model_artifact_manifest.json",
    )
    return parser


def load_prediction_csv(path: Path) -> pd.DataFrame:
    """读取预测 CSV 文件。"""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"prediction file not found: {path}")

    df = pd.read_csv(path, encoding="utf-8-sig")
    validate_prediction_dataframe(df, path)
    return df


def validate_prediction_dataframe(df: pd.DataFrame, path: Path) -> None:
    """校验预测文件是否包含概率校准所需字段。"""
    required_columns = {"y_true", "y_prob"}
    missing_columns = sorted(required_columns - set(df.columns))

    if missing_columns:
        raise ValueError(f"{path.name} missing required columns: {missing_columns}")

    if df.empty:
        raise ValueError(f"{path.name} must not be empty")

    y_true = pd.to_numeric(df["y_true"], errors="coerce")
    y_prob = pd.to_numeric(df["y_prob"], errors="coerce")

    if y_true.isna().any():
        raise ValueError(f"{path.name} y_true contains non-numeric values")

    if y_prob.isna().any():
        raise ValueError(f"{path.name} y_prob contains non-numeric values")

    y_true_values = y_true.to_numpy(dtype=np.float64)
    y_prob_values = y_prob.to_numpy(dtype=np.float64)

    if not np.isfinite(y_true_values).all():
        raise ValueError(f"{path.name} y_true contains NaN or inf")

    if not np.isfinite(y_prob_values).all():
        raise ValueError(f"{path.name} y_prob contains NaN or inf")

    if not np.isin(y_true_values, [0.0, 1.0]).all():
        raise ValueError(f"{path.name} y_true must contain only 0/1 labels")

    if (y_prob_values < 0).any() or (y_prob_values > 1).any():
        raise ValueError(f"{path.name} y_prob must be within [0, 1]")


def extract_prediction_arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """从 DataFrame 中提取 y_true 和 y_prob 数组。"""
    y_true = pd.to_numeric(df["y_true"], errors="raise").to_numpy(dtype=np.float64)
    y_prob = pd.to_numeric(df["y_prob"], errors="raise").to_numpy(dtype=np.float64)
    return y_true.astype(np.int64), y_prob.astype(np.float64)


def compute_probability_metrics(y_true: Any, y_prob: Any) -> dict[str, Any]:
    """计算概率校准相关指标。"""
    y_true_array = np.asarray(y_true, dtype=np.int64)
    y_prob_array = np.asarray(y_prob, dtype=np.float64)

    if y_true_array.ndim != 1 or y_prob_array.ndim != 1:
        raise ValueError("y_true and y_prob must be 1D arrays")

    if y_true_array.shape[0] != y_prob_array.shape[0]:
        raise ValueError("y_true and y_prob must have the same length")

    if y_true_array.shape[0] == 0:
        raise ValueError("y_true and y_prob must not be empty")

    warnings: list[str] = []
    auc = None

    try:
        auc = float(roc_auc_score(y_true_array, y_prob_array))
    except ValueError as exc:
        warnings.append(f"auc is None because roc_auc_score failed: {exc}")

    positive_count = int((y_true_array == 1).sum())
    negative_count = int((y_true_array == 0).sum())

    return {
        "brier_score": float(brier_score_loss(y_true_array, y_prob_array)),
        "auc": auc,
        "prob_min": float(np.min(y_prob_array)),
        "prob_max": float(np.max(y_prob_array)),
        "prob_mean": float(np.mean(y_prob_array)),
        "sample_count": int(y_true_array.shape[0]),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "warnings": warnings,
    }


def add_calibrated_probabilities(
    df: pd.DataFrame,
    calibrator: IsotonicRiskCalibrator,
) -> pd.DataFrame:
    """在预测 DataFrame 中新增 y_prob_raw 和 y_prob_calibrated 字段。"""
    output_df = df.copy()
    _, y_prob = extract_prediction_arrays(output_df)

    calibrated_prob = calibrator.transform(y_prob)

    output_df["y_prob_raw"] = y_prob
    output_df["y_prob_calibrated"] = calibrated_prob

    return output_df


def load_threshold_summary(model_dir: Path) -> dict[str, Any]:
    """读取 threshold_summary.json。不存在时返回空字典。"""
    path = Path(model_dir) / "threshold_summary.json"

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"threshold_summary.json 解析失败: {exc}") from None


def build_threshold_info(threshold_summary: dict[str, Any]) -> dict[str, Any]:
    """从 threshold_summary.json 中整理原始阈值信息。"""
    raw_best_threshold = None
    if "best_threshold" in threshold_summary:
        raw_best_threshold = threshold_summary["best_threshold"]
    elif "best_val_threshold" in threshold_summary:
        raw_best_threshold = threshold_summary["best_val_threshold"]

    search_on = threshold_summary.get("search_on")
    metric = threshold_summary.get("metric")

    threshold_source = None
    if search_on and metric:
        threshold_source = (
            f"validation_best_{metric}"
            if str(search_on) == "val"
            else f"{search_on}_best_{metric}"
        )

    return {
        "raw_best_threshold": raw_best_threshold,
        "threshold_source": threshold_source,
        "calibrated_threshold": None,
    }


def build_calibration_summary(
    *,
    val_predictions_path: Path,
    test_predictions_path: Path,
    val_before: dict[str, Any],
    val_after: dict[str, Any],
    test_before: dict[str, Any],
    test_after: dict[str, Any],
    threshold_info: dict[str, Any],
) -> dict[str, Any]:
    """构造 calibration_summary.json 内容。"""
    return {
        "calibration_method": "isotonic_regression",
        "fit_split": "val",
        "calibrator_file": OUTPUT_FILENAMES["calibrator"],
        "val_predictions_file": val_predictions_path.name,
        "test_predictions_file": test_predictions_path.name,
        "calibrated_val_predictions_file": OUTPUT_FILENAMES["calibrated_val"],
        "calibrated_test_predictions_file": OUTPUT_FILENAMES["calibrated_test"],
        "raw_best_threshold": threshold_info.get("raw_best_threshold"),
        "threshold_source": threshold_info.get("threshold_source"),
        "calibrated_threshold": threshold_info.get("calibrated_threshold"),
        "val_before": val_before,
        "val_after": val_after,
        "test_before": test_before,
        "test_after": test_after,
        "notes": [
            "Calibrator is fitted on validation split only.",
            "Test split is used only for evaluation.",
            "Model weights and model architecture are not modified.",
            "Calibrated threshold search is not included in this stage.",
        ],
    }


def check_output_overwrite(output_paths: list[Path], overwrite: bool) -> None:
    """检查输出文件是否允许覆盖。"""
    existing = [path for path in output_paths if path.exists()]

    if existing and not overwrite:
        existing_text = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            "calibration output files already exist. "
            f"Use --overwrite to replace them: {existing_text}"
        )


def update_manifest_calibration(model_dir: Path) -> None:
    """
    将概率校准信息写入 model_artifact_manifest.json。

    本函数只更新 manifest 中的 calibration 字段，不删除或重建已有字段，
    不修改 artifacts 中已有模型权重、训练配置、预测文件等信息。
    写入前会检查校准产物文件是否已经存在，避免在产物缺失时错误标记 enabled=true。
    """
    model_dir = Path(model_dir)
    manifest_path = model_dir / "model_artifact_manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"model_artifact_manifest.json not found: {manifest_path}. "
            "Please finish Task 1.3 first."
        )

    required_calibration_files = {
        "calibrator": OUTPUT_FILENAMES["calibrator"],
        "summary": OUTPUT_FILENAMES["summary"],
        "calibrated_val_predictions": OUTPUT_FILENAMES["calibrated_val"],
        "calibrated_test_predictions": OUTPUT_FILENAMES["calibrated_test"],
    }

    missing_files = [
        str(model_dir / file_name)
        for file_name in required_calibration_files.values()
        if not (model_dir / file_name).exists()
    ]
    if missing_files:
        raise FileNotFoundError(
            "calibration artifacts are missing, refuse to write calibration.enabled=true: "
            + ", ".join(missing_files)
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"model_artifact_manifest.json 解析失败: {exc}") from None

    if not isinstance(manifest, dict):
        raise ValueError("model_artifact_manifest.json must be a JSON object")

    manifest["calibration"] = {
        "enabled": True,
        "method": "isotonic_regression",
        "calibrator": required_calibration_files["calibrator"],
        "summary": required_calibration_files["summary"],
        "fit_split": "val",
        "calibrated_val_predictions": required_calibration_files["calibrated_val_predictions"],
        "calibrated_test_predictions": required_calibration_files["calibrated_test_predictions"],
    }

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("[OK] model_artifact_manifest.json updated with calibration info")


def print_summary(
    *,
    model_dir: Path,
    val_predictions_path: Path,
    test_predictions_path: Path,
    output_dir: Path,
    val_before: dict[str, Any],
    val_after: dict[str, Any],
    test_before: dict[str, Any],
    test_after: dict[str, Any],
) -> None:
    """打印校准结果摘要。"""
    print("=" * 60)
    print("RailPHM probability calibrator fitting")
    print("=" * 60)
    print(f"model_dir: {model_dir}")
    print("method: isotonic_regression")
    print("fit_split: val")
    print()
    print("[Input]")
    print(f"val_predictions: {val_predictions_path}")
    print(f"test_predictions: {test_predictions_path}")
    print()
    print("[Validation]")
    print(f"before_brier_score: {val_before['brier_score']}")
    print(f"after_brier_score: {val_after['brier_score']}")
    print(f"before_auc: {val_before['auc']}")
    print(f"after_auc: {val_after['auc']}")
    print()
    print("[Test]")
    print(f"before_brier_score: {test_before['brier_score']}")
    print(f"after_brier_score: {test_after['brier_score']}")
    print(f"before_auc: {test_before['auc']}")
    print(f"after_auc: {test_after['auc']}")
    print()
    print("[Output]")
    print(f"calibrator: {output_dir / OUTPUT_FILENAMES['calibrator']}")
    print(f"summary: {output_dir / OUTPUT_FILENAMES['summary']}")
    print(f"calibrated_val_predictions: {output_dir / OUTPUT_FILENAMES['calibrated_val']}")
    print(f"calibrated_test_predictions: {output_dir / OUTPUT_FILENAMES['calibrated_test']}")
    print()
    print("Calibration finished.")
    print("=" * 60)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """执行概率校准拟合流程。"""
    model_dir = Path(args.model_dir)
    output_dir = Path(args.output_dir) if args.output_dir else model_dir
    val_predictions_path = (
        Path(args.val_predictions)
        if args.val_predictions
        else model_dir / "val_predictions.csv"
    )
    test_predictions_path = (
        Path(args.test_predictions)
        if args.test_predictions
        else model_dir / "test_predictions.csv"
    )

    if not model_dir.exists():
        raise FileNotFoundError(f"model_dir not found: {model_dir}")

    if not model_dir.is_dir():
        raise NotADirectoryError(f"model_dir is not a directory: {model_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths = [
        output_dir / OUTPUT_FILENAMES["calibrator"],
        output_dir / OUTPUT_FILENAMES["summary"],
        output_dir / OUTPUT_FILENAMES["calibrated_val"],
        output_dir / OUTPUT_FILENAMES["calibrated_test"],
    ]
    check_output_overwrite(output_paths, overwrite=bool(args.overwrite))

    val_df = load_prediction_csv(val_predictions_path)
    test_df = load_prediction_csv(test_predictions_path)

    val_y_true, val_y_prob = extract_prediction_arrays(val_df)
    test_y_true, test_y_prob = extract_prediction_arrays(test_df)

    calibrator = IsotonicRiskCalibrator()
    calibrator.fit(y_true=val_y_true, y_prob=val_y_prob)

    calibrated_val_df = add_calibrated_probabilities(val_df, calibrator)
    calibrated_test_df = add_calibrated_probabilities(test_df, calibrator)

    val_y_prob_calibrated = calibrated_val_df["y_prob_calibrated"].to_numpy(dtype=np.float64)
    test_y_prob_calibrated = calibrated_test_df["y_prob_calibrated"].to_numpy(dtype=np.float64)

    val_before = compute_probability_metrics(val_y_true, val_y_prob)
    val_after = compute_probability_metrics(val_y_true, val_y_prob_calibrated)
    test_before = compute_probability_metrics(test_y_true, test_y_prob)
    test_after = compute_probability_metrics(test_y_true, test_y_prob_calibrated)

    threshold_summary = load_threshold_summary(model_dir)
    threshold_info = build_threshold_info(threshold_summary)

    summary = build_calibration_summary(
        val_predictions_path=val_predictions_path,
        test_predictions_path=test_predictions_path,
        val_before=val_before,
        val_after=val_after,
        test_before=test_before,
        test_after=test_after,
        threshold_info=threshold_info,
    )

    calibrator.save(output_dir / OUTPUT_FILENAMES["calibrator"])

    calibrated_val_df.to_csv(
        output_dir / OUTPUT_FILENAMES["calibrated_val"],
        index=False,
        encoding="utf-8-sig",
    )
    calibrated_test_df.to_csv(
        output_dir / OUTPUT_FILENAMES["calibrated_test"],
        index=False,
        encoding="utf-8-sig",
    )
    (output_dir / OUTPUT_FILENAMES["summary"]).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.update_manifest:
        update_manifest_calibration(model_dir)

    print_summary(
        model_dir=model_dir,
        val_predictions_path=val_predictions_path,
        test_predictions_path=test_predictions_path,
        output_dir=output_dir,
        val_before=val_before,
        val_after=val_after,
        test_before=test_before,
        test_after=test_after,
    )

    return summary


def main() -> int:
    """脚本入口。"""
    parser = build_parser()
    args = parser.parse_args()

    try:
        run(args)
        return 0
    except Exception as exc:
        print(f"probability calibrator fitting failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())