#!/usr/bin/env python3
"""
Task 5-3d terminal-only feature ablation diagnosis.

This script:
- reads three feature-profile datasets and trained Bi-LSTM+Attention runs;
- re-infers val/test probabilities;
- searches best threshold on val only;
- evaluates test at threshold=0.5 and best-val-threshold;
- prints all results to terminal.

It does NOT write Markdown / CSV / JSON / PNG reports.
"""

from __future__ import annotations

import argparse
import json
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


DEFAULT_PROFILES = [
    "full_features",
    "remove_id_like_features",
    "continuous_only_features",
]


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"缺少 JSON 文件: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"缺少必要文件: {path}")


def parse_mapping(values: list[str] | None) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not values:
        return result

    for item in values:
        if "=" not in item:
            raise ValueError(f"映射参数必须是 name=path 格式，当前: {item}")
        name, raw_path = item.split("=", 1)
        name = name.strip()
        raw_path = raw_path.strip()
        if not name or not raw_path:
            raise ValueError(f"映射参数非法: {item}")
        result[name] = Path(raw_path)

    return result


def default_dataset_dir(profile: str) -> Path:
    return Path(f"data/datasets/sim_window_w30_s1_h1_{profile}_train_scaled_condition_k3")


def default_run_dir(profile: str) -> Path:
    return Path(f"outputs/sequence_models/bilstm_attention_h1_{profile}")


def load_dataset(dataset_dir: Path) -> dict[str, Any]:
    required = [
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
    for path in required:
        require_file(path)

    X = np.load(dataset_dir / "X.npy", allow_pickle=False)
    y = np.load(dataset_dir / "y.npy", allow_pickle=False)
    train_indices = np.load(dataset_dir / "splits" / "train_indices.npy", allow_pickle=False)
    val_indices = np.load(dataset_dir / "splits" / "val_indices.npy", allow_pickle=False)
    test_indices = np.load(dataset_dir / "splits" / "test_indices.npy", allow_pickle=False)
    feature_columns = load_json(dataset_dir / "feature_columns.json")
    dataset_summary = load_json(dataset_dir / "dataset_summary.json")
    split_summary = load_json(dataset_dir / "splits" / "split_summary.json")
    manifest = pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig")

    if X.ndim != 3:
        raise ValueError(f"X 必须为三维数组，当前 shape={X.shape}")
    if y.ndim != 1:
        raise ValueError(f"y 必须为一维数组，当前 shape={y.shape}")
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"X/y 样本数不一致: X={X.shape[0]}, y={y.shape[0]}")
    if len(feature_columns) != X.shape[2]:
        raise ValueError(f"feature_columns 数量与 X.shape[2] 不一致: {len(feature_columns)} vs {X.shape[2]}")
    if len(manifest) != y.shape[0]:
        raise ValueError(f"manifest 行数与 y 不一致: manifest={len(manifest)}, y={y.shape[0]}")
    if not np.isfinite(X).all():
        raise ValueError("X 存在 NaN 或 inf")
    if not np.isin(y, [0, 1]).all():
        raise ValueError("y 只能包含 0/1 标签")

    return {
        "X": X,
        "y": y,
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
        "feature_columns": feature_columns,
        "dataset_summary": dataset_summary,
        "split_summary": split_summary,
        "manifest": manifest,
    }


def load_model(run_dir: Path, input_dim: int, device: torch.device):
    required = [
        run_dir / "best_model.pt",
        run_dir / "sequence_model_report.json",
        run_dir / "training_config.json",
        run_dir / "metrics_history.csv",
        run_dir / "test_predictions.csv",
    ]
    for path in required:
        require_file(path)

    report = load_json(run_dir / "sequence_model_report.json")
    model_config = report.get("model", {})

    model = build_sequence_model(
        model_name="bilstm_attention",
        input_dim=input_dim,
        hidden_dim=int(model_config.get("hidden_dim", 64)),
        num_layers=int(model_config.get("num_layers", 1)),
        dropout=float(model_config.get("dropout", 0.2)),
    ).to(device)

    checkpoint = torch.load(run_dir / "best_model.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    return model, report


def predict_split(model, X: np.ndarray, y: np.ndarray, indices: np.ndarray, device: torch.device, batch_size: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    with torch.no_grad():
        for start in range(0, int(indices.shape[0]), batch_size):
            end = min(start + batch_size, int(indices.shape[0]))
            batch_indices = indices[start:end].astype(np.int64, copy=False)
            features = torch.as_tensor(X[batch_indices], dtype=torch.float32, device=device)

            logits = model(features).view(-1)
            probs = torch.sigmoid(logits).detach().cpu().numpy()

            for offset, sample_index in enumerate(batch_indices.tolist()):
                y_prob = float(probs[offset])
                rows.append(
                    {
                        "sample_order": int(start + offset),
                        "sample_index": int(sample_index),
                        "y_true": int(y[sample_index]),
                        "y_prob": y_prob,
                        "y_pred_05": int(y_prob >= 0.5),
                    }
                )

    return pd.DataFrame(rows)


def build_threshold_grid(step: float) -> list[float]:
    if step <= 0 or step >= 1:
        raise ValueError("threshold-step 必须位于 0 和 1 之间")

    thresholds = []
    current = float(step)
    while current < 1:
        thresholds.append(round(current, 6))
        current += float(step)
    thresholds.append(0.5)
    return sorted(set(v for v in thresholds if 0 < v < 1))


def search_best_threshold_on_val(val_predictions: pd.DataFrame, thresholds: list[float]) -> tuple[float, dict[str, Any]]:
    y_true = val_predictions["y_true"].to_numpy(dtype=np.int64)
    y_prob = val_predictions["y_prob"].to_numpy(dtype=np.float64)

    best_threshold = None
    best_metrics = None
    best_key = None

    for threshold in thresholds:
        metrics = compute_binary_metrics(y_true=y_true, y_prob=y_prob, threshold=float(threshold))
        key = (
            float(metrics["f1"]),
            float(metrics["recall"]),
            -abs(float(threshold) - 0.5),
            -float(threshold),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_threshold = float(threshold)
            best_metrics = metrics

    if best_threshold is None or best_metrics is None:
        raise RuntimeError("未能搜索到 best threshold")

    return best_threshold, best_metrics


def evaluate(predictions: pd.DataFrame, threshold: float) -> dict[str, Any]:
    y_true = predictions["y_true"].to_numpy(dtype=np.int64)
    y_prob = predictions["y_prob"].to_numpy(dtype=np.float64)

    metrics = compute_binary_metrics(y_true=y_true, y_prob=y_prob, threshold=float(threshold))
    cm = metrics["confusion_matrix"]

    return {
        "threshold": float(threshold),
        "precision": float(metrics["precision"]),
        "recall": float(metrics["recall"]),
        "f1": float(metrics["f1"]),
        "auc": None if metrics["auc"] is None else float(metrics["auc"]),
        "brier": float(metrics["brier_score"]),
        "tp": int(cm["tp"]),
        "fp": int(cm["fp"]),
        "tn": int(cm["tn"]),
        "fn": int(cm["fn"]),
    }


def pos_ratio(y: np.ndarray, indices: np.ndarray) -> float:
    if indices.size == 0:
        return 0.0
    return float(y[indices].sum() / indices.shape[0])


def high_fp_rows(profile: str, manifest: pd.DataFrame, predictions: pd.DataFrame, threshold: float, top_k: int) -> list[dict[str, Any]]:
    pred = predictions.copy()
    pred["y_pred"] = (pred["y_prob"].astype(float) >= float(threshold)).astype(int)
    pred["is_fp"] = (pred["y_true"].astype(int) == 0) & (pred["y_pred"] == 1)

    sample_indices = pred["sample_index"].to_numpy(dtype=np.int64)
    test_manifest = manifest.iloc[sample_indices].copy().reset_index(drop=True)

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

    rows = []
    grouped = merged.groupby(["segment_id", "segment_file"], dropna=False)
    for (segment_id, segment_file), group in grouped:
        total = int(len(group))
        fp_count = int(group["is_fp"].sum())
        if fp_count <= 0:
            continue
        pos_count = int((group["y_true"] == 1).sum())

        rows.append(
            {
                "feature_profile": profile,
                "segment_id": str(segment_id),
                "segment_file": str(segment_file),
                "fp_count": fp_count,
                "fp_ratio": float(fp_count / total) if total else 0.0,
                "pos_count": pos_count,
                "pos_ratio": float(pos_count / total) if total else 0.0,
                "total_samples": total,
            }
        )

    rows.sort(key=lambda row: (row["fp_count"], row["fp_ratio"]), reverse=True)
    return rows[:top_k]


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def print_table(title: str, headers: list[str], rows: list[list[Any]]) -> None:
    print()
    print(title)
    print("-" * 120)
    print(" | ".join(headers))
    print("-" * 120)
    for row in rows:
        print(" | ".join(fmt(item) for item in row))


def print_feature_columns(profile: str, feature_columns: list[str]) -> None:
    print()
    print(f"[{profile}] actual feature columns ({len(feature_columns)}):")
    for column in feature_columns:
        print(f"- {column}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Print terminal-only Task 5-3d feature ablation diagnosis.")
    parser.add_argument("--profiles", nargs="+", default=DEFAULT_PROFILES)
    parser.add_argument("--dataset-dirs", nargs="*", default=None, help="name=path mappings")
    parser.add_argument("--model-output-dirs", nargs="*", default=None, help="name=path mappings")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument("--default-threshold", type=float, default=0.5)
    parser.add_argument("--top-fp", type=int, default=10)
    args = parser.parse_args()

    dataset_map = parse_mapping(args.dataset_dirs)
    run_map = parse_mapping(args.model_output_dirs)

    device = resolve_device(args.device)
    thresholds = build_threshold_grid(args.threshold_step)

    dataset_table = []
    metrics_05_table = []
    metrics_best_table = []
    delta_table = []
    all_high_fp_rows = []
    results = {}

    print()
    print("=" * 120)
    print("RailPHM Task 5-3d Feature Ablation Diagnosis")
    print("=" * 120)
    print("Fixed: window_size=30, stride=1, prediction_horizon=1, model=Bi-LSTM+Attention")
    print("Threshold selection: val only")
    print("Output mode: terminal only, no reports generated")

    for profile in args.profiles:
        dataset_dir = dataset_map.get(profile, default_dataset_dir(profile))
        run_dir = run_map.get(profile, default_run_dir(profile))

        print()
        print("=" * 120)
        print(f"[{profile}] Loading dataset and model")
        print(f"dataset_dir: {dataset_dir}")
        print(f"run_dir: {run_dir}")
        print("=" * 120)

        data = load_dataset(dataset_dir)
        model, report = load_model(run_dir, input_dim=int(data["X"].shape[2]), device=device)

        print_feature_columns(profile, data["feature_columns"])

        print(f"[{profile}] Predicting val split...")
        val_pred = predict_split(
            model=model,
            X=data["X"],
            y=data["y"],
            indices=data["val_indices"],
            device=device,
            batch_size=args.batch_size,
        )

        print(f"[{profile}] Predicting test split...")
        test_pred = predict_split(
            model=model,
            X=data["X"],
            y=data["y"],
            indices=data["test_indices"],
            device=device,
            batch_size=args.batch_size,
        )

        best_threshold, best_val_metrics = search_best_threshold_on_val(val_pred, thresholds)
        test_05 = evaluate(test_pred, threshold=args.default_threshold)
        test_best = evaluate(test_pred, threshold=best_threshold)

        y = data["y"]
        total_samples = int(y.shape[0])
        positive_count = int(y.sum())
        negative_count = total_samples - positive_count

        dataset_table.append(
            [
                profile,
                int(data["X"].shape[2]),
                ", ".join(data["feature_columns"]),
                str([int(v) for v in data["X"].shape]),
                total_samples,
                positive_count,
                negative_count,
                positive_count / total_samples if total_samples else 0.0,
                pos_ratio(y, data["train_indices"]),
                pos_ratio(y, data["val_indices"]),
                pos_ratio(y, data["test_indices"]),
            ]
        )

        metrics_05_table.append(
            [
                profile,
                test_05["precision"],
                test_05["recall"],
                test_05["f1"],
                test_05["auc"],
                test_05["brier"],
                test_05["tp"],
                test_05["fp"],
                test_05["tn"],
                test_05["fn"],
            ]
        )

        metrics_best_table.append(
            [
                profile,
                best_threshold,
                test_best["precision"],
                test_best["recall"],
                test_best["f1"],
                test_best["auc"],
                test_best["brier"],
                test_best["tp"],
                test_best["fp"],
                test_best["tn"],
                test_best["fn"],
            ]
        )

        fp_rows = high_fp_rows(
            profile=profile,
            manifest=data["manifest"],
            predictions=test_pred,
            threshold=best_threshold,
            top_k=args.top_fp,
        )
        all_high_fp_rows.extend(fp_rows)

        results[profile] = {
            "dataset": data,
            "best_threshold": best_threshold,
            "best_val_metrics": best_val_metrics,
            "test_05": test_05,
            "test_best": test_best,
            "high_fp_rows": fp_rows,
        }

        print()
        print(f"[{profile}] val best threshold:")
        print(f"- best_val_threshold: {best_threshold:.4f}")
        print(f"- val_precision@best: {float(best_val_metrics['precision']):.4f}")
        print(f"- val_recall@best   : {float(best_val_metrics['recall']):.4f}")
        print(f"- val_f1@best       : {float(best_val_metrics['f1']):.4f}")
        print(f"- val_auc           : {fmt(best_val_metrics['auc'])}")
        print(f"- val_brier         : {float(best_val_metrics['brier_score']):.4f}")

    full_result = results.get("full_features")
    full_high_fp_segments = set()
    if full_result:
        full_high_fp_segments = {row["segment_id"] for row in full_result["high_fp_rows"]}

    high_fp_table = []
    for row in all_high_fp_rows:
        overlap = row["segment_id"] in full_high_fp_segments
        high_fp_table.append(
            [
                row["feature_profile"],
                row["segment_id"],
                row["segment_file"],
                row["fp_count"],
                row["fp_ratio"],
                row["pos_count"],
                row["pos_ratio"],
                row["total_samples"],
                overlap,
            ]
        )

    if full_result:
        full_best = full_result["test_best"]
        full_fp = full_best["fp"]
        full_tp = full_best["tp"]
        full_segments = full_high_fp_segments

        for profile, result in results.items():
            if profile == "full_features":
                continue

            best = result["test_best"]
            profile_segments = {row["segment_id"] for row in result["high_fp_rows"]}
            overlap_count = len(full_segments.intersection(profile_segments))

            delta_table.append(
                [
                    profile,
                    best["precision"] - full_best["precision"],
                    best["recall"] - full_best["recall"],
                    best["f1"] - full_best["f1"],
                    (best["auc"] or 0.0) - (full_best["auc"] or 0.0),
                    best["brier"] - full_best["brier"],
                    best["fp"] - full_fp,
                    best["tp"] - full_tp,
                    overlap_count,
                ]
            )

    print_table(
        "表 1：特征配置与数据集分布",
        [
            "Feature Profile",
            "Feature Dim",
            "Feature Columns",
            "X Shape",
            "Total Samples",
            "Positive Count",
            "Negative Count",
            "Positive Ratio",
            "Train Pos Ratio",
            "Val Pos Ratio",
            "Test Pos Ratio",
        ],
        dataset_table,
    )

    print_table(
        "表 2：默认阈值 0.5 测试集结果",
        [
            "Feature Profile",
            "Precision@0.5",
            "Recall@0.5",
            "F1@0.5",
            "AUC",
            "Brier",
            "TP",
            "FP",
            "TN",
            "FN",
        ],
        metrics_05_table,
    )

    print_table(
        "表 3：验证集最佳阈值固定到测试集后的结果",
        [
            "Feature Profile",
            "Best Val Threshold",
            "Precision@Best",
            "Recall@Best",
            "F1@Best",
            "AUC",
            "Brier",
            "TP",
            "FP",
            "TN",
            "FN",
        ],
        metrics_best_table,
    )

    print_table(
        "表 4：高误报 segment Top N",
        [
            "Feature Profile",
            "Segment ID",
            "Segment File",
            "FP Count",
            "FP Ratio",
            "Pos Count",
            "Pos Ratio",
            "Total Samples",
            "Overlap With Full",
        ],
        high_fp_table,
    )

    print_table(
        "表 5：与 full_features 的变化量",
        [
            "Feature Profile",
            "ΔPrecision@Best",
            "ΔRecall@Best",
            "ΔF1@Best",
            "ΔAUC",
            "ΔBrier",
            "ΔFP",
            "ΔTP",
            "High FP Overlap Count",
        ],
        delta_table,
    )

    print()
    print("=" * 120)
    print("自动初步判断")
    print("=" * 120)

    if "remove_id_like_features" in results and full_result:
        full_best = full_result["test_best"]
        remove_best = results["remove_id_like_features"]["test_best"]

        precision_delta = remove_best["precision"] - full_best["precision"]
        fp_delta = remove_best["fp"] - full_best["fp"]
        auc_delta = (remove_best["auc"] or 0.0) - (full_best["auc"] or 0.0)
        brier_delta = remove_best["brier"] - full_best["brier"]

        print(f"remove_id_like_features 相对 full_features:")
        print(f"- ΔPrecision@Best: {precision_delta:+.4f}")
        print(f"- ΔFP            : {fp_delta:+d}")
        print(f"- ΔAUC           : {auc_delta:+.4f}")
        print(f"- ΔBrier         : {brier_delta:+.4f}")

        if precision_delta > 0.02 and fp_delta < 0 and auc_delta > -0.02 and brier_delta < 0.02:
            print()
            print("结论倾向：编号类 / ID 类字段可能是高误报的重要来源。去除后 Precision 提升、FP 减少，且 AUC/Brier 未明显恶化。")
        elif precision_delta <= 0 and fp_delta >= 0:
            print()
            print("结论倾向：ID 类字段不是当前误报主因。去除后 Precision 没提升、FP 没减少，应继续排查标签单点口径、报警邻近性或 segment 整体状态相似问题。")
        elif auc_delta < -0.03:
            print()
            print("结论倾向：ID / 业务字段虽然可能带来误报风险，但也贡献了有效排序信息；不宜简单删除所有编号字段，应考虑更合理编码。")
        else:
            print()
            print("结论倾向：三组差异不够强，暂不能认定 ID 类字段是误报主因。建议继续做概率校准、高 FP 人工复核或样本权重策略。")

    if "continuous_only_features" in results and full_result:
        full_best = full_result["test_best"]
        continuous_best = results["continuous_only_features"]["test_best"]

        print()
        print("continuous_only_features 可用性观察:")
        print(f"- Precision@Best: {continuous_best['precision']:.4f}")
        print(f"- Recall@Best   : {continuous_best['recall']:.4f}")
        print(f"- F1@Best       : {continuous_best['f1']:.4f}")
        print(f"- AUC           : {fmt(continuous_best['auc'])}")
        print(f"- Brier         : {continuous_best['brier']:.4f}")

        auc_delta = (continuous_best["auc"] or 0.0) - (full_best["auc"] or 0.0)
        recall_delta = continuous_best["recall"] - full_best["recall"]

        if auc_delta < -0.03 or recall_delta < -0.10:
            print("结论倾向：仅依赖连续物理量会损失较多识别能力，说明业务字段仍含有效信息。")
        else:
            print("结论倾向：连续物理量仍具备一定识别能力，可作为更稳健输入方案的候选。")

    print()
    print("注意：本脚本只做终端输出，不生成 reports / csv / json / md / png。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())