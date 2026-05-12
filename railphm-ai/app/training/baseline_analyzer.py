"""
baseline 训练结果分析模块。

本模块用于 RailPHM Task 4-5：baseline 训练结果分析与可训练性结论报告。

主要职责：
1. 读取 Task 4-4 生成的 baseline_report.json、metrics_history.csv、test_predictions.csv。
2. 读取数据集侧 dataset_summary.json、inspection_summary.json、split_summary.json。
3. 汇总数据集规模、划分情况、训练过程、最终 train/val/test 指标和测试集预测分布。
4. 根据 AUC、F1、Recall、Brier Score、loss 变化等信息，给出可训练性判断。
5. 生成 baseline_analysis.json 和 baseline_analysis.md。

注意：
- 本模块不重新训练模型。
- 本模块不加载 best_model.pt。
- 本模块不修改 train_baseline.py 主流程。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


@dataclass
class BaselineAnalysisConfig:
    run_dir: Path
    dataset_dir: Path | None = None
    output_json: Path | None = None
    output_markdown: Path | None = None
    auc_threshold: float = 0.60
    f1_threshold: float = 0.30
    recall_threshold: float = 0.30
    brier_threshold: float = 0.25
    overwrite: bool = True


class BaselineAnalyzer:
    """
    baseline 训练结果分析器。
    """

    def analyze(self, config: BaselineAnalysisConfig) -> Dict[str, Any]:
        self._validate_config(config)

        run_dir = Path(config.run_dir)
        if not run_dir.exists() or not run_dir.is_dir():
            raise FileNotFoundError(f"训练结果目录不存在: {run_dir}")

        baseline_report_path = run_dir / "baseline_report.json"
        metrics_history_path = run_dir / "metrics_history.csv"
        test_predictions_path = run_dir / "test_predictions.csv"

        self._require_file(baseline_report_path, "baseline_report.json")
        self._require_file(metrics_history_path, "metrics_history.csv")
        self._require_file(test_predictions_path, "test_predictions.csv")

        output_json = Path(config.output_json) if config.output_json else run_dir / "baseline_analysis.json"
        output_markdown = (
            Path(config.output_markdown)
            if config.output_markdown
            else run_dir / "baseline_analysis.md"
        )

        self._check_output_file(output_json, config.overwrite)
        self._check_output_file(output_markdown, config.overwrite)

        baseline_report = self._load_json(baseline_report_path)
        metrics_history = pd.read_csv(metrics_history_path)
        test_predictions = pd.read_csv(test_predictions_path)

        dataset_dir = self._resolve_dataset_dir(config, baseline_report)

        warnings: List[str] = []
        dataset_summary_raw = self._load_optional_json(dataset_dir / "dataset_summary.json", warnings)
        inspection_summary_raw = self._load_optional_json(dataset_dir / "inspection_summary.json", warnings)
        split_summary_raw = self._load_optional_json(dataset_dir / "splits" / "split_summary.json", warnings)

        inspection_warnings = inspection_summary_raw.get("warnings", [])
        if isinstance(inspection_warnings, list):
            warnings.extend(str(item) for item in inspection_warnings)

        dataset_summary = self._build_dataset_summary(
            baseline_report=baseline_report,
            dataset_summary=dataset_summary_raw,
        )
        split_summary = self._build_split_summary(
            baseline_report=baseline_report,
            split_summary=split_summary_raw,
        )
        training_summary = self._build_training_summary(baseline_report)
        final_metrics = self._build_final_metrics(baseline_report)
        curve_summary = self._build_curve_summary(metrics_history)
        prediction_summary = self._build_prediction_summary(
            predictions=test_predictions,
            threshold=self._get_threshold(baseline_report),
        )

        judgement = self._judge_trainability(
            final_metrics=final_metrics,
            curve_summary=curve_summary,
            prediction_summary=prediction_summary,
            inspection_warnings=inspection_warnings,
            config=config,
        )

        analysis = {
            "task": "baseline_trainability_analysis",
            "run_dir": str(run_dir),
            "dataset_dir": str(dataset_dir),
            "dataset_summary": dataset_summary,
            "split_summary": split_summary,
            "training_summary": training_summary,
            "final_metrics": final_metrics,
            "curve_summary": curve_summary,
            "prediction_summary": prediction_summary,
            "trainability_judgement": judgement,
            "warnings": warnings,
            "artifacts": {
                "baseline_analysis_json": str(output_json),
                "baseline_analysis_markdown": str(output_markdown),
            },
        }

        analysis = self._json_safe(analysis)

        self._save_json(output_json, analysis)
        markdown = self._render_markdown(analysis, metrics_history)
        output_markdown.parent.mkdir(parents=True, exist_ok=True)
        output_markdown.write_text(markdown, encoding="utf-8")

        return analysis

    @staticmethod
    def _validate_config(config: BaselineAnalysisConfig) -> None:
        if not isinstance(config.auc_threshold, (int, float)) or not 0 < float(config.auc_threshold) <= 1:
            raise ValueError("auc_threshold 必须位于 0 到 1 之间")

        if not isinstance(config.f1_threshold, (int, float)) or not 0 <= float(config.f1_threshold) <= 1:
            raise ValueError("f1_threshold 必须位于 0 到 1 之间")

        if not isinstance(config.recall_threshold, (int, float)) or not 0 <= float(config.recall_threshold) <= 1:
            raise ValueError("recall_threshold 必须位于 0 到 1 之间")

        if not isinstance(config.brier_threshold, (int, float)) or float(config.brier_threshold) <= 0:
            raise ValueError("brier_threshold 必须大于 0")

    @staticmethod
    def _require_file(path: Path, name: str) -> None:
        if not path.exists():
            raise FileNotFoundError(f"缺少训练结果文件: {name}")

    @staticmethod
    def _check_output_file(path: Path, overwrite: bool) -> None:
        if path.exists() and not overwrite:
            raise FileExistsError(f"输出文件已存在: {path}，如需覆盖请使用 --overwrite")

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _load_optional_json(self, path: Path, warnings: List[str]) -> Dict[str, Any]:
        if not path.exists():
            warnings.append(f"可选统计文件不存在: {path}")
            return {}

        return self._load_json(path)

    @staticmethod
    def _resolve_dataset_dir(
        config: BaselineAnalysisConfig,
        baseline_report: Dict[str, Any],
    ) -> Path:
        if config.dataset_dir is not None:
            return Path(config.dataset_dir)

        dataset_dir = (
            baseline_report.get("dataset", {})
            .get("dataset_dir")
        )
        if not dataset_dir:
            raise ValueError("未提供 dataset_dir，且 baseline_report.json 中缺少 dataset.dataset_dir")

        return Path(dataset_dir)

    def _build_dataset_summary(
        self,
        baseline_report: Dict[str, Any],
        dataset_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        report_dataset = baseline_report.get("dataset", {})

        X_shape = dataset_summary.get("X_shape") or report_dataset.get("X_shape")
        y_shape = dataset_summary.get("y_shape") or report_dataset.get("y_shape")

        total_windows = (
            dataset_summary.get("total_windows")
            or dataset_summary.get("sample_count")
            or self._first_shape_dim(X_shape)
        )

        positive_count = dataset_summary.get("positive_count")
        negative_count = dataset_summary.get("negative_count")
        positive_ratio = dataset_summary.get("positive_ratio")

        if positive_ratio is None and positive_count is not None and negative_count is not None:
            total = int(positive_count) + int(negative_count)
            positive_ratio = float(positive_count) / total if total > 0 else None

        feature_dim = (
            dataset_summary.get("feature_dim")
            or self._third_shape_dim(X_shape)
        )

        return {
            "X_shape": self._shape_to_list(X_shape),
            "y_shape": self._shape_to_list(y_shape),
            "total_windows": self._to_optional_int(total_windows),
            "positive_count": self._to_optional_int(positive_count),
            "negative_count": self._to_optional_int(negative_count),
            "positive_ratio": self._to_optional_float(positive_ratio),
            "feature_dim": self._to_optional_int(feature_dim),
            "used_segment_count": self._to_optional_int(dataset_summary.get("used_segment_count")),
            "skipped_segment_count": self._to_optional_int(dataset_summary.get("skipped_segment_count")),
        }

    def _build_split_summary(
        self,
        baseline_report: Dict[str, Any],
        split_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        report_dataset = baseline_report.get("dataset", {})

        train_detail = self._extract_split_detail(
            split_summary=split_summary,
            split_name="train",
            fallback_samples=report_dataset.get("train_samples"),
        )
        val_detail = self._extract_split_detail(
            split_summary=split_summary,
            split_name="val",
            fallback_samples=report_dataset.get("val_samples"),
        )
        test_detail = self._extract_split_detail(
            split_summary=split_summary,
            split_name="test",
            fallback_samples=report_dataset.get("test_samples"),
        )

        leakage_check = split_summary.get("leakage_check", {})
        has_segment_leakage = split_summary.get("has_segment_leakage")
        if has_segment_leakage is None and isinstance(leakage_check, dict):
            has_segment_leakage = leakage_check.get("has_segment_leakage")

        return {
            "train_samples": train_detail["sample_count"],
            "val_samples": val_detail["sample_count"],
            "test_samples": test_detail["sample_count"],
            "has_segment_leakage": bool(has_segment_leakage) if has_segment_leakage is not None else None,
            "train": train_detail,
            "val": val_detail,
            "test": test_detail,
        }

    def _extract_split_detail(
        self,
        split_summary: Dict[str, Any],
        split_name: str,
        fallback_samples: Any = None,
    ) -> Dict[str, Any]:
        raw_detail = split_summary.get(split_name, {})
        if not isinstance(raw_detail, dict):
            raw_detail = {}

        sample_count = (
            raw_detail.get("sample_count")
            or raw_detail.get("samples")
            or raw_detail.get(f"{split_name}_samples")
            or fallback_samples
        )

        return {
            "sample_count": self._to_optional_int(sample_count),
            "segment_count": self._to_optional_int(raw_detail.get("segment_count")),
            "positive_count": self._to_optional_int(raw_detail.get("positive_count")),
            "negative_count": self._to_optional_int(raw_detail.get("negative_count")),
            "positive_ratio": self._to_optional_float(raw_detail.get("positive_ratio")),
        }

    @staticmethod
    def _build_training_summary(baseline_report: Dict[str, Any]) -> Dict[str, Any]:
        model = baseline_report.get("model", {})
        training = baseline_report.get("training", {})

        return {
            "model_name": model.get("name"),
            "epochs": training.get("epochs"),
            "best_epoch": training.get("best_epoch"),
            "best_metric": training.get("best_metric"),
            "best_metric_value": training.get("best_metric_value"),
            "device": training.get("device"),
            "batch_size": training.get("batch_size"),
            "lr": training.get("lr"),
            "threshold": training.get("threshold"),
        }

    def _build_final_metrics(self, baseline_report: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "train": self._json_safe(baseline_report.get("train_metrics", {})),
            "val": self._json_safe(baseline_report.get("val_metrics", {})),
            "test": self._json_safe(baseline_report.get("test_metrics", {})),
        }

    def _build_curve_summary(self, metrics_history: pd.DataFrame) -> Dict[str, Any]:
        if metrics_history.empty:
            raise ValueError("metrics_history.csv 为空，无法分析训练过程")

        first_train_loss = self._series_first(metrics_history, "train_loss")
        last_train_loss = self._series_last(metrics_history, "train_loss")
        best_val_loss = self._series_min(metrics_history, "val_loss")
        best_val_f1 = self._series_max(metrics_history, "val_f1")
        best_val_auc = self._series_max(metrics_history, "val_auc")

        loss_decreased = None
        if first_train_loss is not None and last_train_loss is not None:
            loss_decreased = bool(last_train_loss < first_train_loss)

        return {
            "first_train_loss": first_train_loss,
            "last_train_loss": last_train_loss,
            "best_val_loss": best_val_loss,
            "best_val_f1": best_val_f1,
            "best_val_auc": best_val_auc,
            "loss_decreased": loss_decreased,
        }

    def _build_prediction_summary(
        self,
        predictions: pd.DataFrame,
        threshold: float,
    ) -> Dict[str, Any]:
        if predictions.empty:
            raise ValueError("test_predictions.csv 为空，无法分析测试集预测分布")

        if "y_prob" not in predictions.columns:
            raise ValueError("test_predictions.csv 缺少 y_prob 列")

        y_prob = predictions["y_prob"].astype(float)

        if "y_pred" in predictions.columns:
            y_pred = predictions["y_pred"].astype(int)
        else:
            y_pred = (y_prob >= float(threshold)).astype(int)

        return {
            "test_prediction_rows": int(len(predictions)),
            "y_prob_min": float(y_prob.min()),
            "y_prob_max": float(y_prob.max()),
            "y_prob_mean": float(y_prob.mean()),
            "predicted_positive_ratio": float((y_pred == 1).mean()),
        }

    def _judge_trainability(
        self,
        final_metrics: Dict[str, Any],
        curve_summary: Dict[str, Any],
        prediction_summary: Dict[str, Any],
        inspection_warnings: List[Any],
        config: BaselineAnalysisConfig,
    ) -> Dict[str, Any]:
        train_metrics = final_metrics.get("train", {})
        val_metrics = final_metrics.get("val", {})
        test_metrics = final_metrics.get("test", {})

        val_auc = self._to_optional_float(val_metrics.get("auc"))
        test_auc = self._to_optional_float(test_metrics.get("auc"))
        val_f1 = self._to_optional_float(val_metrics.get("f1"))
        test_f1 = self._to_optional_float(test_metrics.get("f1"))
        val_recall = self._to_optional_float(val_metrics.get("recall"))
        test_recall = self._to_optional_float(test_metrics.get("recall"))
        test_brier = self._to_optional_float(test_metrics.get("brier_score"))

        best_auc = self._max_optional([val_auc, test_auc])
        best_f1 = self._max_optional([val_f1, test_f1])
        best_recall = self._max_optional([val_recall, test_recall])

        reasons: List[str] = []
        risks: List[str] = []
        next_steps: List[str] = []

        loss_decreased = bool(curve_summary.get("loss_decreased"))

        if best_auc is not None and best_auc >= config.auc_threshold and best_f1 is not None and best_f1 >= config.f1_threshold:
            level = "pass"
            reasons.append("验证集或测试集 AUC 与 F1 达到 baseline 可训练性参考阈值。")
            reasons.append("MLP baseline 已经证明当前窗口特征与报警标签之间存在较明确的可学习信号。")
        elif (
            best_auc is not None
            and best_auc > 0.55
        ) or (
            best_f1 is not None
            and best_f1 >= config.f1_threshold
        ) or (
            best_recall is not None
            and best_recall >= config.recall_threshold
            and loss_decreased
        ):
            level = "weak_pass"
            reasons.append("baseline 指标高于完全随机水平，说明数据集中存在一定可学习信号。")
            risks.append("F1、Recall 或 AUC 尚未同时达到较稳定水平，后续仍需优化特征、窗口或模型结构。")
        else:
            level = "fail"
            reasons.append("当前 baseline 尚未充分证明窗口数据集具有稳定可训练性。")
            risks.append("AUC 接近随机水平，或 F1/Recall 偏低，需要回查标签规则、特征选择和窗口构造策略。")

        if not loss_decreased:
            risks.append("train_loss 从首轮到末轮未明显下降，可能说明模型尚未有效学习或训练轮数不足。")

        if test_brier is not None and test_brier > config.brier_threshold:
            risks.append("测试集 Brier Score 偏高，说明概率输出质量仍需关注。")

        predicted_positive_ratio = prediction_summary.get("predicted_positive_ratio")
        if predicted_positive_ratio == 0:
            risks.append("测试集预测正样本比例为 0，模型可能退化为全预测负样本。")
        elif predicted_positive_ratio == 1:
            risks.append("测试集预测正样本比例为 1，模型可能退化为全预测正样本。")

        train_f1 = self._to_optional_float(train_metrics.get("f1"))
        val_f1_for_overfit = self._to_optional_float(val_metrics.get("f1"))
        test_f1_for_overfit = self._to_optional_float(test_metrics.get("f1"))

        if train_f1 is not None:
            compare_targets = [
                value for value in [val_f1_for_overfit, test_f1_for_overfit]
                if value is not None
            ]
            if compare_targets and train_f1 - max(compare_targets) > 0.20:
                risks.append("训练集 F1 明显高于验证集或测试集，存在过拟合风险。")

        if inspection_warnings:
            risks.append("数据集检查阶段存在 warning，建议结合 inspection_summary.json 继续核查。")

        if level == "pass":
            next_steps.append("继续推进简单 LSTM baseline，验证时序结构是否带来增益。")
            next_steps.append("继续推进 K-means 工况划分，按运行工况分析模型表现差异。")
        elif level == "weak_pass":
            next_steps.append("优先检查标签规则，确认是否仅使用第一列“报警部位”作为正负样本依据。")
            next_steps.append("尝试调整窗口长度、隐藏层维度、训练轮数和阈值，再比较 baseline 指标。")
            next_steps.append("继续补充简单 LSTM baseline，用时序模型验证是否优于展平 MLP。")
        else:
            next_steps.append("回查 y 标签生成规则，确认目标时刻报警字段是否正确对应风险标签。")
            next_steps.append("复核特征字段选择和归一化方式，排查关键字段被误删或异常压缩。")
            next_steps.append("检查 train/val/test 的正负样本比例和 segment 划分是否合理。")

        next_steps.append("后续加入 Bi-LSTM + Attention、概率校准和 MC-Dropout 前，应先保留本次 baseline 结果作为对照。")

        return {
            "is_trainable": level in {"pass", "weak_pass"},
            "level": level,
            "reasons": reasons,
            "risks": risks,
            "next_steps": next_steps,
        }

    def _render_markdown(self, analysis: Dict[str, Any], metrics_history: pd.DataFrame) -> str:
        dataset = analysis["dataset_summary"]
        split = analysis["split_summary"]
        training = analysis["training_summary"]
        final_metrics = analysis["final_metrics"]
        curve = analysis["curve_summary"]
        prediction = analysis["prediction_summary"]
        judgement = analysis["trainability_judgement"]

        lines = [
            "# RailPHM Baseline 可训练性分析报告",
            "",
            "## 1. 分析对象",
            "",
            f"- run_dir：`{analysis['run_dir']}`",
            f"- dataset_dir：`{analysis['dataset_dir']}`",
            f"- 模型名称：{self._fmt(training.get('model_name'))}",
            f"- 训练轮数：{self._fmt(training.get('epochs'))}",
            f"- batch_size：{self._fmt(training.get('batch_size'))}",
            f"- learning_rate：{self._fmt(training.get('lr'))}",
            f"- best_epoch：{self._fmt(training.get('best_epoch'))}",
            f"- best_metric：{self._fmt(training.get('best_metric'))}",
            f"- best_metric_value：{self._fmt_float(training.get('best_metric_value'))}",
            "",
            "## 2. 数据集概况",
            "",
            "| 指标 | 数值 |",
            "|---|---:|",
            f"| X_shape | {self._fmt(dataset.get('X_shape'))} |",
            f"| y_shape | {self._fmt(dataset.get('y_shape'))} |",
            f"| total_windows | {self._fmt(dataset.get('total_windows'))} |",
            f"| positive_count | {self._fmt(dataset.get('positive_count'))} |",
            f"| negative_count | {self._fmt(dataset.get('negative_count'))} |",
            f"| positive_ratio | {self._fmt_float(dataset.get('positive_ratio'))} |",
            f"| feature_dim | {self._fmt(dataset.get('feature_dim'))} |",
            f"| used_segment_count | {self._fmt(dataset.get('used_segment_count'))} |",
            f"| skipped_segment_count | {self._fmt(dataset.get('skipped_segment_count'))} |",
            "",
            "## 3. 数据划分情况",
            "",
            "| 集合 | 样本数 | segment 数 | 正样本数 | 负样本数 | 正样本比例 |",
            "|---|---:|---:|---:|---:|---:|",
        ]

        for name in ["train", "val", "test"]:
            detail = split.get(name, {})
            lines.append(
                f"| {name} | "
                f"{self._fmt(detail.get('sample_count'))} | "
                f"{self._fmt(detail.get('segment_count'))} | "
                f"{self._fmt(detail.get('positive_count'))} | "
                f"{self._fmt(detail.get('negative_count'))} | "
                f"{self._fmt_float(detail.get('positive_ratio'))} |"
            )

        leakage = split.get("has_segment_leakage")
        if leakage is False:
            leakage_text = "未发现 segment 泄露。"
        elif leakage is True:
            leakage_text = "发现 segment 泄露，需要重新划分数据集。"
        else:
            leakage_text = "未能从 split_summary.json 中确认 segment 泄露状态。"

        lines.extend(
            [
                "",
                f"segment 泄露检查结论：{leakage_text}",
                "",
                "## 4. 训练过程概况",
                "",
                f"- train_loss 是否下降：{self._fmt_bool(curve.get('loss_decreased'))}",
                f"- 首轮 train_loss：{self._fmt_float(curve.get('first_train_loss'))}",
                f"- 末轮 train_loss：{self._fmt_float(curve.get('last_train_loss'))}",
                f"- 最低 val_loss：{self._fmt_float(curve.get('best_val_loss'))}",
                f"- 最高 val_f1：{self._fmt_float(curve.get('best_val_f1'))}",
                f"- 最高 val_auc：{self._fmt_float(curve.get('best_val_auc'))}",
                f"- best_epoch：{self._fmt(training.get('best_epoch'))}",
                "",
                "| epoch | train_loss | val_loss | val_accuracy | val_precision | val_recall | val_f1 | val_auc | val_brier_score |",
                "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )

        history_view = self._history_for_markdown(metrics_history)
        for _, row in history_view.iterrows():
            lines.append(
                f"| {self._fmt(row.get('epoch'))} | "
                f"{self._fmt_float(row.get('train_loss'))} | "
                f"{self._fmt_float(row.get('val_loss'))} | "
                f"{self._fmt_float(row.get('val_accuracy'))} | "
                f"{self._fmt_float(row.get('val_precision'))} | "
                f"{self._fmt_float(row.get('val_recall'))} | "
                f"{self._fmt_float(row.get('val_f1'))} | "
                f"{self._fmt_float(row.get('val_auc'))} | "
                f"{self._fmt_float(row.get('val_brier_score'))} |"
            )

        lines.extend(
            [
                "",
                "## 5. 最终评估指标",
                "",
                "| 集合 | accuracy | precision | recall | f1 | auc | brier_score |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )

        for name in ["train", "val", "test"]:
            metrics = final_metrics.get(name, {})
            lines.append(
                f"| {name} | "
                f"{self._fmt_float(metrics.get('accuracy'))} | "
                f"{self._fmt_float(metrics.get('precision'))} | "
                f"{self._fmt_float(metrics.get('recall'))} | "
                f"{self._fmt_float(metrics.get('f1'))} | "
                f"{self._fmt_float(metrics.get('auc'))} | "
                f"{self._fmt_float(metrics.get('brier_score'))} |"
            )

        lines.extend(
            [
                "",
                "## 6. 测试集预测分布",
                "",
                f"- y_prob_min：{self._fmt_float(prediction.get('y_prob_min'))}",
                f"- y_prob_max：{self._fmt_float(prediction.get('y_prob_max'))}",
                f"- y_prob_mean：{self._fmt_float(prediction.get('y_prob_mean'))}",
                f"- predicted_positive_ratio：{self._fmt_float(prediction.get('predicted_positive_ratio'))}",
                "",
            ]
        )

        predicted_positive_ratio = prediction.get("predicted_positive_ratio")
        if predicted_positive_ratio == 0:
            lines.append("测试集预测正样本比例为 0，模型可能存在全预测负样本的问题。")
            lines.append("")
        elif predicted_positive_ratio == 1:
            lines.append("测试集预测正样本比例为 1，模型可能存在全预测正样本的问题。")
            lines.append("")

        lines.extend(
            [
                "## 7. 可训练性结论",
                "",
                f"- 判断等级：**{judgement.get('level')}**",
                f"- 是否具备基本可训练性：**{self._fmt_bool(judgement.get('is_trainable'))}**",
                "",
                self._conclusion_text(judgement),
                "",
                "主要依据：",
                "",
            ]
        )

        for reason in judgement.get("reasons", []):
            lines.append(f"- {reason}")

        lines.extend(
            [
                "",
                "## 8. 风险与后续建议",
                "",
                "### 风险提示",
                "",
            ]
        )

        risks = judgement.get("risks", [])
        if risks:
            for risk in risks:
                lines.append(f"- {risk}")
        else:
            lines.append("- 当前自动分析未发现明显风险，但仍建议结合训练曲线和数据构造过程人工复核。")

        lines.extend(
            [
                "",
                "### 后续建议",
                "",
            ]
        )

        for step in judgement.get("next_steps", []):
            lines.append(f"- {step}")

        warnings = analysis.get("warnings", [])
        if warnings:
            lines.extend(
                [
                    "",
                    "### 附加 warnings",
                    "",
                ]
            )
            for warning in warnings:
                lines.append(f"- {warning}")

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _conclusion_text(judgement: Dict[str, Any]) -> str:
        level = judgement.get("level")

        if level == "pass":
            return (
                "当前 MLP baseline 在验证集或测试集上取得了高于随机水平且较稳定的指标，"
                "说明当前由 ATP segment CSV 构建的窗口样本与报警标签之间存在较明确的可学习关系。"
                "因此，当前数据集可以继续用于后续工况划分、LSTM/Bi-LSTM + Attention 模型开发和概率校准实验。"
            )

        if level == "weak_pass":
            return (
                "当前 MLP baseline 已经表现出一定可学习信号，但 F1、Recall、AUC 或概率质量仍不够稳定。"
                "因此，可以认为当前数据集具备初步可训练性，但在进入复杂模型前，仍建议继续复核标签规则、窗口长度、"
                "特征字段选择和阈值设置。"
            )

        return (
            "当前 MLP baseline 尚未充分证明数据集具有稳定可学习性。模型在验证集或测试集上的 AUC、F1、Recall "
            "表现偏弱，说明需要进一步检查标签规则、窗口长度、特征字段选择、归一化方式以及 train/val/test 划分策略。"
        )

    @staticmethod
    def _history_for_markdown(metrics_history: pd.DataFrame) -> pd.DataFrame:
        if len(metrics_history) <= 12:
            return metrics_history

        head = metrics_history.head(5)
        tail = metrics_history.tail(5)
        return pd.concat([head, tail], ignore_index=True)

    @staticmethod
    def _save_json(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _series_first(df: pd.DataFrame, column: str) -> float | None:
        if column not in df.columns or df[column].dropna().empty:
            return None
        return float(df[column].dropna().iloc[0])

    @staticmethod
    def _series_last(df: pd.DataFrame, column: str) -> float | None:
        if column not in df.columns or df[column].dropna().empty:
            return None
        return float(df[column].dropna().iloc[-1])

    @staticmethod
    def _series_min(df: pd.DataFrame, column: str) -> float | None:
        if column not in df.columns or df[column].dropna().empty:
            return None
        return float(df[column].dropna().min())

    @staticmethod
    def _series_max(df: pd.DataFrame, column: str) -> float | None:
        if column not in df.columns or df[column].dropna().empty:
            return None
        return float(df[column].dropna().max())

    @staticmethod
    def _get_threshold(baseline_report: Dict[str, Any]) -> float:
        test_metrics = baseline_report.get("test_metrics", {})
        training = baseline_report.get("training", {})

        threshold = test_metrics.get("threshold", training.get("threshold", 0.5))
        return float(threshold)

    @staticmethod
    def _shape_to_list(value: Any) -> List[int] | None:
        if value is None:
            return None
        return [int(item) for item in value]

    @staticmethod
    def _first_shape_dim(value: Any) -> int | None:
        if not value:
            return None
        return int(value[0])

    @staticmethod
    def _third_shape_dim(value: Any) -> int | None:
        if not value or len(value) < 3:
            return None
        return int(value[2])

    @staticmethod
    def _max_optional(values: List[float | None]) -> float | None:
        valid_values = [value for value in values if value is not None]
        if not valid_values:
            return None
        return max(valid_values)

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        if value is None or BaselineAnalyzer._is_nan(value):
            return None
        return int(value)

    @staticmethod
    def _to_optional_float(value: Any) -> float | None:
        if value is None or BaselineAnalyzer._is_nan(value):
            return None
        return float(value)

    @staticmethod
    def _is_nan(value: Any) -> bool:
        try:
            return bool(pd.isna(value))
        except TypeError:
            return False

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}

        if isinstance(value, list):
            return [self._json_safe(item) for item in value]

        if isinstance(value, tuple):
            return [self._json_safe(item) for item in value]

        if isinstance(value, np.integer):
            return int(value)

        if isinstance(value, np.floating):
            if math.isnan(float(value)):
                return None
            return float(value)

        if isinstance(value, float):
            if math.isnan(value):
                return None
            return value

        if isinstance(value, (int, str, bool)):
            return value

        return value

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None:
            return "-"
        return str(value)

    @staticmethod
    def _fmt_float(value: Any) -> str:
        if value is None or BaselineAnalyzer._is_nan(value):
            return "-"
        return f"{float(value):.6f}"

    @staticmethod
    def _fmt_bool(value: Any) -> str:
        if value is True:
            return "是"
        if value is False:
            return "否"
        return "-"