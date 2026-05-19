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

    # 去掉明显编号类 / ID 类字段，但保留“运行方向”作为轻量运行状态编码。
    "remove_id_like_features": [
        "速度",
        "里程",
        "运行距离",
        "应答器里程",
        "信号机里程",
        "信号机里程.1",
        "运行方向",
        "室外温度",
        "湿度",
    ],

    # 只保留连续物理量或近似连续字段，彻底去掉 ID / 编号 / 类别编码字段。
    "continuous_only_features": [
        "速度",
        "里程",
        "运行距离",
        "应答器里程",
        "信号机里程",
        "信号机里程.1",
        "室外温度",
        "湿度",
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
    "司机操作",
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