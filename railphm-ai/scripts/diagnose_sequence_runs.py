#!/usr/bin/env python3
"""
RailPHM 时序模型诊断脚本。

当前支持：
- Stage 2: threshold analysis

默认行为：
- 只在终端输出；
- 不保存 csv/json/md；
- 不重新训练模型；
- 不使用 test 集选择 threshold。

只有显式传入 --save 时，才保存轻量级 threshold_summary.csv
和 diagnosis_stage2_threshold.json。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.training.metrics import compute_binary_metrics


MODEL_SPECS = {
    "lstm": {
        "label": "LSTM",
        "prediction_prefix": "lstm",
    },
    "bilstm": {
        "label": "Bi-LSTM",
        "prediction_prefix": "bilstm",
    },
    "lstm_attention": {
        "label": "LSTM+Attention",
        "prediction_prefix": "lstm_attention",
    },
    "bilstm_attention": {
        "label": "Bi-LSTM+Attention",
        "prediction_prefix": "bilstm_attention",
    },
}

REQUIRED_PREDICTION_COLUMNS = {
    "sample_order",
    "sample_index",
    "y_true",
    "y_prob",
    "y_pred_05",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose RailPHM sequence model training results."
    )

    parser.add_argument(
        "--stage",
        type=str,
        required=True,
        choices=["threshold", "distribution", "segment"],
        help="诊断阶段，目前支持 threshold。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Stage 1 诊断目录，用于读取 predictions 子目录。",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help="内存推理模式使用的数据集目录。",
    )
    parser.add_argument("--lstm-run", type=Path, default=None)
    parser.add_argument("--bilstm-run", type=Path, default=None)
    parser.add_argument("--lstm-attention-run", type=Path, default=None)
    parser.add_argument("--bilstm-attention-run", type=Path, default=None)
    parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.01,
        help="阈值搜索步长，默认 0.01。",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help="内存推理模式使用的设备。",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="显式保存 threshold_summary.csv 和 diagnosis_stage2_threshold.json。",
    )
    parser.add_argument(
        "--save-detail",
        action="store_true",
        help="显式保存 threshold_search_detail.csv。只有 --save-detail 时才保存明细。",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出更详细结果。",
    )
    parser.add_argument(
    "--thresholds",
    type=str,
    default=None,
    help=(
        "Stage 3 使用的各模型 best_val_threshold，例如："
        "lstm=0.26,bilstm=0.27,lstm_attention=0.28,bilstm_attention=0.26"
        ),
    )
    parser.add_argument(
    "--top-k-segments",
    type=int,
    default=10,
    help="Stage 4 每个模型输出 FP 数最高的前 K 个 segment，默认 10。",
    )
    parser.add_argument(
        "--horizon-seconds",
        type=str,
        default="5,10,30",
        help="Stage 4 future-horizon 标签潜力分析窗口，默认 5,10,30。",
    )

    return parser


def build_threshold_grid(step: float) -> list[float]:
    if (
        isinstance(step, bool)
        or not isinstance(step, (int, float))
        or not math.isfinite(float(step))
        or float(step) <= 0
        or float(step) >= 1
    ):
        raise ValueError("threshold-step 必须大于 0 且小于 1")

    thresholds: list[float] = []
    current = float(step)

    while current < 1:
        rounded = round(current, 6)
        if 0 < rounded < 1:
            thresholds.append(rounded)
        current += float(step)

    thresholds.append(0.5)

    unique_thresholds = sorted({round(value, 6) for value in thresholds if 0 < value < 1})
    return unique_thresholds


def load_prediction_csv(path: Path, model_key: str, split: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"缺少 prediction 文件: {path}")

    df = pd.read_csv(path)
    validate_prediction_dataframe(df, model_key=model_key, split=split, path=path)
    return df


def validate_prediction_dataframe(
    df: pd.DataFrame,
    model_key: str,
    split: str,
    path: Path | None = None,
) -> None:
    missing_columns = REQUIRED_PREDICTION_COLUMNS - set(df.columns)
    if missing_columns:
        location = f" file={path}" if path else ""
        raise ValueError(
            f"{model_key}/{split} prediction 缺少字段: {sorted(missing_columns)}{location}"
        )

    if df.empty:
        raise ValueError(f"{model_key}/{split} prediction 不能为空")

    y_true = df["y_true"]
    y_pred_05 = df["y_pred_05"]
    y_prob = pd.to_numeric(df["y_prob"], errors="coerce")

    if y_prob.isna().any():
        raise ValueError(f"{model_key}/{split} y_prob 存在 NaN 或无法转数值")

    y_prob_values = y_prob.to_numpy(dtype=np.float64)
    if not np.isfinite(y_prob_values).all():
        raise ValueError(f"{model_key}/{split} y_prob 存在 NaN 或 inf")

    if (y_prob_values < 0).any() or (y_prob_values > 1).any():
        raise ValueError(f"{model_key}/{split} y_prob 必须位于 [0, 1] 范围内")

    if not set(pd.Series(y_true).dropna().astype(int).unique().tolist()).issubset({0, 1}):
        raise ValueError(f"{model_key}/{split} y_true 只能包含 0/1")

    if not set(pd.Series(y_pred_05).dropna().astype(int).unique().tolist()).issubset({0, 1}):
        raise ValueError(f"{model_key}/{split} y_pred_05 只能包含 0/1")

    if df["sample_index"].isna().any():
        raise ValueError(f"{model_key}/{split} sample_index 存在空值")


def load_stage1_predictions(output_dir: Path) -> dict[str, dict[str, pd.DataFrame]]:
    predictions_dir = output_dir / "predictions"
    if not predictions_dir.exists():
        raise FileNotFoundError(f"prediction 目录不存在: {predictions_dir}")

    predictions: dict[str, dict[str, pd.DataFrame]] = {}

    for model_key, spec in MODEL_SPECS.items():
        prefix = spec["prediction_prefix"]
        val_path = predictions_dir / f"{prefix}_val_predictions.csv"
        test_path = predictions_dir / f"{prefix}_test_predictions.csv"

        predictions[model_key] = {
            "val": load_prediction_csv(val_path, model_key=model_key, split="val"),
            "test": load_prediction_csv(test_path, model_key=model_key, split="test"),
        }

    validate_prediction_consistency(predictions, split="val")
    validate_prediction_consistency(predictions, split="test")

    return predictions


def validate_prediction_consistency(
    predictions_by_model: dict[str, dict[str, pd.DataFrame]],
    split: str,
) -> None:
    reference_model = next(iter(predictions_by_model.keys()))
    reference_df = predictions_by_model[reference_model][split]

    reference_sample_index = reference_df["sample_index"].to_numpy()
    reference_y_true = reference_df["y_true"].astype(int).to_numpy()

    for model_key, split_predictions in predictions_by_model.items():
        current_df = split_predictions[split]

        if len(current_df) != len(reference_df):
            raise ValueError(
                f"{split} 样本数不一致: {reference_model}={len(reference_df)}, "
                f"{model_key}={len(current_df)}"
            )

        current_sample_index = current_df["sample_index"].to_numpy()
        current_y_true = current_df["y_true"].astype(int).to_numpy()

        if not np.array_equal(reference_sample_index, current_sample_index):
            raise ValueError(f"{split} sample_index 不一致: {model_key}")

        if not np.array_equal(reference_y_true, current_y_true):
            raise ValueError(f"{split} y_true 不一致: {model_key}")


def compute_metrics_at_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    return compute_binary_metrics(
        y_true=y_true,
        y_prob=y_prob,
        threshold=float(threshold),
    )


def search_best_threshold_on_val(
    val_predictions: pd.DataFrame,
    thresholds: list[float],
) -> tuple[float, dict[str, Any], list[dict[str, Any]]]:
    y_true = val_predictions["y_true"].astype(int).to_numpy()
    y_prob = val_predictions["y_prob"].astype(float).to_numpy()

    best_threshold = None
    best_metrics = None
    best_key = None
    details: list[dict[str, Any]] = []

    for threshold in thresholds:
        metrics = compute_metrics_at_threshold(y_true, y_prob, threshold)

        detail = {
            "threshold": float(threshold),
            "accuracy": float(metrics["accuracy"]),
            "precision": float(metrics["precision"]),
            "recall": float(metrics["recall"]),
            "f1": float(metrics["f1"]),
            "predicted_positive_count": int(metrics["predicted_positive_count"]),
            "predicted_negative_count": int(metrics["predicted_negative_count"]),
            "predicted_positive_ratio": (
                int(metrics["predicted_positive_count"]) / int(len(y_true))
                if len(y_true) > 0
                else 0.0
            ),
            "confusion_matrix": metrics["confusion_matrix"],
        }
        details.append(detail)

        candidate_key = (
            float(metrics["f1"]),
            float(metrics["recall"]),
            -abs(float(threshold) - 0.5),
            -float(threshold),
        )

        if best_key is None or candidate_key > best_key:
            best_key = candidate_key
            best_threshold = float(threshold)
            best_metrics = metrics

    if best_threshold is None or best_metrics is None:
        raise ValueError("未能搜索到有效 threshold")

    return best_threshold, best_metrics, details


def evaluate_split_with_threshold(
    predictions: pd.DataFrame,
    threshold: float,
) -> dict[str, Any]:
    y_true = predictions["y_true"].astype(int).to_numpy()
    y_prob = predictions["y_prob"].astype(float).to_numpy()
    metrics = compute_metrics_at_threshold(y_true, y_prob, threshold)

    metrics["predicted_positive_ratio"] = (
        int(metrics["predicted_positive_count"]) / int(len(y_true))
        if len(y_true) > 0
        else 0.0
    )
    return metrics


def judge_threshold_effect(
    test_05: dict[str, Any],
    test_best: dict[str, Any],
) -> tuple[str, str, list[str]]:
    f1_delta = float(test_best["f1"]) - float(test_05["f1"])
    recall_delta = float(test_best["recall"]) - float(test_05["recall"])
    precision_delta = float(test_best["precision"]) - float(test_05["precision"])

    warnings: list[str] = []

    if recall_delta > 0 and precision_delta <= -0.10:
        warnings.append("召回率提升伴随精确率明显下降，需要结合告警误报成本谨慎选择阈值。")

    if f1_delta >= 0.05 and recall_delta > 0:
        return "strong_improvement", "strong", warnings

    if f1_delta >= 0.02 and recall_delta > 0:
        return "moderate_improvement", "moderate", warnings

    if f1_delta > 0 and recall_delta > 0:
        return "weak_improvement", "weak", warnings

    return "no_improvement", "none", warnings


def build_threshold_summary(
    predictions: dict[str, dict[str, pd.DataFrame]],
    thresholds: list[float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    summary_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    best_val_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for model_key, split_predictions in predictions.items():
        model_label = MODEL_SPECS[model_key]["label"]

        best_threshold, best_val_metrics, threshold_details = search_best_threshold_on_val(
            split_predictions["val"],
            thresholds,
        )

        for detail in threshold_details:
            detail_rows.append(
                {
                    "model_key": model_key,
                    "model_label": model_label,
                    **detail,
                }
            )

        test_05 = evaluate_split_with_threshold(split_predictions["test"], threshold=0.5)
        test_best = evaluate_split_with_threshold(
            split_predictions["test"],
            threshold=best_threshold,
        )

        effect_level, effect_display, effect_warnings = judge_threshold_effect(
            test_05=test_05,
            test_best=test_best,
        )
        warnings.extend([f"{model_label}: {warning}" for warning in effect_warnings])

        precision_delta = float(test_best["precision"]) - float(test_05["precision"])
        recall_delta = float(test_best["recall"]) - float(test_05["recall"])
        f1_delta = float(test_best["f1"]) - float(test_05["f1"])
        ppr_delta = (
            float(test_best["predicted_positive_ratio"])
            - float(test_05["predicted_positive_ratio"])
        )

        summary_rows.append(
            {
                "model_key": model_key,
                "model": model_label,
                "best_val_threshold": float(best_threshold),
                "test_precision_05": float(test_05["precision"]),
                "test_recall_05": float(test_05["recall"]),
                "test_f1_05": float(test_05["f1"]),
                "test_auc_05": _optional_float(test_05["auc"]),
                "test_brier_score_05": float(test_05["brier_score"]),
                "test_predicted_positive_ratio_05": float(test_05["predicted_positive_ratio"]),
                "test_precision_best": float(test_best["precision"]),
                "test_recall_best": float(test_best["recall"]),
                "test_f1_best": float(test_best["f1"]),
                "test_auc_best": _optional_float(test_best["auc"]),
                "test_brier_score_best": float(test_best["brier_score"]),
                "test_predicted_positive_ratio_best": float(test_best["predicted_positive_ratio"]),
                "test_precision_delta": precision_delta,
                "test_recall_delta": recall_delta,
                "test_f1_delta": f1_delta,
                "test_predicted_positive_ratio_delta": ppr_delta,
                "effect_level": effect_level,
                "effect": effect_display,
                "test_05_confusion_matrix": test_05["confusion_matrix"],
                "test_best_confusion_matrix": test_best["confusion_matrix"],
            }
        )

        best_val_rows.append(
            {
                "model_key": model_key,
                "model": model_label,
                "best_val_threshold": float(best_threshold),
                "val_precision": float(best_val_metrics["precision"]),
                "val_recall": float(best_val_metrics["recall"]),
                "val_f1": float(best_val_metrics["f1"]),
                "val_predicted_positive_ratio": (
                    int(best_val_metrics["predicted_positive_count"])
                    / int(len(split_predictions["val"]))
                    if len(split_predictions["val"]) > 0
                    else 0.0
                ),
                "val_confusion_matrix": best_val_metrics["confusion_matrix"],
            }
        )

    return summary_rows, best_val_rows, detail_rows, warnings


def build_global_threshold_judgement(
    summary_rows: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    strong_or_moderate_count = sum(
        row["effect_level"] in {"strong_improvement", "moderate_improvement"}
        for row in summary_rows
    )
    weak_count = sum(row["effect_level"] == "weak_improvement" for row in summary_rows)
    no_improvement_count = sum(row["effect_level"] == "no_improvement" for row in summary_rows)

    reasons: list[str] = []
    risks: list[str] = []
    next_steps: list[str] = []

    if strong_or_moderate_count >= 2:
        level = "threshold_likely_main_issue"
        conclusion = (
            "多个模型在验证集阈值搜索后测试集 F1 或 Recall 明显改善，"
            "当前模型效果受 threshold=0.5 偏保守影响较大。"
        )
        reasons.append("至少两个模型达到 moderate 或 strong improvement。")
        next_steps.append("后续可在验证集上固定选择阈值，再报告测试集指标。")
    elif strong_or_moderate_count == 1 or weak_count >= 1:
        level = "threshold_partly_issue"
        conclusion = (
            "阈值调整对部分模型有帮助，但并非所有模型都明显受益，"
            "仍需继续排查分布偏移和标签信号。"
        )
        reasons.append("至少一个模型在验证集阈值搜索后测试集 F1 或 Recall 有改善。")
        next_steps.append("继续检查 train/val/test 正负样本比例、工况分布和标签时间尺度。")
    else:
        level = "threshold_not_main_issue"
        conclusion = (
            "验证集阈值搜索未带来明显改善，当前瓶颈更可能来自模型排序能力、"
            "数据分布或标签定义。"
        )
        reasons.append("所有模型均为 no_improvement。")
        next_steps.append("优先排查标签定义、窗口长度、prediction_horizon 和 split 分布差异。")

    if warnings:
        risks.append(
            "部分模型降低阈值后可能出现精确率明显下降，需结合告警误报成本评估。"
        )

    if no_improvement_count == len(summary_rows):
        risks.append("单纯调整阈值无法改善测试集 F1。")

    return {
        "level": level,
        "conclusion": conclusion,
        "reasons": reasons,
        "risks": risks,
        "next_steps": next_steps,
    }


def print_threshold_diagnosis(
    *,
    mode: str,
    threshold_step: float,
    predictions: dict[str, dict[str, pd.DataFrame]],
    summary_rows: list[dict[str, Any]],
    best_val_rows: list[dict[str, Any]],
    global_judgement: dict[str, Any],
    warnings: list[str],
    save_enabled: bool,
) -> None:
    val_count = len(next(iter(predictions.values()))["val"])
    test_count = len(next(iter(predictions.values()))["test"])

    print("=" * 60)
    print("RailPHM Task 5-3b-2 Threshold Diagnosis")
    print("=" * 60)
    print()
    print("[Input]")
    print(f"mode: {mode}")
    print(f"threshold_step: {threshold_step}")
    print("models: LSTM, Bi-LSTM, LSTM+Attention, Bi-LSTM+Attention")
    print()
    print("[Sanity Check]")
    print(f"val samples: {val_count}")
    print(f"test samples: {test_count}")
    print("val y_true consistent: OK")
    print("test y_true consistent: OK")
    print()
    print("[Threshold Summary]")
    print(
        "| Model | Test F1@0.5 | Test Recall@0.5 | Test Precision@0.5 | "
        "Best Val Threshold | Test F1@Best | Test Recall@Best | "
        "Test Precision@Best | F1 Delta | Recall Delta | Effect |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    for row in summary_rows:
        print(
            f"| {row['model']} | "
            f"{_fmt_float(row['test_f1_05'])} | "
            f"{_fmt_float(row['test_recall_05'])} | "
            f"{_fmt_float(row['test_precision_05'])} | "
            f"{_fmt_threshold(row['best_val_threshold'])} | "
            f"{_fmt_float(row['test_f1_best'])} | "
            f"{_fmt_float(row['test_recall_best'])} | "
            f"{_fmt_float(row['test_precision_best'])} | "
            f"{_fmt_delta(row['test_f1_delta'])} | "
            f"{_fmt_delta(row['test_recall_delta'])} | "
            f"{row['effect']} |"
        )

    print()
    print("[Best Val Threshold Detail]")
    print(
        "| Model | Best Val Threshold | Val Precision | Val Recall | "
        "Val F1 | Val Predicted Positive Ratio |"
    )
    print("|---|---:|---:|---:|---:|---:|")

    for row in best_val_rows:
        print(
            f"| {row['model']} | "
            f"{_fmt_threshold(row['best_val_threshold'])} | "
            f"{_fmt_float(row['val_precision'])} | "
            f"{_fmt_float(row['val_recall'])} | "
            f"{_fmt_float(row['val_f1'])} | "
            f"{_fmt_float(row['val_predicted_positive_ratio'])} |"
        )

    print()
    print("[Global Judgement]")
    print(f"level: {global_judgement['level']}")
    print(f"conclusion: {global_judgement['conclusion']}")
    print("reasons:")
    for reason in global_judgement["reasons"]:
        print(f"- {reason}")
    print("risks:")
    if global_judgement["risks"]:
        for risk in global_judgement["risks"]:
            print(f"- {risk}")
    else:
        print("- None")
    print("next_steps:")
    for step in global_judgement["next_steps"]:
        print(f"- {step}")

    print()
    print("[Warnings]")
    if warnings:
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("No warnings.")

    print()
    print("[Save]")
    if save_enabled:
        print("Save mode enabled. Lightweight files will be saved.")
    else:
        print("No files saved. Terminal-only diagnosis mode.")


def save_threshold_outputs_if_requested(
    *,
    output_dir: Path | None,
    summary_rows: list[dict[str, Any]],
    best_val_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
    global_judgement: dict[str, Any],
    warnings: list[str],
    save: bool,
    save_detail: bool,
) -> None:
    if not save and not save_detail:
        return

    if output_dir is None:
        raise ValueError("--save 或 --save-detail 需要同时提供 --output-dir")

    output_dir.mkdir(parents=True, exist_ok=True)

    if save:
        threshold_summary_path = output_dir / "threshold_summary.csv"
        diagnosis_json_path = output_dir / "diagnosis_stage2_threshold.json"

        pd.DataFrame(summary_rows).to_csv(threshold_summary_path, index=False)

        diagnosis = {
            "task": "stage2_threshold_analysis",
            "summary": summary_rows,
            "best_val_threshold_detail": best_val_rows,
            "global_judgement": global_judgement,
            "warnings": warnings,
        }
        diagnosis_json_path.write_text(
            json.dumps(_json_safe(diagnosis), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print()
        print("[Save]")
        print(f"threshold_summary.csv saved: {threshold_summary_path}")
        print(f"diagnosis_stage2_threshold.json saved: {diagnosis_json_path}")

    if save_detail:
        detail_path = output_dir / "threshold_search_detail.csv"
        pd.DataFrame(_flatten_detail_rows(detail_rows)).to_csv(detail_path, index=False)
        print(f"threshold_search_detail.csv saved: {detail_path}")


def run_threshold_analysis(args: argparse.Namespace) -> dict[str, Any]:
    thresholds = build_threshold_grid(args.threshold_step)

    predictions, mode = load_predictions_for_threshold_analysis(args)

    summary_rows, best_val_rows, detail_rows, warnings = build_threshold_summary(
        predictions=predictions,
        thresholds=thresholds,
    )
    global_judgement = build_global_threshold_judgement(
        summary_rows=summary_rows,
        warnings=warnings,
    )

    print_threshold_diagnosis(
        mode=mode,
        threshold_step=args.threshold_step,
        predictions=predictions,
        summary_rows=summary_rows,
        best_val_rows=best_val_rows,
        global_judgement=global_judgement,
        warnings=warnings,
        save_enabled=bool(args.save or args.save_detail),
    )

    save_threshold_outputs_if_requested(
        output_dir=args.output_dir,
        summary_rows=summary_rows,
        best_val_rows=best_val_rows,
        detail_rows=detail_rows,
        global_judgement=global_judgement,
        warnings=warnings,
        save=args.save,
        save_detail=args.save_detail,
    )

    return {
        "mode": mode,
        "thresholds": thresholds,
        "summary": summary_rows,
        "best_val_threshold_detail": best_val_rows,
        "threshold_search_detail": detail_rows,
        "global_judgement": global_judgement,
        "warnings": warnings,
    }


def load_predictions_for_threshold_analysis(
    args: argparse.Namespace,
) -> tuple[dict[str, dict[str, pd.DataFrame]], str]:
    if args.output_dir is not None:
        predictions_dir = args.output_dir / "predictions"
        if predictions_dir.exists():
            return load_stage1_predictions(args.output_dir), "csv_predictions"

    has_in_memory_args = all(
        value is not None
        for value in [
            args.dataset_dir,
            args.lstm_run,
            args.bilstm_run,
            args.lstm_attention_run,
            args.bilstm_attention_run,
        ]
    )

    if has_in_memory_args:
        return load_predictions_in_memory(args), "in_memory_inference"

    raise FileNotFoundError(
        "未找到 Stage 1 prediction CSV，且未提供完整内存推理参数。"
        "请提供 --output-dir 指向含 predictions 的诊断目录，或提供 "
        "--dataset-dir 与四个模型 run 目录。"
    )


def load_predictions_in_memory(
    args: argparse.Namespace,
) -> dict[str, dict[str, pd.DataFrame]]:
    import torch
    from torch.utils.data import DataLoader

    from app.models import build_sequence_model
    from app.training.dataset_loader import WindowDataset, load_dataset_arrays
    from app.training.train_sequence_model import resolve_device

    dataset_dir = Path(args.dataset_dir)
    arrays = load_dataset_arrays(dataset_dir)

    X = arrays["X"]
    y = arrays["y"]
    val_indices = arrays["val_indices"]
    test_indices = arrays["test_indices"]

    if X.ndim != 3:
        raise ValueError("X 必须为三维数组 [num_samples, window_size, feature_dim]")

    device = resolve_device(args.device)
    input_dim = int(X.shape[2])

    run_dirs = {
        "lstm": args.lstm_run,
        "bilstm": args.bilstm_run,
        "lstm_attention": args.lstm_attention_run,
        "bilstm_attention": args.bilstm_attention_run,
    }

    predictions: dict[str, dict[str, pd.DataFrame]] = {}

    for model_key, run_dir in run_dirs.items():
        run_dir = Path(run_dir)
        checkpoint_path = run_dir / "best_model.pt"
        report_path = run_dir / "sequence_model_report.json"

        if not checkpoint_path.exists():
            raise FileNotFoundError(f"缺少 best_model.pt: {checkpoint_path}")

        if not report_path.exists():
            raise FileNotFoundError(f"缺少 sequence_model_report.json: {report_path}")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        model_config = report.get("model", {})

        model = build_sequence_model(
            model_name=model_key,
            input_dim=input_dim,
            hidden_dim=int(model_config.get("hidden_dim", 64)),
            num_layers=int(model_config.get("num_layers", 1)),
            dropout=float(model_config.get("dropout", 0.2)),
        ).to(device)

        checkpoint = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        predictions[model_key] = {
            "val": _predict_split_in_memory(
                model=model,
                X=X,
                y=y,
                indices=val_indices,
                device=device,
                split_name="val",
                WindowDataset=WindowDataset,
                DataLoader=DataLoader,
                torch=torch,
            ),
            "test": _predict_split_in_memory(
                model=model,
                X=X,
                y=y,
                indices=test_indices,
                device=device,
                split_name="test",
                WindowDataset=WindowDataset,
                DataLoader=DataLoader,
                torch=torch,
            ),
        }

    validate_prediction_consistency(predictions, split="val")
    validate_prediction_consistency(predictions, split="test")

    return predictions


def _predict_split_in_memory(
    *,
    model,
    X: np.ndarray,
    y: np.ndarray,
    indices: np.ndarray,
    device,
    split_name: str,
    WindowDataset,
    DataLoader,
    torch,
) -> pd.DataFrame:
    dataset = WindowDataset(X, y, indices, flatten=False)
    loader = DataLoader(dataset, batch_size=512, shuffle=False, num_workers=0)

    y_true_values: list[int] = []
    y_prob_values: list[float] = []

    with torch.no_grad():
        for features, labels in loader:
            features = features.to(device=device, dtype=torch.float32)
            logits = model(features).view(-1)
            probs = torch.sigmoid(logits)

            y_true_values.extend([int(value) for value in labels.detach().cpu().numpy().tolist()])
            y_prob_values.extend([float(value) for value in probs.detach().cpu().numpy().tolist()])

    df = pd.DataFrame(
        {
            "sample_order": np.arange(len(indices), dtype=np.int64),
            "sample_index": indices.astype(np.int64),
            "y_true": y_true_values,
            "y_prob": y_prob_values,
        }
    )
    df["y_pred_05"] = (df["y_prob"] >= 0.5).astype(int)

    validate_prediction_dataframe(df, model_key="in_memory", split=split_name)
    return df


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _fmt_float(value: Any) -> str:
    if value is None:
        return "null"
    return f"{float(value):.4f}"


def _fmt_threshold(value: Any) -> str:
    if value is None:
        return "null"
    return f"{float(value):.2f}"


def _fmt_delta(value: Any) -> str:
    if value is None:
        return "null"
    number = float(value)
    return f"{number:+.4f}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.ndarray):
        return value.tolist()

    return value


def _flatten_detail_rows(detail_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []

    for row in detail_rows:
        confusion_matrix = row.get("confusion_matrix", {})
        copied = dict(row)
        copied.pop("confusion_matrix", None)
        copied["tn"] = confusion_matrix.get("tn")
        copied["fp"] = confusion_matrix.get("fp")
        copied["fn"] = confusion_matrix.get("fn")
        copied["tp"] = confusion_matrix.get("tp")
        flattened.append(copied)

    return flattened

def parse_thresholds(raw: str | None, output_dir: Path | None = None) -> dict[str, float]:
    if raw:
        result: dict[str, float] = {}

        for item in raw.split(","):
            if "=" not in item:
                raise ValueError(f"thresholds 格式错误: {item}")

            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key not in MODEL_SPECS:
                supported = ", ".join(MODEL_SPECS.keys())
                raise ValueError(f"未知模型 key: {key}，支持: {supported}")

            threshold = float(value)
            if not 0 < threshold < 1:
                raise ValueError(f"{key} threshold 必须位于 0 到 1 之间")

            result[key] = threshold

        missing = set(MODEL_SPECS.keys()) - set(result.keys())
        if missing:
            raise ValueError(f"thresholds 缺少模型: {sorted(missing)}")

        return result

    if output_dir is not None:
        stage2_json = output_dir / "diagnosis_stage2_threshold.json"
        if stage2_json.exists():
            data = json.loads(stage2_json.read_text(encoding="utf-8"))
            summary = data.get("summary", [])
            result = {}

            for row in summary:
                model_key = row.get("model_key")
                threshold = row.get("best_val_threshold")
                if model_key in MODEL_SPECS and threshold is not None:
                    result[model_key] = float(threshold)

            missing = set(MODEL_SPECS.keys()) - set(result.keys())
            if not missing:
                return result

    raise ValueError("缺少 best_val_threshold，请通过 --thresholds 传入各模型阈值。")


def load_dataset_distribution_inputs(dataset_dir: Path) -> dict[str, Any]:
    dataset_dir = Path(dataset_dir)

    required_files = [
        dataset_dir / "X.npy",
        dataset_dir / "y.npy",
        dataset_dir / "splits" / "train_indices.npy",
        dataset_dir / "splits" / "val_indices.npy",
        dataset_dir / "splits" / "test_indices.npy",
        dataset_dir / "condition_labels.npy",
        dataset_dir / "condition_summary.json",
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(f"缺少数据集诊断文件: {path}")

    X = np.load(dataset_dir / "X.npy", allow_pickle=False)
    y = np.load(dataset_dir / "y.npy", allow_pickle=False)
    train_indices = np.load(dataset_dir / "splits" / "train_indices.npy", allow_pickle=False)
    val_indices = np.load(dataset_dir / "splits" / "val_indices.npy", allow_pickle=False)
    test_indices = np.load(dataset_dir / "splits" / "test_indices.npy", allow_pickle=False)
    condition_labels = np.load(dataset_dir / "condition_labels.npy", allow_pickle=False)

    condition_summary = json.loads(
        (dataset_dir / "condition_summary.json").read_text(encoding="utf-8")
    )

    window_manifest_path = dataset_dir / "window_manifest.csv"
    window_manifest = None
    warnings = []

    if window_manifest_path.exists():
        window_manifest = pd.read_csv(window_manifest_path)
        if len(window_manifest) != len(y):
            warnings.append(
                "window_manifest.csv 行数与 y.npy 样本数不一致，已跳过 segment 误报集中度分析。"
            )
            window_manifest = None
        elif "segment_id" not in window_manifest.columns:
            warnings.append(
                "window_manifest.csv 缺少 segment_id 字段，已跳过 segment 误报集中度分析。"
            )
            window_manifest = None
    else:
        warnings.append("缺少 window_manifest.csv，已跳过 segment 误报集中度分析。")

    if X.ndim != 3:
        raise ValueError("X.npy 必须为三维数组 [num_samples, window_size, feature_dim]")

    if y.ndim != 1:
        raise ValueError("y.npy 必须为一维数组")

    if len(y) != len(condition_labels):
        raise ValueError("condition_labels.npy 样本数与 y.npy 不一致")

    return {
        "dataset_dir": dataset_dir,
        "X": X,
        "y": y.astype(int),
        "split_indices": {
            "train": train_indices.astype(np.int64),
            "val": val_indices.astype(np.int64),
            "test": test_indices.astype(np.int64),
        },
        "condition_labels": condition_labels.astype(np.int64),
        "condition_summary": condition_summary,
        "window_manifest": window_manifest,
        "warnings": warnings,
    }


def _condition_mapping(condition_summary: dict[str, Any]) -> dict[int, str]:
    raw_mapping = condition_summary.get("condition_label_mapping") or {}
    mapping = {}

    for key, value in raw_mapping.items():
        try:
            mapping[int(key)] = str(value)
        except Exception:
            continue

    return mapping


def _condition_label(condition_id: int, mapping: dict[int, str]) -> str:
    return mapping.get(int(condition_id), f"工况{condition_id}")


def compute_split_label_distribution(
    y: np.ndarray,
    split_indices: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows = []

    for split_name in ["train", "val", "test"]:
        indices = split_indices[split_name]
        labels = y[indices]

        positive_count = int((labels == 1).sum())
        negative_count = int((labels == 0).sum())
        sample_count = int(len(indices))

        rows.append(
            {
                "split": split_name,
                "sample_count": sample_count,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "positive_ratio": positive_count / sample_count if sample_count else 0.0,
            }
        )

    return rows


def compute_condition_distribution(
    y: np.ndarray,
    condition_labels: np.ndarray,
    split_indices: dict[str, np.ndarray],
    condition_mapping: dict[int, str],
) -> list[dict[str, Any]]:
    rows = []
    all_conditions = sorted(np.unique(condition_labels).astype(int).tolist())

    for split_name in ["train", "val", "test"]:
        indices = split_indices[split_name]
        split_count = int(len(indices))

        for condition_id in all_conditions:
            mask = condition_labels[indices] == condition_id
            condition_indices = indices[mask]
            labels = y[condition_indices]

            sample_count = int(len(condition_indices))
            positive_count = int((labels == 1).sum())
            negative_count = int((labels == 0).sum())

            rows.append(
                {
                    "split": split_name,
                    "condition_id": int(condition_id),
                    "condition_label": _condition_label(condition_id, condition_mapping),
                    "sample_count": sample_count,
                    "positive_count": positive_count,
                    "negative_count": negative_count,
                    "positive_ratio": positive_count / sample_count if sample_count else 0.0,
                    "condition_sample_ratio": sample_count / split_count if split_count else 0.0,
                }
            )

    return rows


def compute_confusion_by_model(
    predictions: dict[str, dict[str, pd.DataFrame]],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    rows = []

    for model_key, split_predictions in predictions.items():
        df = split_predictions["test"]
        threshold = thresholds[model_key]

        y_true = df["y_true"].astype(int).to_numpy()
        y_prob = df["y_prob"].astype(float).to_numpy()
        y_pred = (y_prob >= threshold).astype(int)

        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        tn = int(((y_true == 0) & (y_pred == 0)).sum())

        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0

        rows.append(
            {
                "model_key": model_key,
                "model_label": MODEL_SPECS[model_key]["label"],
                "threshold": threshold,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "predicted_positive_ratio": float((y_pred == 1).mean()) if len(y_pred) else 0.0,
            }
        )

    return rows


def compute_per_condition_errors(
    predictions: dict[str, dict[str, pd.DataFrame]],
    condition_labels: np.ndarray,
    thresholds: dict[str, float],
    condition_mapping: dict[int, str],
) -> list[dict[str, Any]]:
    rows = []

    for model_key, split_predictions in predictions.items():
        df = split_predictions["test"]
        threshold = thresholds[model_key]

        sample_indices = df["sample_index"].astype(int).to_numpy()
        y_true = df["y_true"].astype(int).to_numpy()
        y_prob = df["y_prob"].astype(float).to_numpy()
        y_pred = (y_prob >= threshold).astype(int)
        test_condition_labels = condition_labels[sample_indices]

        total_fp = int(((y_true == 0) & (y_pred == 1)).sum())

        for condition_id in sorted(np.unique(test_condition_labels).astype(int).tolist()):
            mask = test_condition_labels == condition_id

            condition_y_true = y_true[mask]
            condition_y_pred = y_pred[mask]

            sample_count = int(mask.sum())
            positive_count = int((condition_y_true == 1).sum())
            negative_count = int((condition_y_true == 0).sum())

            tp = int(((condition_y_true == 1) & (condition_y_pred == 1)).sum())
            fp = int(((condition_y_true == 0) & (condition_y_pred == 1)).sum())
            fn = int(((condition_y_true == 1) & (condition_y_pred == 0)).sum())
            tn = int(((condition_y_true == 0) & (condition_y_pred == 0)).sum())

            precision = tp / (tp + fp) if tp + fp > 0 else 0.0
            recall = tp / (tp + fn) if tp + fn > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0

            rows.append(
                {
                    "model_key": model_key,
                    "model_label": MODEL_SPECS[model_key]["label"],
                    "condition_id": int(condition_id),
                    "condition_label": _condition_label(condition_id, condition_mapping),
                    "sample_count": sample_count,
                    "positive_count": positive_count,
                    "negative_count": negative_count,
                    "positive_ratio": positive_count / sample_count if sample_count else 0.0,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "tn": tn,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "fp_ratio_in_condition": fp / sample_count if sample_count else 0.0,
                    "fp_share_of_model": fp / total_fp if total_fp else 0.0,
                }
            )

    return rows


def _prob_stats(values: np.ndarray) -> dict[str, float | None]:
    if len(values) == 0:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "min": None,
            "max": None,
        }

    return {
        "count": int(len(values)),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "p25": float(np.percentile(values, 25)),
        "p50": float(np.percentile(values, 50)),
        "p75": float(np.percentile(values, 75)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def _overlap_hint(mean_gap: float) -> str:
    if mean_gap < 0.03:
        return "severe_overlap"
    if mean_gap < 0.08:
        return "moderate_overlap"
    return "separable_signal"


def compute_probability_distribution(
    predictions: dict[str, dict[str, pd.DataFrame]],
) -> list[dict[str, Any]]:
    rows = []

    for model_key, split_predictions in predictions.items():
        df = split_predictions["test"]

        y_true = df["y_true"].astype(int).to_numpy()
        y_prob = df["y_prob"].astype(float).to_numpy()

        pos_probs = y_prob[y_true == 1]
        neg_probs = y_prob[y_true == 0]

        pos_stats = _prob_stats(pos_probs)
        neg_stats = _prob_stats(neg_probs)

        pos_mean = pos_stats["mean"] or 0.0
        neg_mean = neg_stats["mean"] or 0.0
        pos_median = pos_stats["p50"] or 0.0
        neg_median = neg_stats["p50"] or 0.0

        mean_gap = float(pos_mean - neg_mean)
        median_gap = float(pos_median - neg_median)

        rows.append(
            {
                "model_key": model_key,
                "model_label": MODEL_SPECS[model_key]["label"],
                "pos_count": pos_stats["count"],
                "pos_mean": pos_stats["mean"],
                "pos_std": pos_stats["std"],
                "pos_p25": pos_stats["p25"],
                "pos_p50": pos_stats["p50"],
                "pos_p75": pos_stats["p75"],
                "pos_min": pos_stats["min"],
                "pos_max": pos_stats["max"],
                "neg_count": neg_stats["count"],
                "neg_mean": neg_stats["mean"],
                "neg_std": neg_stats["std"],
                "neg_p25": neg_stats["p25"],
                "neg_p50": neg_stats["p50"],
                "neg_p75": neg_stats["p75"],
                "neg_min": neg_stats["min"],
                "neg_max": neg_stats["max"],
                "mean_gap": mean_gap,
                "median_gap": median_gap,
                "overlap_hint": _overlap_hint(mean_gap),
            }
        )

    return rows


def compute_top_fp_segments(
    predictions: dict[str, dict[str, pd.DataFrame]],
    thresholds: dict[str, float],
    window_manifest: pd.DataFrame | None,
    y: np.ndarray,
    top_n: int = 10,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    warnings = []
    result: dict[str, list[dict[str, Any]]] = {}

    if window_manifest is None:
        warnings.append("未提供可用 window_manifest.csv，已跳过 segment 误报集中度分析。")
        return result, warnings

    if "segment_id" not in window_manifest.columns:
        warnings.append("window_manifest.csv 缺少 segment_id 字段，已跳过 segment 误报集中度分析。")
        return result, warnings

    for model_key, split_predictions in predictions.items():
        df = split_predictions["test"].copy()
        threshold = thresholds[model_key]

        df["sample_index"] = df["sample_index"].astype(int)
        df["y_true"] = df["y_true"].astype(int)
        df["y_prob"] = df["y_prob"].astype(float)
        df["y_pred"] = (df["y_prob"] >= threshold).astype(int)
        df["is_fp"] = ((df["y_true"] == 0) & (df["y_pred"] == 1)).astype(int)

        test_sample_indices = df["sample_index"].to_numpy()
        segment_ids = window_manifest.iloc[test_sample_indices]["segment_id"].to_numpy()
        df["segment_id"] = segment_ids

        rows = []
        total_fp = int(df["is_fp"].sum())

        if total_fp == 0:
            result[model_key] = []
            continue

        grouped = df.groupby("segment_id", sort=False)

        for segment_id, group in grouped:
            fp_count = int(group["is_fp"].sum())
            if fp_count == 0:
                continue

            test_sample_count = int(len(group))
            positive_count = int((group["y_true"] == 1).sum())
            positive_ratio = positive_count / test_sample_count if test_sample_count else 0.0
            fp_ratio = fp_count / test_sample_count if test_sample_count else 0.0

            rows.append(
                {
                    "model_key": model_key,
                    "model_label": MODEL_SPECS[model_key]["label"],
                    "segment_id": segment_id,
                    "fp_count": fp_count,
                    "test_sample_count_in_segment": test_sample_count,
                    "positive_count_in_segment": positive_count,
                    "positive_ratio_in_segment": positive_ratio,
                    "fp_ratio_in_segment": fp_ratio,
                    "fp_share_of_model": fp_count / total_fp if total_fp else 0.0,
                }
            )

        rows = sorted(rows, key=lambda item: item["fp_count"], reverse=True)
        result[model_key] = rows[:top_n]

    return result, warnings


def judge_distribution_diagnosis(
    split_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    confusion_rows: list[dict[str, Any]],
    per_condition_rows: list[dict[str, Any]],
    probability_rows: list[dict[str, Any]],
    top_fp_segments: dict[str, list[dict[str, Any]]],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    findings = []
    risks = []
    next_steps = []
    flags = set()

    split_ratios = [row["positive_ratio"] for row in split_rows]
    if max(split_ratios) - min(split_ratios) >= 0.10:
        flags.add("label_shift")
        findings.append("train / val / test 正样本比例存在明显差异，segment 级划分带来一定分布偏移。")

    split_map = {row["split"]: row for row in split_rows}
    if (
        split_map["test"]["positive_ratio"] > split_map["train"]["positive_ratio"] + 0.10
    ):
        findings.append("test 正样本比例明显高于 train，模型在测试集可能更容易表现为偏保守。")

    if abs(split_map["val"]["positive_ratio"] - split_map["test"]["positive_ratio"]) >= 0.10:
        flags.add("label_shift")
        risks.append("val 与 test 正样本比例差异较大，验证集阈值迁移到测试集可能存在偏差。")

    condition_lookup = {
        (row["split"], row["condition_id"]): row for row in condition_rows
    }

    condition_ids = sorted({row["condition_id"] for row in condition_rows})
    for condition_id in condition_ids:
        train_row = condition_lookup.get(("train", condition_id))
        test_row = condition_lookup.get(("test", condition_id))
        if not train_row or not test_row:
            continue

        split_ratio_diff = (
            test_row["condition_sample_ratio"] - train_row["condition_sample_ratio"]
        )
        pos_ratio_diff = test_row["positive_ratio"] - train_row["positive_ratio"]

        if abs(split_ratio_diff) >= 0.15:
            flags.add("condition_shift")
            findings.append(
                f"{test_row['condition_label']} 在 test 与 train 中占比差异较大，可能存在工况分布偏移。"
            )

        if abs(pos_ratio_diff) >= 0.10:
            flags.add("condition_shift")
            findings.append(
                f"{test_row['condition_label']} 在 test 与 train 中正样本比例差异较大，"
                "该工况可能影响模型泛化。"
            )

    high_fp_condition_rows = [
        row for row in per_condition_rows if row["fp_share_of_model"] >= 0.50
    ]
    if high_fp_condition_rows:
        flags.add("condition_fp_concentration")
        for row in high_fp_condition_rows:
            findings.append(
                f"{row['model_label']} 的误报主要集中在 {row['condition_label']}，"
                f"该工况 FP Share={row['fp_share_of_model']:.4f}。"
            )

    severe_overlap = [
        row for row in probability_rows if row["overlap_hint"] == "severe_overlap"
    ]
    moderate_overlap = [
        row for row in probability_rows if row["overlap_hint"] == "moderate_overlap"
    ]

    if severe_overlap:
        flags.add("probability_overlap")
        findings.append("部分模型正负样本预测概率均值差距小于 0.03，概率分布高度重叠。")
    elif moderate_overlap:
        flags.add("probability_overlap")
        findings.append("部分模型正负样本预测概率存在中等重叠，Precision 提升空间受到限制。")

    for row in probability_rows:
        model_key = row["model_key"]
        threshold = thresholds[model_key]
        neg_p75 = row["neg_p75"]

        if neg_p75 is not None and neg_p75 > threshold:
            flags.add("probability_threshold_issue")
            findings.append(
                f"{row['model_label']} 负样本概率 P75 高于当前阈值，"
                "较多无报警窗口超过阈值是 FP 偏多的直接原因。"
            )

    for model_key, rows in top_fp_segments.items():
        if not rows:
            continue

        top5_share = sum(row["fp_share_of_model"] for row in rows[:5])
        if top5_share >= 0.50:
            flags.add("segment_concentration")
            findings.append(
                f"{MODEL_SPECS[model_key]['label']} 前 5 个 segment 贡献超过 50% 的 FP，"
                "误报存在片段集中现象。"
            )

    if len(flags) >= 2:
        level = "mixed_issue"
    elif "segment_concentration" in flags:
        level = "segment_concentration_issue"
    elif "condition_shift" in flags or "condition_fp_concentration" in flags:
        level = "condition_shift_issue"
    elif "probability_overlap" in flags or "probability_threshold_issue" in flags:
        level = "threshold_and_probability_issue"
    elif "label_shift" in flags:
        level = "label_or_signal_issue"
    else:
        level = "mixed_issue"
        findings.append("未发现单一主导因素，误报可能来自概率分布、工况差异和标签信号的共同作用。")

    if "probability_threshold_issue" in flags:
        next_steps.append("优先进行概率校准或阈值策略分析，例如保序回归、Platt Scaling 或验证集阈值固化。")

    if "condition_fp_concentration" in flags or "condition_shift" in flags:
        next_steps.append("进一步做按工况阈值分析，不急于重新训练模型。")

    if "probability_overlap" in flags:
        next_steps.append("继续诊断标签定义和风险窗口构造，可对未来 5 秒 / 10 秒 / 30 秒内是否报警进行对照实验。")

    if "label_shift" in flags:
        next_steps.append("继续保留 segment 级划分，并在论文中说明连续片段之间存在分布差异。")

    if "segment_concentration" in flags:
        next_steps.append("查看 Top FP segment 的原始监测曲线和报警分布，不要直接判定模型整体失败。")

    if not next_steps:
        next_steps.append("继续结合概率校准、阈值策略和标签 horizon 进行后续诊断。")

    return {
        "level": level,
        "main_findings": findings,
        "risks": risks,
        "next_steps": next_steps,
        "flags": sorted(flags),
    }


def print_distribution_diagnosis(
    *,
    dataset_dir: Path,
    mode: str,
    thresholds: dict[str, float],
    split_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    confusion_rows: list[dict[str, Any]],
    per_condition_rows: list[dict[str, Any]],
    probability_rows: list[dict[str, Any]],
    top_fp_segments: dict[str, list[dict[str, Any]]],
    global_diagnosis: dict[str, Any],
    warnings: list[str],
    save_enabled: bool,
) -> None:
    print("=" * 60)
    print("RailPHM Task 5-3b-3 Distribution & Error Diagnosis")
    print("=" * 60)
    print()
    print("[Input]")
    print(f"dataset_dir: {dataset_dir}")
    print(f"mode: {mode}")
    print("thresholds:")
    for model_key, threshold in thresholds.items():
        print(f"- {MODEL_SPECS[model_key]['label']}: {_fmt_threshold(threshold)}")

    print()
    print("[Split Label Distribution]")
    print("| Split | Samples | Positive | Negative | Positive Ratio |")
    print("|---|---:|---:|---:|---:|")
    for row in split_rows:
        print(
            f"| {row['split']} | {row['sample_count']} | "
            f"{row['positive_count']} | {row['negative_count']} | "
            f"{_fmt_float(row['positive_ratio'])} |"
        )

    print()
    print("[Condition Distribution]")
    print("| Split | Condition | Samples | Split Ratio | Positive | Positive Ratio |")
    print("|---|---|---:|---:|---:|---:|")
    for row in condition_rows:
        print(
            f"| {row['split']} | {row['condition_label']} | "
            f"{row['sample_count']} | {_fmt_float(row['condition_sample_ratio'])} | "
            f"{row['positive_count']} | {_fmt_float(row['positive_ratio'])} |"
        )

    print()
    print("[Test Confusion Matrix @ Best Val Threshold]")
    print("| Model | Threshold | TP | FP | FN | TN | Precision | Recall | F1 | Pred Pos Ratio |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in confusion_rows:
        print(
            f"| {row['model_label']} | {_fmt_threshold(row['threshold'])} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} | "
            f"{_fmt_float(row['precision'])} | {_fmt_float(row['recall'])} | "
            f"{_fmt_float(row['f1'])} | {_fmt_float(row['predicted_positive_ratio'])} |"
        )

    print()
    print("[Per-condition Error Analysis @ Best Val Threshold]")
    print(
        "| Model | Condition | Samples | Pos Ratio | TP | FP | FN | TN | "
        "Precision | Recall | F1 | FP Share |"
    )
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in per_condition_rows:
        print(
            f"| {row['model_label']} | {row['condition_label']} | "
            f"{row['sample_count']} | {_fmt_float(row['positive_ratio'])} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} | "
            f"{_fmt_float(row['precision'])} | {_fmt_float(row['recall'])} | "
            f"{_fmt_float(row['f1'])} | {_fmt_float(row['fp_share_of_model'])} |"
        )

    print()
    print("[Probability Distribution by True Label]")
    print(
        "| Model | Pos Mean | Pos P25 | Pos P50 | Pos P75 | "
        "Neg Mean | Neg P25 | Neg P50 | Neg P75 | Mean Gap | Overlap |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in probability_rows:
        print(
            f"| {row['model_label']} | {_fmt_float(row['pos_mean'])} | "
            f"{_fmt_float(row['pos_p25'])} | {_fmt_float(row['pos_p50'])} | "
            f"{_fmt_float(row['pos_p75'])} | {_fmt_float(row['neg_mean'])} | "
            f"{_fmt_float(row['neg_p25'])} | {_fmt_float(row['neg_p50'])} | "
            f"{_fmt_float(row['neg_p75'])} | {_fmt_float(row['mean_gap'])} | "
            f"{row['overlap_hint']} |"
        )

    print()
    print("[Top FP Segments]")
    if not top_fp_segments:
        print("Segment analysis skipped.")
    else:
        for model_key, rows in top_fp_segments.items():
            print(f"Model: {MODEL_SPECS[model_key]['label']}")
            print("| Rank | Segment ID | FP Count | Test Samples | Segment Pos Ratio | FP Ratio |")
            print("|---:|---|---:|---:|---:|---:|")
            for rank, row in enumerate(rows, start=1):
                print(
                    f"| {rank} | {row['segment_id']} | {row['fp_count']} | "
                    f"{row['test_sample_count_in_segment']} | "
                    f"{_fmt_float(row['positive_ratio_in_segment'])} | "
                    f"{_fmt_float(row['fp_ratio_in_segment'])} |"
                )
            print()

    print("[Global Diagnosis]")
    print(f"level: {global_diagnosis['level']}")
    print("main_findings:")
    if global_diagnosis["main_findings"]:
        for finding in global_diagnosis["main_findings"]:
            print(f"- {finding}")
    else:
        print("- None")

    print("risks:")
    if global_diagnosis["risks"]:
        for risk in global_diagnosis["risks"]:
            print(f"- {risk}")
    else:
        print("- None")

    print("next_steps:")
    for step in global_diagnosis["next_steps"]:
        print(f"- {step}")

    print()
    print("[Warnings]")
    if warnings:
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("No warnings.")

    print()
    print("[Save]")
    if save_enabled:
        print("Save mode enabled. Lightweight summary will be saved.")
    else:
        print("No files saved. Terminal-only diagnosis mode.")


def save_distribution_summary_if_requested(
    *,
    output_dir: Path | None,
    save: bool,
    save_detail: bool,
    payload: dict[str, Any],
) -> None:
    if not save and not save_detail:
        return

    if output_dir is None:
        raise ValueError("--save 或 --save-detail 需要同时提供 --output-dir")

    output_dir.mkdir(parents=True, exist_ok=True)

    if save:
        summary_path = output_dir / "distribution_diagnosis_summary.json"
        summary_path.write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print()
        print("[Save]")
        print(f"distribution_diagnosis_summary.json saved: {summary_path}")

    if save_detail:
        pd.DataFrame(payload["split_label_distribution"]).to_csv(
            output_dir / "split_label_distribution.csv",
            index=False,
        )
        pd.DataFrame(payload["condition_distribution"]).to_csv(
            output_dir / "condition_distribution.csv",
            index=False,
        )
        pd.DataFrame(payload["per_condition_error_analysis"]).to_csv(
            output_dir / "per_condition_error_analysis.csv",
            index=False,
        )
        pd.DataFrame(payload["probability_distribution"]).to_csv(
            output_dir / "probability_distribution_summary.csv",
            index=False,
        )

        fp_rows = []
        for model_key, rows in payload["top_fp_segments"].items():
            for row in rows:
                fp_rows.append(row)
        pd.DataFrame(fp_rows).to_csv(
            output_dir / "top_fp_segments.csv",
            index=False,
        )
        print("detail CSV files saved.")


def run_distribution_analysis(args: argparse.Namespace) -> dict[str, Any]:
    if args.dataset_dir is None:
        raise ValueError("--stage distribution 必须提供 --dataset-dir")

    thresholds = parse_thresholds(args.thresholds, output_dir=args.output_dir)

    dataset_inputs = load_dataset_distribution_inputs(args.dataset_dir)
    condition_mapping = _condition_mapping(dataset_inputs["condition_summary"])

    predictions, mode = load_predictions_for_threshold_analysis(args)

    split_rows = compute_split_label_distribution(
        y=dataset_inputs["y"],
        split_indices=dataset_inputs["split_indices"],
    )
    condition_rows = compute_condition_distribution(
        y=dataset_inputs["y"],
        condition_labels=dataset_inputs["condition_labels"],
        split_indices=dataset_inputs["split_indices"],
        condition_mapping=condition_mapping,
    )
    confusion_rows = compute_confusion_by_model(
        predictions=predictions,
        thresholds=thresholds,
    )
    per_condition_rows = compute_per_condition_errors(
        predictions=predictions,
        condition_labels=dataset_inputs["condition_labels"],
        thresholds=thresholds,
        condition_mapping=condition_mapping,
    )
    probability_rows = compute_probability_distribution(predictions=predictions)
    top_fp_segments, segment_warnings = compute_top_fp_segments(
        predictions=predictions,
        thresholds=thresholds,
        window_manifest=dataset_inputs["window_manifest"],
        y=dataset_inputs["y"],
    )

    warnings = list(dataset_inputs["warnings"]) + list(segment_warnings)

    global_diagnosis = judge_distribution_diagnosis(
        split_rows=split_rows,
        condition_rows=condition_rows,
        confusion_rows=confusion_rows,
        per_condition_rows=per_condition_rows,
        probability_rows=probability_rows,
        top_fp_segments=top_fp_segments,
        thresholds=thresholds,
    )

    payload = {
        "task": "stage3_distribution_error_diagnosis",
        "dataset_dir": str(args.dataset_dir),
        "mode": mode,
        "thresholds": thresholds,
        "split_label_distribution": split_rows,
        "condition_distribution": condition_rows,
        "test_confusion_matrix": confusion_rows,
        "per_condition_error_analysis": per_condition_rows,
        "probability_distribution": probability_rows,
        "top_fp_segments": top_fp_segments,
        "global_diagnosis": global_diagnosis,
        "warnings": warnings,
    }

    print_distribution_diagnosis(
        dataset_dir=Path(args.dataset_dir),
        mode=mode,
        thresholds=thresholds,
        split_rows=split_rows,
        condition_rows=condition_rows,
        confusion_rows=confusion_rows,
        per_condition_rows=per_condition_rows,
        probability_rows=probability_rows,
        top_fp_segments=top_fp_segments,
        global_diagnosis=global_diagnosis,
        warnings=warnings,
        save_enabled=bool(args.save or args.save_detail),
    )

    save_distribution_summary_if_requested(
        output_dir=args.output_dir,
        save=args.save,
        save_detail=args.save_detail,
        payload=payload,
    )

    return payload

def parse_horizons(raw: str) -> list[int]:
    if raw is None or not str(raw).strip():
        raise ValueError("horizon-seconds 不能为空")

    horizons = []

    for item in str(raw).split(","):
        item = item.strip()
        if not item:
            continue

        try:
            value = int(item)
        except Exception as exc:
            raise ValueError(f"horizon-seconds 中存在非法值: {item}") from exc

        if value <= 0:
            raise ValueError("horizon-seconds 必须为正整数")

        horizons.append(value)

    if not horizons:
        raise ValueError("horizon-seconds 不能为空")

    return sorted(set(horizons))


def load_stage4_dataset_inputs(dataset_dir: Path) -> dict[str, Any]:
    dataset_dir = Path(dataset_dir)

    required_files = [
        dataset_dir / "X.npy",
        dataset_dir / "y.npy",
        dataset_dir / "splits" / "test_indices.npy",
        dataset_dir / "window_manifest.csv",
    ]

    for path in required_files:
        if not path.exists():
            if path.name == "window_manifest.csv":
                raise FileNotFoundError("缺少 window_manifest.csv，无法进行高误报 segment 与标签连续性诊断。")
            raise FileNotFoundError(f"缺少 Stage 4 诊断文件: {path}")

    X = np.load(dataset_dir / "X.npy", allow_pickle=False)
    y = np.load(dataset_dir / "y.npy", allow_pickle=False).astype(int)
    test_indices = np.load(dataset_dir / "splits" / "test_indices.npy", allow_pickle=False).astype(np.int64)

    window_manifest = pd.read_csv(dataset_dir / "window_manifest.csv")

    if len(window_manifest) != len(y):
        raise ValueError("window_manifest 行数与 y.npy 样本数不一致，无法根据 sample_index 追溯 segment。")

    if "segment_id" not in window_manifest.columns:
        raise ValueError("window_manifest.csv 缺少 segment_id 字段，无法进行 segment 诊断。")

    warnings = []

    if "label" in window_manifest.columns:
        try:
            manifest_label = pd.to_numeric(window_manifest["label"], errors="coerce")
            if manifest_label.notna().all():
                mismatch_count = int((manifest_label.astype(int).to_numpy() != y).sum())
                if mismatch_count > 0:
                    warnings.append(
                        f"window_manifest.csv 中 label 与 y.npy 存在 {mismatch_count} 处不一致，诊断以 y.npy 为准。"
                    )
        except Exception:
            warnings.append("window_manifest.csv 中 label 字段无法完整转为整数，诊断以 y.npy 为准。")

    return {
        "dataset_dir": dataset_dir,
        "X_shape": [int(value) for value in X.shape],
        "y": y,
        "test_indices": test_indices,
        "window_manifest": window_manifest,
        "warnings": warnings,
    }


def build_predictions_with_manifest(
    predictions: dict[str, dict[str, pd.DataFrame]],
    thresholds: dict[str, float],
    window_manifest: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    result = {}

    for model_key, split_predictions in predictions.items():
        if model_key not in thresholds:
            raise ValueError(f"缺少 {model_key} 的 best_val_threshold")

        df = split_predictions["test"].copy()

        required_columns = {"sample_index", "y_true", "y_prob"}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            raise ValueError(f"{model_key} test predictions 缺少字段: {sorted(missing_columns)}")

        df["sample_index"] = df["sample_index"].astype(int)
        df["y_true"] = df["y_true"].astype(int)
        df["y_prob"] = df["y_prob"].astype(float)

        if (df["sample_index"] < 0).any() or (df["sample_index"] >= len(window_manifest)).any():
            raise ValueError(f"{model_key} test predictions 中 sample_index 越界")

        manifest_part = window_manifest.iloc[df["sample_index"].to_numpy()].reset_index(drop=True)

        for column in ["segment_id", "segment_file", "target_time", "window_start_time", "window_end_time"]:
            if column in manifest_part.columns:
                df[column] = manifest_part[column].to_numpy()
            else:
                df[column] = None

        threshold = thresholds[model_key]
        df["y_pred_best"] = (df["y_prob"] >= threshold).astype(int)
        df["is_tp"] = ((df["y_true"] == 1) & (df["y_pred_best"] == 1)).astype(int)
        df["is_fp"] = ((df["y_true"] == 0) & (df["y_pred_best"] == 1)).astype(int)
        df["is_fn"] = ((df["y_true"] == 1) & (df["y_pred_best"] == 0)).astype(int)
        df["is_tn"] = ((df["y_true"] == 0) & (df["y_pred_best"] == 0)).astype(int)

        df["_target_time_parsed"] = pd.to_datetime(df["target_time"], errors="coerce")
        if df["_target_time_parsed"].notna().any():
            df = df.sort_values(["segment_id", "_target_time_parsed", "sample_index"]).reset_index(drop=True)
        else:
            df = df.sort_values(["segment_id", "sample_index"]).reset_index(drop=True)

        result[model_key] = df

    return result


def _safe_segment_file(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, float) and np.isnan(value):
        return None

    text = str(value)
    if text == "nan":
        return None

    return text


def _metrics_from_counts(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def compute_stage4_top_fp_segments(
    predictions_with_manifest: dict[str, pd.DataFrame],
    top_k: int,
) -> dict[str, list[dict[str, Any]]]:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top-k-segments 必须为正整数")

    result = {}

    for model_key, df in predictions_with_manifest.items():
        total_fp = int(df["is_fp"].sum())
        rows = []

        grouped = df.groupby("segment_id", sort=False)

        for segment_id, group in grouped:
            fp = int(group["is_fp"].sum())
            if fp <= 0:
                continue

            tp = int(group["is_tp"].sum())
            fn = int(group["is_fn"].sum())
            tn = int(group["is_tn"].sum())
            sample_count = int(len(group))
            positive_count = int((group["y_true"] == 1).sum())
            negative_count = int((group["y_true"] == 0).sum())

            metrics = _metrics_from_counts(tp=tp, fp=fp, fn=fn, tn=tn)

            segment_file = None
            if "segment_file" in group.columns:
                non_null_files = [
                    _safe_segment_file(value)
                    for value in group["segment_file"].tolist()
                    if _safe_segment_file(value) is not None
                ]
                if non_null_files:
                    segment_file = non_null_files[0]

            first_target_time = None
            last_target_time = None
            if "target_time" in group.columns:
                target_times = [
                    str(value)
                    for value in group["target_time"].tolist()
                    if _safe_segment_file(value) is not None
                ]
                if target_times:
                    first_target_time = target_times[0]
                    last_target_time = target_times[-1]

            rows.append(
                {
                    "model_key": model_key,
                    "model_label": MODEL_SPECS[model_key]["label"],
                    "segment_id": segment_id,
                    "segment_file": segment_file,
                    "test_sample_count": sample_count,
                    "positive_count": positive_count,
                    "negative_count": negative_count,
                    "positive_ratio": positive_count / sample_count if sample_count else 0.0,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "tn": tn,
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1": metrics["f1"],
                    "fp_ratio": fp / sample_count if sample_count else 0.0,
                    "fp_share": fp / total_fp if total_fp else 0.0,
                    "first_target_time": first_target_time,
                    "last_target_time": last_target_time,
                }
            )

        rows = sorted(rows, key=lambda item: (item["fp"], item["fp_ratio"]), reverse=True)
        for rank, row in enumerate(rows[:top_k], start=1):
            row["rank"] = rank

        result[model_key] = rows[:top_k]

    return result


def compute_common_high_fp_segments(
    top_fp_segments: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}

    for model_key, rows in top_fp_segments.items():
        for row in rows:
            segment_id = row["segment_id"]
            grouped.setdefault(segment_id, []).append(row)

    common_rows = []

    for segment_id, rows in grouped.items():
        appeared_models = [row["model_label"] for row in rows]
        segment_files = [row["segment_file"] for row in rows if row.get("segment_file")]
        segment_file = segment_files[0] if segment_files else None

        common_rows.append(
            {
                "segment_id": segment_id,
                "segment_file": segment_file,
                "appeared_models": appeared_models,
                "appear_count": len(rows),
                "avg_fp_count": float(np.mean([row["fp"] for row in rows])),
                "avg_fp_ratio": float(np.mean([row["fp_ratio"] for row in rows])),
                "pos_ratio": float(np.mean([row["positive_ratio"] for row in rows])),
            }
        )

    common_rows = sorted(
        common_rows,
        key=lambda item: (item["appear_count"], item["avg_fp_count"]),
        reverse=True,
    )
    return common_rows


def _positive_runs(labels: list[int]) -> tuple[list[int], int, float]:
    runs = []
    current = 0

    for label in labels:
        if label == 1:
            current += 1
        else:
            if current > 0:
                runs.append(current)
                current = 0

    if current > 0:
        runs.append(current)

    isolated = 0
    for index, label in enumerate(labels):
        if label != 1:
            continue

        left_positive = index > 0 and labels[index - 1] == 1
        right_positive = index < len(labels) - 1 and labels[index + 1] == 1

        if not left_positive and not right_positive:
            isolated += 1

    positive_count = sum(labels)
    isolated_ratio = isolated / positive_count if positive_count else 0.0

    return runs, isolated, isolated_ratio


def compute_label_continuity_for_segments(
    predictions_with_manifest: dict[str, pd.DataFrame],
    top_fp_segments: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []

    for model_key, segments in top_fp_segments.items():
        df = predictions_with_manifest[model_key]

        for segment_row in segments:
            segment_id = segment_row["segment_id"]
            group = df[df["segment_id"] == segment_id].copy()

            if group["_target_time_parsed"].notna().any():
                group = group.sort_values(["_target_time_parsed", "sample_index"])
            else:
                group = group.sort_values("sample_index")

            labels = group["y_true"].astype(int).tolist()
            runs, isolated_count, isolated_ratio = _positive_runs(labels)

            positive_count = int(sum(labels))
            sample_count = int(len(labels))
            positive_run_count = int(len(runs))
            max_run = int(max(runs)) if runs else 0
            mean_run = float(np.mean(runs)) if runs else 0.0

            rows.append(
                {
                    "model_key": model_key,
                    "model_label": MODEL_SPECS[model_key]["label"],
                    "segment_id": segment_id,
                    "segment_file": segment_row.get("segment_file"),
                    "positive_count": positive_count,
                    "sample_count": sample_count,
                    "positive_ratio": positive_count / sample_count if sample_count else 0.0,
                    "positive_run_count": positive_run_count,
                    "positive_run_lengths": runs,
                    "max_positive_run_length": max_run,
                    "mean_positive_run_length": mean_run,
                    "isolated_positive_count": isolated_count,
                    "isolated_positive_ratio": isolated_ratio,
                }
            )

    return rows


def _position_values(group: pd.DataFrame) -> tuple[np.ndarray, bool]:
    parsed = group["_target_time_parsed"]

    if parsed.notna().all():
        # 使用相对时间差，避免不同 pandas / datetime 精度导致 ns/us/ms 换算不一致。
        # 返回单位为秒，且当前 segment 内第一个样本位置为 0。
        relative_seconds = (
            parsed - parsed.iloc[0]
        ).dt.total_seconds().to_numpy(dtype=np.float64)

        return relative_seconds, True

    # target_time 不可用时，退回到样本顺序近似，每个样本间隔约 1 秒。
    return np.arange(len(group), dtype=np.float64), False


def compute_fp_distance_to_positive(
    predictions_with_manifest: dict[str, pd.DataFrame],
    top_fp_segments: dict[str, list[dict[str, Any]]],
    horizons: list[int],
) -> list[dict[str, Any]]:
    rows = []

    sorted_horizons = sorted(horizons)

    for model_key, segments in top_fp_segments.items():
        df = predictions_with_manifest[model_key]

        for segment_row in segments:
            segment_id = segment_row["segment_id"]
            group = df[df["segment_id"] == segment_id].copy()

            if group["_target_time_parsed"].notna().any():
                group = group.sort_values(["_target_time_parsed", "sample_index"]).reset_index(drop=True)
            else:
                group = group.sort_values("sample_index").reset_index(drop=True)

            positions, _ = _position_values(group)
            y_true = group["y_true"].astype(int).to_numpy()
            is_fp = group["is_fp"].astype(int).to_numpy() == 1

            fp_positions = positions[is_fp]
            positive_positions = positions[y_true == 1]

            fp_count = int(len(fp_positions))
            no_positive = len(positive_positions) == 0

            if fp_count == 0:
                continue

            if no_positive:
                row = {
                    "model_key": model_key,
                    "model_label": MODEL_SPECS[model_key]["label"],
                    "segment_id": segment_id,
                    "segment_file": segment_row.get("segment_file"),
                    "fp_count": fp_count,
                    "mean_distance_to_nearest_positive": None,
                    "median_distance_to_nearest_positive": None,
                    "p75_distance_to_nearest_positive": None,
                    "no_positive_in_segment": True,
                }
                for horizon in sorted_horizons:
                    row[f"fp_within_{horizon}s_count"] = 0
                    row[f"fp_within_{horizon}s_ratio"] = 0.0
                rows.append(row)
                continue

            distances = []
            for fp_position in fp_positions:
                nearest = float(np.min(np.abs(positive_positions - fp_position)))
                distances.append(nearest)

            distances_array = np.asarray(distances, dtype=np.float64)

            row = {
                "model_key": model_key,
                "model_label": MODEL_SPECS[model_key]["label"],
                "segment_id": segment_id,
                "segment_file": segment_row.get("segment_file"),
                "fp_count": fp_count,
                "mean_distance_to_nearest_positive": float(np.mean(distances_array)),
                "median_distance_to_nearest_positive": float(np.median(distances_array)),
                "p75_distance_to_nearest_positive": float(np.percentile(distances_array, 75)),
                "no_positive_in_segment": False,
            }

            for horizon in sorted_horizons:
                count = int((distances_array <= horizon).sum())
                row[f"fp_within_{horizon}s_count"] = count
                row[f"fp_within_{horizon}s_ratio"] = count / fp_count if fp_count else 0.0

            rows.append(row)

    return rows


def _future_convertible_count(group: pd.DataFrame, horizon: int) -> tuple[int, int]:
    if group["_target_time_parsed"].notna().any():
        group = group.sort_values(["_target_time_parsed", "sample_index"]).reset_index(drop=True)
    else:
        group = group.sort_values("sample_index").reset_index(drop=True)

    positions, _ = _position_values(group)
    y_true = group["y_true"].astype(int).to_numpy()
    is_fp = group["is_fp"].astype(int).to_numpy() == 1

    fp_indices = np.where(is_fp)[0]
    positive_indices = np.where(y_true == 1)[0]

    if len(fp_indices) == 0:
        return 0, 0

    if len(positive_indices) == 0:
        return int(len(fp_indices)), 0

    positive_positions = positions[positive_indices]

    convertible = 0

    for fp_index in fp_indices:
        fp_position = positions[fp_index]
        future_positive = positive_positions[
            (positive_positions > fp_position) & (positive_positions <= fp_position + horizon)
        ]
        if len(future_positive) > 0:
            convertible += 1

    return int(len(fp_indices)), int(convertible)


def compute_future_horizon_potential(
    predictions_with_manifest: dict[str, pd.DataFrame],
    top_fp_segments: dict[str, list[dict[str, Any]]],
    horizons: list[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overall_rows = []
    segment_rows = []

    for model_key, df in predictions_with_manifest.items():
        for horizon in horizons:
            fp_count, convertible_count = 0, 0

            grouped = df.groupby("segment_id", sort=False)

            for _, group in grouped:
                group_fp_count, group_convertible = _future_convertible_count(group, horizon)
                fp_count += group_fp_count
                convertible_count += group_convertible

            overall_rows.append(
                {
                    "model_key": model_key,
                    "model_label": MODEL_SPECS[model_key]["label"],
                    "horizon": int(horizon),
                    "fp_count": int(fp_count),
                    "fp_convertible_count": int(convertible_count),
                    "fp_convertible_ratio": convertible_count / fp_count if fp_count else 0.0,
                }
            )

        top_segment_ids = {row["segment_id"] for row in top_fp_segments.get(model_key, [])}

        for segment_id in top_segment_ids:
            group = df[df["segment_id"] == segment_id].copy()
            if group.empty:
                continue

            segment_file = None
            files = [
                _safe_segment_file(value)
                for value in group["segment_file"].tolist()
                if _safe_segment_file(value) is not None
            ]
            if files:
                segment_file = files[0]

            for horizon in horizons:
                fp_count, convertible_count = _future_convertible_count(group, horizon)

                segment_rows.append(
                    {
                        "model_key": model_key,
                        "model_label": MODEL_SPECS[model_key]["label"],
                        "segment_id": segment_id,
                        "segment_file": segment_file,
                        "horizon": int(horizon),
                        "segment_fp_count": int(fp_count),
                        "segment_fp_convertible_count": int(convertible_count),
                        "segment_fp_convertible_ratio": (
                            convertible_count / fp_count if fp_count else 0.0
                        ),
                    }
                )

    return overall_rows, segment_rows


def judge_segment_label_diagnosis(
    top_fp_segments: dict[str, list[dict[str, Any]]],
    common_segments: list[dict[str, Any]],
    distance_rows: list[dict[str, Any]],
    future_overall_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    findings = []
    risks = []
    next_steps = []
    flags = set()

    common_repeated = [row for row in common_segments if row["appear_count"] >= 2]
    if common_repeated:
        flags.add("common_segments")
        findings.append("多个模型的高 FP segment 存在重叠，说明误报与特定连续片段有关。")

    top_fp_all = [
        row
        for rows in top_fp_segments.values()
        for row in rows
    ]
    high_fp_ratio_segments = [row for row in top_fp_all if row["fp_ratio"] >= 0.50]
    if high_fp_ratio_segments:
        flags.add("segment_high_fp")
        findings.append("部分高 FP segment 的 FP ratio 很高，模型可能对整段状态存在风险高估。")
        risks.append("若直接降低阈值部署，可能在某些 segment 上出现连续误报。")

    close_to_positive_rows = []
    for row in distance_rows:
        for key, value in row.items():
            if key.startswith("fp_within_10s_ratio") and value is not None and value >= 0.30:
                close_to_positive_rows.append(row)

    if close_to_positive_rows:
        flags.add("near_positive_fp")
        findings.append("部分 FP 距离真实报警点较近，当前单点报警标签可能将报警邻近窗口计为 FP。")

    high_convertible = [
        row for row in future_overall_rows
        if row["horizon"] in {10, 30} and row["fp_convertible_ratio"] >= 0.30
    ]
    low_convertible = [
        row for row in future_overall_rows
        if row["horizon"] == max([item["horizon"] for item in future_overall_rows])
        and row["fp_convertible_ratio"] < 0.10
    ] if future_overall_rows else []

    if high_convertible:
        flags.add("future_horizon_promising")
        findings.append("future-horizon 估算显示较多 FP 后续会出现真实报警，标签 horizon 实验具有潜力。")
        next_steps.append("优先做 future-horizon 标签实验，例如未来 5 秒 / 10 秒 / 30 秒内是否报警。")
    elif low_convertible:
        flags.add("true_fp")
        findings.append("多数 FP 距离后续真实报警较远，标签 horizon 未必能解决误报问题。")
        next_steps.append("优先做概率校准、按工况阈值分析或查看高 FP segment 原始曲线。")

    if "common_segments" in flags:
        next_steps.append("人工查看共同高 FP segment 的原始 CSV，重点看速度、里程、信号机、应答器和报警部位变化。")

    if "near_positive_fp" in flags:
        risks.append("单点报警标签可能低估报警邻近窗口的风险属性。")

    if len(flags) >= 2:
        level = "mixed_issue"
    elif "future_horizon_promising" in flags:
        level = "future_horizon_promising"
    elif "true_fp" in flags:
        level = "true_false_positive_issue"
    elif "common_segments" in flags or "segment_high_fp" in flags:
        level = "segment_specific_shift"
    elif "near_positive_fp" in flags:
        level = "segment_label_issue"
    else:
        level = "mixed_issue"
        findings.append("未发现单一主导因素，需结合原始曲线和标签 horizon 继续诊断。")

    if not next_steps:
        next_steps.append("暂不建议继续堆叠更复杂模型结构，优先进行标签连续性、概率校准和 segment 原始曲线检查。")

    return {
        "level": level,
        "main_findings": findings,
        "risks": risks,
        "next_steps": next_steps,
        "flags": sorted(flags),
    }


def print_segment_label_diagnosis(
    *,
    dataset_dir: Path,
    prediction_source: str,
    thresholds: dict[str, float],
    top_k_segments: int,
    horizons: list[int],
    high_fp_segments: dict[str, list[dict[str, Any]]],
    common_segments: list[dict[str, Any]],
    label_continuity_rows: list[dict[str, Any]],
    distance_rows: list[dict[str, Any]],
    future_overall_rows: list[dict[str, Any]],
    future_segment_rows: list[dict[str, Any]],
    global_diagnosis: dict[str, Any],
    warnings: list[str],
    save_enabled: bool,
) -> None:
    print("=" * 60)
    print("RailPHM Task 5-3b-4 High-FP Segment & Label Continuity Diagnosis")
    print("=" * 60)
    print()
    print("[Input]")
    print(f"dataset_dir: {dataset_dir}")
    print(f"prediction_source: {prediction_source}")
    print(f"top_k_segments: {top_k_segments}")
    print(f"horizons: {','.join(str(value) for value in horizons)}")
    print("thresholds:")
    for model_key, threshold in thresholds.items():
        print(f"- {MODEL_SPECS[model_key]['label']}: {_fmt_threshold(threshold)}")

    print()
    print("[High-FP Segment Files]")
    print("| Model | Rank | Segment ID | Segment File | FP Count | FP Ratio | Pos Ratio |")
    print("|---|---:|---|---|---:|---:|---:|")
    for model_key, rows in high_fp_segments.items():
        for row in rows:
            print(
                f"| {row['model_label']} | {row['rank']} | {row['segment_id']} | "
                f"{row.get('segment_file') or 'null'} | {row['fp']} | "
                f"{_fmt_float(row['fp_ratio'])} | {_fmt_float(row['positive_ratio'])} |"
            )

    print()
    print("[Top FP Segments @ Best Val Threshold]")
    for model_key, rows in high_fp_segments.items():
        print(f"Model: {MODEL_SPECS[model_key]['label']}")
        print("| Rank | Segment ID | Segment File | Test Samples | Pos Ratio | TP | FP | FN | TN | FP Ratio | FP Share |")
        print("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in rows:
            print(
                f"| {row['rank']} | {row['segment_id']} | {row.get('segment_file') or 'null'} | "
                f"{row['test_sample_count']} | {_fmt_float(row['positive_ratio'])} | "
                f"{row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} | "
                f"{_fmt_float(row['fp_ratio'])} | {_fmt_float(row['fp_share'])} |"
            )
        print()

    print("[Common High-FP Segments Across Models]")
    print("| Segment ID | Segment File | Appeared Models | Appear Count | Avg FP Count | Avg FP Ratio | Pos Ratio |")
    print("|---|---|---|---:|---:|---:|---:|")
    for row in common_segments:
        print(
            f"| {row['segment_id']} | {row.get('segment_file') or 'null'} | "
            f"{', '.join(row['appeared_models'])} | {row['appear_count']} | "
            f"{_fmt_float(row['avg_fp_count'])} | {_fmt_float(row['avg_fp_ratio'])} | "
            f"{_fmt_float(row['pos_ratio'])} |"
        )

    print()
    print("[Label Continuity in Top FP Segments]")
    print("| Model | Segment ID | Segment File | Positive Count | Positive Ratio | Pos Runs | Max Run | Mean Run | Isolated Pos | Isolated Ratio |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in label_continuity_rows:
        print(
            f"| {row['model_label']} | {row['segment_id']} | {row.get('segment_file') or 'null'} | "
            f"{row['positive_count']} | {_fmt_float(row['positive_ratio'])} | "
            f"{row['positive_run_count']} | {row['max_positive_run_length']} | "
            f"{_fmt_float(row['mean_positive_run_length'])} | "
            f"{row['isolated_positive_count']} | {_fmt_float(row['isolated_positive_ratio'])} |"
        )

    print()
    print("[FP Distance to Nearest Positive]")
    first_horizon = horizons[0]
    second_horizon = horizons[1] if len(horizons) > 1 else horizons[0]
    third_horizon = horizons[2] if len(horizons) > 2 else horizons[-1]
    print(
        f"| Model | Segment ID | Segment File | FP | FP<={first_horizon}s | "
        f"FP<={second_horizon}s | FP<={third_horizon}s | Mean Dist | Median Dist | No Positive |"
    )
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    for row in distance_rows:
        print(
            f"| {row['model_label']} | {row['segment_id']} | {row.get('segment_file') or 'null'} | "
            f"{row['fp_count']} | "
            f"{row.get(f'fp_within_{first_horizon}s_count', 0)} | "
            f"{row.get(f'fp_within_{second_horizon}s_count', 0)} | "
            f"{row.get(f'fp_within_{third_horizon}s_count', 0)} | "
            f"{_fmt_float(row['mean_distance_to_nearest_positive'])} | "
            f"{_fmt_float(row['median_distance_to_nearest_positive'])} | "
            f"{str(row['no_positive_in_segment']).lower()} |"
        )

    print()
    print("[Future-horizon Label Potential]")
    print("| Model | Horizon | FP Count | FP Convertible | Convertible Ratio |")
    print("|---|---:|---:|---:|---:|")
    for row in future_overall_rows:
        print(
            f"| {row['model_label']} | {row['horizon']} | {row['fp_count']} | "
            f"{row['fp_convertible_count']} | {_fmt_float(row['fp_convertible_ratio'])} |"
        )

    print()
    print("[Future-horizon Potential in Top FP Segments]")
    print("| Model | Segment ID | Segment File | Horizon | FP | Convertible | Convertible Ratio |")
    print("|---|---|---|---:|---:|---:|---:|")
    for row in future_segment_rows:
        print(
            f"| {row['model_label']} | {row['segment_id']} | {row.get('segment_file') or 'null'} | "
            f"{row['horizon']} | {row['segment_fp_count']} | "
            f"{row['segment_fp_convertible_count']} | "
            f"{_fmt_float(row['segment_fp_convertible_ratio'])} |"
        )

    print()
    print("[Global Diagnosis]")
    print(f"level: {global_diagnosis['level']}")
    print("main_findings:")
    if global_diagnosis["main_findings"]:
        for finding in global_diagnosis["main_findings"]:
            print(f"- {finding}")
    else:
        print("- None")

    print("risks:")
    if global_diagnosis["risks"]:
        for risk in global_diagnosis["risks"]:
            print(f"- {risk}")
    else:
        print("- None")

    print("next_steps:")
    for step in global_diagnosis["next_steps"]:
        print(f"- {step}")

    print()
    print("[Warnings]")
    if warnings:
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("No warnings.")

    print()
    print("[Save]")
    if save_enabled:
        print("Save mode enabled. Lightweight summary will be saved.")
    else:
        print("No files saved. Terminal-only diagnosis mode.")


def save_segment_label_summary_if_requested(
    *,
    output_dir: Path | None,
    save: bool,
    save_detail: bool,
    payload: dict[str, Any],
) -> None:
    if not save and not save_detail:
        return

    if output_dir is None:
        raise ValueError("--save 或 --save-detail 需要同时提供 --output-dir")

    output_dir.mkdir(parents=True, exist_ok=True)

    if save:
        summary_path = output_dir / "segment_label_diagnosis_summary.json"
        summary_path.write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print()
        print("[Save]")
        print(f"segment_label_diagnosis_summary.json saved: {summary_path}")

    if save_detail:
        high_fp_rows = [
            row
            for rows in payload["high_fp_segments"].values()
            for row in rows
        ]
        pd.DataFrame(high_fp_rows).to_csv(output_dir / "high_fp_segment_files.csv", index=False)
        pd.DataFrame(high_fp_rows).to_csv(output_dir / "top_fp_segments.csv", index=False)
        pd.DataFrame(payload["common_high_fp_segments"]).to_csv(
            output_dir / "common_high_fp_segments.csv",
            index=False,
        )
        pd.DataFrame(payload["label_continuity"]).to_csv(
            output_dir / "label_continuity_top_fp_segments.csv",
            index=False,
        )
        pd.DataFrame(payload["fp_distance_to_positive"]).to_csv(
            output_dir / "fp_distance_to_nearest_positive.csv",
            index=False,
        )
        pd.DataFrame(payload["future_horizon_overall"]).to_csv(
            output_dir / "future_horizon_label_potential.csv",
            index=False,
        )
        pd.DataFrame(payload["future_horizon_top_segments"]).to_csv(
            output_dir / "future_horizon_top_fp_segments.csv",
            index=False,
        )
        print("detail CSV files saved.")


def run_segment_label_analysis(args: argparse.Namespace) -> dict[str, Any]:
    if args.dataset_dir is None:
        raise ValueError("--stage segment 必须提供 --dataset-dir")

    thresholds = parse_thresholds(args.thresholds, output_dir=args.output_dir)
    horizons = parse_horizons(args.horizon_seconds)

    dataset_inputs = load_stage4_dataset_inputs(args.dataset_dir)

    predictions, prediction_source = load_predictions_for_threshold_analysis(args)

    predictions_with_manifest = build_predictions_with_manifest(
        predictions=predictions,
        thresholds=thresholds,
        window_manifest=dataset_inputs["window_manifest"],
    )

    high_fp_segments = compute_stage4_top_fp_segments(
        predictions_with_manifest=predictions_with_manifest,
        top_k=args.top_k_segments,
    )
    common_segments = compute_common_high_fp_segments(high_fp_segments)
    label_continuity_rows = compute_label_continuity_for_segments(
        predictions_with_manifest=predictions_with_manifest,
        top_fp_segments=high_fp_segments,
    )
    distance_rows = compute_fp_distance_to_positive(
        predictions_with_manifest=predictions_with_manifest,
        top_fp_segments=high_fp_segments,
        horizons=horizons,
    )
    future_overall_rows, future_segment_rows = compute_future_horizon_potential(
        predictions_with_manifest=predictions_with_manifest,
        top_fp_segments=high_fp_segments,
        horizons=horizons,
    )

    global_diagnosis = judge_segment_label_diagnosis(
        top_fp_segments=high_fp_segments,
        common_segments=common_segments,
        distance_rows=distance_rows,
        future_overall_rows=future_overall_rows,
    )

    payload = {
        "task": "stage4_high_fp_segment_label_continuity_diagnosis",
        "dataset_dir": str(args.dataset_dir),
        "prediction_source": prediction_source,
        "thresholds": thresholds,
        "top_k_segments": int(args.top_k_segments),
        "horizons": horizons,
        "high_fp_segments": high_fp_segments,
        "common_high_fp_segments": common_segments,
        "label_continuity": label_continuity_rows,
        "fp_distance_to_positive": distance_rows,
        "future_horizon_overall": future_overall_rows,
        "future_horizon_top_segments": future_segment_rows,
        "global_diagnosis": global_diagnosis,
        "warnings": dataset_inputs["warnings"],
    }

    print_segment_label_diagnosis(
        dataset_dir=Path(args.dataset_dir),
        prediction_source=prediction_source,
        thresholds=thresholds,
        top_k_segments=int(args.top_k_segments),
        horizons=horizons,
        high_fp_segments=high_fp_segments,
        common_segments=common_segments,
        label_continuity_rows=label_continuity_rows,
        distance_rows=distance_rows,
        future_overall_rows=future_overall_rows,
        future_segment_rows=future_segment_rows,
        global_diagnosis=global_diagnosis,
        warnings=dataset_inputs["warnings"],
        save_enabled=bool(args.save or args.save_detail),
    )

    save_segment_label_summary_if_requested(
        output_dir=args.output_dir,
        save=args.save,
        save_detail=args.save_detail,
        payload=payload,
    )

    return payload


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.stage == "threshold":
            run_threshold_analysis(args)
            return 0
        if args.stage == "distribution":
            run_distribution_analysis(args)
            return 0
        if args.stage == "segment":
            run_segment_label_analysis(args)
            return 0
        
        raise ValueError(f"不支持的 stage: {args.stage}")

    except Exception as exc:
        print(f"诊断失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())