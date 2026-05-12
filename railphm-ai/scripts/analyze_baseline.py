#!/usr/bin/env python3
"""
baseline 训练结果分析命令行入口。

本脚本只负责：
1. 解析命令行参数；
2. 构造 BaselineAnalysisConfig；
3. 调用 BaselineAnalyzer；
4. 打印核心分析结果。

分析核心逻辑不写在 scripts 中。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.training.baseline_analyzer import BaselineAnalysisConfig, BaselineAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze RailPHM baseline training outputs and generate trainability report."
    )

    parser.add_argument("--run-dir", type=Path, required=True, help="Task 4-4 baseline 训练输出目录")
    parser.add_argument("--dataset-dir", type=Path, default=None, help="数据集目录；不传则从 baseline_report.json 中读取")
    parser.add_argument("--output-json", type=Path, default=None, help="分析 JSON 输出路径")
    parser.add_argument("--output-markdown", type=Path, default=None, help="分析 Markdown 输出路径")
    parser.add_argument("--auc-threshold", type=float, default=0.60, help="AUC 可训练性参考阈值")
    parser.add_argument("--f1-threshold", type=float, default=0.30, help="F1 可训练性参考阈值")
    parser.add_argument("--recall-threshold", type=float, default=0.30, help="Recall 可训练性参考阈值")
    parser.add_argument("--brier-threshold", type=float, default=0.25, help="Brier Score 风险参考阈值")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的分析报告")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = BaselineAnalysisConfig(
            run_dir=args.run_dir,
            dataset_dir=args.dataset_dir,
            output_json=args.output_json,
            output_markdown=args.output_markdown,
            auc_threshold=args.auc_threshold,
            f1_threshold=args.f1_threshold,
            recall_threshold=args.recall_threshold,
            brier_threshold=args.brier_threshold,
            overwrite=args.overwrite,
        )

        analysis = BaselineAnalyzer().analyze(config)

        judgement = analysis["trainability_judgement"]
        artifacts = analysis["artifacts"]
        test_metrics = analysis["final_metrics"]["test"]

        print("Baseline analysis finished.")
        print(f"baseline_analysis.json: {artifacts['baseline_analysis_json']}")
        print(f"baseline_analysis.md: {artifacts['baseline_analysis_markdown']}")
        print(f"trainability level: {judgement['level']}")
        print(f"is_trainable: {judgement['is_trainable']}")
        print(
            "test_metrics: "
            f"accuracy={test_metrics.get('accuracy')}, "
            f"precision={test_metrics.get('precision')}, "
            f"recall={test_metrics.get('recall')}, "
            f"f1={test_metrics.get('f1')}, "
            f"auc={test_metrics.get('auc')}, "
            f"brier_score={test_metrics.get('brier_score')}"
        )

        return 0

    except Exception as exc:
        print(f"baseline 分析失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())