"""
MC-Dropout 工具函数测试。

本测试只验证 app/uncertainty/mc_dropout.py 中的通用函数，不依赖真实模型产物，
不读取真实 best_model.pt，也不保存采样结果文件。
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from app.uncertainty import (
    collect_mc_dropout_probabilities,
    enable_dropout_for_inference,
    summarize_probabilities,
)


def test_summarize_probabilities_without_calibration() -> None:
    raw_probs = np.array([0.2, 0.4, 0.6])

    summary = summarize_probabilities(raw_probs)

    assert summary["risk_raw"] == pytest.approx(np.mean(raw_probs))
    assert summary["risk_score"] == pytest.approx(summary["risk_raw"])
    assert summary["risk_raw_std"] == pytest.approx(np.std(raw_probs, ddof=0))
    assert summary["risk_std"] == pytest.approx(summary["risk_raw_std"])


def test_summarize_probabilities_with_calibration() -> None:
    raw_probs = np.array([0.2, 0.4, 0.6])
    calibrated_probs = np.array([0.1, 0.5, 0.9])

    summary = summarize_probabilities(raw_probs, calibrated_probs)

    assert summary["risk_raw"] == pytest.approx(np.mean(raw_probs))
    assert summary["risk_score"] == pytest.approx(np.mean(calibrated_probs))
    assert summary["risk_raw_std"] == pytest.approx(np.std(raw_probs, ddof=0))
    assert summary["risk_std"] == pytest.approx(np.std(calibrated_probs, ddof=0))


def test_summarize_probabilities_rejects_nan() -> None:
    raw_probs = np.array([0.2, np.nan, 0.6])

    with pytest.raises(ValueError, match="finite"):
        summarize_probabilities(raw_probs)


def test_summarize_probabilities_rejects_inf() -> None:
    raw_probs = np.array([0.2, np.inf, 0.6])

    with pytest.raises(ValueError, match="finite"):
        summarize_probabilities(raw_probs)


def test_summarize_probabilities_rejects_out_of_range() -> None:
    raw_probs = np.array([0.2, 1.2, 0.6])

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        summarize_probabilities(raw_probs)


def test_enable_dropout_for_inference() -> None:
    model = torch.nn.Sequential(
        torch.nn.Linear(3, 4),
        torch.nn.ReLU(),
        torch.nn.Dropout(p=0.5),
        torch.nn.Linear(4, 1),
    )

    model.eval()
    dropout_layer = model[2]
    assert dropout_layer.training is False

    count = enable_dropout_for_inference(model)

    assert count >= 1
    assert dropout_layer.training is True


def test_collect_mc_dropout_probabilities_success() -> None:
    model = torch.nn.Sequential(
        torch.nn.Flatten(),
        torch.nn.Linear(6, 4),
        torch.nn.ReLU(),
        torch.nn.Dropout(p=0.5),
        torch.nn.Linear(4, 1),
    )

    input_tensor = torch.zeros((1, 2, 3), dtype=torch.float32)

    probs = collect_mc_dropout_probabilities(
        model=model,
        input_tensor=input_tensor,
        mc_samples=5,
    )

    assert probs.shape == (5,)
    assert np.all(probs >= 0)
    assert np.all(probs <= 1)
    assert model.training is False


def test_collect_mc_dropout_probabilities_rejects_bad_mc_samples() -> None:
    model = torch.nn.Linear(3, 1)
    input_tensor = torch.zeros((1, 1, 3), dtype=torch.float32)

    with pytest.raises(ValueError, match="mc_samples"):
        collect_mc_dropout_probabilities(model, input_tensor, 0)

    with pytest.raises(ValueError, match="mc_samples"):
        collect_mc_dropout_probabilities(model, input_tensor, True)


def test_collect_mc_dropout_probabilities_rejects_bad_input_shape() -> None:
    model = torch.nn.Linear(3, 1)
    input_tensor = torch.zeros((2, 3), dtype=torch.float32)

    with pytest.raises(ValueError, match="3D"):
        collect_mc_dropout_probabilities(model, input_tensor, 5)