"""
K-means 工况聚类核心模块。

该文件基于工况统计特征矩阵完成训练集拟合、全量样本工况预测、
聚类中心解释和初步工况标签映射，为后续命令行脚本和增强数据集构造提供基础能力。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


@dataclass
class ConditionClusterConfig:
    """K-means 工况聚类配置。"""

    n_clusters: int = 3
    seed: int = 42
    max_iter: int = 300
    n_init: int = 10
    auto_label: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.n_clusters, bool) or not isinstance(self.n_clusters, int) or self.n_clusters < 2:
            raise ValueError("n_clusters 必须为大于等于 2 的整数")

        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed 必须为整数")

        if isinstance(self.max_iter, bool) or not isinstance(self.max_iter, int) or self.max_iter <= 0:
            raise ValueError("max_iter 必须为正整数")

        if isinstance(self.n_init, bool) or not isinstance(self.n_init, int) or self.n_init <= 0:
            raise ValueError("n_init 必须为正整数")

        if not isinstance(self.auto_label, bool):
            raise ValueError("auto_label 必须为 bool")


@dataclass
class ConditionClusterResult:
    """K-means 工况聚类结果。"""

    condition_ids: np.ndarray
    condition_labels: list[str]
    condition_label_mapping: dict[int, str]
    cluster_centers: np.ndarray
    cluster_centers_original_scale: np.ndarray
    feature_names: list[str]
    summary: dict
    warnings: list[str]


class ConditionKMeansClusterer:
    """基于工况统计特征执行 K-means 聚类。"""

    LOW_CLUSTER_RATIO_THRESHOLD = 0.01
    MIN_TRAIN_SAMPLES_PER_CLUSTER = 2

    def fit_predict(
        self,
        feature_matrix: np.ndarray,
        feature_names: list[str],
        train_indices: np.ndarray,
        val_indices: np.ndarray | None = None,
        test_indices: np.ndarray | None = None,
        config: ConditionClusterConfig | None = None,
    ) -> ConditionClusterResult:
        """
        只使用训练集样本拟合 StandardScaler 和 KMeans，并对全量样本预测工况 ID。
        """
        config = config or ConditionClusterConfig()

        self._validate_feature_matrix(feature_matrix)
        self._validate_feature_names(feature_names, feature_matrix.shape[1])

        train_indices = self._validate_indices(
            indices=train_indices,
            sample_count=feature_matrix.shape[0],
            name="train_indices",
            allow_empty=False,
            check_duplicate=True,
        )

        val_indices = self._validate_optional_indices(
            indices=val_indices,
            sample_count=feature_matrix.shape[0],
            name="val_indices",
        )
        test_indices = self._validate_optional_indices(
            indices=test_indices,
            sample_count=feature_matrix.shape[0],
            name="test_indices",
        )

        self._validate_cluster_count(
            feature_matrix=feature_matrix,
            train_indices=train_indices,
            n_clusters=config.n_clusters,
        )

        warnings: list[str] = []

        train_features = feature_matrix[train_indices].astype(np.float32, copy=False)

        scaler = StandardScaler()
        train_scaled = scaler.fit_transform(train_features).astype(np.float32, copy=False)

        kmeans = KMeans(
            n_clusters=config.n_clusters,
            random_state=config.seed,
            max_iter=config.max_iter,
            n_init=config.n_init,
        )
        kmeans.fit(train_scaled)

        full_scaled = scaler.transform(feature_matrix).astype(np.float32, copy=False)
        condition_ids = kmeans.predict(full_scaled).astype(np.int64, copy=False)

        cluster_centers = kmeans.cluster_centers_.astype(np.float32, copy=False)
        cluster_centers_original_scale = scaler.inverse_transform(cluster_centers).astype(
            np.float32,
            copy=False,
        )

        condition_label_mapping = self._build_condition_label_mapping(
            feature_names=feature_names,
            cluster_centers_original_scale=cluster_centers_original_scale,
            config=config,
            warnings=warnings,
        )
        condition_labels = [
            condition_label_mapping[int(condition_id)]
            for condition_id in condition_ids.tolist()
        ]

        summary = self._build_summary(
            feature_matrix=feature_matrix,
            feature_names=feature_names,
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            condition_ids=condition_ids,
            condition_label_mapping=condition_label_mapping,
            cluster_centers_original_scale=cluster_centers_original_scale,
            warnings=warnings,
            n_clusters=config.n_clusters,
        )

        return ConditionClusterResult(
            condition_ids=condition_ids,
            condition_labels=condition_labels,
            condition_label_mapping=condition_label_mapping,
            cluster_centers=cluster_centers,
            cluster_centers_original_scale=cluster_centers_original_scale,
            feature_names=list(feature_names),
            summary=summary,
            warnings=warnings,
        )

    def _validate_feature_matrix(self, feature_matrix: np.ndarray) -> None:
        if not isinstance(feature_matrix, np.ndarray):
            raise ValueError("feature_matrix 必须是 numpy.ndarray")

        if feature_matrix.ndim != 2:
            raise ValueError(
                "feature_matrix 必须为二维数组 [num_samples, condition_feature_dim]"
            )

        if feature_matrix.shape[0] == 0 or feature_matrix.shape[1] == 0:
            raise ValueError("feature_matrix 不能为空")

        if not np.isfinite(feature_matrix).all():
            raise ValueError("feature_matrix 中存在 NaN 或 inf")

    def _validate_feature_names(self, feature_names: list[str], feature_dim: int) -> None:
        if not isinstance(feature_names, list) or not feature_names:
            raise ValueError("feature_names 必须是非空 list[str]")

        if not all(isinstance(name, str) and name for name in feature_names):
            raise ValueError("feature_names 必须是非空 list[str]")

        if len(feature_names) != feature_dim:
            raise ValueError(
                "feature_names 数量必须与特征维度一致: "
                f"feature_names={len(feature_names)}, feature_dim={feature_dim}"
            )

    def _validate_optional_indices(
        self,
        indices: np.ndarray | None,
        sample_count: int,
        name: str,
    ) -> np.ndarray | None:
        if indices is None:
            return None

        return self._validate_indices(
            indices=indices,
            sample_count=sample_count,
            name=name,
            allow_empty=True,
            check_duplicate=True,
        )

    def _validate_indices(
        self,
        indices: np.ndarray,
        sample_count: int,
        name: str,
        allow_empty: bool,
        check_duplicate: bool,
    ) -> np.ndarray:
        if not isinstance(indices, np.ndarray):
            raise ValueError(f"{name} 必须是 numpy.ndarray")

        if indices.ndim != 1:
            raise ValueError(f"{name} 必须是一维整数数组")

        if not np.issubdtype(indices.dtype, np.integer):
            raise ValueError(f"{name} 必须是一维整数数组")

        normalized = indices.astype(np.int64, copy=False)

        if not allow_empty and normalized.size == 0:
            raise ValueError(f"{name} 不能为空，训练集样本数必须大于 0")

        if normalized.size == 0:
            return normalized

        if normalized.min() < 0 or normalized.max() >= sample_count:
            raise ValueError(f"{name} 存在越界索引")

        if check_duplicate and np.unique(normalized).shape[0] != normalized.shape[0]:
            raise ValueError(f"{name} 存在重复索引")

        return normalized

    def _validate_cluster_count(
        self,
        feature_matrix: np.ndarray,
        train_indices: np.ndarray,
        n_clusters: int,
    ) -> None:
        train_sample_count = int(train_indices.shape[0])

        if n_clusters > train_sample_count:
            raise ValueError(
                "n_clusters 不能大于训练集样本数: "
                f"n_clusters={n_clusters}, train_sample_count={train_sample_count}"
            )

        train_features = feature_matrix[train_indices]
        unique_train_features = np.unique(train_features, axis=0)
        unique_count = int(unique_train_features.shape[0])

        if n_clusters > unique_count:
            raise ValueError(
                "n_clusters 不能大于训练集中可区分样本数: "
                f"n_clusters={n_clusters}, unique_train_sample_count={unique_count}"
            )

    def _build_condition_label_mapping(
        self,
        feature_names: list[str],
        cluster_centers_original_scale: np.ndarray,
        config: ConditionClusterConfig,
        warnings: list[str],
    ) -> dict[int, str]:
        if not config.auto_label:
            warnings.append("auto_label=False，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        if config.n_clusters != 3:
            warnings.append("n_clusters 不等于 3，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        if "speed_mean" not in feature_names:
            warnings.append("缺少 speed_mean，无法基于速度均值解释工况，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        if "speed_delta" not in feature_names:
            warnings.append("缺少 speed_delta，无法基于速度变化解释进站/出站，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        speed_delta_index = feature_names.index("speed_delta")
        speed_delta_values = cluster_centers_original_scale[:, speed_delta_index]

        accelerate_cluster = int(np.argmax(speed_delta_values))
        decelerate_cluster = int(np.argmin(speed_delta_values))

        if accelerate_cluster == decelerate_cluster:
            warnings.append("自动标签映射不确定，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        max_delta = float(speed_delta_values[accelerate_cluster])
        min_delta = float(speed_delta_values[decelerate_cluster])

        if max_delta <= 0 or min_delta >= 0:
            warnings.append("speed_delta 正负变化不明显，自动标签映射不确定，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        remaining_clusters = sorted(
            set(range(config.n_clusters)) - {accelerate_cluster, decelerate_cluster}
        )
        if len(remaining_clusters) != 1:
            warnings.append("自动标签映射不确定，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        cruise_cluster = remaining_clusters[0]

        return {
            cruise_cluster: "高速巡航",
            decelerate_cluster: "进站减速",
            accelerate_cluster: "出站加速",
        }

    def _default_label_mapping(self, n_clusters: int) -> dict[int, str]:
        return {cluster_id: f"工况{cluster_id}" for cluster_id in range(n_clusters)}

    def _build_summary(
        self,
        feature_matrix: np.ndarray,
        feature_names: list[str],
        train_indices: np.ndarray,
        val_indices: np.ndarray | None,
        test_indices: np.ndarray | None,
        condition_ids: np.ndarray,
        condition_label_mapping: dict[int, str],
        cluster_centers_original_scale: np.ndarray,
        warnings: list[str],
        n_clusters: int,
    ) -> dict[str, Any]:
        cluster_sample_count = self._count_by_cluster(condition_ids, n_clusters)
        cluster_train_sample_count = self._count_by_cluster(
            condition_ids[train_indices],
            n_clusters,
        )

        self._append_cluster_warnings(
            cluster_sample_count=cluster_sample_count,
            cluster_train_sample_count=cluster_train_sample_count,
            sample_count=int(feature_matrix.shape[0]),
            warnings=warnings,
        )

        cluster_feature_summary = self._build_cluster_feature_summary(
            feature_names=feature_names,
            cluster_centers_original_scale=cluster_centers_original_scale,
            n_clusters=n_clusters,
        )

        return {
            "n_clusters": int(n_clusters),
            "fit_scope": "train_split_only",
            "sample_count": int(feature_matrix.shape[0]),
            "train_sample_count": int(train_indices.shape[0]),
            "val_sample_count": None if val_indices is None else int(val_indices.shape[0]),
            "test_sample_count": None if test_indices is None else int(test_indices.shape[0]),
            "feature_names": list(feature_names),
            "cluster_sample_count": {
                str(cluster_id): int(count)
                for cluster_id, count in cluster_sample_count.items()
            },
            "cluster_train_sample_count": {
                str(cluster_id): int(count)
                for cluster_id, count in cluster_train_sample_count.items()
            },
            "condition_label_mapping": {
                str(cluster_id): label
                for cluster_id, label in condition_label_mapping.items()
            },
            "cluster_feature_summary": cluster_feature_summary,
            "warnings": warnings,
        }

    def _count_by_cluster(self, condition_ids: np.ndarray, n_clusters: int) -> dict[int, int]:
        return {
            cluster_id: int((condition_ids == cluster_id).sum())
            for cluster_id in range(n_clusters)
        }

    def _append_cluster_warnings(
        self,
        cluster_sample_count: dict[int, int],
        cluster_train_sample_count: dict[int, int],
        sample_count: int,
        warnings: list[str],
    ) -> None:
        for cluster_id, count in cluster_sample_count.items():
            ratio = count / sample_count if sample_count > 0 else 0.0
            if ratio < self.LOW_CLUSTER_RATIO_THRESHOLD:
                warnings.append(
                    f"簇 {cluster_id} 全量样本占比过低，ratio={ratio:.6f}"
                )

        for cluster_id, count in cluster_train_sample_count.items():
            if count < self.MIN_TRAIN_SAMPLES_PER_CLUSTER:
                warnings.append(
                    f"簇 {cluster_id} 在训练集中样本数过少，train_count={count}"
                )

    def _build_cluster_feature_summary(
        self,
        feature_names: list[str],
        cluster_centers_original_scale: np.ndarray,
        n_clusters: int,
    ) -> dict[str, dict[str, float]]:
        summary: dict[str, dict[str, float]] = {}

        for cluster_id in range(n_clusters):
            summary[str(cluster_id)] = {
                feature_name: float(cluster_centers_original_scale[cluster_id, feature_index])
                for feature_index, feature_name in enumerate(feature_names)
            }

        return summary