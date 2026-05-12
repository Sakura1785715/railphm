"""
IsotonicRiskCalibrator 单元测试。

本测试只验证保序回归校准器本身，不依赖真实模型、不读取真实训练产物。
"""

from __future__ import annotations

import numpy as np
import pytest

from app.calibration import IsotonicRiskCalibrator


def test_fit_and_transform_success() -> None:
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])

    calibrator = IsotonicRiskCalibrator()
    calibrator.fit(y_true, y_prob)

    transformed = calibrator.transform(y_prob)

    assert calibrator.is_fitted is True
    assert transformed.shape == y_prob.shape
    assert np.all(transformed >= 0)
    assert np.all(transformed <= 1)


def test_fit_transform_success() -> None:
    y_true = [0, 0, 1, 1]
    y_prob = [0.1, 0.3, 0.7, 0.9]

    calibrator = IsotonicRiskCalibrator()
    transformed = calibrator.fit_transform(y_true, y_prob)

    assert transformed.shape == (4,)
    assert np.all(transformed >= 0)
    assert np.all(transformed <= 1)


def test_transform_before_fit_fails() -> None:
    calibrator = IsotonicRiskCalibrator()

    with pytest.raises(ValueError, match="not fitted"):
        calibrator.transform([0.1, 0.2])


def test_fit_fails_when_length_mismatch() -> None:
    calibrator = IsotonicRiskCalibrator()

    with pytest.raises(ValueError, match="same length"):
        calibrator.fit([0, 1], [0.1, 0.2, 0.3])


def test_fit_fails_when_y_true_invalid() -> None:
    calibrator = IsotonicRiskCalibrator()

    with pytest.raises(ValueError, match="0/1"):
        calibrator.fit([0, 2, 1], [0.1, 0.5, 0.9])


def test_fit_fails_when_y_prob_out_of_range() -> None:
    calibrator = IsotonicRiskCalibrator()

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        calibrator.fit([0, 1], [0.1, 1.2])


def test_transform_fails_when_y_prob_out_of_range() -> None:
    calibrator = IsotonicRiskCalibrator()
    calibrator.fit([0, 1], [0.1, 0.9])

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        calibrator.transform([-0.1, 0.8])


def test_save_and_load_success(tmp_path) -> None:
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])

    calibrator = IsotonicRiskCalibrator()
    calibrator.fit(y_true, y_prob)

    path = tmp_path / "calibrator.pkl"
    calibrator.save(path)

    loaded = IsotonicRiskCalibrator.load(path)
    transformed = loaded.transform(y_prob)

    assert loaded.is_fitted is True
    assert transformed.shape == y_prob.shape
    assert np.all(transformed >= 0)
    assert np.all(transformed <= 1)


def test_save_before_fit_fails(tmp_path) -> None:
    calibrator = IsotonicRiskCalibrator()

    with pytest.raises(ValueError, match="not fitted"):
        calibrator.save(tmp_path / "calibrator.pkl")