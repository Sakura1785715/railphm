#!/usr/bin/env python3
"""
Summarize RailPHM Task 5-3c prediction_horizon comparison results.

This script does NOT build datasets or train models.
It reads h1/h5/h10 condition-augmented datasets and trained Bi-LSTM+Attention runs,
re-infers val/test probabilities, searches best threshold on val only,
evaluates test at threshold=0.5 and best-val-threshold, and writes CSV/JSON/Markdown reports.

Important:
- Do not use test split to select threshold.
- Do not modify labels.
- Do not implement future-horizon interval labels.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models import build_sequence_model
from app.training.metrics import compute_binary_metrics
from app.training.train_sequence_model import resolve_device


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"缺少 JSON 文件: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), ensure_ascii=False, indent=2), encoding="utf-8")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if pd.isna(value) if not isinstance(value, (dict, list, tuple, np.ndarray)) else False:
        return None
    return value


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"输出目录已存在: {output_dir}，如需覆盖请添加 --overwrite")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "predictions").mkdir(parents=True, exist_ok=True)


def validate_required_dataset_files(dataset_dir: Path) -> None:
    required_files = [
        dataset_dir / "X.npy",
        dataset_dir / "y.npy",
        dataset_dir / "feature_columns.json",
        dataset_dir / "window_manifest.csv",
        dataset_dir / "dataset_summary.json",
        dataset_dir / "splits" / "train_indices.npy",
        dataset_dir / "splits" / "val_indices.npy",
        dataset_dir / "splits" / "test_indices.npy",
        dataset_dir / "splits" / "split_summary.json",
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(f"数据集缺少必要文件: {path}")


def validate_required_run_files(run_dir: Path) -> None:
    required_files = [
        run_dir / "best_model.pt",
        run_dir / "sequence_model_report.json",
        run_dir / "training_config.json",
        run_dir / "metrics_history.csv",
        run_dir / "test_predictions.csv",
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(f"训练输出目录缺少必要文件: {path}")


def load_dataset(dataset_dir: Path) -> dict[str, Any]:
    validate_required_dataset_files(dataset_dir)

    X = np.load(dataset_dir / "X.npy", allow_pickle=False)
    y = np.load(dataset_dir / "y.npy", allow_pickle=False)
    train_indices = np.load(dataset_dir / "splits" / "train_indices.npy", allow_pickle=False)
    val_indices = np.load(dataset_dir / "splits" / "val_indices.npy", allow_pickle=False)
    test_indices = np.load(dataset_dir / "splits" / "test_indices.npy", allow_pickle=False)
    feature_columns = load_json(dataset_dir / "feature_columns.json")
    manifest = pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig")
    dataset_summary = load_json(dataset_dir / "dataset_summary.json")
    split_summary = load_json(dataset_dir / "splits" / "split_summary.json")

    if X.ndim != 3:
        raise ValueError(f"X 必须为三维数组，当前 shape={X.shape}")
    if y.ndim != 1:
        raise ValueError(f"y 必须为一维数组，当前 shape={y.shape}")
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"X/y 样本数不一致: X={X.shape[0]}, y={y.shape[0]}")
    if len(manifest) != y.shape[0]:
        raise ValueError(f"manifest 行数与 y 不一致: manifest={len(manifest)}, y={y.shape[0]}")
    if len(feature_columns) != X.shape[2]:
        raise ValueError(f"feature_columns 数量与 X.shape[2] 不一致: columns={len(feature_columns)}, feature_dim={X.shape[2]}")
    if not np.isfinite(X).all():
        raise ValueError("X 中存在 NaN 或 inf")
    if not np.isin(y, [0, 1]).all():
        raise ValueError("y 只能包含 0/1 标签")

    return {
        "X": X,
        "y": y,
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
        "feature_columns": feature_columns,
        "manifest": manifest,
        "dataset_summary": dataset_summary,
        "split_summary": split_summary,
    }


def build_model_from_run(run_dir: Path, input_dim: int, device: torch.device):
    validate_required_run_files(run_dir)

    report = load_json(run_dir / "sequence_model_report.json")
    model_config = report.get("model", {})

    model_name = str(model_config.get("name", "")).lower()
    if "bilstm" not in model_name or "attention" not in model_name:
        raise ValueError(f"当前脚本只用于 Bi-LSTM+Attention，对应 run_dir 模型配置异常: {model_config}")

    hidden_dim = int(model_config.get("hidden_dim", 64))
    num_layers = int(model_config.get("num_layers", 1))
    dropout = float(model_config.get("dropout", 0.2))

    model = build_sequence_model(
        model_name="bilstm_attention",
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        dropout=dropout,
    ).to(device)

    checkpoint = torch.load(run_dir / "best_model.pt", map_location=device)
    if "model_state_dict" not in checkpoint:
        raise ValueError(f"best_model.pt 缺少 model_state_dict: {run_dir / 'best_model.pt'}")

    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    return model, report


def predict_split(
    *,
    model,
    X: np.ndarray,
    y: np.ndarray,
    indices: np.ndarray,
    device: torch.device,
    batch_size: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total = int(indices.shape[0])

    with torch.no_grad():
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_indices = indices[start:end].astype(np.int64, copy=False)

            features = torch.as_tensor(X[batch_indices], dtype=torch.float32, device=device)
            logits = model(features).view(-1)
            probs = torch.sigmoid(logits).detach().cpu().numpy()

            for offset, sample_index in enumerate(batch_indices.tolist()):
                y_true = int(y[sample_index])
                y_prob = float(probs[offset])
                rows.append(
                    {
                        "sample_order": int(start + offset),
                        "sample_index": int(sample_index),
                        "y_true": y_true,
                        "y_prob": y_prob,
                        "y_pred_05": int(y_prob >= 0.5),
                    }
                )

    return pd.DataFrame(rows)


def build_threshold_grid(step: float) -> list[float]:
    if step <= 0 or step >= 1:
        raise ValueError("threshold-step 必须大于 0 且小于 1")

    values = []
    current = step
    while current < 1:
        values.append(round(float(current), 6))
        current += step

    values.append(0.5)
    return sorted(set(v for v in values if 0 < v < 1))


def search_best_threshold_on_val(val_predictions: pd.DataFrame, thresholds: list[float]) -> tuple[float, dict[str, Any]]:
    y_true = val_predictions["y_true"].to_numpy(dtype=np.int64)
    y_prob = val_predictions["y_prob"].to_numpy(dtype=np.float64)

    best_threshold = None
    best_metrics = None
    best_key = None

    for threshold in thresholds:
        metrics = compute_binary_metrics(y_true=y_true, y_prob=y_prob, threshold=float(threshold))
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
        raise RuntimeError("未能搜索到 best threshold")

    return best_threshold, best_metrics


def evaluate_predictions(predictions: pd.DataFrame, threshold: float) -> dict[str, Any]:
    y_true = predictions["y_true"].to_numpy(dtype=np.int64)
    y_prob = predictions["y_prob"].to_numpy(dtype=np.float64)
    metrics = compute_binary_metrics(y_true=y_true, y_prob=y_prob, threshold=float(threshold))
    cm = metrics["confusion_matrix"]

    return {
        "precision": float(metrics["precision"]),
        "recall": float(metrics["recall"]),
        "f1": float(metrics["f1"]),
        "auc": None if metrics["auc"] is None else float(metrics["auc"]),
        "brier": float(metrics["brier_score"]),
        "threshold": float(threshold),
        "tp": int(cm["tp"]),
        "fp": int(cm["fp"]),
        "tn": int(cm["tn"]),
        "fn": int(cm["fn"]),
        "predicted_positive_count": int(metrics["predicted_positive_count"]),
        "predicted_negative_count": int(metrics["predicted_negative_count"]),
    }


def positive_ratio(y: np.ndarray, indices: np.ndarray) -> float:
    if indices.size == 0:
        return 0.0
    return float(y[indices].sum() / indices.shape[0])


def build_dataset_summary_row(horizon: int, dataset_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    X = data["X"]
    y = data["y"]
    train_indices = data["train_indices"]
    val_indices = data["val_indices"]
    test_indices = data["test_indices"]

    positive_count = int(y.sum())
    total_samples = int(y.shape[0])
    negative_count = total_samples - positive_count

    return {
        "prediction_horizon": int(horizon),
        "dataset_dir": str(dataset_dir),
        "X_shape": str([int(v) for v in X.shape]),
        "total_samples": total_samples,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "positive_ratio": float(positive_count / total_samples) if total_samples > 0 else 0.0,
        "train_pos_ratio": positive_ratio(y, train_indices),
        "val_pos_ratio": positive_ratio(y, val_indices),
        "test_pos_ratio": positive_ratio(y, test_indices),
    }


def build_high_fp_rows(
    *,
    horizon: int,
    manifest: pd.DataFrame,
    test_predictions: pd.DataFrame,
    threshold: float,
    top_k: int,
) -> list[dict[str, Any]]:
    pred = test_predictions.copy()
    pred["y_pred"] = (pred["y_prob"].astype(float) >= float(threshold)).astype(int)
    pred["is_fp"] = (pred["y_true"].astype(int) == 0) & (pred["y_pred"] == 1)

    test_sample_indices = pred["sample_index"].to_numpy(dtype=np.int64)
    test_manifest = manifest.iloc[test_sample_indices].copy().reset_index(drop=True)

    if "segment_id" not in test_manifest.columns:
        test_manifest["segment_id"] = ""
    if "segment_file" not in test_manifest.columns:
        test_manifest["segment_file"] = ""

    merged = pd.DataFrame(
        {
            "segment_id": test_manifest["segment_id"].astype(str),
            "segment_file": test_manifest["segment_file"].astype(str),
            "y_true": pred["y_true"].astype(int).to_numpy(),
            "is_fp": pred["is_fp"].astype(bool).to_numpy(),
        }
    )

    grouped = merged.groupby(["segment_id", "segment_file"], dropna=False)
    rows = []

    for (segment_id, segment_file), group in grouped:
        total_samples = int(len(group))
        fp_count = int(group["is_fp"].sum())
        pos_count = int((group["y_true"] == 1).sum())

        if fp_count <= 0:
            continue

        rows.append(
            {
                "prediction_horizon": int(horizon),
                "segment_id": str(segment_id),
                "segment_file": str(segment_file),
                "fp_count": fp_count,
                "fp_ratio": float(fp_count / total_samples) if total_samples > 0 else 0.0,
                "pos_count": pos_count,
                "pos_ratio": float(pos_count / total_samples) if total_samples > 0 else 0.0,
                "total_samples": total_samples,
                "threshold_used": float(threshold),
            }
        )

    rows.sort(key=lambda item: (item["fp_count"], item["fp_ratio"]), reverse=True)
    return rows[:top_k]


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in rows:
        lines.append("| " + " | ".join(format_markdown_value(v) for v in row) + " |")

    return "\n".join(lines)


def format_markdown_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_markdown_report(
    *,
    dataset_rows: list[dict[str, Any]],
    metrics_05_rows: list[dict[str, Any]],
    metrics_best_rows: list[dict[str, Any]],
    high_fp_rows: list[dict[str, Any]],
    judgement: dict[str, Any],
) -> str:
    lines = [
        "# RailPHM Task 5-3c prediction_horizon 对照实验报告",
        "",
        "## 1. 实验说明",
        "",
        "本实验固定 window_size=30、stride=1、模型为 Bi-LSTM+Attention，只比较 prediction_horizon=1/5/10 对故障风险预测效果的影响。标签仍然只看窗口结束后第 H 个目标时刻的“报警部位”是否非空，不使用 future-horizon 区间标签。",
        "",
        "## 2. 数据集与标签分布",
        "",
    ]

    lines.append(
        markdown_table(
            [
                "Prediction Horizon",
                "X Shape",
                "Total Samples",
                "Positive Count",
                "Negative Count",
                "Positive Ratio",
                "Train Pos Ratio",
                "Val Pos Ratio",
                "Test Pos Ratio",
            ],
            [
                [
                    row["prediction_horizon"],
                    row["X_shape"],
                    row["total_samples"],
                    row["positive_count"],
                    row["negative_count"],
                    row["positive_ratio"],
                    row["train_pos_ratio"],
                    row["val_pos_ratio"],
                    row["test_pos_ratio"],
                ]
                for row in dataset_rows
            ],
        )
    )

    lines.extend(["", "## 3. 默认阈值 0.5 测试集结果", ""])

    lines.append(
        markdown_table(
            ["Prediction Horizon", "Precision@0.5", "Recall@0.5", "F1@0.5", "AUC", "Brier", "TP", "FP", "TN", "FN"],
            [
                [
                    row["prediction_horizon"],
                    row["precision_05"],
                    row["recall_05"],
                    row["f1_05"],
                    row["auc"],
                    row["brier"],
                    row["tp"],
                    row["fp"],
                    row["tn"],
                    row["fn"],
                ]
                for row in metrics_05_rows
            ],
        )
    )

    lines.extend(["", "## 4. 验证集最佳阈值固定到测试集后的结果", ""])

    lines.append(
        markdown_table(
            ["Prediction Horizon", "Best Val Threshold", "Precision@Best", "Recall@Best", "F1@Best", "AUC", "Brier", "TP", "FP", "TN", "FN"],
            [
                [
                    row["prediction_horizon"],
                    row["best_val_threshold"],
                    row["precision_best"],
                    row["recall_best"],
                    row["f1_best"],
                    row["auc"],
                    row["brier"],
                    row["tp"],
                    row["fp"],
                    row["tn"],
                    row["fn"],
                ]
                for row in metrics_best_rows
            ],
        )
    )

    lines.extend(["", "## 5. 高误报 segment 对比", ""])

    lines.append(
        markdown_table(
            ["Prediction Horizon", "Segment ID", "Segment File", "FP Count", "FP Ratio", "Pos Count", "Pos Ratio", "Total Samples", "Overlap With H1"],
            [
                [
                    row["prediction_horizon"],
                    row["segment_id"],
                    row["segment_file"],
                    row["fp_count"],
                    row["fp_ratio"],
                    row["pos_count"],
                    row["pos_ratio"],
                    row["total_samples"],
                    row.get("overlap_with_h1", ""),
                ]
                for row in high_fp_rows
            ],
        )
    )

    lines.extend(["", "## 6. 自动初步判断", ""])

    lines.append(f"- 综合最优 horizon：**h{judgement['best_horizon']}**")
    lines.append(f"- 判断等级：{judgement['level']}")
    lines.append("")
    lines.append("主要依据：")
    for reason in judgement["reasons"]:
        lines.append(f"- {reason}")

    if judgement["risks"]:
        lines.append("")
        lines.append("风险提示：")
        for risk in judgement["risks"]:
            lines.append(f"- {risk}")

    lines.append("")
    lines.append("后续建议：")
    for step in judgement["next_steps"]:
        lines.append(f"- {step}")

    lines.append("")
    return "\n".join(lines)


def judge_horizon_results(metrics_best_rows: list[dict[str, Any]], high_fp_rows: list[dict[str, Any]]) -> dict[str, Any]:
    # 以 best threshold 下的 test 表现作为主判断，同时关注 precision、F1、AUC、Brier。
    scored = []
    for row in metrics_best_rows:
        precision = float(row["precision_best"])
        recall = float(row["recall_best"])
        f1 = float(row["f1_best"])
        auc = float(row["auc"]) if row["auc"] is not None else 0.0
        brier = float(row["brier"])

        score = (
            f1 * 0.35
            + precision * 0.25
            + recall * 0.15
            + auc * 0.20
            - brier * 0.05
        )

        scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    best_row = scored[0][1]
    best_horizon = int(best_row["prediction_horizon"])

    h1_row = next((row for row in metrics_best_rows if int(row["prediction_horizon"]) == 1), None)
    reasons = []
    risks = []
    next_steps = []

    reasons.append(
        f"h{best_horizon} 在综合评分中最高，best-threshold 下 Precision={best_row['precision_best']:.4f}、Recall={best_row['recall_best']:.4f}、F1={best_row['f1_best']:.4f}、AUC={best_row['auc']:.4f}、Brier={best_row['brier']:.4f}。"
    )

    if h1_row is not None and best_horizon != 1:
        precision_delta = float(best_row["precision_best"]) - float(h1_row["precision_best"])
        recall_delta = float(best_row["recall_best"]) - float(h1_row["recall_best"])
        f1_delta = float(best_row["f1_best"]) - float(h1_row["f1_best"])

        reasons.append(
            f"相对 h1，h{best_horizon} 的 Precision 变化为 {precision_delta:+.4f}，Recall 变化为 {recall_delta:+.4f}，F1 变化为 {f1_delta:+.4f}。"
        )

        if precision_delta > 0.03 and recall_delta > -0.08:
            level = "horizon_improved"
            next_steps.append(f"可以优先考虑将 h{best_horizon} 作为论文实验候选口径，但仍需结合高 FP segment 变化确认。")
        elif precision_delta > 0.03 and recall_delta <= -0.08:
            level = "precision_tradeoff"
            risks.append("Precision 提升伴随 Recall 明显下降，可能只是少报风险换来误报减少，不宜直接判定更优。")
            next_steps.append("建议保留 h1 作为稳健口径，同时在论文中把 h5/h10 作为对照实验说明。")
        else:
            level = "weak_difference"
            next_steps.append("horizon 差异不强，建议优先保持 h1，并将 h5/h10 作为排查实验记录。")
    else:
        level = "h1_best_or_stable"
        next_steps.append("若 h1 综合最优，论文继续保持 prediction_horizon=1 更稳。")

    if float(best_row["precision_best"]) < 0.45:
        risks.append("最优 horizon 的 Precision 仍低于 0.45，说明误报问题仍未彻底解决。")

    if float(best_row["best_val_threshold"]) < 0.4:
        risks.append("best_val_threshold 明显低于 0.5，说明默认阈值偏保守的问题仍然存在。")

    h1_segments = {
        row["segment_id"]
        for row in high_fp_rows
        if int(row["prediction_horizon"]) == 1
    }
    best_segments = {
        row["segment_id"]
        for row in high_fp_rows
        if int(row["prediction_horizon"]) == best_horizon
    }
    if best_horizon != 1 and h1_segments:
        overlap = len(h1_segments.intersection(best_segments))
        reasons.append(f"h{best_horizon} 的高 FP segment 与 h1 top FP segment 重合数量为 {overlap}。")
        if overlap >= min(5, len(h1_segments)):
            risks.append("高 FP segment 仍与 h1 高度重合，说明 prediction_horizon 可能不是误报主因。")

    next_steps.append("不要改成 future-horizon 区间标签；后续如需继续优化，应考虑概率校准、高 FP segment 人工复核或样本权重策略。")

    return {
        "best_horizon": best_horizon,
        "level": level,
        "reasons": reasons,
        "risks": risks,
        "next_steps": next_steps,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize RailPHM Task 5-3c prediction_horizon results.")
    parser.add_argument("--horizons", nargs="+", type=int, default=[1, 5, 10])
    parser.add_argument(
        "--dataset-template",
        type=str,
        default="data/datasets/sim_window_w30_s1_h{H}_train_scaled_condition_k3",
    )
    parser.add_argument(
        "--run-template",
        type=str,
        default="outputs/sequence_bilstm_attention_sim_window_w30_s1_h{H}_condition_k3_e30",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports/task_5_3c"))
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument("--top-k-segments", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    prepare_output_dir(args.output_dir, overwrite=args.overwrite)
    device = resolve_device(args.device)
    thresholds = build_threshold_grid(args.threshold_step)

    dataset_rows: list[dict[str, Any]] = []
    metrics_05_rows: list[dict[str, Any]] = []
    metrics_best_rows: list[dict[str, Any]] = []
    high_fp_rows: list[dict[str, Any]] = []
    all_summary: dict[str, Any] = {
        "task": "task_5_3c_prediction_horizon_comparison",
        "horizons": args.horizons,
        "device": str(device),
        "threshold_step": args.threshold_step,
        "results": {},
    }

    for horizon in args.horizons:
        print("=" * 72)
        print(f"[H={horizon}] Loading dataset and run artifacts")
        print("=" * 72)

        dataset_dir = Path(args.dataset_template.format(H=horizon))
        run_dir = Path(args.run_template.format(H=horizon))

        data = load_dataset(dataset_dir)
        model, report = build_model_from_run(run_dir=run_dir, input_dim=int(data["X"].shape[2]), device=device)

        print(f"[H={horizon}] Predicting val split...")
        val_predictions = predict_split(
            model=model,
            X=data["X"],
            y=data["y"],
            indices=data["val_indices"],
            device=device,
            batch_size=args.batch_size,
        )

        print(f"[H={horizon}] Predicting test split...")
        test_predictions = predict_split(
            model=model,
            X=data["X"],
            y=data["y"],
            indices=data["test_indices"],
            device=device,
            batch_size=args.batch_size,
        )

        pred_dir = args.output_dir / "predictions"
        val_pred_path = pred_dir / f"h{horizon}_val_predictions.csv"
        test_pred_path = pred_dir / f"h{horizon}_test_predictions.csv"
        val_predictions.to_csv(val_pred_path, index=False)
        test_predictions.to_csv(test_pred_path, index=False)

        print(f"[H={horizon}] Searching best threshold on val only...")
        best_threshold, best_val_metrics = search_best_threshold_on_val(val_predictions, thresholds)

        test_05 = evaluate_predictions(test_predictions, threshold=0.5)
        test_best = evaluate_predictions(test_predictions, threshold=best_threshold)

        dataset_row = build_dataset_summary_row(horizon, dataset_dir, data)
        dataset_rows.append(dataset_row)

        metrics_05_rows.append(
            {
                "prediction_horizon": int(horizon),
                "precision_05": test_05["precision"],
                "recall_05": test_05["recall"],
                "f1_05": test_05["f1"],
                "auc": test_05["auc"],
                "brier": test_05["brier"],
                "tp": test_05["tp"],
                "fp": test_05["fp"],
                "tn": test_05["tn"],
                "fn": test_05["fn"],
            }
        )

        metrics_best_rows.append(
            {
                "prediction_horizon": int(horizon),
                "best_val_threshold": float(best_threshold),
                "val_precision_at_best": float(best_val_metrics["precision"]),
                "val_recall_at_best": float(best_val_metrics["recall"]),
                "val_f1_at_best": float(best_val_metrics["f1"]),
                "precision_best": test_best["precision"],
                "recall_best": test_best["recall"],
                "f1_best": test_best["f1"],
                "auc": test_best["auc"],
                "brier": test_best["brier"],
                "tp": test_best["tp"],
                "fp": test_best["fp"],
                "tn": test_best["tn"],
                "fn": test_best["fn"],
            }
        )

        fp_rows = build_high_fp_rows(
            horizon=horizon,
            manifest=data["manifest"],
            test_predictions=test_predictions,
            threshold=best_threshold,
            top_k=args.top_k_segments,
        )
        high_fp_rows.extend(fp_rows)

        all_summary["results"][f"h{horizon}"] = {
            "dataset_dir": str(dataset_dir),
            "run_dir": str(run_dir),
            "dataset": dataset_row,
            "best_val_threshold": float(best_threshold),
            "best_val_metrics": best_val_metrics,
            "test_metrics_05": test_05,
            "test_metrics_best": test_best,
            "prediction_files": {
                "val": str(val_pred_path),
                "test": str(test_pred_path),
            },
            "model_report": report,
        }

    h1_segments = {
        row["segment_id"]
        for row in high_fp_rows
        if int(row["prediction_horizon"]) == 1
    }
    for row in high_fp_rows:
        row["overlap_with_h1"] = bool(row["segment_id"] in h1_segments) if int(row["prediction_horizon"]) != 1 else True

    judgement = judge_horizon_results(metrics_best_rows, high_fp_rows)
    all_summary["judgement"] = judgement

    dataset_df = pd.DataFrame(dataset_rows)
    metrics_05_df = pd.DataFrame(metrics_05_rows)
    metrics_best_df = pd.DataFrame(metrics_best_rows)
    high_fp_df = pd.DataFrame(high_fp_rows)

    dataset_df.to_csv(args.output_dir / "prediction_horizon_dataset_summary.csv", index=False)
    metrics_05_df.to_csv(args.output_dir / "prediction_horizon_metrics_threshold_0_5.csv", index=False)
    metrics_best_df.to_csv(args.output_dir / "prediction_horizon_metrics_best_threshold.csv", index=False)
    high_fp_df.to_csv(args.output_dir / "prediction_horizon_high_fp_segments.csv", index=False)
    save_json(args.output_dir / "prediction_horizon_summary.json", all_summary)

    markdown = render_markdown_report(
        dataset_rows=dataset_rows,
        metrics_05_rows=metrics_05_rows,
        metrics_best_rows=metrics_best_rows,
        high_fp_rows=high_fp_rows,
        judgement=judgement,
    )
    (args.output_dir / "prediction_horizon_comparison_report.md").write_text(markdown, encoding="utf-8")

    print()
    print("=" * 72)
    print("Task 5-3c summary generated.")
    print("=" * 72)
    print(f"- {args.output_dir / 'prediction_horizon_dataset_summary.csv'}")
    print(f"- {args.output_dir / 'prediction_horizon_metrics_threshold_0_5.csv'}")
    print(f"- {args.output_dir / 'prediction_horizon_metrics_best_threshold.csv'}")
    print(f"- {args.output_dir / 'prediction_horizon_high_fp_segments.csv'}")
    print(f"- {args.output_dir / 'prediction_horizon_summary.json'}")
    print(f"- {args.output_dir / 'prediction_horizon_comparison_report.md'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())