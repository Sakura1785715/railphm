"""
MLP baseline 模型定义。

BaselineMLP 用于 RailPHM 二分类风险预测任务的 baseline 可训练性验证。
该模型接收已经展平的窗口特征：

    x.shape = [batch_size, input_dim]

其中 input_dim = window_size * feature_dim。
例如当前真实窗口数据集为 window_size=30、feature_dim=25，则 input_dim=750。

模型输出为二分类 logits：

    logits.shape = [batch_size]

- 后续训练时应使用 torch.nn.BCEWithLogitsLoss。
- 评估时再使用 torch.sigmoid(logits) 得到风险概率 y_prob。
"""

import math
from typing import Sequence

import torch
from torch import nn


class BaselineMLP(nn.Module):
    """
    用于窗口数据集可训练性验证的 MLP baseline。

    参数：
        input_dim: 展平后的输入特征维度。
        hidden_dims: 隐藏层维度列表或元组，例如 (128, 64)。
        dropout: Dropout 概率，必须满足 0 <= dropout < 1。
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dims: Sequence[int] = (128, 64),
        dropout: float = 0.2,
    ) -> None:
        super().__init__()

        self._validate_init_args(input_dim, hidden_dims, dropout)

        self.input_dim = int(input_dim)
        self.hidden_dims = tuple(int(dim) for dim in hidden_dims)
        self.dropout = float(dropout)

        layers: list[nn.Module] = []
        previous_dim = self.input_dim

        for hidden_dim in self.hidden_dims:
            layers.append(nn.Linear(previous_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(self.dropout))
            previous_dim = hidden_dim

        layers.append(nn.Linear(previous_dim, 1))

        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播。

        输入：
            x: shape 为 [batch_size, input_dim] 的二维张量。

        输出：
            logits: shape 为 [batch_size] 的一维张量。
        """
        if not isinstance(x, torch.Tensor):
            raise ValueError("BaselineMLP 输入必须为 torch.Tensor")

        if x.ndim != 2:
            raise ValueError("BaselineMLP 输入必须为二维张量 [batch_size, input_dim]")

        if x.shape[1] != self.input_dim:
            raise ValueError("BaselineMLP 输入特征维度不匹配")

        logits = self.network(x)
        return logits.squeeze(-1)

    def get_config(self) -> dict:
        """
        返回模型配置，便于后续写入 baseline 训练报告。
        """
        return {
            "name": "BaselineMLP",
            "input_dim": int(self.input_dim),
            "hidden_dims": [int(dim) for dim in self.hidden_dims],
            "dropout": float(self.dropout),
        }

    @staticmethod
    def _validate_init_args(
        input_dim: int,
        hidden_dims: Sequence[int],
        dropout: float,
    ) -> None:
        if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim <= 0:
            raise ValueError("input_dim 必须为正整数")

        if hidden_dims is None or not isinstance(hidden_dims, (list, tuple)) or len(hidden_dims) == 0:
            raise ValueError("hidden_dims 不能为空")

        for dim in hidden_dims:
            if isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0:
                raise ValueError("hidden_dims 中的每个维度都必须为正整数")

        if (
            isinstance(dropout, bool)
            or not isinstance(dropout, (int, float))
            or not math.isfinite(float(dropout))
            or float(dropout) < 0
            or float(dropout) >= 1
        ):
            raise ValueError("dropout 必须满足 0 <= dropout < 1")