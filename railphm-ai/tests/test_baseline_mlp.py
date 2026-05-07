"""
BaselineMLP 单元测试。

测试内容只覆盖 MLP baseline 模型定义本身：
- forward 输出形状
- 自定义隐藏层结构
- 最后一层不使用 Sigmoid
- BCEWithLogitsLoss 反向传播
- 参数数量
- get_config 配置导出
- 初始化参数异常
- forward 输入异常

本测试不依赖真实数据集，不实现训练循环，不保存模型文件。
"""

import numpy as np
import pytest
import torch

from app.models.baseline_mlp import BaselineMLP


def test_baseline_mlp_forward_shape():
    model = BaselineMLP(input_dim=750)
    x = torch.randn(8, 750)

    logits = model(x)

    assert logits.shape == (8,)


def test_baseline_mlp_forward_with_custom_hidden_dims():
    model = BaselineMLP(input_dim=12, hidden_dims=(16, 8), dropout=0.1)
    x = torch.randn(4, 12)

    logits = model(x)

    assert logits.shape == (4,)


def test_baseline_mlp_outputs_logits_not_probabilities():
    model = BaselineMLP(input_dim=10)

    assert not any(isinstance(module, torch.nn.Sigmoid) for module in model.modules())


def test_baseline_mlp_backward_success():
    model = BaselineMLP(input_dim=10)
    x = torch.randn(6, 10)
    y = torch.tensor([0, 1, 0, 1, 0, 1], dtype=torch.float32)

    criterion = torch.nn.BCEWithLogitsLoss()
    logits = model(x)
    loss = criterion(logits, y)
    loss.backward()

    assert torch.isfinite(loss).item()
    assert any(parameter.grad is not None for parameter in model.parameters())


def test_baseline_mlp_parameter_count_positive():
    model = BaselineMLP(input_dim=750)

    parameter_count = sum(parameter.numel() for parameter in model.parameters())

    assert parameter_count > 0


def test_baseline_mlp_get_config():
    model = BaselineMLP(input_dim=750, hidden_dims=(128, 64), dropout=0.2)

    config = model.get_config()

    assert config == {
        "name": "BaselineMLP",
        "input_dim": 750,
        "hidden_dims": [128, 64],
        "dropout": 0.2,
    }
    assert isinstance(config["input_dim"], int)
    assert isinstance(config["hidden_dims"], list)
    assert all(isinstance(dim, int) for dim in config["hidden_dims"])
    assert isinstance(config["dropout"], float)


@pytest.mark.parametrize("input_dim", [0, -1, "750", True])
def test_invalid_input_dim(input_dim):
    with pytest.raises(ValueError, match="input_dim 必须为正整数"):
        BaselineMLP(input_dim=input_dim)


@pytest.mark.parametrize("hidden_dims", [(), []])
def test_invalid_hidden_dims_empty(hidden_dims):
    with pytest.raises(ValueError, match="hidden_dims 不能为空"):
        BaselineMLP(input_dim=10, hidden_dims=hidden_dims)


@pytest.mark.parametrize(
    "hidden_dims",
    [
        (128, 0),
        (128, -1),
        (128, "64"),
        (128, True),
    ],
)
def test_invalid_hidden_dims_value(hidden_dims):
    with pytest.raises(ValueError, match="hidden_dims 中的每个维度都必须为正整数"):
        BaselineMLP(input_dim=10, hidden_dims=hidden_dims)


@pytest.mark.parametrize("dropout", [-0.1, 1.0, 1.5, True, float("nan")])
def test_invalid_dropout(dropout):
    with pytest.raises(ValueError, match="dropout 必须满足 0 <= dropout < 1"):
        BaselineMLP(input_dim=10, dropout=dropout)


@pytest.mark.parametrize(
    "invalid_input",
    [
        [[1.0, 2.0, 3.0]],
        np.array([[1.0, 2.0, 3.0]], dtype=np.float32),
    ],
)
def test_forward_rejects_non_tensor(invalid_input):
    model = BaselineMLP(input_dim=3)

    with pytest.raises(ValueError, match="BaselineMLP 输入必须为 torch.Tensor"):
        model(invalid_input)


def test_forward_rejects_wrong_dimension():
    model = BaselineMLP(input_dim=12)
    x = torch.randn(2, 4, 3)

    with pytest.raises(ValueError, match="BaselineMLP 输入必须为二维张量"):
        model(x)


def test_forward_rejects_feature_dim_mismatch():
    model = BaselineMLP(input_dim=10)
    x = torch.randn(4, 9)

    with pytest.raises(ValueError, match="BaselineMLP 输入特征维度不匹配"):
        model(x)