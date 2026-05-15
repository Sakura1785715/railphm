#!/usr/bin/env python3
"""
统一时序模型训练命令行入口。

本脚本只负责：
1. 解析命令行参数；
2. 构造 SequenceTrainConfig；
3. 调用 app.training.train_sequence_model.train_sequence_model；
4. 打印关键训练结果。

训练核心逻辑不写在 scripts 中。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.training.train_sequence_model import SequenceTrainConfig, train_sequence_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train RailPHM sequence risk prediction models."
    )
    # 训练数据集目录
    parser.add_argument("--dataset-dir", type=Path, required=True, help="窗口数据集目录")
    # 训练结果输出目录
    parser.add_argument("--output-dir", type=Path, required=True, help="训练结果输出目录")
    parser.add_argument(
        "--model",
        type=str,
        default="bilstm_attention",
        choices=["lstm", "bilstm", "lstm_attention", "bilstm_attention"],
        help="时序模型名称",
    )
    # 训练轮数
    parser.add_argument("--epochs", type=int, default=30, help="训练轮数")
    # --batch-size：批大小（每次训练多少个样本）
    parser.add_argument("--batch-size", type=int, default=256, help="batch size")
    # --lr：学习率（默认0.001）
    parser.add_argument("--lr", type=float, default=0.001, help="学习率")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help="训练设备",
    )
    # --threshold：二分类阈值
    parser.add_argument("--threshold", type=float, default=0.5, help="二分类阈值")
    # LSTM 隐藏层维度（默认64）
    parser.add_argument("--hidden-dim", type=int, default=64, help="LSTM hidden_dim")
    # --num-layers：LSTM 层数
    parser.add_argument("--num-layers", type=int, default=1, help="LSTM num_layers")
    # Dropout 概率（默认0.2)
    parser.add_argument("--dropout", type=float, default=0.2, help="Dropout 概率")
    # 评价指标
    parser.add_argument("--num-workers", type=int, default=0, help="DataLoader num_workers")
    parser.add_argument(
        "--best-metric",
        type=str,
        default="val_auc",
        choices=["val_f1", "val_auc", "val_loss"],
        help="最优模型选择指标",
    )
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出目录")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = SequenceTrainConfig(
            dataset_dir=args.dataset_dir,
            output_dir=args.output_dir,
            model=args.model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            seed=args.seed,
            device=args.device,
            threshold=args.threshold,
            hidden_dim=args.hidden_dim,
            num_layers=args.num_layers,
            dropout=args.dropout,
            num_workers=args.num_workers,
            overwrite=args.overwrite,
            best_metric=args.best_metric,
        )

        report = train_sequence_model(config)

        print("\nSequence model training finished.")
        print(f"output_dir: {args.output_dir}")
        print(f"model: {report['model']['name']}")
        print(f"best_epoch: {report['training']['best_epoch']}")
        print(f"best_metric: {report['training']['best_metric']}")
        print(f"best_metric_value: {report['training']['best_metric_value']}")

        val_metrics = report["val_metrics"]
        test_metrics = report["test_metrics"]

        print(
            "val_metrics: "
            f"loss={val_metrics['loss']:.4f}, "
            f"f1={val_metrics['f1']:.4f}, "
            f"auc={val_metrics['auc']}"
        )
        print(
            "test_metrics: "
            f"loss={test_metrics['loss']:.4f}, "
            f"f1={test_metrics['f1']:.4f}, "
            f"auc={test_metrics['auc']}"
        )

        print("artifacts:")
        for _, relative_path in report["artifacts"].items():
            print(f"  - {args.output_dir / relative_path}")
        print(f"  - {args.output_dir / 'sequence_model_report.json'}")

        return 0

    except Exception as exc:
        print(f"时序模型训练失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

