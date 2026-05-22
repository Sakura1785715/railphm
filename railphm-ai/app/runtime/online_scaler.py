from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from app.runtime.model_loader import SequenceModelRuntime


@dataclass
class OnlineScaler:
    """训练集 z-score scaler 的在线推理只读封装。"""

    scaler_path: Path | None
    applied: bool
    reason: str | None
    mean: np.ndarray | None
    safe_std: np.ndarray | None
    feature_indices: np.ndarray | None
    mode: str

    def transform(self, feature_matrix: np.ndarray) -> np.ndarray:
        if not self.applied:
            return feature_matrix.astype(np.float32, copy=False)
        assert self.mean is not None
        assert self.safe_std is not None
        assert self.feature_indices is not None
        scaled = feature_matrix.astype(np.float32, copy=True)
        scaled[:, self.feature_indices] = (
            (scaled[:, self.feature_indices] - self.mean) / self.safe_std
        ).astype(np.float32)
        return scaled

    def trace(self) -> dict[str, Any]:
        return {
            "scaler_applied": self.applied,
            "scaler_mode": self.mode,
            "scaler_path": str(self.scaler_path) if self.scaler_path else None,
            "scaler_reason": self.reason,
        }


class OnlineScalerLoader:
    """按模型运行时加载并缓存 scaler_summary.json。"""

    _cache: dict[tuple[str, tuple[str, ...]], OnlineScaler] = {}

    @classmethod
    def load_for_runtime(cls, runtime: "SequenceModelRuntime") -> OnlineScaler:
        dataset_dir = cls._resolve_dataset_dir(runtime)
        cache_key = (str(dataset_dir), tuple(runtime.feature_columns))

        if cache_key not in cls._cache:
            cls._cache[cache_key] = cls._load(dataset_dir, runtime.feature_columns)

        return cls._cache[cache_key]

    @staticmethod
    def _resolve_dataset_dir(runtime: "SequenceModelRuntime") -> Path:
        dataset_dir = Path(runtime.manifest.dataset_dir)
        if dataset_dir.is_absolute():
            return dataset_dir
        return (runtime.manifest.model_dir / dataset_dir).resolve()

    @classmethod
    def _load(cls, dataset_dir: Path, feature_columns: list[str]) -> OnlineScaler:
        scaler_path = dataset_dir / "scaler_summary.json"
        if not scaler_path.exists():
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason="scaler_summary.json not found under manifest dataset_dir",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )

        try:
            summary = json.loads(scaler_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason=f"failed to read scaler_summary.json: {exc}",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )

        scaler_columns = summary.get("feature_columns")
        mean = summary.get("mean")
        safe_std = summary.get("safe_std")

        if not isinstance(scaler_columns, list) or not all(
            isinstance(column, str) and column for column in scaler_columns
        ):
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason="scaler_summary.json missing valid feature_columns",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )

        if not isinstance(mean, list) or not isinstance(safe_std, list):
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason="scaler_summary.json missing mean or safe_std",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )

        if len(mean) != len(scaler_columns) or len(safe_std) != len(scaler_columns):
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason="scaler mean/safe_std length mismatch",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )

        missing_scaler_columns = [
            column for column in scaler_columns if column not in feature_columns
        ]
        if missing_scaler_columns:
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason="scaler feature_columns contain columns absent from runtime.feature_columns",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )

        feature_indices = np.asarray(
            [feature_columns.index(column) for column in scaler_columns],
            dtype=np.int64,
        )

        mean_array = np.asarray(mean, dtype=np.float32).reshape(1, -1)
        safe_std_array = np.asarray(safe_std, dtype=np.float32).reshape(1, -1)
        if not np.isfinite(mean_array).all() or not np.isfinite(safe_std_array).all():
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason="scaler mean/safe_std contains NaN or inf",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )
        if (safe_std_array == 0).any():
            return OnlineScaler(
                scaler_path=scaler_path,
                applied=False,
                reason="scaler safe_std contains zero",
                mean=None,
                safe_std=None,
                feature_indices=None,
                mode="none",
            )

        return OnlineScaler(
            scaler_path=scaler_path,
            applied=True,
            reason=None if scaler_columns == feature_columns else "partial scaler applied to scaler_summary feature_columns only",
            mean=mean_array,
            safe_std=safe_std_array,
            feature_indices=feature_indices,
            mode="full" if scaler_columns == feature_columns else "partial",
        )
