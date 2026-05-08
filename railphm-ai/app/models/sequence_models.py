"""
时序故障风险预测模型结构。

本模块只定义面向三维窗口输入的 LSTM / Bi-LSTM / Attention 分类模型，
不包含数据读取、训练逻辑、指标计算、概率校准或 Flask 推理接口。
"""

from __future__ import annotations

import math
from typing import Callable

import torch
from torch import nn


def _validate_positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_dropout(dropout: float) -> None:
    if (
        isinstance(dropout, bool)
        or not isinstance(dropout, (int, float))
        or not math.isfinite(float(dropout))
        or float(dropout) < 0
        or float(dropout) >= 1
    ):
        raise ValueError("dropout must satisfy 0 <= dropout < 1")


class TemporalAttention(nn.Module):
    """
    轻量级时间步注意力层。

    输入：
        lstm_outputs: [batch_size, window_size, attention_dim]

    输出：
        context: [batch_size, attention_dim]
        attention_weights: [batch_size, window_size]
    """

    def __init__(self, attention_dim: int) -> None:
        super().__init__()
        _validate_positive_int(attention_dim, "attention_dim")

        self.attention_dim = int(attention_dim)
        self.score_layer = nn.Linear(self.attention_dim, 1)

    def forward(self, lstm_outputs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if not isinstance(lstm_outputs, torch.Tensor):
            raise ValueError("TemporalAttention input must be a torch.Tensor")

        if lstm_outputs.ndim != 3:
            raise ValueError(
                "TemporalAttention input must be 3D: "
                "[batch_size, window_size, attention_dim]"
            )

        if lstm_outputs.shape[-1] != self.attention_dim:
            raise ValueError("TemporalAttention attention_dim mismatch")

        scores = self.score_layer(lstm_outputs).squeeze(-1)
        attention_weights = torch.softmax(scores, dim=1)
        context = torch.sum(lstm_outputs * attention_weights.unsqueeze(-1), dim=1)

        return context, attention_weights


class _BaseSequenceClassifier(nn.Module):
    """时序分类模型公共参数与输入校验。"""

    model_name = "BaseSequenceClassifier"
    bidirectional = False
    attention = False

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        num_layers: int = 1,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()

        _validate_positive_int(input_dim, "input_dim")
        _validate_positive_int(hidden_dim, "hidden_dim")
        _validate_positive_int(num_layers, "num_layers")
        _validate_dropout(dropout)

        self.input_dim = int(input_dim)
        self.hidden_dim = int(hidden_dim)
        self.num_layers = int(num_layers)
        self.dropout = float(dropout)

        lstm_dropout = self.dropout if self.num_layers > 1 else 0.0
        self.lstm = nn.LSTM(
            input_size=self.input_dim,
            hidden_size=self.hidden_dim,
            num_layers=self.num_layers,
            dropout=lstm_dropout,
            batch_first=True,
            bidirectional=self.bidirectional,
        )

        self.output_dim = self.hidden_dim * 2 if self.bidirectional else self.hidden_dim
        self.dropout_layer = nn.Dropout(self.dropout)
        self.classifier = nn.Linear(self.output_dim, 1)

    def _validate_sequence_input(self, x: torch.Tensor) -> None:
        if not isinstance(x, torch.Tensor):
            raise ValueError("Sequence model input must be a torch.Tensor")

        if x.ndim != 3:
            raise ValueError(
                "Sequence model input must be 3D: "
                "[batch_size, window_size, input_dim]"
            )

        if x.shape[-1] != self.input_dim:
            raise ValueError("Sequence model input_dim mismatch")

    def _last_hidden(self, hidden_state: torch.Tensor) -> torch.Tensor:
        if self.bidirectional:
            forward_hidden = hidden_state[-2]
            backward_hidden = hidden_state[-1]
            return torch.cat([forward_hidden, backward_hidden], dim=1)

        return hidden_state[-1]

    def _classify(self, features: torch.Tensor) -> torch.Tensor:
        logits = self.classifier(self.dropout_layer(features)).squeeze(-1)
        return logits

    def get_config(self) -> dict:
        return {
            "name": self.model_name,
            "input_dim": int(self.input_dim),
            "hidden_dim": int(self.hidden_dim),
            "num_layers": int(self.num_layers),
            "dropout": float(self.dropout),
            "bidirectional": bool(self.bidirectional),
            "attention": bool(self.attention),
        }


class LSTMClassifier(_BaseSequenceClassifier):
    """单向 LSTM 二分类模型。"""

    model_name = "LSTMClassifier"
    bidirectional = False
    attention = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        self._validate_sequence_input(x)
        _, (hidden_state, _) = self.lstm(x)
        features = self._last_hidden(hidden_state)
        return self._classify(features)


class BiLSTMClassifier(_BaseSequenceClassifier):
    """双向 LSTM 二分类模型。"""

    model_name = "BiLSTMClassifier"
    bidirectional = True
    attention = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        self._validate_sequence_input(x)
        _, (hidden_state, _) = self.lstm(x)
        features = self._last_hidden(hidden_state)
        return self._classify(features)


class LSTMAttentionClassifier(_BaseSequenceClassifier):
    """单向 LSTM + 时间步注意力二分类模型。"""

    model_name = "LSTMAttentionClassifier"
    bidirectional = False
    attention = True

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        num_layers: int = 1,
        dropout: float = 0.2,
    ) -> None:
        super().__init__(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout,
        )
        self.attention_layer = TemporalAttention(self.output_dim)

    def forward(self, x: torch.Tensor, return_attention: bool = False):
        self._validate_sequence_input(x)
        output_seq, _ = self.lstm(x)
        context, attention_weights = self.attention_layer(output_seq)
        logits = self._classify(context)

        if return_attention:
            return logits, attention_weights

        return logits


class BiLSTMAttentionClassifier(_BaseSequenceClassifier):
    """双向 LSTM + 时间步注意力二分类模型。"""

    model_name = "BiLSTMAttentionClassifier"
    bidirectional = True
    attention = True

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        num_layers: int = 1,
        dropout: float = 0.2,
    ) -> None:
        super().__init__(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout,
        )
        self.attention_layer = TemporalAttention(self.output_dim)

    def forward(self, x: torch.Tensor, return_attention: bool = False):
        self._validate_sequence_input(x)
        output_seq, _ = self.lstm(x)
        context, attention_weights = self.attention_layer(output_seq)
        logits = self._classify(context)

        if return_attention:
            return logits, attention_weights

        return logits


def build_sequence_model(
    model_name: str,
    input_dim: int,
    hidden_dim: int = 64,
    num_layers: int = 1,
    dropout: float = 0.2,
) -> _BaseSequenceClassifier:
    """根据模型名称构造时序分类模型。"""
    model_map: dict[str, Callable[..., _BaseSequenceClassifier]] = {
        "lstm": LSTMClassifier,
        "bilstm": BiLSTMClassifier,
        "lstm_attention": LSTMAttentionClassifier,
        "bilstm_attention": BiLSTMAttentionClassifier,
    }

    if model_name not in model_map:
        supported = ", ".join(sorted(model_map.keys()))
        raise ValueError(
            f"Unsupported sequence model: {model_name}. "
            f"Supported models: {supported}"
        )

    model_class = model_map[model_name]
    return model_class(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        dropout=dropout,
    )