from __future__ import annotations

from typing import Any

import pandas as pd


class MonitorFeatureAdapter:
    """
    将 server 传入的 InfluxDB monitor_rows 轻量转换为训练特征字段。

    缺失值、数值转换和最终特征列抽取均由 FeatureProcessor 负责。
    """

    FIELD_TO_FEATURE_COLUMNS = {
        "speed": ("速度",),
        "mileage": ("里程",),
        "line_id": ("线路编号", "线路编号.1", "线路编号.2", "线路编号.3"),
        "direction": ("行别", "行别.1", "行别.2", "行别.3", "运行方向"),
        "balise_id": ("应答器编号",),
        "balise_mileage": ("应答器里程",),
        "signal_id": ("信号机ID", "信号机ID.1"),
        "signal_mileage": ("信号机里程", "信号机里程.1"),
        "outdoor_temperature": ("室外温度",),
        "humidity": ("湿度",),
    }

    METADATA_COLUMNS = ("sample_time", "condition_label", "device_code")

    def to_feature_dataframe(self, monitor_rows: list[dict[str, Any]]) -> pd.DataFrame:
        if not monitor_rows:
            return pd.DataFrame()

        output_rows: list[dict[str, Any]] = []
        first_mileage = self._to_float(monitor_rows[0].get("mileage"))

        for row in monitor_rows:
            adapted: dict[str, Any] = {}

            for metadata_column in self.METADATA_COLUMNS:
                if metadata_column in row:
                    adapted[metadata_column] = row.get(metadata_column)

            for source_field, target_columns in self.FIELD_TO_FEATURE_COLUMNS.items():
                if source_field not in row:
                    continue
                for target_column in target_columns:
                    adapted[target_column] = row.get(source_field)

            mileage = self._to_float(row.get("mileage"))
            if mileage is not None and first_mileage is not None:
                adapted["运行距离"] = mileage - first_mileage

            output_rows.append(adapted)

        return pd.DataFrame(output_rows)

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
