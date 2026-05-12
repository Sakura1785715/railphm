#!/usr/bin/env python3
"""
Task 5-3 四组时序模型训练结果轻量汇总脚本。

本脚本只读取四个 sequence_model_report.json、metrics_history.csv、
test_predictions.csv，生成本轮训练运行记录 Markdown。

不做正式模型对比结论，不实现 compare_sequence_models.py。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any


RUNS = [
    (
        "LSTM",
        Path("outputs/sequence_lstm_sim_window_w30_s1_h1_condition_k3_e30"),
    ),
    (
        "Bi-LSTM",
        Path("outputs/sequence_bilstm_sim_window_w30_s1_h1_condition_k3_e30"),
    ),
    (
        "LSTM+Attention",
        Path("outputs/sequence_lstm_attention_sim_window_w30_s1_h1_condition_k3_e30"),
    ),
    (
        "Bi-LSTM+Attention",
        Path("outputs/sequence_bilstm_attention_sim_window_w30_s1_h1_condition_k3_e30"),
    ),
]

OUTPUT_FILE = Path("outputs/sequence_training_runs_summary_w30_s1_h1_condition_k3.md")

REQUIRED_RUN_FILES = [
    "best_model.pt",
    "metrics_history.csv",
    "test_predictions.csv",
    "training_config.json",
    "sequence_model_report.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def check_run_files() -> list[str]:
    errors: list[str] = []

    for model_name, run_dir in RUNS:
        if not run_dir.exists():
            errors.append(f"{model_name}: 输出目录不存在：{run_dir}")
            continue

        for filename in REQUIRED_RUN_FILES:
            path = run_dir / filename
            if not path.exists():
                errors.append(f"{model_name}: 缺少文件：{path}")

    return errors


def validate_report(model_name: str, run_dir: Path, report: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if report.get("task") != "sequence_model_training":
        errors.append(f"{model_name}: task 不是 sequence_model_training")

    for key in ["model", "dataset", "training", "train_metrics", "val_metrics", "test_metrics", "artifacts"]:
        if key not in report:
            errors.append(f"{model_name}: sequence_model_report.json 缺少字段：{key}")

    dataset = report.get("dataset", {})
    for key in ["dataset_dir", "X_shape", "y_shape", "window_size", "feature_dim", "train_samples", "val_samples", "test_samples"]:
        if key not in dataset:
            errors.append(f"{model_name}: dataset 缺少字段：{key}")

    training = report.get("training", {})
    for key in ["epochs", "batch_size", "lr", "seed", "device", "threshold", "best_epoch", "best_metric", "best_metric_value"]:
        if key not in training:
            errors.append(f"{model_name}: training 缺少字段：{key}")

    for part in ["train_metrics", "val_metrics", "test_metrics"]:
        metrics = report.get(part, {})
        for key in ["loss", "accuracy", "precision", "recall", "f1", "auc", "brier_score"]:
            if key not in metrics:
                errors.append(f"{model_name}: {part} 缺少字段：{key}")

    artifacts = report.get("artifacts", {})
    for key in ["best_model", "metrics_history", "test_predictions", "training_config"]:
        if key not in artifacts:
            errors.append(f"{model_name}: artifacts 缺少字段：{key}")

    history_path = run_dir / "metrics_history.csv"
    if history_path.exists():
        rows = read_csv_rows(history_path)
        expected_epochs = int(training.get("epochs", 30))
        if len(rows) != expected_epochs:
            errors.append(f"{model_name}: metrics_history.csv 行数不是 {expected_epochs}，当前为 {len(rows)}")

        if rows:
            required_history_cols = {"epoch", "train_loss", "val_loss", "val_f1", "val_auc"}
            missing_cols = required_history_cols - set(rows[0].keys())
            if missing_cols:
                errors.append(f"{model_name}: metrics_history.csv 缺少列：{sorted(missing_cols)}")

            epochs = [int(row["epoch"]) for row in rows if row.get("epoch")]
            if epochs != list(range(1, len(rows) + 1)):
                errors.append(f"{model_name}: epoch 序号不是从 1 连续递增")

            if all(not row.get("train_loss") for row in rows):
                errors.append(f"{model_name}: train_loss 全部为空")

            if all(not row.get("val_loss") for row in rows):
                errors.append(f"{model_name}: val_loss 全部为空")

    pred_path = run_dir / "test_predictions.csv"
    if pred_path.exists():
        rows = read_csv_rows(pred_path)
        required_pred_cols = {"sample_order", "y_true", "y_prob", "y_pred"}
        if rows:
            missing_cols = required_pred_cols - set(rows[0].keys())
            if missing_cols:
                errors.append(f"{model_name}: test_predictions.csv 缺少列：{sorted(missing_cols)}")

        test_samples = int(dataset.get("test_samples", -1))
        if len(rows) != test_samples:
            errors.append(f"{model_name}: test_predictions.csv 行数与 test_samples 不一致：rows={len(rows)}, test_samples={test_samples}")

        y_probs = []
        y_true_values = set()
        y_pred_values = set()

        for row in rows:
            try:
                y_prob = float(row["y_prob"])
                y_probs.append(y_prob)
            except Exception:
                errors.append(f"{model_name}: y_prob 存在无法转 float 的值")
                continue

            y_true_values.add(str(row.get("y_true")))
            y_pred_values.add(str(row.get("y_pred")))

        if y_probs and (min(y_probs) < 0 or max(y_probs) > 1):
            errors.append(f"{model_name}: y_prob 超出 [0, 1] 范围")

        if not y_true_values.issubset({"0", "1"}):
            errors.append(f"{model_name}: y_true 存在非 0/1 取值：{sorted(y_true_values)}")

        if not y_pred_values.issubset({"0", "1"}):
            errors.append(f"{model_name}: y_pred 存在非 0/1 取值：{sorted(y_pred_values)}")

    return errors


def prediction_notes(run_dir: Path) -> list[str]:
    pred_path = run_dir / "test_predictions.csv"
    if not pred_path.exists():
        return ["test_predictions.csv 不存在，无法检查预测分布。"]

    rows = read_csv_rows(pred_path)
    if not rows:
        return ["test_predictions.csv 为空。"]

    y_pred = [int(row["y_pred"]) for row in rows]
    positive_ratio = sum(y_pred) / len(y_pred)

    notes = [f"predicted_positive_ratio={positive_ratio:.4f}"]

    if positive_ratio == 0:
        notes.append("模型可能退化为全预测负类。")
    elif positive_ratio == 1:
        notes.append("模型可能退化为全预测正类。")

    return notes


def render_summary(reports: list[tuple[str, Path, dict[str, Any]]], validation_errors: list[str]) -> str:
    first_report = reports[0][2]
    dataset = first_report["dataset"]
    training = first_report["training"]
    model_config = first_report["model"]

    lines = [
        "# RailPHM Task 5-3 时序模型训练运行记录",
        "",
        "## 1. 任务说明",
        "",
        "本任务使用同一个工况增强窗口数据集，分别训练 LSTM、Bi-LSTM、LSTM+Attention、Bi-LSTM+Attention 四个时序故障风险预测模型。四组模型使用相同的数据集、相同的 train/val/test 划分和相同训练参数。本记录仅用于本轮训练检查，不替代后续 compare_sequence_models.py 的正式模型对比结论。",
        "",
        "## 2. 数据集信息",
        "",
        f"- dataset_dir：`{dataset.get('dataset_dir')}`",
        f"- X_shape：`{dataset.get('X_shape')}`",
        f"- y_shape：`{dataset.get('y_shape')}`",
        f"- window_size：{dataset.get('window_size')}",
        f"- feature_dim：{dataset.get('feature_dim')}",
        f"- train_samples：{dataset.get('train_samples')}",
        f"- val_samples：{dataset.get('val_samples')}",
        f"- test_samples：{dataset.get('test_samples')}",
        "",
        "## 3. 统一训练参数",
        "",
        f"- epochs：{training.get('epochs')}",
        f"- batch_size：{training.get('batch_size')}",
        f"- lr：{training.get('lr')}",
        f"- hidden_dim：{model_config.get('hidden_dim')}",
        f"- num_layers：{model_config.get('num_layers')}",
        f"- dropout：{model_config.get('dropout')}",
        f"- best_metric：{training.get('best_metric')}",
        f"- seed：{training.get('seed')}",
        f"- device：{training.get('device')}",
        f"- threshold：{training.get('threshold')}",
        "",
        "## 4. 四模型训练输出目录",
        "",
    ]

    for model_name, run_dir, _ in reports:
        lines.append(f"- {model_name}：`{run_dir}`")

    lines.extend(
        [
            "",
            "## 5. 四模型结果初步汇总",
            "",
            "| 模型 | best_epoch | val_loss | val_precision | val_recall | val_f1 | val_auc | test_precision | test_recall | test_f1 | test_auc | test_brier_score |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for model_name, _, report in reports:
        val_metrics = report["val_metrics"]
        test_metrics = report["test_metrics"]
        training_info = report["training"]

        lines.append(
            f"| {model_name} | "
            f"{fmt(training_info.get('best_epoch'))} | "
            f"{fmt(val_metrics.get('loss'))} | "
            f"{fmt(val_metrics.get('precision'))} | "
            f"{fmt(val_metrics.get('recall'))} | "
            f"{fmt(val_metrics.get('f1'))} | "
            f"{fmt(val_metrics.get('auc'))} | "
            f"{fmt(test_metrics.get('precision'))} | "
            f"{fmt(test_metrics.get('recall'))} | "
            f"{fmt(test_metrics.get('f1'))} | "
            f"{fmt(test_metrics.get('auc'))} | "
            f"{fmt(test_metrics.get('brier_score'))} |"
        )

    lines.extend(
        [
            "",
            "## 6. 训练异常检查",
            "",
        ]
    )

    if validation_errors:
        lines.append("存在以下检查问题：")
        lines.append("")
        for error in validation_errors:
            lines.append(f"- {error}")
    else:
        lines.append("- 四个模型输出目录均存在。")
        lines.append("- 必要输出文件均存在。")
        lines.append("- sequence_model_report.json 字段完整性检查通过。")
        lines.append("- metrics_history.csv 基本结构检查通过。")
        lines.append("- test_predictions.csv 基本结构检查通过。")
        lines.append("- 未发现 y_prob 超出 [0,1]。")

    lines.append("")
    lines.append("预测分布检查：")
    lines.append("")

    for model_name, run_dir, _ in reports:
        notes = "；".join(prediction_notes(run_dir))
        lines.append(f"- {model_name}：{notes}")

    lines.extend(
        [
            "",
            "## 7. 初步观察",
            "",
            "本节只记录客观观察，不给出最终模型优劣结论。正式结论需等待 Task 5-4 的 compare_sequence_models.py 对四组模型进行统一读取、校验和对比后再给出。",
            "",
        ]
    )

    for model_name, _, report in reports:
        test_metrics = report["test_metrics"]
        lines.append(
            f"- {model_name}：test_f1={fmt(test_metrics.get('f1'))}，"
            f"test_auc={fmt(test_metrics.get('auc'))}，"
            f"test_brier_score={fmt(test_metrics.get('brier_score'))}。"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    file_errors = check_run_files()
    if file_errors:
        print("输出文件检查失败：", file=sys.stderr)
        for error in file_errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    reports = []
    validation_errors: list[str] = []

    for model_name, run_dir in RUNS:
        report = load_json(run_dir / "sequence_model_report.json")
        reports.append((model_name, run_dir, report))
        validation_errors.extend(validate_report(model_name, run_dir, report))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        render_summary(reports, validation_errors),
        encoding="utf-8",
    )

    print(f"summary saved to: {OUTPUT_FILE}")

    if validation_errors:
        print("存在检查问题，请查看 summary 文件。", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())