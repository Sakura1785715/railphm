"""
WindowSampleRepository
负责根据 sample_index 从 X.npy / y.npy 里取出一个窗口样本

SequenceModelRuntime
负责加载 Bi-LSTM+Attention 模型，并对这个窗口做预测
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from flask import current_app

from app.core.errors import BusinessException
from app.repository.window_sample_repository import WindowSampleRepository

if TYPE_CHECKING:
    from app.runtime.model_loader import SequenceModelRuntime

class InferRepository:
    """
    推理结果访问层。

    默认使用 SequenceModelRuntime 执行真实模型推理，并在模型或本地数据集缺失时按配置
    退回 mock fallback，避免开发环境服务完全不可用。
    """

    # mock模拟预测结果
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

    # 类变量缓存：避免每次请求都重新加载模型
    _runtime: "SequenceModelRuntime | None" = None
    _window_repository: WindowSampleRepository | None = None
    _runtime_key: tuple[str, str] | None = None
    _window_repository_key: str | None = None

    @classmethod
    # 外部推理入口
    def infer(cls, payload: dict[str, Any]) -> Dict[str, object]:
        try:
            return cls._infer_with_runtime(payload)
        except IndexError as exc:
            raise BusinessException(code=400, message=str(exc), status_code=400) from exc
        except Exception as exc:
            if current_app.config.get("AI_ENABLE_MOCK_FALLBACK", True):
                return cls._infer_mock(payload, error=exc)
            raise

    @classmethod
    def _infer_with_runtime(cls, payload: dict[str, Any]) -> Dict[str, object]:
        runtime = cls._get_runtime() # 得到 SequenceModelRuntime
        window_repository = cls._get_window_repository() # 获取窗口样本仓储

        sample_index = payload["sample_index"]
        mc_samples = payload["mc_samples"]

        sample = window_repository.get_window_by_sample_index(sample_index)
        # 调用模型做预测以及不确定性推理
        prediction = runtime.predict_with_uncertainty(
            sample["window"],
            mc_samples=mc_samples,
        )

        prediction["sample_index"] = sample["sample_index"]
        prediction["y_true"] = sample["y_true"]
        prediction["trace"] = sample.get("trace", {})
        prediction["data_source"] = "local_window_dataset"
        return prediction

    @classmethod
    def _get_runtime(cls) -> "SequenceModelRuntime":
        from app.runtime.model_loader import SequenceModelRuntime

        model_dir = str(Path(current_app.config["AI_MODEL_DIR"]))
        device = current_app.config.get("AI_RUNTIME_DEVICE", "auto")
        runtime_key = (model_dir, str(device))

        if cls._runtime is None or cls._runtime_key != runtime_key:
            # 加载模型
            cls._runtime = SequenceModelRuntime.from_model_dir(
                model_dir=model_dir,
                device=device,
            )
            cls._runtime_key = runtime_key

        return cls._runtime

    @classmethod
    def _get_window_repository(cls) -> WindowSampleRepository:
        dataset_dir = str(Path(current_app.config["AI_DATASET_DIR"]))

        if cls._window_repository is None or cls._window_repository_key != dataset_dir:
            cls._window_repository = WindowSampleRepository(dataset_dir)
            cls._window_repository_key = dataset_dir

        return cls._window_repository

    @classmethod
    def _infer_mock(
        cls,
        payload: dict[str, Any],
        error: Exception | None = None,
    ) -> Dict[str, object]:
        device_id = payload["device_id"]
        mc_samples = payload.get("mc_samples", 0)
        profile = cls._MOCK_PROFILE[device_id % 3].copy()
        risk_score = float(profile["risk_score"])
        threshold = 0.26

        result = {
            "condition_label": profile["condition_label"],
            "sample_index": payload.get("sample_index", 0),
            "y_true": None,
            "risk_raw": risk_score,
            "risk_score": risk_score,
            "risk_raw_std": 0.0,
            "risk_std": 0.0,
            "threshold": threshold,
            "predicted_label": int(risk_score >= threshold),
            "model_version": "mock",
            "model_name": "mock",
            "calibration_enabled": False,
            "calibration_method": None,
            "uncertainty_enabled": False,
            "uncertainty_method": None,
            "mc_samples": 0 if error is not None else mc_samples,
            "data_source": "mock_fallback",
            "trace": {},
        }

        if error is not None:
            result["runtime_error"] = str(error).splitlines()[0][:300]

        return result
