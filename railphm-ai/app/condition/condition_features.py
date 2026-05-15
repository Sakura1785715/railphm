"""
把三维窗口数据 X
[num_samples, window_size, feature_dim]

转换成二维工况统计特征矩阵
[num_samples, condition_feature_dim]

选取速度作为输入特征，根据速度计算统计了七个特征：
speed_mean：窗口内所有速度值的平均值
speed_std：窗口内速度值的标准差
speed_min：窗口内最低速度
speed_max：窗口内最高速度
speed_delta：窗口首尾速度差
speed_diff_mean：相邻速度变化均值
speed_diff_std：相邻速度变化标准差
进行工况划分
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np



@dataclass
class ConditionFeatureResult:
    """工况统计特征提取结果"""
    # 提取出来的工况统计特征矩阵,feature_matrix.shape = [sample_num, feature_dim]
    feature_matrix: np.ndarray
    # 每一列工况特征的名称
    feature_names: list[str]
    # 提取过程中的警告信息
    warnings: list[str]


class ConditionFeatureExtractor:
    """
    从窗口数据 X 中提取用于 K-means 工况划分的窗口级统计特征。

    输入 X 的形状为 [num_samples, window_size, feature_dim]，
    feature_columns 用于定位 X 第三维对应的原始字段。
    """
    # 核心工况字段: 速度
    SPEED_COLUMN = "速度"   
    # 可选工况辅助字段（原始特征名，输出特征名，计算方式）
    OPTIONAL_FEATURES = ()
    # 禁止进入工况特征的字段
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

    FORBIDDEN_KEYWORDS = (
        "报警部位",
        "司机名",
        "司机手机号",
        "司机操作",
    )

    def extract(self, X: np.ndarray, feature_columns: list[str]) -> ConditionFeatureResult:
        """
        提取窗口级工况统计特征。

        返回 feature_matrix、feature_names 和 warnings。
        """
        self._validate_inputs(X, feature_columns)

        warnings: list[str] = []
        self._collect_forbidden_column_warnings(feature_columns, warnings)

        column_index = {column: index for index, column in enumerate(feature_columns)}

        if self.SPEED_COLUMN not in column_index:
            raise ValueError("缺少核心工况字段：速度，无法提取工况特征")

        num_samples, window_size, _ = X.shape
        feature_parts: list[np.ndarray] = []
        feature_names: list[str] = []
        # 每个窗口样本的30个速度值
        # speed_values.shape = [325800, 30]
        speed_values = X[:, :, column_index[self.SPEED_COLUMN]].astype(np.float32, copy=False)

        self._append_feature(feature_parts, feature_names, "speed_mean", np.mean(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_std", np.std(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_min", np.min(speed_values, axis=1))
        self._append_feature(feature_parts, feature_names, "speed_max", np.max(speed_values, axis=1))
        self._append_feature(
            feature_parts,
            feature_names,
            "speed_delta",
            speed_values[:, -1] - speed_values[:, 0],
        )

        if window_size < 2:
            warnings.append("window_size 小于 2，speed_diff_mean 和 speed_diff_std 已置为 0")
            zero_values = np.zeros(num_samples, dtype=np.float32)
            self._append_feature(feature_parts, feature_names, "speed_diff_mean", zero_values)
            self._append_feature(feature_parts, feature_names, "speed_diff_std", zero_values)
        else:
            # 相邻时间点速度变化量
            speed_diff = np.diff(speed_values, axis=1)
            self._append_feature(
                feature_parts,
                feature_names,
                "speed_diff_mean",
                np.mean(speed_diff, axis=1), # 窗口内平均每一步速度变化
            )
            self._append_feature(
                feature_parts,
                feature_names,
                "speed_diff_std", # 窗口内每一步速度变化标准差
                np.std(speed_diff, axis=1),
            )

        for column_name, output_name, method in self.OPTIONAL_FEATURES:
            if column_name not in column_index:
                warnings.append(f"缺少可选工况字段：{column_name}，已跳过 {output_name}")
                continue

            if self._is_forbidden_column(column_name):
                warnings.append(f"检测到标签字段或泄露字段：{column_name}，已跳过 {output_name}")
                continue
            # values.shape = [num_samples, window_size]，取出窗口对应特征字段的值
            values = X[:, :, column_index[column_name]].astype(np.float32, copy=False)

            if method == "delta":
                feature_values = values[:, -1] - values[:, 0]
            else:
                feature_values = np.mean(values, axis=1)

            self._append_feature(feature_parts, feature_names, output_name, feature_values)

        if not feature_parts:
            raise ValueError("未生成任何工况特征，请检查输入字段")

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
        if normalized in self.FORBIDDEN_EXACT_COLUMNS:
            return True

        return any(keyword in column for keyword in self.FORBIDDEN_KEYWORDS)

    def _append_feature(
        self,
        feature_parts: list[np.ndarray],
        feature_names: list[str],
        name: str,
        values: np.ndarray,
    ) -> None:
        feature_parts.append(np.asarray(values, dtype=np.float32))
        feature_names.append(name)