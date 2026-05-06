from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from app.dataset.feature_config import (
    LABEL_COL,
    MANIFEST_METADATA_COLUMNS,
    MODEL_EXCLUDED_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
)


@dataclass
class FeatureProcessResult:
    """
    单个 segment 的特征处理结果。

    feature_matrix:
        模型输入矩阵，shape = [row_count, feature_dim]。

    feature_columns:
        实际进入模型输入 X 的字段顺序。

    missing_feature_columns:
        在当前 segment 中不存在、但配置要求使用的特征列。

    all_nan_feature_columns:
        当前 segment 中存在，但转数值后整列为空的特征列。
    """

    feature_matrix: np.ndarray
    feature_columns: list[str]
    missing_feature_columns: list[str]
    all_nan_feature_columns: list[str]

# 特征处理器类，将原始 DataFrame 转换成模型可用的特征矩阵
class FeatureProcessor:
    """
    ATP segment 特征处理器。

    职责：
    1. 从完整 DataFrame 中抽取模型输入字段；
    2. 防止标签字段、敏感字段、业务追溯字段进入模型 X；
    3. 将输入统一转成数值；
    4. 处理缺失值；
    5. 做 segment 内 min-max 归一化。

    没有做：
    - 读取 CSV；
    - 解析时间；
    - 构造滑动窗口；
    - 生成标签 y；
    - 写出 X.npy / y.npy。
    """

    LABEL_RELATED_COLUMNS = {
        LABEL_COL,
        f"{LABEL_COL}.1",
        f"{LABEL_COL}.2",
    }

    def __init__(self, feature_columns: Optional[list[str]] = None):
        raw_feature_columns = feature_columns or NUMERIC_FEATURE_COLUMNS
        self._feature_columns = self._sanitize_feature_columns(raw_feature_columns)
    # 接收一个 DataFrame，返回特征处理结果对象
    def transform(self, df: pd.DataFrame) -> FeatureProcessResult:
        if df is None or not isinstance(df, pd.DataFrame):
            raise ValueError("FeatureProcessor.transform 需要传入 pandas DataFrame")

        row_count = len(df)
        missing_feature_columns: list[str] = []
        all_nan_feature_columns: list[str] = []
        # 存储每列转换后的数值 Series
        numeric_data: dict[str, pd.Series] = {}

        for column in self._feature_columns:
            if column not in df.columns:
                missing_feature_columns.append(column)
                numeric_data[column] = pd.Series([np.nan] * row_count, index=df.index)
                continue

            numeric_series = self._to_numeric_series(df[column])

            if numeric_series.isna().all():
                all_nan_feature_columns.append(column)

            numeric_data[column] = numeric_series

        feature_df = pd.DataFrame(numeric_data, index=df.index)

        feature_df = self._fill_missing_values(feature_df)
        # 对每列进行 min-max 归一化，统一到 [0,1] 范围
        feature_df = self._min_max_normalize(feature_df)
        feature_matrix = feature_df.to_numpy(dtype=np.float32, copy=True)

        if np.isnan(feature_matrix).any():
            raise ValueError("特征处理结果中仍存在 NaN，请检查缺失值处理逻辑")

        return FeatureProcessResult(
            feature_matrix=feature_matrix,
            feature_columns=self.get_feature_columns(),
            missing_feature_columns=missing_feature_columns,
            all_nan_feature_columns=all_nan_feature_columns,
        )

    def get_feature_columns(self) -> list[str]:
        return list(self._feature_columns)

    def _sanitize_feature_columns(self, raw_feature_columns: list[str]) -> list[str]:
        excluded = set(MODEL_EXCLUDED_COLUMNS)
        label_related = set(self.LABEL_RELATED_COLUMNS)
        metadata_columns = set(MANIFEST_METADATA_COLUMNS)

        sanitized: list[str] = []
        seen: set[str] = set()

        for column in raw_feature_columns:
            if not column or column in seen:
                continue

            if column in excluded:
                continue

            if column in label_related:
                continue

            # 元信息字段默认不进入模型 X。
            if column in metadata_columns and column not in NUMERIC_FEATURE_COLUMNS:
                continue

            sanitized.append(column)
            seen.add(column)

        return sanitized

    def _to_numeric_series(self, series: pd.Series) -> pd.Series:
        """
        将单列特征转为数值。

        这里对 True/False 字符串做轻量处理，是为了兼容“司机操作是否合规”
        这类布尔业务字段。其他无法转数值的内容统一变成 NaN。
        """
        normalized = series.replace(
            {
                True: 1,
                False: 0,
                "True": 1,
                "False": 0,
                "true": 1,
                "false": 0,
                "TRUE": 1,
                "FALSE": 0,
                "是": 1,
                "否": 0,
            }
        )

        return pd.to_numeric(normalized, errors="coerce")
    # 缺失值处理
    def _fill_missing_values(self, feature_df: pd.DataFrame) -> pd.DataFrame:
        """
        1. 线性插值；
        2. 前向填充；
        3. 后向填充；
        4. 仍为空则填 0。
        """
        if feature_df.empty:
            return feature_df

        filled = feature_df.interpolate(method="linear", limit_direction="both")
        filled = filled.ffill()
        filled = filled.bfill()
        filled = filled.fillna(0)

        return filled

    def _min_max_normalize(self, feature_df: pd.DataFrame) -> pd.DataFrame:
        """
        segment 内部 min-max 归一化。

        如果某列 max == min，说明该列在当前 segment 内没有变化，
        归一化后统一置为 0。
        """
        normalized = feature_df.copy()

        for column in normalized.columns:
            col_min = normalized[column].min()
            col_max = normalized[column].max()

            if pd.isna(col_min) or pd.isna(col_max) or col_max == col_min:
                normalized[column] = 0.0
            else:
                normalized[column] = (normalized[column] - col_min) / (col_max - col_min)

        return normalized