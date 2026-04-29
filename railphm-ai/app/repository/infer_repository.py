from datetime import datetime, timedelta
from typing import Dict


class InferRepository:
    """
    mock 推理结果访问层。
    当前不依赖数据库与真实模型，后续可在此层替换为真实模型推理调用。
    """

    _MOCK_PROFILE = {
        1: {
            "risk_score": 0.82,
            "risk_std": 0.07,
            "condition_label": "abnormal-trend",
        },
        2: {
            "risk_score": 0.52,
            "risk_std": 0.04,
            "condition_label": "normal-cruise",
        },
        0: {
            "risk_score": 0.21,
            "risk_std": 0.02,
            "condition_label": "stable",
        },
    }

    @classmethod
    def infer(
        cls,
        device_id: int,
        ts_end: datetime,
        window_minutes: int,
        model_version: str,
    ) -> Dict[str, object]:
        profile = cls._MOCK_PROFILE[device_id % 3].copy()
        window_start = ts_end - timedelta(minutes=window_minutes)

        result = {
            "device_id": device_id,
            "ts_end": ts_end.strftime("%Y-%m-%d %H:%M:%S"),
            "window_minutes": window_minutes,
            "window_start_time": window_start.strftime("%Y-%m-%d %H:%M:%S"),
            "window_end_time": ts_end.strftime("%Y-%m-%d %H:%M:%S"),
            "model_version": model_version,
        }
        result.update(profile)

        return result
