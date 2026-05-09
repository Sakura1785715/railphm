"""
MC-Dropout 不确定性估计工具函数。

本文件只实现 MC-Dropout 的通用运行时逻辑：
1. 在推理阶段仅启用 Dropout 层；
2. 执行多次随机前向传播；
3. 汇总原始概率和可选校准概率的均值、标准差。

本文件不修改模型结构，不更新模型权重，不保存采样明细文件，也不接入接口层。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch


DROPOUT_TYPES = (
    torch.nn.Dropout,
    torch.nn.Dropout1d,
    torch.nn.Dropout2d,
    torch.nn.Dropout3d,
    torch.nn.AlphaDropout,
)


def enable_dropout_for_inference(model: torch.nn.Module) -> int:
    """
    在推理阶段仅启用模型中的 Dropout 层。

    注意：
    - 不调用整个 model.train()；
    - 只将 Dropout 层切换为 train；
    - 不修改模型参数；
    - 返回被切换的 Dropout 层数量。
    """
    dropout_count = 0

    for module in model.modules():
        if isinstance(module, DROPOUT_TYPES):
            module.train()
            dropout_count += 1

    return dropout_count


def collect_mc_dropout_probabilities(
    model: torch.nn.Module,
    input_tensor: torch.Tensor,
    mc_samples: int,
) -> np.ndarray:
    """
    执行多次 MC-Dropout 随机前向传播，收集原始风险概率。

    Args:
        model:
            已加载的 PyTorch 模型。
        input_tensor:
            已放置到正确 device 上的输入张量，形状应为
            [1, window_size, feature_dim]。
        mc_samples:
            MC-Dropout 随机前向传播次数。

    Returns:
        shape=[mc_samples] 的 numpy.ndarray，每个元素为一次 forward 后
        sigmoid 得到的原始风险概率。
    """
    _validate_mc_samples(mc_samples)

    if not isinstance(input_tensor, torch.Tensor):
        raise ValueError("input_tensor must be a torch.Tensor")

    if input_tensor.ndim != 3:
        raise ValueError(
            "input_tensor must be 3D with shape [1, window_size, feature_dim]"
        )

    if input_tensor.shape[0] != 1:
        raise ValueError("input_tensor batch size must be 1")

    probs: list[float] = []

    model.eval()
    enable_dropout_for_inference(model)

    try:
        with torch.no_grad():
            for _ in range(mc_samples):
                logits = model(input_tensor).view(-1)
                if logits.numel() != 1:
                    raise ValueError(
                        f"model output should contain one logit, got {logits.numel()}"
                    )

                prob = torch.sigmoid(logits)[0]
                prob_value = float(prob.detach().cpu().item())
                probs.append(prob_value)
    finally:
        model.eval()

    raw_probs = np.asarray(probs, dtype=np.float64)
    _validate_probability_array(raw_probs, name="raw_probs")

    return raw_probs


def summarize_probabilities(
    raw_probs: Any,
    calibrated_probs: Any | None = None,
) -> dict[str, float]:
    """
    汇总 MC-Dropout 概率数组，计算风险均值和不确定性标准差。

    如果 calibrated_probs 为 None：
        risk_score = risk_raw
        risk_std = risk_raw_std

    如果 calibrated_probs 存在：
        risk_score = mean(calibrated_probs)
        risk_std = std(calibrated_probs)
    """
    raw_array = _validate_probability_array(raw_probs, name="raw_probs")

    risk_raw = float(np.mean(raw_array))
    risk_raw_std = float(np.std(raw_array, ddof=0))

    if calibrated_probs is None:
        return {
            "risk_raw": risk_raw,
            "risk_raw_std": risk_raw_std,
            "risk_score": risk_raw,
            "risk_std": risk_raw_std,
        }

    calibrated_array = _validate_probability_array(
        calibrated_probs,
        name="calibrated_probs",
    )

    if calibrated_array.shape[0] != raw_array.shape[0]:
        raise ValueError(
            "raw_probs and calibrated_probs must have the same length: "
            f"raw_probs={raw_array.shape[0]}, "
            f"calibrated_probs={calibrated_array.shape[0]}"
        )

    return {
        "risk_raw": risk_raw,
        "risk_raw_std": risk_raw_std,
        "risk_score": float(np.mean(calibrated_array)),
        "risk_std": float(np.std(calibrated_array, ddof=0)),
    }


def _validate_mc_samples(mc_samples: int) -> None:
    """校验 MC 采样次数。"""
    if isinstance(mc_samples, bool) or not isinstance(mc_samples, int):
        raise ValueError("mc_samples must be a positive integer")

    if mc_samples <= 0:
        raise ValueError("mc_samples must be a positive integer")

    if mc_samples > 1000:
        raise ValueError("mc_samples must be <= 1000 to avoid slow inference")


def _validate_probability_array(values: Any, name: str) -> np.ndarray:
    """校验概率数组为一维有限数组，且全部位于 [0, 1]。"""
    array = np.asarray(values, dtype=np.float64)

    if array.ndim != 1:
        raise ValueError(f"{name} must be a 1D array")

    if array.shape[0] == 0:
        raise ValueError(f"{name} must not be empty")

    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")

    if (array < 0).any() or (array > 1).any():
        raise ValueError(f"{name} must be within [0, 1]")

    return array