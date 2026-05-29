"""
动态派生 ATP 窗口模型所需特征。

新数据集不再提前把派生特征写入 CSV，本模块在单个 segment 内按原始行顺序生成。
"""
from __future__ import annotations

import pandas as pd


class DerivedFeatureBuilder:
    """在单个 CSV segment 内构造派生特征，不跨文件、不使用未来信息。"""

    BASE_COLUMNS = [
        "速度",
        "制动信息",
        "常用制动速度",
        "紧急制动速度",
        "天气信息",
        "室外温度",
        "湿度",
    ]

    DERIVED_COLUMNS = [
        "加速度",
        "加速度变化率",
        "速度滚动标准差",
        "速度滚动最大跳变",
        "常用制动裕度",
        "紧急制动裕度",
        "常用制动裕度变化",
        "紧急制动裕度变化",
        "温度变化率",
        "湿度变化率",
        "恶劣天气标志",
    ]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame):
            raise ValueError("DerivedFeatureBuilder.transform 需要传入 pandas DataFrame")

        missing_columns = [column for column in self.BASE_COLUMNS if column not in df.columns]
        if missing_columns:
            raise ValueError(f"缺少派生特征基础字段: {missing_columns}")

        enriched = df.copy()

        for column in self.BASE_COLUMNS:
            enriched[column] = pd.to_numeric(enriched[column], errors="coerce")

        all_nan_base_columns = [
            column for column in self.BASE_COLUMNS if enriched[column].isna().all()
        ]
        if all_nan_base_columns:
            raise ValueError(f"派生特征基础字段转数值后全为空: {all_nan_base_columns}")

        # “加速度”是速度一阶差分近似表征加速度趋势，不是严格物理单位。
        enriched["加速度"] = enriched["速度"].diff().fillna(0)
        enriched["加速度变化率"] = enriched["加速度"].diff().fillna(0)
        enriched["速度滚动标准差"] = (
            enriched["速度"].rolling(window=5, min_periods=1).std().fillna(0)
        )
        enriched["速度滚动最大跳变"] = (
            enriched["速度"].diff().abs().rolling(window=5, min_periods=1).max().fillna(0)
        )
        enriched["常用制动裕度"] = enriched["常用制动速度"] - enriched["速度"]
        enriched["紧急制动裕度"] = enriched["紧急制动速度"] - enriched["速度"]
        enriched["常用制动裕度变化"] = enriched["常用制动裕度"].diff().fillna(0)
        enriched["紧急制动裕度变化"] = enriched["紧急制动裕度"].diff().fillna(0)
        enriched["温度变化率"] = enriched["室外温度"].diff().fillna(0)
        enriched["湿度变化率"] = enriched["湿度"].diff().fillna(0)
        enriched["恶劣天气标志"] = enriched["天气信息"].isin([1, 2, 3, 4]).astype(int)

        missing_derived = [
            column for column in self.DERIVED_COLUMNS if column not in enriched.columns
        ]
        if missing_derived:
            raise ValueError(f"派生特征生成失败，缺少字段: {missing_derived}")

        enriched[self.DERIVED_COLUMNS] = enriched[self.DERIVED_COLUMNS].fillna(0)

        return enriched
