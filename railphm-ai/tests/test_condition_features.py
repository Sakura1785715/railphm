import numpy as np
import pytest

from app.condition import ConditionFeatureExtractor


def _build_full_feature_X() -> np.ndarray:
    return np.array(
        [
            [
                [10.0, 100.0, 0.0, 20.0, 50.0],
                [20.0, 101.0, 10.0, 21.0, 51.0],
                [30.0, 102.0, 20.0, 22.0, 52.0],
                [40.0, 103.0, 30.0, 23.0, 53.0],
            ],
            [
                [40.0, 200.0, 100.0, 18.0, 55.0],
                [30.0, 201.0, 105.0, 18.0, 54.0],
                [20.0, 202.0, 110.0, 19.0, 53.0],
                [10.0, 203.0, 115.0, 19.0, 52.0],
            ],
        ],
        dtype=np.float32,
    )


def test_condition_features_extracts_speed_mileage_and_distance_features():
    X = _build_full_feature_X()
    feature_columns = ["速度", "里程", "运行距离", "室外温度", "湿度"]

    result = ConditionFeatureExtractor().extract(X, feature_columns)

    assert result.feature_matrix.shape[0] == 2
    assert result.feature_matrix.dtype == np.float32
    assert "speed_mean" in result.feature_names
    assert "speed_delta" in result.feature_names
    assert "mileage_delta" in result.feature_names
    assert "run_distance_delta" in result.feature_names
    assert np.isfinite(result.feature_matrix).all()
    assert not np.isnan(result.feature_matrix).any()
    assert not np.isinf(result.feature_matrix).any()


def test_condition_features_skip_missing_optional_fields():
    X = np.array(
        [
            [[10.0], [20.0], [30.0], [40.0]],
            [[40.0], [30.0], [20.0], [10.0]],
        ],
        dtype=np.float32,
    )
    feature_columns = ["速度"]

    result = ConditionFeatureExtractor().extract(X, feature_columns)

    assert "speed_mean" in result.feature_names
    assert "speed_std" in result.feature_names
    assert "speed_min" in result.feature_names
    assert "speed_max" in result.feature_names
    assert "speed_delta" in result.feature_names
    assert "speed_diff_mean" in result.feature_names
    assert "speed_diff_std" in result.feature_names

    assert "mileage_delta" not in result.feature_names
    assert "run_distance_delta" not in result.feature_names
    assert "temperature_mean" not in result.feature_names
    assert "humidity_mean" not in result.feature_names

    assert any("缺少可选工况字段：里程" in warning for warning in result.warnings)
    assert any("缺少可选工况字段：运行距离" in warning for warning in result.warnings)
    assert any("缺少可选工况字段：室外温度" in warning for warning in result.warnings)
    assert any("缺少可选工况字段：湿度" in warning for warning in result.warnings)


def test_condition_features_raise_error_when_speed_missing():
    X = np.array(
        [
            [[100.0, 0.0], [101.0, 10.0], [102.0, 20.0]],
        ],
        dtype=np.float32,
    )
    feature_columns = ["里程", "运行距离"]

    with pytest.raises(ValueError, match="速度"):
        ConditionFeatureExtractor().extract(X, feature_columns)


@pytest.mark.parametrize(
    "invalid_X",
    [
        np.zeros((2, 4), dtype=np.float32),
        np.zeros((2, 4, 3, 1), dtype=np.float32),
    ],
)
def test_condition_features_raise_error_when_X_dimension_invalid(invalid_X):
    with pytest.raises(ValueError, match="三维数组|\\[num_samples, window_size, feature_dim\\]"):
        ConditionFeatureExtractor().extract(invalid_X, ["速度"])


def test_condition_features_raise_error_when_feature_columns_mismatch():
    X = np.zeros((2, 4, 2), dtype=np.float32)

    with pytest.raises(ValueError, match="feature_columns|特征维度"):
        ConditionFeatureExtractor().extract(X, ["速度"])


@pytest.mark.parametrize("bad_value", [np.nan, np.inf])
def test_condition_features_raise_error_when_X_contains_nan_or_inf(bad_value):
    X = np.array(
        [
            [[10.0], [20.0], [30.0], [40.0]],
            [[40.0], [30.0], [20.0], [10.0]],
        ],
        dtype=np.float32,
    )
    X[0, 0, 0] = bad_value

    with pytest.raises(ValueError, match="NaN|inf"):
        ConditionFeatureExtractor().extract(X, ["速度"])


def test_condition_features_do_not_use_label_related_columns():
    X = np.array(
        [
            [[10.0, 1.0], [20.0, 0.0], [30.0, 1.0], [40.0, 0.0]],
            [[40.0, 0.0], [30.0, 1.0], [20.0, 0.0], [10.0, 1.0]],
        ],
        dtype=np.float32,
    )
    feature_columns = ["速度", "报警部位"]

    result = ConditionFeatureExtractor().extract(X, feature_columns)

    assert any("标签字段" in warning or "泄露字段" in warning for warning in result.warnings)
    assert all("报警" not in name for name in result.feature_names)
    assert all("label" not in name.lower() for name in result.feature_names)
    assert "speed_mean" in result.feature_names
    assert np.isfinite(result.feature_matrix).all()