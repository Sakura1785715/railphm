"""
K-means 工况聚类核心模块。

训练阶段使用稳健运行阶段特征拟合三类固定工况；高置信物理规则命中时，
最终 condition_id 以规则锚定结果为准，KMeans 作为不确定窗口的辅助判断。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from app.condition.rule_condition import RuleConditionClassifier


@dataclass
class ConditionClusterConfig:
    n_clusters: int = 3
    seed: int = 42
    max_iter: int = 300
    n_init: int = 10
    auto_label: bool = True
    stable_fit_enabled: bool = True
    stable_filter_quantile: float = 0.90
    feature_weights: dict[str, float] | None = None
    cluster_feature_names: list[str] | None = None
    rule_anchor_enabled: bool = True

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
        if not isinstance(self.stable_fit_enabled, bool):
            raise ValueError("stable_fit_enabled 必须为 bool")
        if not isinstance(self.rule_anchor_enabled, bool):
            raise ValueError("rule_anchor_enabled 必须为 bool")
        if not (0.0 < float(self.stable_filter_quantile) < 1.0):
            raise ValueError("stable_filter_quantile 必须位于 (0, 1)")
        if self.feature_weights is not None and not isinstance(self.feature_weights, dict):
            raise ValueError("feature_weights 必须为 dict[str, float] 或 None")
        if self.cluster_feature_names is not None:
            if not isinstance(self.cluster_feature_names, list) or not all(
                isinstance(name, str) and name for name in self.cluster_feature_names
            ):
                raise ValueError("cluster_feature_names 必须为 list[str] 或 None")


@dataclass
class ConditionClusterResult:
    condition_ids: np.ndarray
    condition_labels: list[str]
    condition_label_mapping: dict[int, str]
    cluster_centers: np.ndarray
    cluster_centers_original_scale: np.ndarray
    feature_names: list[str]
    summary: dict
    warnings: list[str]
    condition_feature_scaler: Any | None = None
    kmeans_model: Any | None = None
    cluster_feature_names: list[str] | None = None
    stable_train_indices: np.ndarray | None = None
    anchor_summary: dict[str, Any] | None = None
    feature_weights: dict[str, float] | None = None


class ConditionKMeansClusterer:
    """基于稳健工况特征执行 K-means 聚类。"""

    LOW_CLUSTER_RATIO_THRESHOLD = 0.01
    MIN_TRAIN_SAMPLES_PER_CLUSTER = 2
    FIXED_LABELS = ("出站加速", "高速巡航", "进站减速")

    DEFAULT_CLUSTER_FEATURE_NAMES = [
        "speed_median",
        "speed_delta_robust",
        "speed_diff_clipped_mean",
        "positive_diff_ratio",
        "negative_diff_ratio",
        "brake_mean",
        "brake_active_ratio",
    ]
    LEGACY_CLUSTER_FEATURE_NAMES = [
        "speed_mean",
        "speed_delta",
        "speed_diff_mean",
        "speed_diff_std",
    ]
    DEFAULT_FEATURE_WEIGHTS = {
        "speed_median": 1.20,
        "speed_delta_robust": 1.80,
        "speed_diff_clipped_mean": 1.60,
        "positive_diff_ratio": 1.20,
        "negative_diff_ratio": 1.20,
        "brake_mean": 0.90,
        "brake_active_ratio": 1.10,
    }
    DIAGNOSTIC_FEATURE_NAMES = {
        "large_jump_count",
        "freeze_ratio",
        "speed_diff_abs_p95",
        "service_margin_min",
        "emergency_margin_min",
    }

    def fit_predict(
        self,
        feature_matrix: np.ndarray,
        feature_names: list[str],
        train_indices: np.ndarray,
        val_indices: np.ndarray | None = None,
        test_indices: np.ndarray | None = None,
        config: ConditionClusterConfig | None = None,
        *,
        raw_windows: np.ndarray | None = None,
        raw_feature_columns: list[str] | None = None,
    ) -> ConditionClusterResult:
        """只使用训练集拟合 scaler 和 KMeans，并对全量样本预测最终工况。"""
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
        val_indices = self._validate_optional_indices(val_indices, feature_matrix.shape[0], "val_indices")
        test_indices = self._validate_optional_indices(test_indices, feature_matrix.shape[0], "test_indices")

        warnings: list[str] = []
        cluster_feature_names = self._select_cluster_feature_names(feature_names, config, warnings)
        cluster_feature_indices = np.asarray(
            [feature_names.index(name) for name in cluster_feature_names],
            dtype=np.int64,
        )
        cluster_feature_matrix = feature_matrix[:, cluster_feature_indices].astype(np.float32, copy=False)

        stable_train_indices = self._select_stable_train_indices(
            feature_matrix=feature_matrix,
            feature_names=feature_names,
            train_indices=train_indices,
            config=config,
            warnings=warnings,
        )
        self._validate_cluster_count(
            feature_matrix=cluster_feature_matrix,
            train_indices=stable_train_indices,
            n_clusters=config.n_clusters,
        )

        scaler = StandardScaler()
        train_features = cluster_feature_matrix[stable_train_indices].astype(np.float32, copy=False)
        train_scaled = scaler.fit_transform(train_features).astype(np.float32, copy=False)
        weights = self._build_feature_weights(cluster_feature_names, config)
        weight_vector = np.asarray([weights[name] for name in cluster_feature_names], dtype=np.float32).reshape(1, -1)
        train_weighted = (train_scaled * weight_vector).astype(np.float32, copy=False)

        kmeans = KMeans(
            n_clusters=config.n_clusters,
            random_state=config.seed,
            max_iter=config.max_iter,
            n_init=config.n_init,
        )
        kmeans.fit(train_weighted)

        full_scaled = scaler.transform(cluster_feature_matrix).astype(np.float32, copy=False)
        full_weighted = (full_scaled * weight_vector).astype(np.float32, copy=False)
        kmeans_condition_ids = kmeans.predict(full_weighted).astype(np.int64, copy=False)

        cluster_centers = kmeans.cluster_centers_.astype(np.float32, copy=False)
        unweighted_centers = cluster_centers / weight_vector
        cluster_centers_original_scale = scaler.inverse_transform(unweighted_centers).astype(np.float32, copy=False)

        condition_label_mapping = self._build_condition_label_mapping(
            feature_names=cluster_feature_names,
            cluster_centers_original_scale=cluster_centers_original_scale,
            config=config,
            warnings=warnings,
        )

        condition_ids, anchor_summary = self._apply_rule_anchor(
            kmeans_condition_ids=kmeans_condition_ids,
            condition_label_mapping=condition_label_mapping,
            rule_feature_matrix=feature_matrix,
            rule_feature_names=feature_names,
            raw_windows=raw_windows,
            raw_feature_columns=raw_feature_columns,
            config=config,
            warnings=warnings,
        )
        condition_labels = [
            condition_label_mapping.get(int(condition_id), f"工况{int(condition_id)}")
            for condition_id in condition_ids.tolist()
        ]

        summary = self._build_summary(
            feature_matrix=cluster_feature_matrix,
            feature_names=cluster_feature_names,
            train_indices=train_indices,
            stable_train_indices=stable_train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            condition_ids=condition_ids,
            kmeans_condition_ids=kmeans_condition_ids,
            condition_label_mapping=condition_label_mapping,
            cluster_centers_original_scale=cluster_centers_original_scale,
            warnings=warnings,
            n_clusters=config.n_clusters,
            feature_weights=weights,
            anchor_summary=anchor_summary,
            stable_fit_enabled=config.stable_fit_enabled,
        )

        return ConditionClusterResult(
            condition_ids=condition_ids,
            condition_labels=condition_labels,
            condition_label_mapping=condition_label_mapping,
            cluster_centers=cluster_centers,
            cluster_centers_original_scale=cluster_centers_original_scale,
            feature_names=list(cluster_feature_names),
            summary=summary,
            warnings=warnings,
            condition_feature_scaler=scaler,
            kmeans_model=kmeans,
            cluster_feature_names=list(cluster_feature_names),
            stable_train_indices=stable_train_indices,
            anchor_summary=anchor_summary,
            feature_weights=weights,
        )

    def _select_cluster_feature_names(
        self,
        feature_names: list[str],
        config: ConditionClusterConfig,
        warnings: list[str],
    ) -> list[str]:
        available = set(feature_names)
        if config.cluster_feature_names is not None:
            missing = [name for name in config.cluster_feature_names if name not in available]
            if missing:
                raise ValueError(f"cluster_feature_names 包含不存在的工况特征: {missing}")
            return list(config.cluster_feature_names)

        selected = [name for name in self.DEFAULT_CLUSTER_FEATURE_NAMES if name in available]
        if len(selected) >= 3 and "speed_delta_robust" in selected:
            return selected

        legacy = [name for name in self.LEGACY_CLUSTER_FEATURE_NAMES if name in available]
        if len(legacy) >= 2:
            warnings.append("增强工况特征不完整，已降级使用旧版速度特征进行 KMeans")
            return legacy

        warnings.append("缺少推荐工况聚类特征，已使用全部可用工况特征进行 KMeans")
        return list(feature_names)

    def _select_stable_train_indices(
        self,
        *,
        feature_matrix: np.ndarray,
        feature_names: list[str],
        train_indices: np.ndarray,
        config: ConditionClusterConfig,
        warnings: list[str],
    ) -> np.ndarray:
        if not config.stable_fit_enabled:
            return train_indices

        feature_index = {name: index for index, name in enumerate(feature_names)}
        masks: list[np.ndarray] = []
        q_high = float(config.stable_filter_quantile)
        q_low = 1.0 - q_high
        train_features = feature_matrix[train_indices]

        for name in ("large_jump_count", "freeze_ratio", "speed_diff_clipped_std"):
            if name not in feature_index:
                continue
            values = train_features[:, feature_index[name]]
            threshold = float(np.quantile(values, q_high))
            masks.append(values <= threshold)

        for name in ("service_margin_min", "emergency_margin_min"):
            if name not in feature_index:
                continue
            values = train_features[:, feature_index[name]]
            threshold = float(np.quantile(values, q_low))
            masks.append(values >= threshold)

        if not masks:
            warnings.append("缺少稳定样本诊断特征，stable_fit 已使用完整训练集")
            return train_indices

        stable_mask = np.logical_and.reduce(masks)
        stable_indices = train_indices[stable_mask]
        if stable_indices.shape[0] < config.n_clusters:
            warnings.append(
                "stable_fit 筛选后样本数不足，已回退到完整训练集: "
                f"stable_count={stable_indices.shape[0]}, train_count={train_indices.shape[0]}"
            )
            return train_indices

        unique_count = int(np.unique(feature_matrix[stable_indices], axis=0).shape[0])
        if unique_count < config.n_clusters:
            warnings.append(
                "stable_fit 筛选后可区分样本不足，已回退到完整训练集: "
                f"unique_count={unique_count}, n_clusters={config.n_clusters}"
            )
            return train_indices

        return stable_indices.astype(np.int64, copy=False)

    def _build_feature_weights(
        self,
        cluster_feature_names: list[str],
        config: ConditionClusterConfig,
    ) -> dict[str, float]:
        configured = config.feature_weights or {}
        weights: dict[str, float] = {}
        for name in cluster_feature_names:
            value = configured.get(name, self.DEFAULT_FEATURE_WEIGHTS.get(name, 1.0))
            weights[name] = float(value)
        return weights

    def _apply_rule_anchor(
        self,
        *,
        kmeans_condition_ids: np.ndarray,
        condition_label_mapping: dict[int, str],
        rule_feature_matrix: np.ndarray,
        rule_feature_names: list[str],
        raw_windows: np.ndarray | None,
        raw_feature_columns: list[str] | None,
        config: ConditionClusterConfig,
        warnings: list[str],
    ) -> tuple[np.ndarray, dict[str, Any]]:
        condition_ids = kmeans_condition_ids.astype(np.int64, copy=True)
        anchor_summary: dict[str, Any] = {
            "enabled": bool(config.rule_anchor_enabled),
            "status": "disabled" if not config.rule_anchor_enabled else "not_evaluated",
            "evaluated_count": 0,
            "high_confidence_count": 0,
            "applied_count": 0,
            "changed_count": 0,
            "rule_label_count": {},
        }
        if not config.rule_anchor_enabled:
            return condition_ids, anchor_summary

        vectorized_result = self._apply_vectorized_rule_anchor(
            condition_ids=condition_ids,
            kmeans_condition_ids=kmeans_condition_ids,
            condition_label_mapping=condition_label_mapping,
            rule_feature_matrix=rule_feature_matrix,
            rule_feature_names=rule_feature_names,
        )
        if vectorized_result is not None:
            return vectorized_result

        if raw_windows is None or raw_feature_columns is None:
            anchor_summary["status"] = "raw_window_missing"
            warnings.append("rule_anchor_enabled=True 但缺少 raw_windows，最终工况仅使用 KMeans")
            return condition_ids, anchor_summary

        if not isinstance(raw_windows, np.ndarray) or raw_windows.ndim != 3:
            anchor_summary["status"] = "raw_window_invalid"
            warnings.append("raw_windows 不是三维数组，最终工况仅使用 KMeans")
            return condition_ids, anchor_summary

        if raw_windows.shape[0] != kmeans_condition_ids.shape[0] or raw_windows.shape[2] != len(raw_feature_columns):
            anchor_summary["status"] = "raw_window_shape_mismatch"
            warnings.append("raw_windows 与样本数或 feature_columns 不一致，最终工况仅使用 KMeans")
            return condition_ids, anchor_summary

        classifier = RuleConditionClassifier(condition_label_mapping=condition_label_mapping)
        label_count: dict[str, int] = {}
        high_confidence_count = 0
        applied_count = 0
        changed_count = 0

        for index, raw_window in enumerate(raw_windows):
            kmeans_id = int(kmeans_condition_ids[index])
            kmeans_label = condition_label_mapping.get(kmeans_id)
            rule_result = classifier.classify(
                raw_window,
                raw_feature_columns,
                kmeans_condition_id=kmeans_id,
                kmeans_condition_label=kmeans_label,
            )
            if rule_result.condition_label is not None:
                label_count[rule_result.condition_label] = label_count.get(rule_result.condition_label, 0) + 1
            if not rule_result.is_high_confidence or rule_result.condition_id is None:
                continue
            high_confidence_count += 1
            applied_count += 1
            if int(rule_result.condition_id) != kmeans_id:
                changed_count += 1
            condition_ids[index] = int(rule_result.condition_id)

        anchor_summary.update(
            {
                "status": "applied",
                "evaluated_count": int(kmeans_condition_ids.shape[0]),
                "high_confidence_count": int(high_confidence_count),
                "applied_count": int(applied_count),
                "changed_count": int(changed_count),
                "rule_label_count": {key: int(value) for key, value in label_count.items()},
            }
        )
        return condition_ids, anchor_summary

    def _apply_vectorized_rule_anchor(
        self,
        *,
        condition_ids: np.ndarray,
        kmeans_condition_ids: np.ndarray,
        condition_label_mapping: dict[int, str],
        rule_feature_matrix: np.ndarray,
        rule_feature_names: list[str],
    ) -> tuple[np.ndarray, dict[str, Any]] | None:
        required = {
            "speed_median",
            "speed_delta_robust",
            "speed_diff_clipped_mean",
            "positive_diff_ratio",
            "negative_diff_ratio",
            "brake_active_ratio",
            "large_jump_count",
            "freeze_ratio",
            "speed_diff_abs_p95",
            "service_margin_min",
        }
        if not required.issubset(set(rule_feature_names)):
            return None

        label_to_id = {label: int(condition_id) for condition_id, label in condition_label_mapping.items()}
        if not all(label in label_to_id for label in self.FIXED_LABELS):
            return None

        values = {
            name: rule_feature_matrix[:, rule_feature_names.index(name)].astype(np.float32, copy=False)
            for name in required
        }

        speed_median = values["speed_median"]
        delta = values["speed_delta_robust"]
        clipped_mean = values["speed_diff_clipped_mean"]
        positive_ratio = values["positive_diff_ratio"]
        negative_ratio = values["negative_diff_ratio"]
        brake_active = values["brake_active_ratio"]
        large_jump = values["large_jump_count"]
        freeze_ratio = values["freeze_ratio"]
        diff_abs_p95 = values["speed_diff_abs_p95"]
        service_margin_min = values["service_margin_min"]

        cruise_guard = (
            (speed_median >= 240.0)
            & ((large_jump >= 1.0) | (freeze_ratio >= 0.20) | (diff_abs_p95 >= 12.0))
            & (np.abs(delta) <= 15.0)
            & (np.abs(clipped_mean) <= 2.2)
        )
        high_speed_bounded_cruise = (
            (speed_median >= 240.0)
            & (np.abs(delta) <= 15.0)
            & (np.abs(clipped_mean) <= 1.0)
        )
        strong_negative_trend = delta <= -22.0
        sustained_negative = (negative_ratio >= 0.55) & (clipped_mean <= -0.6)
        brake_guard = (
            (brake_active >= 0.25)
            & (speed_median >= 160.0)
            & (speed_median < 240.0)
            & (delta <= 12.0)
        )
        decel = (
            (strong_negative_trend & (sustained_negative | (brake_active >= 0.10)) & ~high_speed_bounded_cruise)
            | ((delta <= -35.0) & ~cruise_guard & ~high_speed_bounded_cruise)
            | brake_guard
        )
        low_brake = brake_active < 0.30
        positive_trend = delta >= 22.0
        sustained_positive = (positive_ratio >= 0.55) & (clipped_mean >= 0.6)
        not_high_stable_cruise = (speed_median < 240.0) | (delta >= 35.0)
        departure_response_guard = (
            (speed_median < 180.0)
            & (delta >= -10.0)
            & (service_margin_min > 0.0)
            & ((large_jump >= 3.0) | (diff_abs_p95 >= 15.0))
        )
        accel = (
            (positive_trend & sustained_positive & low_brake & not_high_stable_cruise)
            | ((delta >= 35.0) & low_brake)
            | departure_response_guard
        )
        cruise = (
            ((speed_median >= 160.0) & (np.abs(delta) <= 22.0) & (np.abs(clipped_mean) <= 1.0) & (brake_active < 0.30))
            | ((speed_median >= 220.0) & (np.abs(delta) <= 40.0))
        )

        final_ids = condition_ids.astype(np.int64, copy=True)
        source_label = np.full(final_ids.shape[0], "", dtype=object)
        ordered_rules = [
            ("高速巡航", cruise_guard),
            ("高速巡航", high_speed_bounded_cruise),
            ("进站减速", decel),
            ("出站加速", accel),
            ("高速巡航", cruise),
        ]
        assigned = np.zeros(final_ids.shape[0], dtype=bool)
        for label, mask in ordered_rules:
            apply_mask = mask & ~assigned
            if not apply_mask.any():
                continue
            final_ids[apply_mask] = label_to_id[label]
            source_label[apply_mask] = label
            assigned[apply_mask] = True

        changed_count = int((final_ids[assigned] != kmeans_condition_ids[assigned]).sum()) if assigned.any() else 0
        label_count = {
            label: int((source_label == label).sum())
            for label in self.FIXED_LABELS
            if int((source_label == label).sum()) > 0
        }
        anchor_summary = {
            "enabled": True,
            "status": "applied_vectorized",
            "evaluated_count": int(final_ids.shape[0]),
            "high_confidence_count": int(assigned.sum()),
            "applied_count": int(assigned.sum()),
            "changed_count": changed_count,
            "rule_label_count": label_count,
        }
        return final_ids, anchor_summary

    def _validate_feature_matrix(self, feature_matrix: np.ndarray) -> None:
        if not isinstance(feature_matrix, np.ndarray):
            raise ValueError("feature_matrix 必须是 numpy.ndarray")
        if feature_matrix.ndim != 2:
            raise ValueError("feature_matrix 必须为二维数组 [num_samples, condition_feature_dim]")
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
        return self._validate_indices(indices, sample_count, name, allow_empty=True, check_duplicate=True)

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
        unique_count = int(np.unique(train_features, axis=0).shape[0])
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

        if self._has_enhanced_label_features(feature_names):
            return self._build_enhanced_label_mapping(
                feature_names=feature_names,
                cluster_centers_original_scale=cluster_centers_original_scale,
            )

        if "speed_mean" not in feature_names:
            warnings.append("缺少 speed_mean，无法基于速度均值解释工况，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)
        if "speed_delta" not in feature_names:
            warnings.append("缺少 speed_delta，无法基于速度变化解释进站/出站，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        warnings.append("增强工况命名特征缺失，已降级到 speed_delta 命名逻辑")
        speed_delta_values = cluster_centers_original_scale[:, feature_names.index("speed_delta")]
        accelerate_cluster = int(np.argmax(speed_delta_values))
        decelerate_cluster = int(np.argmin(speed_delta_values))
        if accelerate_cluster == decelerate_cluster:
            warnings.append("自动标签映射不确定，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        remaining_clusters = sorted(set(range(config.n_clusters)) - {accelerate_cluster, decelerate_cluster})
        if len(remaining_clusters) != 1:
            warnings.append("自动标签映射不确定，已使用默认工况名称")
            return self._default_label_mapping(config.n_clusters)

        return {
            accelerate_cluster: "出站加速",
            remaining_clusters[0]: "高速巡航",
            decelerate_cluster: "进站减速",
        }

    def _has_enhanced_label_features(self, feature_names: list[str]) -> bool:
        required = {
            "speed_median",
            "speed_delta_robust",
            "speed_diff_clipped_mean",
            "positive_diff_ratio",
            "negative_diff_ratio",
        }
        return required.issubset(set(feature_names))

    def _build_enhanced_label_mapping(
        self,
        *,
        feature_names: list[str],
        cluster_centers_original_scale: np.ndarray,
    ) -> dict[int, str]:
        metrics = {
            name: self._center_metric(name, feature_names, cluster_centers_original_scale)
            for name in (
                "speed_median",
                "speed_delta_robust",
                "speed_diff_clipped_mean",
                "positive_diff_ratio",
                "negative_diff_ratio",
                "brake_mean",
                "brake_active_ratio",
            )
        }
        decel_score = (
            -self._zscore(metrics["speed_delta_robust"])
            - self._zscore(metrics["speed_diff_clipped_mean"])
            + self._zscore(metrics["negative_diff_ratio"])
            + 0.70 * self._zscore(metrics["brake_active_ratio"])
            + 0.40 * self._zscore(metrics["brake_mean"])
        )
        decelerate_cluster = int(np.argmax(decel_score))

        remaining = sorted(set(range(cluster_centers_original_scale.shape[0])) - {decelerate_cluster})
        accel_score = (
            self._zscore(metrics["speed_delta_robust"])
            + self._zscore(metrics["speed_diff_clipped_mean"])
            + self._zscore(metrics["positive_diff_ratio"])
            - 0.70 * self._zscore(metrics["brake_active_ratio"])
        )
        accelerate_cluster = max(remaining, key=lambda cluster_id: float(accel_score[cluster_id]))
        cruise_cluster_candidates = sorted(set(range(cluster_centers_original_scale.shape[0])) - {decelerate_cluster, accelerate_cluster})
        cruise_cluster = cruise_cluster_candidates[0]

        return {
            int(accelerate_cluster): "出站加速",
            int(cruise_cluster): "高速巡航",
            int(decelerate_cluster): "进站减速",
        }

    def _center_metric(
        self,
        name: str,
        feature_names: list[str],
        centers: np.ndarray,
    ) -> np.ndarray:
        if name not in feature_names:
            return np.zeros(centers.shape[0], dtype=np.float32)
        return centers[:, feature_names.index(name)].astype(np.float32, copy=False)

    @staticmethod
    def _zscore(values: np.ndarray) -> np.ndarray:
        std = float(np.std(values))
        if std < 1e-6:
            return np.zeros_like(values, dtype=np.float32)
        return ((values - float(np.mean(values))) / std).astype(np.float32, copy=False)

    def _default_label_mapping(self, n_clusters: int) -> dict[int, str]:
        return {cluster_id: f"工况{cluster_id}" for cluster_id in range(n_clusters)}

    def _build_summary(
        self,
        *,
        feature_matrix: np.ndarray,
        feature_names: list[str],
        train_indices: np.ndarray,
        stable_train_indices: np.ndarray,
        val_indices: np.ndarray | None,
        test_indices: np.ndarray | None,
        condition_ids: np.ndarray,
        kmeans_condition_ids: np.ndarray,
        condition_label_mapping: dict[int, str],
        cluster_centers_original_scale: np.ndarray,
        warnings: list[str],
        n_clusters: int,
        feature_weights: dict[str, float],
        anchor_summary: dict[str, Any],
        stable_fit_enabled: bool,
    ) -> dict[str, Any]:
        cluster_sample_count = self._count_by_cluster(condition_ids, n_clusters)
        cluster_train_sample_count = self._count_by_cluster(condition_ids[train_indices], n_clusters)
        kmeans_cluster_sample_count = self._count_by_cluster(kmeans_condition_ids, n_clusters)

        self._append_cluster_warnings(
            cluster_sample_count=cluster_sample_count,
            cluster_train_sample_count=cluster_train_sample_count,
            sample_count=int(feature_matrix.shape[0]),
            warnings=warnings,
        )

        return {
            "n_clusters": int(n_clusters),
            "fit_scope": "train_split_only",
            "stable_fit_enabled": bool(stable_fit_enabled),
            "sample_count": int(feature_matrix.shape[0]),
            "train_sample_count": int(train_indices.shape[0]),
            "stable_train_sample_count": int(stable_train_indices.shape[0]),
            "val_sample_count": None if val_indices is None else int(val_indices.shape[0]),
            "test_sample_count": None if test_indices is None else int(test_indices.shape[0]),
            "feature_names": list(feature_names),
            "cluster_feature_names": list(feature_names),
            "feature_weights": {key: float(value) for key, value in feature_weights.items()},
            "cluster_sample_count": {str(cluster_id): int(count) for cluster_id, count in cluster_sample_count.items()},
            "kmeans_cluster_sample_count": {str(cluster_id): int(count) for cluster_id, count in kmeans_cluster_sample_count.items()},
            "cluster_train_sample_count": {str(cluster_id): int(count) for cluster_id, count in cluster_train_sample_count.items()},
            "condition_label_mapping": {str(cluster_id): label for cluster_id, label in condition_label_mapping.items()},
            "cluster_feature_summary": self._build_cluster_feature_summary(
                feature_names=feature_names,
                cluster_centers_original_scale=cluster_centers_original_scale,
                n_clusters=n_clusters,
            ),
            "anchor_summary": anchor_summary,
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
                warnings.append(f"簇 {cluster_id} 全量样本占比过低，ratio={ratio:.6f}")

        for cluster_id, count in cluster_train_sample_count.items():
            if count < self.MIN_TRAIN_SAMPLES_PER_CLUSTER:
                warnings.append(f"簇 {cluster_id} 在训练集中样本数过少，train_count={count}")

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
