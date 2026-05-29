from __future__ import annotations

from typing import Any

import pandas as pd

from app.dataset.derived_feature_builder import DerivedFeatureBuilder


class MonitorFeatureAdapter:
    """
    将 server 传入的 InfluxDB monitor_rows 轻量转换为训练特征字段。

    缺失值、数值转换和最终特征列抽取均由 FeatureProcessor 负责。
    """

    FIELD_TO_FEATURE_COLUMNS = {
        "speed": ("速度",),
        "速度": ("速度",),
        "brake_info": ("制动信息",),
        "制动信息": ("制动信息",),
        "service_brake_speed": ("常用制动速度",),
        "常用制动速度": ("常用制动速度",),
        "emergency_brake_speed": ("紧急制动速度",),
        "紧急制动速度": ("紧急制动速度",),
        "weather_info": ("天气信息",),
        "weather": ("天气信息",),
        "天气信息": ("天气信息",),
        "outdoor_temperature": ("室外温度",),
        "室外温度": ("室外温度",),
        "humidity": ("湿度",),
        "湿度": ("湿度",),
        "mileage": ("里程",),
        "里程": ("里程",),
        "run_distance": ("运行距离",),
        "运行距离": ("运行距离",),
        "line_id": ("线路编号", "线路编号.1", "线路编号.2", "线路编号.3"),
        "direction": ("行别", "行别.1", "行别.2", "行别.3", "运行方向"),
        "balise_id": ("应答器编号",),
        "balise_mileage": ("应答器里程",),
        "signal_id": ("信号机ID", "信号机ID.1"),
        "signal_mileage": ("信号机里程", "信号机里程.1"),
    }

    METADATA_COLUMNS = ("sample_time", "condition_label", "device_code")

    def __init__(self, derived_feature_builder: DerivedFeatureBuilder | None = None) -> None:
        self.derived_feature_builder = derived_feature_builder or DerivedFeatureBuilder()

    def to_feature_dataframe(self, monitor_rows: list[dict[str, Any]]) -> pd.DataFrame:
        if not monitor_rows:
            return pd.DataFrame()

        output_rows: list[dict[str, Any]] = []
        first_mileage = self._to_float(self._first_present_value(monitor_rows[0], ("mileage", "里程")))

        for row in monitor_rows:
            adapted: dict[str, Any] = dict(row)

            for metadata_column in self.METADATA_COLUMNS:
                if metadata_column in row:
                    adapted[metadata_column] = row.get(metadata_column)

            for source_field, target_columns in self.FIELD_TO_FEATURE_COLUMNS.items():
                if source_field not in row:
                    continue
                for target_column in target_columns:
                    if self._has_value(adapted.get(target_column)):
                        continue
                    adapted[target_column] = row.get(source_field)

            mileage = self._to_float(self._first_present_value(row, ("mileage", "里程")))
            if mileage is not None and first_mileage is not None:
                adapted["运行距离"] = mileage - first_mileage

            output_rows.append(adapted)

        feature_df = pd.DataFrame(output_rows)
        if self._can_build_derived_features(feature_df):
            return self.derived_feature_builder.transform(feature_df)

        return feature_df

    def _can_build_derived_features(self, feature_df: pd.DataFrame) -> bool:
        for column in self.derived_feature_builder.BASE_COLUMNS:
            if column not in feature_df.columns:
                return False
            numeric_series = pd.to_numeric(feature_df[column], errors="coerce")
            if numeric_series.isna().all():
                return False
        return True

    @staticmethod
    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    @staticmethod
    def _first_present_value(row: dict[str, Any], fields: tuple[str, ...]) -> Any:
        for field in fields:
            value = row.get(field)
            if MonitorFeatureAdapter._has_value(value):
                return value
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
