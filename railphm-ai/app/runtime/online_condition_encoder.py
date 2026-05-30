from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

from app.condition.condition_features import ConditionFeatureExtractor
from app.condition.rule_condition import RuleConditionClassifier
from app.core.errors import BusinessException

if TYPE_CHECKING:
    from app.runtime.model_loader import SequenceModelRuntime


@dataclass
class OnlineConditionEncoder:
    """在线推理阶段把标准化后的基础窗口编码为工况 one-hot。"""

    condition_model_path: Path
    condition_summary_path: Path | None
    model_info: dict[str, Any]
    summary: dict[str, Any]
    n_clusters: int
    condition_label_mapping: dict[int, str]
    extractor: ConditionFeatureExtractor

    _cache: ClassVar[dict[str, "OnlineConditionEncoder"] | None] = None

    @classmethod
    def load_for_runtime(cls, runtime: "SequenceModelRuntime") -> "OnlineConditionEncoder":
        dataset_dir = cls._resolve_dataset_dir(runtime)
        cache_key = str(dataset_dir)
        if cls._cache is None:
            cls._cache = {}
        if cache_key not in cls._cache:
            cls._cache[cache_key] = cls._load(dataset_dir)
        return cls._cache[cache_key]

    def encode(
        self,
        scaled_base_window: np.ndarray,
        *,
        base_feature_columns: list[str],
        condition_columns: list[str],
        raw_base_window: np.ndarray | None = None,
    ) -> dict[str, Any]:
        self._validate_inputs(
            scaled_base_window=scaled_base_window,
            base_feature_columns=base_feature_columns,
            condition_columns=condition_columns,
            raw_base_window=raw_base_window,
        )

        condition_feature_source = raw_base_window if raw_base_window is not None else scaled_base_window
        condition_result = self.extractor.extract(
            condition_feature_source[np.newaxis, :, :].astype(np.float32, copy=False),
            base_feature_columns,
        )
        condition_feature_matrix = condition_result.feature_matrix

        kmeans_condition_id, predict_trace = self._predict_condition_id(
            condition_feature_matrix,
            condition_result.feature_names,
        )
        kmeans_condition_label = self.condition_label_mapping.get(
            kmeans_condition_id,
            f"condition_{kmeans_condition_id}",
        )
        condition_id = kmeans_condition_id
        condition_label = kmeans_condition_label
        final_condition_source = "kmeans"
        rule_trace = self._build_rule_trace(
            raw_base_window=raw_base_window,
            base_feature_columns=base_feature_columns,
            kmeans_condition_id=kmeans_condition_id,
            kmeans_condition_label=kmeans_condition_label,
        )
        if rule_trace.get("rule_is_high_confidence") and rule_trace.get("rule_condition_id") is not None:
            condition_id = int(rule_trace["rule_condition_id"])
            condition_label = str(rule_trace["rule_condition_label"])
            final_condition_source = "rule_anchor"

        column_index = self._condition_column_index(condition_id, condition_columns)

        condition_one_hot = np.zeros(len(condition_columns), dtype=np.float32)
        condition_one_hot[column_index] = 1.0
        if not np.isfinite(condition_one_hot).all() or condition_one_hot.sum() != 1.0:
            raise BusinessException(code=500, message="在线工况 one-hot 编码异常", status_code=500)

        return {
            "condition_id": condition_id,
            "condition_label": condition_label,
            "condition_one_hot": condition_one_hot,
            "trace": {
                "condition_model_path": str(self.condition_model_path),
                "condition_summary_path": str(self.condition_summary_path) if self.condition_summary_path else None,
                "condition_feature_names": condition_result.feature_names,
                "condition_feature_warnings": condition_result.warnings,
                "condition_feature_source": "raw_base_window" if raw_base_window is not None else "scaled_base_window",
                "condition_predict_method": predict_trace["method"],
                "condition_distance_to_centers": predict_trace.get("distance_to_centers"),
                "cluster_feature_names": predict_trace.get("cluster_feature_names"),
                "kmeans_condition_id": int(kmeans_condition_id),
                "kmeans_condition_label": kmeans_condition_label,
                "final_condition_source": final_condition_source,
                **rule_trace,
            },
        }

    @classmethod
    def _load(cls, dataset_dir: Path) -> "OnlineConditionEncoder":
        condition_model_path = dataset_dir / "condition_model.pkl"
        if not condition_model_path.exists():
            raise BusinessException(
                code=500,
                message=f"在线工况模型文件不存在: {condition_model_path}",
                status_code=500,
            )

        try:
            with condition_model_path.open("rb") as file_obj:
                model_info = pickle.load(file_obj)
        except Exception as exc:
            raise BusinessException(
                code=500,
                message=f"在线工况模型文件读取失败: {condition_model_path}, error={exc}",
                status_code=500,
            ) from exc

        if not isinstance(model_info, dict):
            raise BusinessException(code=500, message="condition_model.pkl 内容必须为 dict", status_code=500)

        condition_summary_path, summary = cls._load_summary(dataset_dir, model_info)
        n_clusters = cls._infer_n_clusters(model_info, summary)
        label_mapping = cls._load_label_mapping(model_info, summary)

        return cls(
            condition_model_path=condition_model_path,
            condition_summary_path=condition_summary_path,
            model_info=model_info,
            summary=summary,
            n_clusters=n_clusters,
            condition_label_mapping=label_mapping,
            extractor=ConditionFeatureExtractor(),
        )

    @staticmethod
    def _resolve_dataset_dir(runtime: "SequenceModelRuntime") -> Path:
        dataset_dir = Path(runtime.manifest.dataset_dir)
        if dataset_dir.is_absolute():
            return dataset_dir
        candidates = [(runtime.manifest.model_dir / dataset_dir).resolve()]
        candidates.extend((parent / dataset_dir).resolve() for parent in runtime.manifest.model_dir.parents)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    @classmethod
    def _load_summary(cls, dataset_dir: Path, model_info: dict[str, Any]) -> tuple[Path | None, dict[str, Any]]:
        for filename in (
            "condition_summary.json",
            "condition_model_summary.json",
            "condition_augmented_summary.json",
        ):
            summary_path = dataset_dir / filename
            if not summary_path.exists():
                continue
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(summary, dict):
                return summary_path, summary

        summary = model_info.get("summary")
        return None, summary if isinstance(summary, dict) else {}

    @staticmethod
    def _infer_n_clusters(model_info: dict[str, Any], summary: dict[str, Any]) -> int:
        candidates = [
            summary.get("n_clusters"),
            (model_info.get("config") or {}).get("n_clusters")
            if isinstance(model_info.get("config"), dict)
            else None,
        ]
        for value in candidates:
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                return int(value)

        centers = model_info.get("cluster_centers_original_scale")
        if isinstance(centers, np.ndarray) and centers.ndim == 2 and centers.shape[0] > 0:
            return int(centers.shape[0])

        mapping = OnlineConditionEncoder._load_label_mapping(model_info, summary)
        if mapping:
            return max(mapping) + 1

        raise BusinessException(code=500, message="无法确定在线工况数量 n_clusters", status_code=500)

    @staticmethod
    def _load_label_mapping(model_info: dict[str, Any], summary: dict[str, Any]) -> dict[int, str]:
        raw_mapping = model_info.get("condition_label_mapping")
        if not isinstance(raw_mapping, dict):
            raw_mapping = summary.get("condition_label_mapping", {})

        mapping: dict[int, str] = {}
        if isinstance(raw_mapping, dict):
            for raw_key, raw_value in raw_mapping.items():
                try:
                    key = int(raw_key)
                except (TypeError, ValueError):
                    continue
                if isinstance(raw_value, str) and raw_value.strip():
                    mapping[key] = raw_value.strip()
        return mapping

    def _validate_inputs(
        self,
        *,
        scaled_base_window: np.ndarray,
        base_feature_columns: list[str],
        condition_columns: list[str],
        raw_base_window: np.ndarray | None,
    ) -> None:
        if not isinstance(scaled_base_window, np.ndarray) or scaled_base_window.ndim != 2:
            raise BusinessException(code=500, message="scaled_base_window 必须为二维数组", status_code=500)
        if len(base_feature_columns) != scaled_base_window.shape[1]:
            raise BusinessException(
                code=500,
                message=(
                    "base_feature_columns 数量与基础窗口维度不一致: "
                    f"columns={len(base_feature_columns)}, dim={scaled_base_window.shape[1]}"
                ),
                status_code=500,
            )
        if len(condition_columns) != self.n_clusters:
            raise BusinessException(
                code=500,
                message=(
                    "模型工况列数量与 condition_model 不一致: "
                    f"condition_columns={len(condition_columns)}, n_clusters={self.n_clusters}"
                ),
                status_code=500,
            )
        if not np.isfinite(scaled_base_window).all():
            raise BusinessException(code=500, message="标准化基础窗口存在非法数值", status_code=500)
        if raw_base_window is not None:
            if not isinstance(raw_base_window, np.ndarray) or raw_base_window.ndim != 2:
                raise BusinessException(code=500, message="raw_base_window 必须为二维数组", status_code=500)
            if raw_base_window.shape != scaled_base_window.shape:
                raise BusinessException(
                    code=500,
                    message=(
                        "raw_base_window shape 与 scaled_base_window 不一致: "
                        f"raw={raw_base_window.shape}, scaled={scaled_base_window.shape}"
                    ),
                    status_code=500,
                )
            if not np.isfinite(raw_base_window).all():
                raise BusinessException(code=500, message="原始基础窗口存在非法数值", status_code=500)

    def _predict_condition_id(
        self,
        condition_feature_matrix: np.ndarray,
        condition_feature_names: list[str],
    ) -> tuple[int, dict[str, Any]]:
        model_features, cluster_feature_names = self._select_cluster_features(
            condition_feature_matrix,
            condition_feature_names,
        )
        scaler = self.model_info.get("condition_feature_scaler") or self.model_info.get("scaler")
        kmeans = self.model_info.get("kmeans") or self.model_info.get("model") or self.model_info.get("condition_model")

        if kmeans is not None and hasattr(kmeans, "predict"):
            model_input = model_features
            method = "kmeans_predict"
            if scaler is not None and hasattr(scaler, "transform"):
                model_input = scaler.transform(model_features).astype(np.float32, copy=False)
                model_input = self._apply_feature_weights(model_input, cluster_feature_names)
                method = "condition_feature_scaler_weights_then_kmeans_predict"
            condition_id = int(kmeans.predict(model_input)[0])
            return self._validate_condition_id(condition_id), {
                "method": method,
                "cluster_feature_names": cluster_feature_names,
            }

        centers_original = self.model_info.get("cluster_centers_original_scale")
        if isinstance(centers_original, np.ndarray) and centers_original.ndim == 2:
            self._validate_center_shape(centers_original, model_features, "cluster_centers_original_scale")
            distances = np.linalg.norm(
                model_features.astype(np.float32, copy=False) - centers_original.astype(np.float32, copy=False),
                axis=1,
            )
            condition_id = int(np.argmin(distances))
            return self._validate_condition_id(condition_id), {
                "method": "nearest_cluster_center_original_scale",
                "distance_to_centers": [float(value) for value in distances.tolist()],
                "cluster_feature_names": cluster_feature_names,
            }

        centers = self.model_info.get("cluster_centers")
        if isinstance(centers, np.ndarray) and centers.ndim == 2:
            self._validate_center_shape(centers, model_features, "cluster_centers")
            distances = np.linalg.norm(
                model_features.astype(np.float32, copy=False) - centers.astype(np.float32, copy=False),
                axis=1,
            )
            condition_id = int(np.argmin(distances))
            return self._validate_condition_id(condition_id), {
                "method": "nearest_cluster_center_saved_scale",
                "distance_to_centers": [float(value) for value in distances.tolist()],
                "cluster_feature_names": cluster_feature_names,
            }

        raise BusinessException(
            code=500,
            message="condition_model.pkl 缺少可用于在线工况识别的模型或聚类中心",
            status_code=500,
        )

    def _select_cluster_features(
        self,
        condition_feature_matrix: np.ndarray,
        condition_feature_names: list[str],
    ) -> tuple[np.ndarray, list[str]]:
        raw_cluster_feature_names = self.model_info.get("cluster_feature_names")
        if not isinstance(raw_cluster_feature_names, list) or not raw_cluster_feature_names:
            raw_cluster_feature_names = self.model_info.get("feature_names")
        if not isinstance(raw_cluster_feature_names, list) or not raw_cluster_feature_names:
            raw_cluster_feature_names = self.model_info.get("condition_feature_names")

        if isinstance(raw_cluster_feature_names, list) and raw_cluster_feature_names:
            cluster_feature_names = [
                str(name) for name in raw_cluster_feature_names
                if isinstance(name, str) and name in condition_feature_names
            ]
            if len(cluster_feature_names) != len(raw_cluster_feature_names):
                missing = [
                    str(name) for name in raw_cluster_feature_names
                    if not isinstance(name, str) or name not in condition_feature_names
                ]
                raise BusinessException(
                    code=500,
                    message=f"在线工况特征缺少训练时聚类字段: {missing}",
                    status_code=500,
                )
            indices = [condition_feature_names.index(name) for name in cluster_feature_names]
            return condition_feature_matrix[:, indices].astype(np.float32, copy=False), cluster_feature_names

        return condition_feature_matrix.astype(np.float32, copy=False), list(condition_feature_names)

    def _apply_feature_weights(
        self,
        model_input: np.ndarray,
        cluster_feature_names: list[str],
    ) -> np.ndarray:
        raw_weights = self.model_info.get("feature_weights")
        if not isinstance(raw_weights, dict):
            return model_input
        weights = np.asarray(
            [float(raw_weights.get(name, 1.0)) for name in cluster_feature_names],
            dtype=np.float32,
        ).reshape(1, -1)
        return (model_input * weights).astype(np.float32, copy=False)

    def _build_rule_trace(
        self,
        *,
        raw_base_window: np.ndarray | None,
        base_feature_columns: list[str],
        kmeans_condition_id: int,
        kmeans_condition_label: str,
    ) -> dict[str, Any]:
        if raw_base_window is None:
            return {
                "rule_condition_status": "raw_window_missing",
                "rule_condition_id": None,
                "rule_condition_label": None,
                "rule_confidence": 0.0,
                "rule_reason": None,
                "rule_stats": {},
                "rule_is_high_confidence": False,
            }

        classifier = RuleConditionClassifier(condition_label_mapping=self.condition_label_mapping)
        rule_result = classifier.classify(
            raw_base_window,
            base_feature_columns,
            kmeans_condition_id=kmeans_condition_id,
            kmeans_condition_label=kmeans_condition_label,
        )
        return {
            "rule_condition_status": "evaluated",
            "rule_condition_id": rule_result.condition_id,
            "rule_condition_label": rule_result.condition_label,
            "rule_confidence": float(rule_result.confidence),
            "rule_reason": rule_result.reason,
            "rule_stats": rule_result.stats,
            "rule_is_high_confidence": bool(rule_result.is_high_confidence),
        }

    def _validate_center_shape(
        self,
        centers: np.ndarray,
        condition_feature_matrix: np.ndarray,
        field_name: str,
    ) -> None:
        if centers.shape[0] != self.n_clusters or centers.shape[1] != condition_feature_matrix.shape[1]:
            raise BusinessException(
                code=500,
                message=(
                    f"condition_model.pkl 中 {field_name} 形状异常: "
                    f"centers={centers.shape}, "
                    f"expected=({self.n_clusters}, {condition_feature_matrix.shape[1]})"
                ),
                status_code=500,
            )

    def _validate_condition_id(self, condition_id: int) -> int:
        if condition_id < 0 or condition_id >= self.n_clusters:
            raise BusinessException(
                code=500,
                message=f"在线工况识别结果越界: condition_id={condition_id}, n_clusters={self.n_clusters}",
                status_code=500,
            )
        return condition_id

    @staticmethod
    def _condition_column_index(condition_id: int, condition_columns: list[str]) -> int:
        expected_column = f"condition_{condition_id}"
        if expected_column in condition_columns:
            return condition_columns.index(expected_column)
        if condition_id < len(condition_columns):
            return condition_id
        raise BusinessException(
            code=500,
            message=f"无法把 condition_id 映射到 one-hot 列: condition_id={condition_id}",
            status_code=500,
        )
