"""
RailPHM feature profile definitions for Task 5-3d feature ablation.

This module only defines feature-column profiles. It does not read CSV files,
build windows, split datasets, train models, or evaluate metrics.
"""

from __future__ import annotations

from app.dataset.feature_config import NUMERIC_FEATURE_COLUMNS


FEATURE_PROFILES: dict[str, list[str]] = {
    # 全量特征：所有数值类特征，从 NUMERIC_FEATURE_COLUMNS 导入
    "full_features": list(NUMERIC_FEATURE_COLUMNS),

    # 原始 CSV 中保留的基础动态字段，派生特征由 DerivedFeatureBuilder 计算。
    "base_dynamic_features": [
        "速度",
        "制动信息",
        "常用制动速度",
        "紧急制动速度",
        "天气信息",
        "室外温度",
        "湿度",
    ],

    # 仅使用代码动态生成的派生特征。
    "derived_only_features": [
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
    ],
}


FORBIDDEN_INPUT_COLUMNS = {
    "报警部位",
    "报警部位.1",
    "报警部位.2",
    "唯一标识",
    "司机名",
    "司机手机号",
    "司机号",
    "司机号.1",
    "司机操作",
    "司机操作是否合规",
    "数据时间",
    "车号",
    "车次",
    "唯一标识",
    "ATP类型",
    "配属铁路局",
    "途经铁路局",
    "里程",
    "运行距离",
    "行别",
    "行别.1",
    "行别.2",
    "行别.3",
    "线路编号",
    "线路编号.1",
    "线路编号.2",
    "线路编号.3",
    "应答器编号",
    "应答器编号.1",
    "应答器里程",
    "信号机ID",
    "信号机ID.1",
    "信号机里程",
    "信号机里程.1",
    "经度",
    "纬度",
    "经度.1",
    "纬度.1",
    "站名",
    "站名.1",
    "站名.2",
}


def list_feature_profiles() -> list[str]:
    return sorted(FEATURE_PROFILES.keys())


def get_feature_profile(profile_name: str) -> list[str]:
    if profile_name not in FEATURE_PROFILES:
        supported = ", ".join(list_feature_profiles())
        raise ValueError(f"不支持的 feature_profile: {profile_name}，支持: {supported}")

    columns = list(FEATURE_PROFILES[profile_name])
    forbidden = [column for column in columns if column in FORBIDDEN_INPUT_COLUMNS]
    if forbidden:
        raise ValueError(f"feature_profile={profile_name} 包含禁止进入模型的字段: {forbidden}")

    return columns
