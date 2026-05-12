"""
csv构建数据集后，进行检查
1. X.npy 是否存在
2. y.npy 是否存在
3. feature_columns.json 是否存在
4. window_manifest.csv 是否存在
5. dataset_summary.json 是否存在
6. X 是否是三维数组
7. y 是否是一维数组
8. X.shape[0] 是否等于 y.shape[0]
9. manifest 行数是否等于 y.shape[0]
10. summary["total_windows"] 是否等于 y.shape[0]
11. y 是否只包含 0 和 1
12. X 是否存在 NaN
13. X 是否存在 inf
14. X 数值是否基本在 0～1 范围内
15. X.shape[2] 是否等于 feature_columns 数量
16. manifest 是否包含 segment_id、sample_id、target_time、label 等关键字段
17. 正负样本数量是否和 summary 对得上
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_DATASET_FILES = [
    "X.npy",
    "y.npy",
    "feature_columns.json",
    "window_manifest.csv",
    "dataset_summary.json",
]

REQUIRED_MANIFEST_COLUMNS = [
    "sample_id",
    "segment_id",
    "segment_file",
    "window_start_row",
    "window_end_row",
    "target_row",
    "window_start_time",
    "window_end_time",
    "target_time",
    "label",
    "target_label_value",
]


@dataclass
class DatasetInspectionResult:
    """
    数据集质量检查结果。

    is_valid:
        是否通过核心一致性检查。

    errors:
        阻断性问题。只要 errors 非空，说明该数据集不应进入训练阶段。

    warnings:
        非阻断性提醒。比如正样本比例偏高/偏低、X 数值范围略微越界等。
    """

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    summary: dict[str, Any]


class DatasetInspector:
    """
    RailPHM 窗口数据集检查器。

    职责：
    1. 加载 X.npy、y.npy、feature_columns.json、window_manifest.csv、dataset_summary.json；
    2. 检查 X/y/manifest/summary 是否一致；
    3. 检查标签是否合法；
    4. 检查 X 是否存在 NaN / inf；
    5. 检查特征维度与 feature_columns 是否一致；
    6. 输出 inspection_summary.json。

    本类不负责：
    - 重新构建数据集；
    - 划分 train/val/test；
    - 训练模型。
    """

    def inspect(
        self,
        dataset_dir: Path,
        output_file: Path | None = None,
    ) -> DatasetInspectionResult:
        dataset_dir = Path(dataset_dir)

        errors: list[str] = []
        warnings: list[str] = []

        self._validate_dataset_dir(dataset_dir, errors)

        if errors:
            result = DatasetInspectionResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                summary={
                    "dataset_dir": str(dataset_dir),
                    "loaded": False,
                },
            )
            self._write_result_if_needed(result, output_file)
            return result

        X = np.load(dataset_dir / "X.npy")
        y = np.load(dataset_dir / "y.npy")
        feature_columns = self._read_json(dataset_dir / "feature_columns.json")
        manifest = pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig")
        build_summary = self._read_json(dataset_dir / "dataset_summary.json")

        self._inspect_shapes(X, y, manifest, feature_columns, build_summary, errors)
        self._inspect_labels(y, manifest, build_summary, errors, warnings)
        self._inspect_feature_values(X, errors, warnings)
        self._inspect_manifest(manifest, errors, warnings)
        self._inspect_segment_distribution(manifest, warnings)

        inspection_summary = self._build_inspection_summary(
            dataset_dir=dataset_dir,
            X=X,
            y=y,
            feature_columns=feature_columns,
            manifest=manifest,
            build_summary=build_summary,
            errors=errors,
            warnings=warnings,
        )

        result = DatasetInspectionResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            summary=inspection_summary,
        )

        self._write_result_if_needed(result, output_file)
        return result

    def _validate_dataset_dir(self, dataset_dir: Path, errors: list[str]) -> None:
        if not dataset_dir.exists():
            errors.append(f"数据集目录不存在: {dataset_dir}")
            return

        if not dataset_dir.is_dir():
            errors.append(f"dataset_dir 不是目录: {dataset_dir}")
            return

        for file_name in REQUIRED_DATASET_FILES:
            file_path = dataset_dir / file_name
            if not file_path.exists():
                errors.append(f"缺少数据集文件: {file_name}")

    def _inspect_shapes(
        self,
        X: np.ndarray,
        y: np.ndarray,
        manifest: pd.DataFrame,
        feature_columns: list[str],
        build_summary: dict[str, Any],
        errors: list[str],
    ) -> None:
        if X.ndim != 3:
            errors.append(f"X 必须为三维数组 [num_samples, window_size, feature_dim]，当前 shape={X.shape}")

        if y.ndim != 1:
            errors.append(f"y 必须为一维数组 [num_samples]，当前 shape={y.shape}")

        if X.ndim == 3 and y.ndim == 1:
            if X.shape[0] != y.shape[0]:
                errors.append(f"X 样本数与 y 样本数不一致: X={X.shape[0]}, y={y.shape[0]}")

            if X.shape[2] != len(feature_columns):
                errors.append(
                    "X 特征维度与 feature_columns 数量不一致: "
                    f"feature_dim={X.shape[2]}, feature_columns={len(feature_columns)}"
                )

        if len(manifest) != y.shape[0]:
            errors.append(f"manifest 行数与 y 样本数不一致: manifest={len(manifest)}, y={y.shape[0]}")

        total_windows = build_summary.get("total_windows")
        if total_windows is not None and int(total_windows) != int(y.shape[0]):
            errors.append(f"summary total_windows 与 y 样本数不一致: summary={total_windows}, y={y.shape[0]}")

        summary_x_shape = build_summary.get("X_shape")
        if summary_x_shape is not None and list(X.shape) != list(summary_x_shape):
            errors.append(f"summary X_shape 与实际 X.shape 不一致: summary={summary_x_shape}, actual={list(X.shape)}")

        summary_y_shape = build_summary.get("y_shape")
        if summary_y_shape is not None and list(y.shape) != list(summary_y_shape):
            errors.append(f"summary y_shape 与实际 y.shape 不一致: summary={summary_y_shape}, actual={list(y.shape)}")

    def _inspect_labels(
        self,
        y: np.ndarray,
        manifest: pd.DataFrame,
        build_summary: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        unique_labels = sorted(np.unique(y).tolist())
        allowed_labels = {0, 1}

        if not set(unique_labels).issubset(allowed_labels):
            errors.append(f"y 只能包含 0/1 标签，当前 unique={unique_labels}")

        if "label" in manifest.columns:
            manifest_labels = sorted(pd.Series(manifest["label"]).dropna().unique().tolist())
            if not set(manifest_labels).issubset(allowed_labels):
                errors.append(f"manifest label 只能包含 0/1，当前 unique={manifest_labels}")

            if len(manifest) == len(y):
                manifest_label_array = manifest["label"].to_numpy()
                if not np.array_equal(manifest_label_array.astype(int), y.astype(int)):
                    errors.append("manifest 中的 label 与 y.npy 不一致")

        positive_count = int(y.sum()) if y.size > 0 else 0
        negative_count = int(y.shape[0]) - positive_count
        positive_ratio = positive_count / int(y.shape[0]) if y.shape[0] > 0 else 0.0

        summary_positive_count = build_summary.get("positive_count")
        summary_negative_count = build_summary.get("negative_count")

        if summary_positive_count is not None and int(summary_positive_count) != positive_count:
            errors.append(
                f"summary positive_count 与 y 统计不一致: "
                f"summary={summary_positive_count}, actual={positive_count}"
            )

        if summary_negative_count is not None and int(summary_negative_count) != negative_count:
            errors.append(
                f"summary negative_count 与 y 统计不一致: "
                f"summary={summary_negative_count}, actual={negative_count}"
            )

        if y.shape[0] > 0 and (positive_ratio < 0.05 or positive_ratio > 0.95):
            warnings.append(f"正样本比例较极端，positive_ratio={positive_ratio:.6f}，后续训练需关注类别不平衡")

    def _inspect_feature_values(
        self,
        X: np.ndarray,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if np.isnan(X).any():
            errors.append("X 中存在 NaN")

        if np.isinf(X).any():
            errors.append("X 中存在 inf")

        if X.size == 0:
            warnings.append("X 为空数组，当前数据集没有可训练样本")
            return

        x_min = float(np.min(X))
        x_max = float(np.max(X))

        # FeatureProcessor 当前使用 segment 内 min-max 归一化，理论上应在 [0, 1]。
        # 这里允许极小浮点误差。
        if x_min < -1e-6 or x_max > 1.0 + 1e-6:
            warnings.append(f"X 数值范围不在预期 [0, 1] 内: min={x_min}, max={x_max}")

    def _inspect_manifest(
        self,
        manifest: pd.DataFrame,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        for column in REQUIRED_MANIFEST_COLUMNS:
            if column not in manifest.columns:
                errors.append(f"window_manifest.csv 缺少必要字段: {column}")

        sensitive_columns = {
            "司机手机号",
            "target_司机手机号",
            "window_start_司机手机号",
            "司机名",
            "target_司机名",
            "window_start_司机名",
        }

        leaked_sensitive_columns = sorted(sensitive_columns.intersection(set(manifest.columns)))
        if leaked_sensitive_columns:
            errors.append(f"manifest 不应包含敏感字段: {leaked_sensitive_columns}")

        if "sample_id" in manifest.columns:
            duplicated = int(manifest["sample_id"].duplicated().sum())
            if duplicated > 0:
                errors.append(f"manifest 中 sample_id 存在重复: duplicated={duplicated}")

        if "segment_id" in manifest.columns and manifest["segment_id"].isna().any():
            errors.append("manifest 中存在空 segment_id")

        if "target_time" in manifest.columns:
            empty_target_time = int(manifest["target_time"].isna().sum())
            if empty_target_time > 0:
                warnings.append(f"manifest 中存在空 target_time: count={empty_target_time}")

    def _inspect_segment_distribution(
        self,
        manifest: pd.DataFrame,
        warnings: list[str],
    ) -> None:
        if "segment_id" not in manifest.columns:
            return

        segment_count = int(manifest["segment_id"].nunique())
        if segment_count == 0:
            warnings.append("manifest 中没有有效 segment_id")
            return

        samples_per_segment = manifest.groupby("segment_id").size()
        min_samples = int(samples_per_segment.min())
        max_samples = int(samples_per_segment.max())

        if min_samples <= 0:
            warnings.append("存在样本数为 0 的 segment")

        if max_samples > min_samples * 20 and min_samples > 0:
            warnings.append(
                "不同 segment 的窗口样本数差异较大: "
                f"min_samples_per_segment={min_samples}, max_samples_per_segment={max_samples}"
            )

    def _build_inspection_summary(
        self,
        *,
        dataset_dir: Path,
        X: np.ndarray,
        y: np.ndarray,
        feature_columns: list[str],
        manifest: pd.DataFrame,
        build_summary: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        positive_count = int(y.sum()) if y.size > 0 else 0
        total_samples = int(y.shape[0])
        negative_count = total_samples - positive_count
        positive_ratio = positive_count / total_samples if total_samples > 0 else 0.0

        unique_y = sorted(np.unique(y).tolist()) if y.size > 0 else []

        segment_count = 0
        samples_per_segment_min = 0
        samples_per_segment_max = 0
        samples_per_segment_mean = 0.0

        if "segment_id" in manifest.columns and len(manifest) > 0:
            samples_per_segment = manifest.groupby("segment_id").size()
            segment_count = int(samples_per_segment.shape[0])
            samples_per_segment_min = int(samples_per_segment.min())
            samples_per_segment_max = int(samples_per_segment.max())
            samples_per_segment_mean = float(samples_per_segment.mean())

        x_min = float(np.min(X)) if X.size > 0 else None
        x_max = float(np.max(X)) if X.size > 0 else None

        return {
            "dataset_dir": str(dataset_dir),
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "X_shape": list(X.shape),
            "y_shape": list(y.shape),
            "manifest_rows": int(len(manifest)),
            "feature_dim": int(X.shape[2]) if X.ndim == 3 else None,
            "feature_column_count": len(feature_columns),
            "unique_y": unique_y,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "positive_ratio": positive_ratio,
            "X_min": x_min,
            "X_max": x_max,
            "has_nan": bool(np.isnan(X).any()),
            "has_inf": bool(np.isinf(X).any()),
            "segment_count": segment_count,
            "samples_per_segment_min": samples_per_segment_min,
            "samples_per_segment_max": samples_per_segment_max,
            "samples_per_segment_mean": samples_per_segment_mean,
            "build_summary_total_windows": build_summary.get("total_windows"),
            "build_summary_used_segment_count": build_summary.get("used_segment_count"),
            "build_summary_skipped_segment_count": build_summary.get("skipped_segment_count"),
        }

    def _read_json(self, file_path: Path) -> Any:
        return json.loads(file_path.read_text(encoding="utf-8"))

    def _write_result_if_needed(
        self,
        result: DatasetInspectionResult,
        output_file: Path | None,
    ) -> None:
        if output_file is None:
            return

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(result.summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )