import numpy as np
import pytest

from app.condition import (
    ConditionClusterConfig,
    ConditionKMeansClusterer,
)


def _build_three_condition_features() -> np.ndarray:
    return np.array(
        [
            [300.0, 0.0, 2.0],
            [310.0, 0.2, 3.0],
            [305.0, -0.1, 2.5],
            [80.0, -20.0, 5.0],
            [75.0, -18.0, 6.0],
            [85.0, -22.0, 5.5],
            [100.0, 20.0, 5.0],
            [110.0, 18.0, 6.0],
            [105.0, 22.0, 5.5],
            [90.0, -19.0, 5.0],
            [115.0, 21.0, 5.0],
            [315.0, 0.1, 2.0],
        ],
        dtype=np.float32,
    )


def test_kmeans_cluster_fit_predict_success():
    feature_matrix = _build_three_condition_features()
    feature_names = ["speed_mean", "speed_delta", "speed_std"]
    train_indices = np.arange(0, 9, dtype=np.int64)
    val_indices = np.array([9, 10], dtype=np.int64)
    test_indices = np.array([11], dtype=np.int64)

    config = ConditionClusterConfig(n_clusters=3, seed=42)
    result = ConditionKMeansClusterer().fit_predict(
        feature_matrix=feature_matrix,
        feature_names=feature_names,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
        config=config,
    )

    assert result.condition_ids.shape == (12,)
    assert result.condition_ids.min() >= 0
    assert result.condition_ids.max() < config.n_clusters
    assert len(result.condition_labels) == 12
    assert result.cluster_centers.shape[0] == config.n_clusters
    assert result.cluster_centers_original_scale.shape[0] == config.n_clusters
    assert result.summary["fit_scope"] == "train_split_only"
    assert "cluster_sample_count" in result.summary
    assert "condition_label_mapping" in result.summary


def test_kmeans_cluster_fit_uses_train_indices_and_predicts_full_samples():
    feature_matrix = np.array(
        [
            [10.0, 0.0],
            [11.0, 0.1],
            [12.0, -0.1],
            [100.0, 10.0],
            [101.0, 9.5],
            [102.0, 10.5],
            [500.0, -50.0],
            [520.0, -55.0],
            [540.0, -60.0],
            [560.0, -65.0],
        ],
        dtype=np.float32,
    )
    feature_names = ["speed_mean", "speed_delta"]
    train_indices = np.array([0, 1, 2, 3, 4, 5], dtype=np.int64)
    test_indices = np.array([6, 7, 8, 9], dtype=np.int64)

    result = ConditionKMeansClusterer().fit_predict(
        feature_matrix=feature_matrix,
        feature_names=feature_names,
        train_indices=train_indices,
        test_indices=test_indices,
        config=ConditionClusterConfig(n_clusters=2, seed=42),
    )

    assert result.condition_ids.shape == (10,)
    assert result.summary["train_sample_count"] == train_indices.shape[0]
    assert result.summary["test_sample_count"] == test_indices.shape[0]


def test_kmeans_cluster_raise_error_when_n_clusters_greater_than_train_samples():
    feature_matrix = _build_three_condition_features()
    feature_names = ["speed_mean", "speed_delta", "speed_std"]
    train_indices = np.array([0, 1], dtype=np.int64)

    with pytest.raises(ValueError, match="n_clusters|训练集样本数"):
        ConditionKMeansClusterer().fit_predict(
            feature_matrix=feature_matrix,
            feature_names=feature_names,
            train_indices=train_indices,
            config=ConditionClusterConfig(n_clusters=3),
        )


@pytest.mark.parametrize(
    "invalid_feature_matrix",
    [
        np.zeros((12,), dtype=np.float32),
        np.zeros((12, 3, 1), dtype=np.float32),
    ],
)
def test_kmeans_cluster_raise_error_when_feature_matrix_dimension_invalid(invalid_feature_matrix):
    with pytest.raises(ValueError, match="二维数组|\\[num_samples, condition_feature_dim\\]"):
        ConditionKMeansClusterer().fit_predict(
            feature_matrix=invalid_feature_matrix,
            feature_names=["speed_mean"],
            train_indices=np.array([0, 1, 2], dtype=np.int64),
        )


def test_kmeans_cluster_raise_error_when_feature_names_mismatch():
    feature_matrix = np.zeros((12, 3), dtype=np.float32)
    train_indices = np.arange(0, 6, dtype=np.int64)

    with pytest.raises(ValueError, match="feature_names|特征维度"):
        ConditionKMeansClusterer().fit_predict(
            feature_matrix=feature_matrix,
            feature_names=["speed_mean", "speed_delta"],
            train_indices=train_indices,
        )


def test_kmeans_cluster_raise_error_when_train_indices_empty():
    feature_matrix = _build_three_condition_features()
    feature_names = ["speed_mean", "speed_delta", "speed_std"]

    with pytest.raises(ValueError, match="train_indices|训练集"):
        ConditionKMeansClusterer().fit_predict(
            feature_matrix=feature_matrix,
            feature_names=feature_names,
            train_indices=np.array([], dtype=np.int64),
        )


def test_kmeans_cluster_raise_error_when_train_indices_out_of_range():
    feature_matrix = _build_three_condition_features()
    feature_names = ["speed_mean", "speed_delta", "speed_std"]

    with pytest.raises(ValueError, match="越界"):
        ConditionKMeansClusterer().fit_predict(
            feature_matrix=feature_matrix,
            feature_names=feature_names,
            train_indices=np.array([0, 1, 12], dtype=np.int64),
        )


@pytest.mark.parametrize("bad_value", [np.nan, np.inf])
def test_kmeans_cluster_raise_error_when_feature_matrix_contains_nan_or_inf(bad_value):
    feature_matrix = _build_three_condition_features()
    feature_matrix[0, 0] = bad_value
    feature_names = ["speed_mean", "speed_delta", "speed_std"]
    train_indices = np.arange(0, 9, dtype=np.int64)

    with pytest.raises(ValueError, match="NaN|inf"):
        ConditionKMeansClusterer().fit_predict(
            feature_matrix=feature_matrix,
            feature_names=feature_names,
            train_indices=train_indices,
        )


def test_kmeans_cluster_use_default_labels_when_speed_features_missing():
    feature_matrix = np.array(
        [
            [1.0, 1.0],
            [1.1, 1.2],
            [1.2, 1.1],
            [5.0, 5.0],
            [5.1, 5.2],
            [5.2, 5.1],
            [9.0, 9.0],
            [9.1, 9.2],
            [9.2, 9.1],
        ],
        dtype=np.float32,
    )
    feature_names = ["some_feature_1", "some_feature_2"]
    train_indices = np.arange(0, 9, dtype=np.int64)

    result = ConditionKMeansClusterer().fit_predict(
        feature_matrix=feature_matrix,
        feature_names=feature_names,
        train_indices=train_indices,
        config=ConditionClusterConfig(n_clusters=3, seed=42),
    )

    assert any("缺少 speed_mean" in warning for warning in result.warnings)
    assert all(label.startswith("工况") for label in result.condition_label_mapping.values())


@pytest.mark.parametrize("n_clusters", [2, 4])
def test_kmeans_cluster_use_default_labels_when_n_clusters_not_three(n_clusters):
    feature_matrix = np.array(
        [
            [10.0, 0.0, 1.0],
            [11.0, 0.1, 1.2],
            [50.0, -5.0, 2.0],
            [51.0, -5.2, 2.1],
            [100.0, 8.0, 3.0],
            [101.0, 8.2, 3.1],
            [150.0, 1.0, 4.0],
            [151.0, 1.2, 4.1],
        ],
        dtype=np.float32,
    )
    feature_names = ["speed_mean", "speed_delta", "speed_std"]
    train_indices = np.arange(0, 8, dtype=np.int64)

    result = ConditionKMeansClusterer().fit_predict(
        feature_matrix=feature_matrix,
        feature_names=feature_names,
        train_indices=train_indices,
        config=ConditionClusterConfig(n_clusters=n_clusters, seed=42),
    )

    assert all(label.startswith("工况") for label in result.condition_label_mapping.values())
    assert "高速巡航" not in result.condition_label_mapping.values()
    assert "进站减速" not in result.condition_label_mapping.values()
    assert "出站加速" not in result.condition_label_mapping.values()