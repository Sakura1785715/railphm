"""
保序回归风险概率校准器。

本文件实现 IsotonicRiskCalibrator，用于基于验证集 y_true 和模型原始
概率 y_prob 拟合保序回归映射。该校准器只做概率后处理，不修改模型结构、
不重训模型、不加载 best_model.pt，也不负责 MC-Dropout 不确定性估计。
risk_raw  →  risk_score
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass
class IsotonicRiskCalibrator:
    method: str = "isotonic_regression" # 校准方法名称
    out_of_bounds: str = "clip" # IsotonicRegression 的参数：裁剪到训练的标准范围里
    model: IsotonicRegression | None = None # 保序回归模型对象
    is_fitted: bool = False # 表示校准器是否已经拟合完成

    # 拟合保序回归校准器
    def fit(self, y_true: Any, y_prob: Any) -> "IsotonicRiskCalibrator":
        """
        使用验证集真实标签和原始概率拟合保序回归校准器。
        """
        y_true_array = _validate_binary_labels(y_true)
        y_prob_array = _validate_probabilities(y_prob, name="y_prob")

        if y_true_array.shape[0] != y_prob_array.shape[0]:
            raise ValueError(
                "y_true and y_prob must have the same length: "
                f"y_true={y_true_array.shape[0]}, y_prob={y_prob_array.shape[0]}"
            )

        self.model = IsotonicRegression(
            y_min=0.0,
            y_max=1.0,
            out_of_bounds=self.out_of_bounds,
        )
        self.model.fit(y_prob_array, y_true_array)
        self.is_fitted = True

        return self

    def transform(self, y_prob: Any) -> np.ndarray:
        """
        将模型原始概率映射为校准后概率。
        """
        if not self.is_fitted or self.model is None:
            raise ValueError("calibrator is not fitted")

        y_prob_array = _validate_probabilities(y_prob, name="y_prob")
        calibrated = self.model.transform(y_prob_array)
        return np.clip(np.asarray(calibrated, dtype=np.float64), 0.0, 1.0)

    def fit_transform(self, y_true: Any, y_prob: Any) -> np.ndarray:
        """
        先拟合校准器，再返回校准后的概率。
        """
        self.fit(y_true=y_true, y_prob=y_prob)
        return self.transform(y_prob)

    def save(self, path: str | Path) -> None:
        """
        保存校准器到 calibrator.pkl。
        """
        if not self.is_fitted or self.model is None:
            raise ValueError("calibrator is not fitted")

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(
            {
                "method": self.method,
                "out_of_bounds": self.out_of_bounds,
                "model": self.model,
                "is_fitted": self.is_fitted,
            },
            output_path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "IsotonicRiskCalibrator":
        """
        从 calibrator.pkl 加载校准器。
        """
        input_path = Path(path)

        if not input_path.exists():
            raise FileNotFoundError(f"calibrator file not found: {input_path}")

        try:
            payload = joblib.load(input_path)
        except Exception as exc:
            raise ValueError(f"failed to load calibrator: {input_path}, error={exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("calibrator file content must be a dict")

        model = payload.get("model")
        is_fitted = payload.get("is_fitted")

        if model is None or not is_fitted:
            raise ValueError("calibrator file is invalid: model is missing or not fitted")

        if not isinstance(model, IsotonicRegression):
            raise ValueError("calibrator file is invalid: model must be IsotonicRegression")

        return cls(
            method=str(payload.get("method", "isotonic_regression")),
            out_of_bounds=str(payload.get("out_of_bounds", "clip")),
            model=model,
            is_fitted=True,
        )


def _to_1d_array(values: Any, name: str) -> np.ndarray:
    """
    将输入转换为一维 numpy 数组。
    """
    array = np.asarray(values)

    if array.ndim != 1:
        raise ValueError(f"{name} must be a 1D array")

    if array.shape[0] == 0:
        raise ValueError(f"{name} must not be empty")

    try:
        array = array.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc

    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")

    return array


def _validate_binary_labels(y_true: Any) -> np.ndarray:
    """
    校验 y_true 是否为一维 0/1 标签数组。
    """
    y_true_array = _to_1d_array(y_true, name="y_true")

    if not np.isin(y_true_array, [0.0, 1.0]).all():
        raise ValueError("y_true must contain only 0/1 labels")

    return y_true_array.astype(np.int64)


def _validate_probabilities(y_prob: Any, name: str) -> np.ndarray:
    """
    校验概率数组是否位于 [0, 1]。
    """
    y_prob_array = _to_1d_array(y_prob, name=name)

    if (y_prob_array < 0).any() or (y_prob_array > 1).any():
        raise ValueError(f"{name} must be within [0, 1]")

    return y_prob_array.astype(np.float64)