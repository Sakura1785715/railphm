#!/usr/bin/env python3
"""
工况增强 baseline 对比分析脚本。

该脚本读取原始 MLP baseline 与加入工况 one-hot 后的 MLP baseline 训练结果，
对比总体指标、训练曲线、预测分布和不同工况下的测试集表现，并生成 JSON 与 Markdown 报告。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.training.metrics import compute_binary_metrics


REQUIRED_RUN_FILES = [
    "baseline_report.json",
    "metrics_history.csv",
    "test_predictions.csv",
]

REQUIRED_DATASET_FILES = [
    "X.npy",
    "y.npy",
    "feature_columns.json",
]

REQUIRED_SPLIT_FILES = [
    "train_indices.npy",
    "val_indices.npy",
    "test_indices.npy",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare original baseline and condition one-hot augmented baseline."
    )

    parser.add_argument("--baseline-a", type=Path, required=True, help="原始 baseline 输出目录")
    parser.add_argument("--baseline-b", type=Path, required=True, help="加入工况 one-hot 后的 baseline 输出目录")
    parser.add_argument("--dataset-a", type=Path, required=True, help="原始数据集目录")
    parser.add_argument("--dataset-b", type=Path, required=True, help="增强数据集目录")
    parser.add_argument("--condition-summary", type=Path, default=None, help="condition_summary.json 路径")
    parser.add_argument("--condition-labels", type=Path, default=None, help="condition_labels.npy 路径")
    parser.add_argument("--output-dir", type=Path, required=True, help="对比报告输出目录")
    parser.add_argument("--auc-delta-threshold", type=float, default=0.02, help="AUC 明显提升阈值")
    parser.add_argument("--f1-delta-threshold", type=float, default=0.02, help="F1 明显提升阈值")
    parser.add_argument("--brier-delta-threshold", type=float, default=0.01, help="Brier Score 明显改善阈值")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出目录")
    parser.add_argument("--verbose", action="store_true", help="打印更详细的对比结果")

    return parser


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"output_dir 已存在: {output_dir}，如需覆盖请使用 --overwrite")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)


def resolve_condition_file(
    explicit_path: Path | None,
    dataset_a: Path,
    dataset_b: Path,
    filename: str,
) -> Path:
    if explicit_path is not None:
        return explicit_path

    dataset_b_path = dataset_b / filename
    if dataset_b_path.exists():
        return dataset_b_path

    dataset_a_path = dataset_a / filename
    if dataset_a_path.exists():
        return dataset_a_path

    return dataset_b_path


def validate_run_dir(run_dir: Path) -> None:
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"baseline 输出目录不存在: {run_dir}")

    for filename in REQUIRED_RUN_FILES:
        path = run_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少 baseline 输出文件：{path}")


def validate_dataset_dir(dataset_dir: Path) -> None:
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"数据集目录不存在: {dataset_dir}")

    for filename in REQUIRED_DATASET_FILES:
        path = dataset_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少数据集文件：{path}")

    for filename in REQUIRED_SPLIT_FILES:
        path = dataset_dir / "splits" / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少划分文件：{path}")


def load_baseline_artifacts(run_dir: Path) -> dict[str, Any]:
    validate_run_dir(run_dir)

    artifacts = {
        "run_dir": run_dir,
        "baseline_report": load_json(run_dir / "baseline_report.json"),
        "metrics_history": pd.read_csv(run_dir / "metrics_history.csv"),
        "test_predictions": pd.read_csv(run_dir / "test_predictions.csv"),
        "baseline_analysis": None,
    }

    analysis_path = run_dir / "baseline_analysis.json"
    if analysis_path.exists():
        artifacts["baseline_analysis"] = load_json(analysis_path)

    return artifacts


def load_dataset_artifacts(dataset_dir: Path) -> dict[str, Any]:
    validate_dataset_dir(dataset_dir)

    return {
        "dataset_dir": dataset_dir,
        "X": np.load(dataset_dir / "X.npy", allow_pickle=False),
        "y": np.load(dataset_dir / "y.npy", allow_pickle=False),
        "feature_columns": load_json(dataset_dir / "feature_columns.json"),
        "train_indices": np.load(dataset_dir / "splits" / "train_indices.npy", allow_pickle=False),
        "val_indices": np.load(dataset_dir / "splits" / "val_indices.npy", allow_pickle=False),
        "test_indices": np.load(dataset_dir / "splits" / "test_indices.npy", allow_pickle=False),
    }


def load_condition_artifacts(
    condition_labels_path: Path,
    condition_summary_path: Path,
) -> dict[str, Any]:
    if not condition_labels_path.exists():
        raise FileNotFoundError(f"缺少 condition_labels 文件：{condition_labels_path}")

    if not condition_summary_path.exists():
        raise FileNotFoundError(f"缺少 condition_summary 文件：{condition_summary_path}")

    return {
        "condition_labels": np.load(condition_labels_path, allow_pickle=False),
        "condition_summary": load_json(condition_summary_path),
        "condition_labels_path": condition_labels_path,
        "condition_summary_path": condition_summary_path,
    }


def validate_loaded_data(
    baseline_a: dict[str, Any],
    baseline_b: dict[str, Any],
    dataset_a: dict[str, Any],
    dataset_b: dict[str, Any],
    condition_artifacts: dict[str, Any],
    warnings: list[str],
) -> None:
    pred_a = baseline_a["test_predictions"]
    pred_b = baseline_b["test_predictions"]

    for name, predictions in [("baseline_a", pred_a), ("baseline_b", pred_b)]:
        for column in ["y_true", "y_prob"]:
            if column not in predictions.columns:
                raise ValueError(f"{name}/test_predictions.csv 缺少字段：{column}")

    if len(pred_a) != len(pred_b):
        raise ValueError("两组 test_predictions.csv 行数不一致，无法对比")

    if not np.array_equal(pred_a["y_true"].to_numpy(), pred_b["y_true"].to_numpy()):
        raise ValueError("两组测试集 y_true 不一致，无法对比")

    y_a = dataset_a["y"]
    y_b = dataset_b["y"]
    if y_a.shape[0] != y_b.shape[0]:
        raise ValueError("dataset-a/y.npy 与 dataset-b/y.npy 样本数不一致")

    test_indices_a = dataset_a["test_indices"]
    test_indices_b = dataset_b["test_indices"]
    if not np.array_equal(test_indices_a, test_indices_b):
        raise ValueError("两组 test_indices 不一致，无法做按工况对比")

    condition_labels = normalize_condition_labels(condition_artifacts["condition_labels"])
    if condition_labels.shape[0] != y_b.shape[0]:
        raise ValueError("condition_labels 样本数与数据集样本数不一致")

    if condition_labels.size > 0 and condition_labels.min() < 0:
        raise ValueError("condition_id 不能为负数")

    condition_summary = condition_artifacts["condition_summary"]
    n_clusters = int(condition_summary.get("n_clusters", int(condition_labels.max()) + 1))
    if condition_labels.size > 0 and condition_labels.max() >= n_clusters:
        raise ValueError("condition_summary.json 中 n_clusters 与 condition_labels 范围不一致")

    if dataset_b["X"].shape[2] <= dataset_a["X"].shape[2]:
        raise ValueError("baseline-b 的特征维度未大于 baseline-a，无法确认工况 one-hot 已追加")

    expected_condition_columns = [f"condition_{cluster_id}" for cluster_id in range(n_clusters)]
    if dataset_b["feature_columns"][-n_clusters:] != expected_condition_columns:
        raise ValueError("baseline-b 的 feature_columns 末尾不符合 condition_0、condition_1 等命名规则")

    test_indices = dataset_b["test_indices"]
    if test_indices.size != len(pred_b):
        warnings.append("test_indices 数量与 test_predictions 行数不一致，请确认 sample_order 映射是否可靠")

    if test_indices.size > 0 and test_indices.max() >= condition_labels.shape[0]:
        raise ValueError("test_indices 中存在 condition_labels 无法映射的样本索引")


def normalize_condition_labels(condition_labels: np.ndarray) -> np.ndarray:
    if not isinstance(condition_labels, np.ndarray):
        raise ValueError("condition_labels 必须是 numpy.ndarray")

    if condition_labels.ndim != 1:
        raise ValueError("condition_labels 必须是一维数组")

    if np.issubdtype(condition_labels.dtype, np.integer):
        return condition_labels.astype(np.int64, copy=False)

    as_float = condition_labels.astype(np.float64)
    rounded = np.rint(as_float)
    if not np.allclose(as_float, rounded):
        raise ValueError("condition_labels 必须是整数类型，或能安全转换为整数")

    return rounded.astype(np.int64)


def get_final_metrics(artifacts: dict[str, Any]) -> dict[str, Any]:
    report = artifacts["baseline_report"]

    return {
        "train": report.get("train_metrics", {}),
        "val": report.get("val_metrics", {}),
        "test": report.get("test_metrics", {}),
    }


def build_final_metric_compare(
    metrics_a: dict[str, Any],
    metrics_b: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        split_name: build_split_metric_delta(
            metrics_a.get(split_name, {}),
            metrics_b.get(split_name, {}),
        )
        for split_name in ["train", "val", "test"]
    }


def build_split_metric_delta(metrics_a: dict[str, Any], metrics_b: dict[str, Any]) -> dict[str, Any]:
    result = {}

    higher_better = ["accuracy", "precision", "recall", "f1", "auc"]
    for metric in higher_better:
        a_value = to_optional_float(metrics_a.get(metric))
        b_value = to_optional_float(metrics_b.get(metric))
        result[f"{metric}_a"] = a_value
        result[f"{metric}_b"] = b_value
        result[f"{metric}_delta"] = optional_delta(b_value, a_value)

    a_brier = to_optional_float(metrics_a.get("brier_score"))
    b_brier = to_optional_float(metrics_b.get("brier_score"))
    result["brier_score_a"] = a_brier
    result["brier_score_b"] = b_brier
    result["brier_improvement"] = optional_delta(a_brier, b_brier)

    a_loss = to_optional_float(metrics_a.get("loss"))
    b_loss = to_optional_float(metrics_b.get("loss"))
    result["loss_a"] = a_loss
    result["loss_b"] = b_loss
    result["loss_delta"] = optional_delta(b_loss, a_loss)

    return result


def build_curve_summary(metrics_history: pd.DataFrame) -> dict[str, Any]:
    if metrics_history.empty:
        raise ValueError("metrics_history.csv 为空，无法对比训练曲线")

    return {
        "epoch_count": int(len(metrics_history)),
        "first_train_loss": series_first(metrics_history, "train_loss"),
        "last_train_loss": series_last(metrics_history, "train_loss"),
        "best_val_loss": series_min(metrics_history, "val_loss"),
        "best_val_f1": series_max(metrics_history, "val_f1"),
        "best_val_auc": series_max(metrics_history, "val_auc"),
        "best_val_brier_score": series_min(metrics_history, "val_brier_score"),
        "train_loss_decreased": bool(
            series_last(metrics_history, "train_loss") < series_first(metrics_history, "train_loss")
        ),
        "best_val_auc_epoch": series_idxmax_epoch(metrics_history, "val_auc"),
        "best_val_f1_epoch": series_idxmax_epoch(metrics_history, "val_f1"),
    }


def build_curve_compare(curve_a: dict[str, Any], curve_b: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    if curve_a["epoch_count"] != curve_b["epoch_count"]:
        warnings.append("两组训练的 epoch 数不同，训练曲线对比仅供参考")

    delta = {}
    for key in [
        "first_train_loss",
        "last_train_loss",
        "best_val_loss",
        "best_val_f1",
        "best_val_auc",
        "best_val_brier_score",
    ]:
        delta[key] = optional_delta(
            to_optional_float(curve_b.get(key)),
            to_optional_float(curve_a.get(key)),
        )

    return {
        "baseline_a": curve_a,
        "baseline_b": curve_b,
        "delta": delta,
    }


def build_prediction_distribution(predictions: pd.DataFrame) -> dict[str, Any]:
    y_true = predictions["y_true"].to_numpy(dtype=np.int64)
    y_prob = predictions["y_prob"].to_numpy(dtype=np.float64)

    if "y_pred" in predictions.columns:
        y_pred = predictions["y_pred"].to_numpy(dtype=np.int64)
    else:
        y_pred = (y_prob >= 0.5).astype(np.int64)

    return {
        "y_prob_min": float(y_prob.min()),
        "y_prob_max": float(y_prob.max()),
        "y_prob_mean": float(y_prob.mean()),
        "y_prob_std": float(y_prob.std()),
        "predicted_positive_ratio": float((y_pred == 1).mean()),
        "true_positive_ratio": float((y_true == 1).mean()),
    }


def build_prediction_distribution_compare(
    dist_a: dict[str, Any],
    dist_b: dict[str, Any],
) -> dict[str, Any]:
    keys = [
        "y_prob_min",
        "y_prob_max",
        "y_prob_mean",
        "y_prob_std",
        "predicted_positive_ratio",
        "true_positive_ratio",
    ]

    return {
        "baseline_a": dist_a,
        "baseline_b": dist_b,
        "delta": {
            key: optional_delta(to_optional_float(dist_b.get(key)), to_optional_float(dist_a.get(key)))
            for key in keys
        },
    }


def build_per_condition_metrics(
    predictions_a: pd.DataFrame,
    predictions_b: pd.DataFrame,
    test_indices: np.ndarray,
    condition_labels: np.ndarray,
    condition_summary: dict,
    warnings: list[str],
) -> dict[str, Any]:
    sample_order = resolve_sample_order(predictions_b, len(test_indices), warnings)
    sample_indices = test_indices[sample_order]
    test_condition_ids = condition_labels[sample_indices]

    if test_condition_ids.min() < 0:
        raise ValueError("测试集映射得到的 condition_id 不能为负数")

    label_mapping = {
        str(key): value
        for key, value in (condition_summary.get("condition_label_mapping") or {}).items()
    }

    result = {}
    for condition_id in sorted(np.unique(test_condition_ids).astype(np.int64).tolist()):
        mask = test_condition_ids == condition_id

        y_true = predictions_a.loc[mask, "y_true"].to_numpy(dtype=np.int64)
        y_prob_a = predictions_a.loc[mask, "y_prob"].to_numpy(dtype=np.float64)
        y_prob_b = predictions_b.loc[mask, "y_prob"].to_numpy(dtype=np.float64)

        if mask.sum() < 5:
            warnings.append(f"工况 {condition_id} 测试样本数少于 5，指标参考价值有限")

        metrics_a = compute_metrics_safely(y_true, y_prob_a, warnings, prefix=f"工况 {condition_id} baseline_a")
        metrics_b = compute_metrics_safely(y_true, y_prob_b, warnings, prefix=f"工况 {condition_id} baseline_b")
        delta = build_condition_delta(metrics_a, metrics_b)

        result[str(condition_id)] = {
            "condition_id": int(condition_id),
            "condition_label": label_mapping.get(str(condition_id), f"工况{condition_id}"),
            "sample_count": int(mask.sum()),
            "positive_count": int((y_true == 1).sum()),
            "positive_ratio": float((y_true == 1).mean()) if mask.sum() > 0 else 0.0,
            "baseline_a": metrics_a,
            "baseline_b": metrics_b,
            "delta": delta,
        }

    return result


def resolve_sample_order(predictions: pd.DataFrame, test_count: int, warnings: list[str]) -> np.ndarray:
    if "sample_order" not in predictions.columns:
        warnings.append("test_predictions.csv 缺少 sample_order，已按行顺序映射测试集样本")
        return np.arange(len(predictions), dtype=np.int64)

    sample_order = predictions["sample_order"].to_numpy(dtype=np.int64)

    if sample_order.min() < 0 or sample_order.max() >= test_count:
        raise ValueError("test_predictions.csv 中 sample_order 超出 test_indices 范围")

    return sample_order


def compute_metrics_safely(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    warnings: list[str],
    prefix: str,
) -> dict[str, Any]:
    metrics = compute_binary_metrics(y_true=y_true, y_prob=y_prob, threshold=0.5)

    metric_warnings = metrics.get("warnings") or []
    for warning in metric_warnings:
        warnings.append(f"{prefix}: {warning}")

    y_pred = (y_prob >= 0.5).astype(np.int64)
    metrics["predicted_positive_ratio"] = float((y_pred == 1).mean())

    return json_safe(metrics)


def build_condition_delta(metrics_a: dict[str, Any], metrics_b: dict[str, Any]) -> dict[str, Any]:
    return {
        "auc_delta": optional_delta(to_optional_float(metrics_b.get("auc")), to_optional_float(metrics_a.get("auc"))),
        "f1_delta": optional_delta(to_optional_float(metrics_b.get("f1")), to_optional_float(metrics_a.get("f1"))),
        "recall_delta": optional_delta(to_optional_float(metrics_b.get("recall")), to_optional_float(metrics_a.get("recall"))),
        "precision_delta": optional_delta(to_optional_float(metrics_b.get("precision")), to_optional_float(metrics_a.get("precision"))),
        "brier_improvement": optional_delta(
            to_optional_float(metrics_a.get("brier_score")),
            to_optional_float(metrics_b.get("brier_score")),
        ),
    }


def judge_condition_effectiveness(
    metric_delta: dict[str, dict[str, Any]],
    per_condition_metrics: dict[str, Any],
    condition_summary: dict,
    auc_delta_threshold: float,
    f1_delta_threshold: float,
    brier_delta_threshold: float,
) -> dict[str, Any]:
    test_delta = metric_delta["test"]

    auc_delta = to_optional_float(test_delta.get("auc_delta")) or 0.0
    f1_delta = to_optional_float(test_delta.get("f1_delta")) or 0.0
    recall_delta = to_optional_float(test_delta.get("recall_delta")) or 0.0
    precision_delta = to_optional_float(test_delta.get("precision_delta")) or 0.0
    brier_improvement = to_optional_float(test_delta.get("brier_improvement")) or 0.0

    reasons: list[str] = []
    risks: list[str] = []
    next_steps: list[str] = []

    per_condition_improved = any(
        (metrics.get("delta", {}).get("auc_delta") or 0) > 0
        or (metrics.get("delta", {}).get("f1_delta") or 0) > 0
        for metrics in per_condition_metrics.values()
    )

    condition_has_difference = has_condition_distribution_difference(condition_summary)

    if (
        (auc_delta >= auc_delta_threshold or f1_delta >= f1_delta_threshold)
        and recall_delta >= 0
        and precision_delta >= -0.01
        and brier_improvement >= -brier_delta_threshold
    ):
        level = "effective"
        level_cn = "工况划分有效"
        is_worth_keeping = True
        reasons.append("加入工况 one-hot 后，测试集 AUC 或 F1 达到有效提升阈值。")
        reasons.append("测试集 Recall 未下降，说明正样本识别能力没有被削弱。")
        if brier_improvement >= 0:
            reasons.append("测试集 Brier Score 未恶化，概率质量保持稳定或略有改善。")
    elif (
        auc_delta > 0
        or f1_delta > 0
        or brier_improvement > 0
        or per_condition_improved
    ):
        level = "weak_effective"
        level_cn = "工况划分弱有效"
        is_worth_keeping = True
        reasons.append("加入工况 one-hot 后整体指标存在小幅改善，但提升幅度未达到明显有效阈值。")
        if per_condition_improved:
            reasons.append("部分工况下测试集指标有所改善，说明工况信息具有一定辅助价值。")
    elif condition_has_difference:
        level = "interpret_only"
        level_cn = "工况划分仅具备解释价值"
        is_worth_keeping = True
        reasons.append("总体预测指标提升不明显，但不同工况的样本分布或正样本比例存在差异。")
        reasons.append("工况划分仍可作为运行状态解释和分组分析维度保留。")
    else:
        level = "not_effective"
        level_cn = "工况划分当前无明显价值"
        is_worth_keeping = False
        reasons.append("加入工况 one-hot 后总体指标未改善，且未观察到明确的按工况解释价值。")

    if auc_delta < 0:
        risks.append("测试集 AUC 出现下降，说明工况 one-hot 可能引入噪声。")

    if f1_delta < 0:
        risks.append("测试集 F1 出现下降，默认阈值下正样本识别能力可能变差。")

    if brier_improvement < -brier_delta_threshold:
        risks.append("测试集 Brier Score 明显恶化，概率质量存在下降风险。")

    if is_worth_keeping:
        next_steps.append("在后续 LSTM、Bi-LSTM 或 Bi-LSTM + Attention 模型中保留工况 one-hot 作为对照输入。")
        next_steps.append("继续观察不同工况下的 Recall、F1 和概率质量差异。")
    else:
        next_steps.append("暂不将当前工况 one-hot 固化为默认输入，优先重新设计工况特征或调整聚类数量。")

    next_steps.append("后续 Task 可进一步比较不同窗口参数、不同 seed 和不同 n_clusters 下的稳定性。")

    return {
        "level": level,
        "level_cn": level_cn,
        "is_worth_keeping": bool(is_worth_keeping),
        "reasons": reasons,
        "risks": risks,
        "next_steps": next_steps,
    }


def has_condition_distribution_difference(condition_summary: dict) -> bool:
    ratios = condition_summary.get("cluster_positive_ratio") or {}
    values = []
    for value in ratios.values():
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if len(values) >= 2 and max(values) - min(values) >= 0.05:
        return True

    counts = condition_summary.get("cluster_sample_count") or {}
    count_values = []
    for value in counts.values():
        try:
            count_values.append(float(value))
        except (TypeError, ValueError):
            continue

    if len(count_values) >= 2 and max(count_values) > 2 * max(min(count_values), 1):
        return True

    return False


def extract_condition_summary(condition_summary: dict) -> dict[str, Any]:
    return {
        "n_clusters": condition_summary.get("n_clusters"),
        "condition_label_mapping": condition_summary.get("condition_label_mapping", {}),
        "cluster_sample_count": condition_summary.get("cluster_sample_count", {}),
        "cluster_positive_ratio": condition_summary.get("cluster_positive_ratio", {}),
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    test_delta = report["metric_delta"]["test"]
    judgement = report["judgement"]

    lines = [
        "# RailPHM 工况划分 Baseline 对比分析报告",
        "",
        "## 1. 分析对象",
        "",
        f"- 原始 baseline：`{report['baseline_a']['run_dir']}`",
        f"- 工况增强 baseline：`{report['baseline_b']['run_dir']}`",
        f"- 原始数据集：`{report['baseline_a']['dataset_dir']}`",
        f"- 工况增强数据集：`{report['baseline_b']['dataset_dir']}`",
        "",
        "## 2. 数据集说明",
        "",
        f"- 原始数据集 X_shape：`{report['baseline_a']['dataset_shape']}`",
        f"- 工况增强数据集 X_shape：`{report['baseline_b']['dataset_shape']}`",
        f"- 工况数量：{report['condition_summary'].get('n_clusters')}",
        "",
        "## 3. 总体指标对比",
        "",
        "| 指标 | 原始 baseline | 加入工况 baseline | 变化 | 判断 |",
        "|---|---:|---:|---:|---|",
    ]

    metric_rows = [
        ("test_auc", "auc_a", "auc_b", "auc_delta", True),
        ("test_f1", "f1_a", "f1_b", "f1_delta", True),
        ("test_precision", "precision_a", "precision_b", "precision_delta", True),
        ("test_recall", "recall_a", "recall_b", "recall_delta", True),
        ("test_brier_score", "brier_score_a", "brier_score_b", "brier_improvement", False),
    ]

    for label, a_key, b_key, delta_key, higher_better in metric_rows:
        a_value = test_delta.get(a_key)
        b_value = test_delta.get(b_key)
        delta_value = test_delta.get(delta_key)
        judgement_text = metric_change_label(delta_value, higher_better=higher_better)
        lines.append(
            f"| {label} | {fmt_float(a_value)} | {fmt_float(b_value)} | "
            f"{fmt_float(delta_value)} | {judgement_text} |"
        )

    lines.extend(
        [
            "",
            "## 4. 训练过程对比",
            "",
            "| 项目 | 原始 baseline | 加入工况 baseline | 变化 |",
            "|---|---:|---:|---:|",
        ]
    )

    curve_compare = report["curve_compare"]
    for key in [
        "first_train_loss",
        "last_train_loss",
        "best_val_loss",
        "best_val_f1",
        "best_val_auc",
        "best_val_brier_score",
    ]:
        lines.append(
            f"| {key} | {fmt_float(curve_compare['baseline_a'].get(key))} | "
            f"{fmt_float(curve_compare['baseline_b'].get(key))} | "
            f"{fmt_float(curve_compare['delta'].get(key))} |"
        )

    lines.extend(
        [
            "",
            "## 5. 测试集预测分布对比",
            "",
            "| 项目 | 原始 baseline | 加入工况 baseline | 变化 |",
            "|---|---:|---:|---:|",
        ]
    )

    pred_compare = report["prediction_distribution_compare"]
    for key in [
        "y_prob_min",
        "y_prob_max",
        "y_prob_mean",
        "y_prob_std",
        "predicted_positive_ratio",
        "true_positive_ratio",
    ]:
        lines.append(
            f"| {key} | {fmt_float(pred_compare['baseline_a'].get(key))} | "
            f"{fmt_float(pred_compare['baseline_b'].get(key))} | "
            f"{fmt_float(pred_compare['delta'].get(key))} |"
        )

    lines.extend(
        [
            "",
            "## 6. 按工况测试集表现分析",
            "",
            "| condition_id | condition_label | 样本数 | 正样本比例 | AUC_A | AUC_B | AUC变化 | F1_A | F1_B | F1变化 | Brier改善 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for condition_id, metrics in report["per_condition_test_metrics"].items():
        delta = metrics["delta"]
        lines.append(
            f"| {condition_id} | {metrics['condition_label']} | "
            f"{metrics['sample_count']} | {fmt_float(metrics['positive_ratio'])} | "
            f"{fmt_float(metrics['baseline_a'].get('auc'))} | "
            f"{fmt_float(metrics['baseline_b'].get('auc'))} | "
            f"{fmt_float(delta.get('auc_delta'))} | "
            f"{fmt_float(metrics['baseline_a'].get('f1'))} | "
            f"{fmt_float(metrics['baseline_b'].get('f1'))} | "
            f"{fmt_float(delta.get('f1_delta'))} | "
            f"{fmt_float(delta.get('brier_improvement'))} |"
        )

    lines.extend(
        [
            "",
            "## 7. 工况划分有效性判断",
            "",
            f"- 判断等级：**{judgement['level_cn']}**",
            f"- 是否值得保留：**{judgement['is_worth_keeping']}**",
            "",
            "判断依据：",
            "",
        ]
    )

    for reason in judgement.get("reasons", []):
        lines.append(f"- {reason}")

    lines.extend(["", "## 8. 风险提示", ""])
    risks = judgement.get("risks", [])
    if risks:
        for risk in risks:
            lines.append(f"- {risk}")
    else:
        lines.append("- 当前对比结果未发现明显风险，但仍建议结合多次实验验证稳定性。")

    lines.extend(["", "## 9. 后续建议", ""])
    for step in judgement.get("next_steps", []):
        lines.append(f"- {step}")

    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(["", "## 附加 warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.append("")
    return "\n".join(lines)


def print_summary(report: dict[str, Any], verbose: bool = False) -> None:
    test_delta = report["metric_delta"]["test"]
    judgement = report["judgement"]

    print()
    print("RailPHM condition baseline comparison finished.")
    print(f"baseline_a: {report['baseline_a']['run_dir']}")
    print(f"baseline_b: {report['baseline_b']['run_dir']}")
    print(f"dataset_a: {report['baseline_a']['dataset_dir']}")
    print(f"dataset_b: {report['baseline_b']['dataset_dir']}")
    print(f"output_dir: {Path(report['artifacts']['json']).parent}")

    print()
    print("test metric delta:")
    print(f"- auc_delta: {test_delta.get('auc_delta')}")
    print(f"- f1_delta: {test_delta.get('f1_delta')}")
    print(f"- recall_delta: {test_delta.get('recall_delta')}")
    print(f"- precision_delta: {test_delta.get('precision_delta')}")
    print(f"- brier_improvement: {test_delta.get('brier_improvement')}")

    print()
    print(f"judgement: {judgement['level_cn']}")

    print()
    print("Output files:")
    print(f"- {report['artifacts']['json']}")
    print(f"- {report['artifacts']['markdown']}")

    if not verbose:
        return

    print()
    print("per-condition metrics:")
    print(json.dumps(report["per_condition_test_metrics"], ensure_ascii=False, indent=2))

    warnings = report.get("warnings") or []
    if warnings:
        print()
        print("warnings:")
        for warning in warnings:
            print(f"- {warning}")

    print()
    print("next_steps:")
    for step in judgement.get("next_steps", []):
        print(f"- {step}")


def run(args: argparse.Namespace) -> dict[str, Any]:
    prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    warnings: list[str] = []

    baseline_a = load_baseline_artifacts(args.baseline_a)
    baseline_b = load_baseline_artifacts(args.baseline_b)
    dataset_a = load_dataset_artifacts(args.dataset_a)
    dataset_b = load_dataset_artifacts(args.dataset_b)

    if baseline_a["baseline_analysis"] is None:
        warnings.append("baseline-a 缺少 baseline_analysis.json，已仅使用 baseline_report.json")
    if baseline_b["baseline_analysis"] is None:
        warnings.append("baseline-b 缺少 baseline_analysis.json，已仅使用 baseline_report.json")

    condition_labels_path = resolve_condition_file(
        explicit_path=args.condition_labels,
        dataset_a=args.dataset_a,
        dataset_b=args.dataset_b,
        filename="condition_labels.npy",
    )
    condition_summary_path = resolve_condition_file(
        explicit_path=args.condition_summary,
        dataset_a=args.dataset_a,
        dataset_b=args.dataset_b,
        filename="condition_summary.json",
    )
    condition_artifacts = load_condition_artifacts(condition_labels_path, condition_summary_path)

    validate_loaded_data(
        baseline_a=baseline_a,
        baseline_b=baseline_b,
        dataset_a=dataset_a,
        dataset_b=dataset_b,
        condition_artifacts=condition_artifacts,
        warnings=warnings,
    )

    metrics_a = get_final_metrics(baseline_a)
    metrics_b = get_final_metrics(baseline_b)
    metric_delta = build_final_metric_compare(metrics_a, metrics_b)

    curve_a = build_curve_summary(baseline_a["metrics_history"])
    curve_b = build_curve_summary(baseline_b["metrics_history"])
    curve_compare = build_curve_compare(curve_a, curve_b, warnings)

    pred_dist_a = build_prediction_distribution(baseline_a["test_predictions"])
    pred_dist_b = build_prediction_distribution(baseline_b["test_predictions"])
    pred_dist_compare = build_prediction_distribution_compare(pred_dist_a, pred_dist_b)

    condition_labels = normalize_condition_labels(condition_artifacts["condition_labels"])
    per_condition_metrics = build_per_condition_metrics(
        predictions_a=baseline_a["test_predictions"],
        predictions_b=baseline_b["test_predictions"],
        test_indices=dataset_b["test_indices"],
        condition_labels=condition_labels,
        condition_summary=condition_artifacts["condition_summary"],
        warnings=warnings,
    )

    judgement = judge_condition_effectiveness(
        metric_delta=metric_delta,
        per_condition_metrics=per_condition_metrics,
        condition_summary=condition_artifacts["condition_summary"],
        auc_delta_threshold=args.auc_delta_threshold,
        f1_delta_threshold=args.f1_delta_threshold,
        brier_delta_threshold=args.brier_delta_threshold,
    )

    json_path = args.output_dir / "condition_baseline_compare.json"
    markdown_path = args.output_dir / "condition_baseline_compare.md"

    report = {
        "task": "condition_baseline_compare",
        "baseline_a": {
            "name": "original_baseline",
            "run_dir": str(args.baseline_a),
            "dataset_dir": str(args.dataset_a),
            "dataset_shape": [int(value) for value in dataset_a["X"].shape],
            "final_metrics": metrics_a,
            "curve_summary": curve_a,
            "prediction_distribution": pred_dist_a,
        },
        "baseline_b": {
            "name": "condition_augmented_baseline",
            "run_dir": str(args.baseline_b),
            "dataset_dir": str(args.dataset_b),
            "dataset_shape": [int(value) for value in dataset_b["X"].shape],
            "final_metrics": metrics_b,
            "curve_summary": curve_b,
            "prediction_distribution": pred_dist_b,
        },
        "metric_delta": metric_delta,
        "curve_compare": curve_compare,
        "prediction_distribution_compare": pred_dist_compare,
        "condition_summary": extract_condition_summary(condition_artifacts["condition_summary"]),
        "per_condition_test_metrics": per_condition_metrics,
        "judgement": judgement,
        "warnings": warnings,
        "artifacts": {
            "json": str(json_path),
            "markdown": str(markdown_path),
        },
    }

    save_json(json_path, report)
    markdown_path.write_text(render_markdown_report(json_safe(report)), encoding="utf-8")

    print_summary(json_safe(report), verbose=args.verbose)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        run(args)
        return 0
    except Exception as exc:
        print(f"工况 baseline 对比分析失败: {exc}", file=sys.stderr)
        return 1


def to_optional_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

    return float(value)


def optional_delta(new_value: float | None, old_value: float | None) -> float | None:
    if new_value is None or old_value is None:
        return None

    return float(new_value - old_value)


def series_first(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    return to_optional_float(df[column].iloc[0])


def series_last(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    return to_optional_float(df[column].iloc[-1])


def series_min(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    return to_optional_float(df[column].min())


def series_max(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    return to_optional_float(df[column].max())


def series_idxmax_epoch(df: pd.DataFrame, column: str) -> int | None:
    if column not in df.columns:
        return None
    index = df[column].idxmax()
    if "epoch" in df.columns:
        return int(df.loc[index, "epoch"])
    return int(index + 1)


def fmt_float(value: Any) -> str:
    if value is None:
        return "-"

    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def metric_change_label(delta: float | None, higher_better: bool = True) -> str:
    if delta is None:
        return "-"

    if abs(delta) < 1e-6:
        return "持平"

    if higher_better:
        return "提升" if delta > 0 else "下降"

    return "改善" if delta > 0 else "恶化"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [json_safe(item) for item in value]

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.ndarray):
        return value.tolist()

    if pd.isna(value) if isinstance(value, (float, np.floating)) else False:
        return None

    return value


if __name__ == "__main__":
    raise SystemExit(main())