"""
窗口级工况特征提取。

工况特征只描述列车运行阶段，不使用报警、标签、司机身份等泄露字段。
速度趋势使用分段中位数和裁剪差分，避免巡航抖动、冻结和跳变把故障形态误当成工况。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ConditionFeatureResult:
    """工况统计特征提取结果。"""

    feature_matrix: np.ndarray
    feature_names: list[str]
    warnings: list[str]


class ConditionFeatureExtractor:
    """
    从窗口数据 X 中提取用于工况划分的窗口级统计特征。

    输入 X 的形状为 [num_samples, window_size, feature_dim]，
    feature_columns 用于定位 X 第三维对应的原始字段。
    """

    SPEED_COLUMN = "速度"
    ACCEL_COLUMN = "加速度"
    BRAKE_COLUMN = "制动信息"
    SERVICE_BRAKE_COLUMN = "常用制动速度"
    EMERGENCY_BRAKE_COLUMN = "紧急制动速度"
    MILEAGE_COLUMN = "里程"
    RUN_DISTANCE_COLUMN = "运行距离"

    FORBIDDEN_EXACT_COLUMNS = {
        "报警部位",
        "报警部位.1",
        "报警部位.2",
        "label",
        "target_label_value",
        "y",
        "y_true",
        "y_pred",
        "risk_score",
        "health_score",
        "alert_level",
        "唯一标识",
        "司机名",
        "司机手机号",
        "司机操作",
    }
    FORBIDDEN_EXACT_COLUMNS_LOWER = {
        column.lower() for column in FORBIDDEN_EXACT_COLUMNS
    }
    FORBIDDEN_KEYWORDS = (
        "报警部位",
        "司机名",
        "司机手机号",
        "司机操作",
    )

    LEGACY_OPTIONAL_COLUMNS = (
        MILEAGE_COLUMN,
        RUN_DISTANCE_COLUMN,
        "室外温度",
        "湿度",
    )

    def extract(self, X: np.ndarray, feature_columns: list[str]) -> ConditionFeatureResult:
        """提取窗口级工况统计特征。"""
        self._validate_inputs(X, feature_columns)

        warnings: list[str] = []
        self._collect_forbidden_column_warnings(feature_columns, warnings)

        column_index = {column: index for index, column in enumerate(feature_columns)}
        if self.SPEED_COLUMN not in column_index:
            raise ValueError("缺少核心工况字段：速度，无法提取工况特征")

        for column in self.LEGACY_OPTIONAL_COLUMNS:
            if column not in column_index:
                warnings.append(f"缺少可选工况字段：{column}")

        speed_values = X[:, :, column_index[self.SPEED_COLUMN]].astype(np.float32, copy=False)
        num_samples, window_size = speed_values.shape

        feature_parts: list[np.ndarray] = []
        feature_names: list[str] = []
        zero_values = np.zeros(num_samples, dtype=np.float32)

        start_slice, end_slice = self._third_slices(window_size)
        speed_start_median = np.median(speed_values[:, start_slice], axis=1)
        speed_end_median = np.median(speed_values[:, end_slice], axis=1)
        speed_delta_robust = speed_end_median - speed_start_median

        self._append_feature(feature_parts, feature_names, "speed_median", np.median(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_mean", np.mean(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_std", np.std(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_min", np.min(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_max", np.max(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_start_median", speed_start_median)
        self._append_feature(feature_parts, feature_names, "speed_end_median", speed_end_median)
        self._append_feature(feature_parts, feature_names, "speed_delta_robust", speed_delta_robust)
        self._append_feature(feature_parts, feature_names, "speed_delta", speed_values[:, -1] - speed_values[:, 0])

        if window_size < 2:
            warnings.append("window_size 小于 2，速度差分相关特征已置为 0")
            speed_diff = np.zeros((num_samples, 0), dtype=np.float32)
            speed_diff_clipped = speed_diff
            speed_diff_mean = zero_values
            speed_diff_std = zero_values
            speed_diff_clipped_mean = zero_values
            speed_diff_clipped_std = zero_values
            positive_diff_ratio = zero_values
            negative_diff_ratio = zero_values
            speed_diff_abs_p95 = zero_values
            large_jump_count = zero_values
            freeze_ratio = zero_values
        else:
            speed_diff = np.diff(speed_values, axis=1).astype(np.float32, copy=False)
            speed_diff_clipped = self._clip_diff_by_row_quantile(speed_diff)
            speed_diff_mean = np.mean(speed_diff, axis=1)
            speed_diff_std = np.std(speed_diff, axis=1)
            speed_diff_clipped_mean = np.mean(speed_diff_clipped, axis=1)
            speed_diff_clipped_std = np.std(speed_diff_clipped, axis=1)
            positive_diff_ratio = np.mean(speed_diff_clipped > 0.05, axis=1)
            negative_diff_ratio = np.mean(speed_diff_clipped < -0.05, axis=1)
            speed_diff_abs_p95 = np.percentile(np.abs(speed_diff), 95, axis=1)
            large_jump_count = np.sum(np.abs(speed_diff) > 20.0, axis=1)
            freeze_ratio = np.mean(np.abs(speed_diff) <= 0.05, axis=1)

        speed_p95 = np.percentile(speed_values, 95, axis=1)
        speed_p05 = np.percentile(speed_values, 5, axis=1)
        self._append_feature(feature_parts, feature_names, "speed_diff_clipped_mean", speed_diff_clipped_mean)
        self._append_feature(feature_parts, feature_names, "speed_diff_clipped_std", speed_diff_clipped_std)
        self._append_feature(feature_parts, feature_names, "positive_diff_ratio", positive_diff_ratio)
        self._append_feature(feature_parts, feature_names, "negative_diff_ratio", negative_diff_ratio)
        self._append_feature(feature_parts, feature_names, "speed_volatility", speed_p95 - speed_p05)
        self._append_feature(feature_parts, feature_names, "large_jump_count", large_jump_count)
        self._append_feature(feature_parts, feature_names, "freeze_ratio", freeze_ratio)
        self._append_feature(feature_parts, feature_names, "speed_diff_abs_p95", speed_diff_abs_p95)
        self._append_feature(feature_parts, feature_names, "speed_diff_mean", speed_diff_mean)
        self._append_feature(feature_parts, feature_names, "speed_diff_std", speed_diff_std)

        accel_values = self._load_or_derive_acceleration(
            X=X,
            column_index=column_index,
            speed_values=speed_values,
            warnings=warnings,
        )
        self._append_feature(feature_parts, feature_names, "accel_mean", np.mean(accel_values, axis=1))
        self._append_feature(feature_parts, feature_names, "accel_std", np.std(accel_values, axis=1))
        self._append_feature(feature_parts, feature_names, "accel_min", np.min(accel_values, axis=1))
        self._append_feature(feature_parts, feature_names, "accel_max", np.max(accel_values, axis=1))
        self._append_feature(feature_parts, feature_names, "accel_delta", accel_values[:, -1] - accel_values[:, 0])

        brake_values = self._optional_column_values(
            X=X,
            column_index=column_index,
            column=self.BRAKE_COLUMN,
            warnings=warnings,
        )
        self._append_feature(feature_parts, feature_names, "brake_mean", np.mean(brake_values, axis=1))
        self._append_feature(feature_parts, feature_names, "brake_max", np.max(brake_values, axis=1))
        self._append_feature(feature_parts, feature_names, "brake_active_ratio", np.mean(brake_values > 0, axis=1))

        service_values = self._optional_column_values(
            X=X,
            column_index=column_index,
            column=self.SERVICE_BRAKE_COLUMN,
            warnings=warnings,
        )
        emergency_values = self._optional_column_values(
            X=X,
            column_index=column_index,
            column=self.EMERGENCY_BRAKE_COLUMN,
            warnings=warnings,
        )
        service_margin = service_values - speed_values
        emergency_margin = emergency_values - speed_values
        self._append_feature(feature_parts, feature_names, "service_margin_mean", np.mean(service_margin, axis=1))
        self._append_feature(feature_parts, feature_names, "service_margin_min", np.min(service_margin, axis=1))
        self._append_feature(feature_parts, feature_names, "emergency_margin_mean", np.mean(emergency_margin, axis=1))
        self._append_feature(feature_parts, feature_names, "emergency_margin_min", np.min(emergency_margin, axis=1))

        self._append_legacy_delta_feature(
            X=X,
            column_index=column_index,
            feature_parts=feature_parts,
            feature_names=feature_names,
            column=self.MILEAGE_COLUMN,
            feature_name="mileage_delta",
        )
        self._append_legacy_delta_feature(
            X=X,
            column_index=column_index,
            feature_parts=feature_parts,
            feature_names=feature_names,
            column=self.RUN_DISTANCE_COLUMN,
            feature_name="run_distance_delta",
        )

        feature_matrix = np.stack(feature_parts, axis=1).astype(np.float32, copy=False)
        if not np.isfinite(feature_matrix).all():
            raise ValueError("工况特征矩阵中存在 NaN 或 inf")

        return ConditionFeatureResult(
            feature_matrix=feature_matrix,
            feature_names=feature_names,
            warnings=warnings,
        )

    def _validate_inputs(self, X: np.ndarray, feature_columns: list[str]) -> None:
        if not isinstance(X, np.ndarray):
            raise ValueError("X 必须是 numpy.ndarray")
        if X.ndim != 3:
            raise ValueError("X 必须为三维数组 [num_samples, window_size, feature_dim]")
        if not isinstance(feature_columns, list) or not feature_columns:
            raise ValueError("feature_columns 必须是非空 list[str]")
        if not all(isinstance(column, str) and column for column in feature_columns):
            raise ValueError("feature_columns 必须是非空 list[str]")
        if len(feature_columns) != X.shape[2]:
            raise ValueError(
                "feature_columns 数量必须与 X 的特征维度一致: "
                f"feature_columns={len(feature_columns)}, feature_dim={X.shape[2]}"
            )
        if not np.isfinite(X).all():
            raise ValueError("X 中存在 NaN 或 inf，无法提取工况特征")

    def _collect_forbidden_column_warnings(
        self,
        feature_columns: list[str],
        warnings: list[str],
    ) -> None:
        for column in feature_columns:
            if self._is_forbidden_column(column):
                warnings.append(f"检测到标签字段或泄露字段：{column}，已跳过")

    def _is_forbidden_column(self, column: str) -> bool:
        if column in self.FORBIDDEN_EXACT_COLUMNS:
            return True
        normalized = column.strip().lower()
        if normalized in self.FORBIDDEN_EXACT_COLUMNS_LOWER:
            return True
        return any(keyword in column for keyword in self.FORBIDDEN_KEYWORDS)

    def _load_or_derive_acceleration(
        self,
        *,
        X: np.ndarray,
        column_index: dict[str, int],
        speed_values: np.ndarray,
        warnings: list[str],
    ) -> np.ndarray:
        if self.ACCEL_COLUMN in column_index:
            return X[:, :, column_index[self.ACCEL_COLUMN]].astype(np.float32, copy=False)

        warnings.append("缺少可选工况字段：加速度，已由速度差分派生")
        if speed_values.shape[1] < 2:
            return np.zeros_like(speed_values, dtype=np.float32)
        first_step = np.zeros((speed_values.shape[0], 1), dtype=np.float32)
        return np.concatenate([first_step, np.diff(speed_values, axis=1)], axis=1).astype(
            np.float32,
            copy=False,
        )

    def _optional_column_values(
        self,
        *,
        X: np.ndarray,
        column_index: dict[str, int],
        column: str,
        warnings: list[str],
    ) -> np.ndarray:
        if column in column_index:
            return X[:, :, column_index[column]].astype(np.float32, copy=False)
        warnings.append(f"缺少可选工况字段：{column}，对应特征已置为 0")
        return np.zeros(X.shape[:2], dtype=np.float32)

    def _append_legacy_delta_feature(
        self,
        *,
        X: np.ndarray,
        column_index: dict[str, int],
        feature_parts: list[np.ndarray],
        feature_names: list[str],
        column: str,
        feature_name: str,
    ) -> None:
        if column not in column_index:
            return
        values = X[:, :, column_index[column]].astype(np.float32, copy=False)
        self._append_feature(feature_parts, feature_names, feature_name, values[:, -1] - values[:, 0])

    @staticmethod
    def _third_slices(window_size: int) -> tuple[slice, slice]:
        third = max(1, window_size // 3)
        return slice(0, third), slice(window_size - third, window_size)

    @staticmethod
    def _clip_diff_by_row_quantile(speed_diff: np.ndarray) -> np.ndarray:
        if speed_diff.shape[1] == 0:
            return speed_diff.astype(np.float32, copy=False)
        lower = np.percentile(speed_diff, 5, axis=1)
        upper = np.percentile(speed_diff, 95, axis=1)
        return np.clip(speed_diff, lower[:, None], upper[:, None]).astype(np.float32, copy=False)

    def _append_feature(
        self,
        feature_parts: list[np.ndarray],
        feature_names: list[str],
        name: str,
        values: np.ndarray,
    ) -> None:
        feature_parts.append(np.asarray(values, dtype=np.float32))
        feature_names.append(name)
