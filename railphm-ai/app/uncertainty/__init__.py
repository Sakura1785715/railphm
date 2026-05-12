"""
RailPHM 不确定性估计模块。

本包用于承载预测阶段的不确定性估计能力。当前阶段实现 MC-Dropout
相关工具函数，供 SequenceModelRuntime 在运行时进行多次随机前向传播，
计算风险概率均值和标准差。

本包不负责模型训练、不修改模型结构、不保存采样明细，也不接入 /infer。
"""

from app.uncertainty.mc_dropout import (
    collect_mc_dropout_probabilities,
    enable_dropout_for_inference,
    summarize_probabilities,
)

__all__ = [
    "enable_dropout_for_inference",
    "collect_mc_dropout_probabilities",
    "summarize_probabilities",
]