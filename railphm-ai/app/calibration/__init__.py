"""
RailPHM 概率校准模块。

本包用于承载模型原始风险概率的后处理校准能力。当前阶段实现
保序回归校准器，后续运行时推理可以复用该模块将模型 sigmoid
输出的原始概率转换为更适合作为 PHM 风险分数的校准概率。
"""

from app.calibration.isotonic_calibrator import IsotonicRiskCalibrator

__all__ = ["IsotonicRiskCalibrator"]