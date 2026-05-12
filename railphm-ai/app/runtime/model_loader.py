"""
模型运行时加载器。

本文件负责从模型产物目录加载 RailPHM 时序预测模型，包括读取模型产物清单、
加载特征字段、构造 Bi-LSTM+Attention 模型、恢复模型权重，并提供单窗口
风险预测能力。

当前文件支持三类运行时能力：
1. 确定性单窗口预测 predict_proba；
2. 可选概率校准器加载，输出校准后的 risk_score；
3. MC-Dropout 不确定性估计 predict_with_uncertainty。

本文件不负责重新训练模型，不修改模型结构，不重新拟合校准器，不修改训练产物，
不接入 /infer，不访问数据库，也不保存 MC 采样明细文件。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.calibration import IsotonicRiskCalibrator
from app.models import build_sequence_model
from app.runtime.artifact_manifest import ArtifactManifest
from app.uncertainty import (
    collect_mc_dropout_probabilities,
    summarize_probabilities,
)


DEFAULT_MODEL_VERSION = "bilstm_attention_h1_full_features"

SUPPORTED_RUNTIME_MODELS = {
    "bilstm_attention": "BiLSTMAttentionClassifier",
}

SUPPORTED_CALIBRATION_METHODS = {
    "isotonic_regression",
}

SUPPORTED_UNCERTAINTY_METHODS = {
    "mc_dropout",
}


@dataclass
class SequenceModelRuntime:
    """
    RailPHM 时序模型运行时对象。

    该类保存已加载模型、运行设备、特征字段顺序、阈值、模型版本等运行时信息。
    如果模型产物清单中启用了概率校准，则会加载校准器，并在预测时将模型原始
    概率 risk_raw 转换为系统最终使用的风险分数 risk_score。

    predict_proba 负责单次确定性推理；
    predict_with_uncertainty 负责 MC-Dropout 多次随机前向传播和不确定性估计。
    """

    manifest: ArtifactManifest
    model: torch.nn.Module
    device: torch.device
    feature_columns: list[str]
    threshold: float
    model_version: str
    model_name: str
    model_class: str
    window_size: int
    feature_dim: int
    calibrator: IsotonicRiskCalibrator | None = None
    calibration_enabled: bool = False
    calibration_method: str | None = None
    uncertainty_enabled: bool = False
    uncertainty_method: str | None = None
    default_mc_samples: int = 30

    @classmethod
    def from_model_dir(
        cls,
        model_dir: str | Path,
        device: str = "auto",
    ) -> "SequenceModelRuntime":
        """
        从模型产物目录加载运行时模型。

        流程：
        1. 读取并校验 ArtifactManifest；
        2. 读取 feature_columns.json；
        3. 根据 manifest 构造时序模型；
        4. 加载 best_model.pt 中的 model_state_dict；
        5. 将模型移动到指定设备并切换为 eval 模式；
        6. 如果 manifest 启用 calibration，则加载 calibrator.pkl；
        7. 如果 manifest 启用 uncertainty，则读取默认 MC-Dropout 配置。
        """
        manifest = ArtifactManifest.load(model_dir)
        runtime_device = resolve_runtime_device(device)

        feature_columns = load_feature_columns(manifest.get_path("feature_columns"))
        if len(feature_columns) != manifest.feature_dim:
            raise ValueError(
                "feature_columns 数量与 manifest.feature_dim 不一致: "
                f"feature_columns={len(feature_columns)}, "
                f"feature_dim={manifest.feature_dim}"
            )

        model = _build_model_from_manifest(manifest)

        checkpoint_path = manifest.get_path("model_weight")
        checkpoint = _load_checkpoint(checkpoint_path, runtime_device)

        model_state_dict = checkpoint.get("model_state_dict")
        if model_state_dict is None:
            raise ValueError("checkpoint missing model_state_dict")

        model.load_state_dict(model_state_dict, strict=True)
        model.to(runtime_device)
        model.eval()

        calibrator, calibration_enabled, calibration_method = _load_calibrator_if_enabled(
            manifest
        )
        uncertainty_enabled, uncertainty_method, default_mc_samples = (
            _load_uncertainty_config(manifest)
        )

        return cls(
            manifest=manifest,
            model=model,
            device=runtime_device,
            feature_columns=feature_columns,
            threshold=manifest.threshold,
            model_version=manifest.model_version,
            model_name=manifest.model_name,
            model_class=manifest.model_class,
            window_size=manifest.window_size,
            feature_dim=manifest.feature_dim,
            calibrator=calibrator,
            calibration_enabled=calibration_enabled,
            calibration_method=calibration_method,
            uncertainty_enabled=uncertainty_enabled,
            uncertainty_method=uncertainty_method,
            default_mc_samples=default_mc_samples,
        )

    def predict_proba(self, window: np.ndarray) -> dict[str, Any]:
        """
        对单个窗口样本执行确定性风险概率预测。

        输入 window 必须是 shape=[window_size, feature_dim] 的 numpy.ndarray。
        对默认模型而言，即 shape=(30, 23)。

        输出说明：
        - risk_raw：模型 sigmoid 后的原始概率；
        - risk_score：系统使用的风险分数。启用校准时为校准后概率，否则等于 risk_raw；
        - predicted_label：基于 risk_score 和 threshold 判断；
        - calibration_enabled / calibration_method：说明本次预测是否使用概率校准。
        """
        window_array = self._validate_window(window)

        self.model.eval()

        with torch.no_grad():
            features = (
                torch.from_numpy(window_array)
                .unsqueeze(0)
                .to(device=self.device, dtype=torch.float32)
            )
            logits = self.model(features).view(-1)
            probs = torch.sigmoid(logits)
            risk_raw = float(probs.detach().cpu().item())

        risk_score = self._apply_calibration(risk_raw)
        predicted_label = int(risk_score >= self.threshold)

        return {
            "risk_raw": risk_raw,
            "risk_score": risk_score,
            "threshold": self.threshold,
            "predicted_label": predicted_label,
            "model_version": self.model_version,
            "model_name": self.model_name,
            "window_size": self.window_size,
            "feature_dim": self.feature_dim,
            "calibration_enabled": self.calibration_enabled,
            "calibration_method": self.calibration_method,
        }

    def predict_with_uncertainty(
        self,
        window: np.ndarray,
        mc_samples: int = 30,
    ) -> dict[str, Any]:
        """
        使用 MC-Dropout 对单个窗口样本进行不确定性估计。

        本方法会执行多次随机前向传播，返回原始概率均值、系统风险分数、
        原始概率标准差和系统不确定性指标。正式输出中不包含完整采样数组。

        输出说明：
        - risk_raw：多次 MC-Dropout 原始概率的均值；
        - risk_score：系统最终风险分数，启用校准时为校准后概率均值；
        - risk_raw_std：原始概率标准差；
        - risk_std：系统最终不确定性指标，启用校准时为校准后概率标准差。
        """
        window_array = self._validate_window(window)
        _validate_runtime_mc_samples(mc_samples)

        features = (
            torch.from_numpy(window_array)
            .unsqueeze(0)
            .to(device=self.device, dtype=torch.float32)
        )

        raw_probs = collect_mc_dropout_probabilities(
            model=self.model,
            input_tensor=features,
            mc_samples=mc_samples,
        )

        calibrated_probs = None
        if self.calibration_enabled and self.calibrator is not None:
            calibrated_probs = self.calibrator.transform(raw_probs)
            calibrated_probs = np.clip(
                np.asarray(calibrated_probs, dtype=np.float64),
                0.0,
                1.0,
            )

        probability_summary = summarize_probabilities(
            raw_probs=raw_probs,
            calibrated_probs=calibrated_probs,
        )

        risk_raw = float(probability_summary["risk_raw"])
        risk_score = float(probability_summary["risk_score"])
        risk_raw_std = float(probability_summary["risk_raw_std"])
        risk_std = float(probability_summary["risk_std"])

        predicted_label = int(risk_score >= self.threshold)

        self.model.eval()

        return {
            "risk_raw": risk_raw,
            "risk_score": risk_score,
            "risk_raw_std": risk_raw_std,
            "risk_std": risk_std,
            "threshold": self.threshold,
            "predicted_label": predicted_label,
            "model_version": self.model_version,
            "model_name": self.model_name,
            "window_size": self.window_size,
            "feature_dim": self.feature_dim,
            "calibration_enabled": self.calibration_enabled,
            "calibration_method": self.calibration_method,
            "uncertainty_enabled": True,
            "uncertainty_method": "mc_dropout",
            "mc_samples": mc_samples,
        }

    def summary(self) -> dict[str, Any]:
        """
        返回轻量运行时摘要，用于调试或接口展示。
        """
        return {
            "model_version": self.model_version,
            "model_name": self.model_name,
            "model_class": self.model_class,
            "window_size": self.window_size,
            "feature_dim": self.feature_dim,
            "threshold": self.threshold,
            "device": str(self.device),
            "feature_columns_count": len(self.feature_columns),
            "calibration_enabled": self.calibration_enabled,
            "calibration_method": self.calibration_method,
            "uncertainty_enabled": self.uncertainty_enabled,
            "uncertainty_method": self.uncertainty_method,
            "default_mc_samples": self.default_mc_samples,
        }

    def _validate_window(self, window: np.ndarray) -> np.ndarray:
        """
        校验单窗口输入，并转换为 float32 numpy 数组。
        """
        if not isinstance(window, np.ndarray):
            raise ValueError("window must be a numpy.ndarray")

        if window.ndim != 2:
            raise ValueError("window must be 2D with shape [window_size, feature_dim]")

        expected_shape = (self.window_size, self.feature_dim)
        if window.shape != expected_shape:
            raise ValueError(
                f"window shape mismatch: expected {expected_shape}, got {window.shape}"
            )

        try:
            window_array = window.astype(np.float32, copy=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("window cannot be safely converted to float32") from exc

        if not np.isfinite(window_array).all():
            raise ValueError("window contains NaN or inf")

        return window_array

    def _apply_calibration(self, risk_raw: float) -> float:
        """
        对模型原始概率应用可选概率校准。

        未启用校准时直接返回 risk_raw；启用校准时调用已加载的校准器。
        """
        if not self.calibration_enabled:
            return risk_raw

        if self.calibrator is None:
            raise ValueError("calibration is enabled but calibrator is not loaded")

        calibrated = self.calibrator.transform([risk_raw])
        if calibrated.shape[0] != 1:
            raise ValueError("calibrator transform should return one value")

        risk_score = float(calibrated[0])
        if not np.isfinite(risk_score):
            raise ValueError("calibrated risk_score is NaN or inf")

        return max(0.0, min(1.0, risk_score))


def resolve_runtime_device(device: str) -> torch.device:
    """
    解析运行设备。

    支持 auto、cpu、cuda、mps。
    """
    normalized = str(device).lower()

    if normalized == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if _mps_available():
            return torch.device("mps")
        return torch.device("cpu")

    if normalized == "cpu":
        return torch.device("cpu")

    if normalized == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("指定 device=cuda，但当前环境不可用")
        return torch.device("cuda")

    if normalized == "mps":
        if not _mps_available():
            raise ValueError("指定 device=mps，但当前环境不可用")
        return torch.device("mps")

    raise ValueError("device 仅支持 auto、cpu、cuda、mps")


def load_feature_columns(path: Path) -> list[str]:
    """
    读取 feature_columns.json，并校验其为非空 list[str]。
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"feature_columns.json 不存在: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"feature_columns.json 解析失败: {path}, error={exc}") from None

    if not isinstance(data, list) or not data:
        raise ValueError("feature_columns.json 必须是非空 list[str]")

    if not all(isinstance(item, str) and item for item in data):
        raise ValueError("feature_columns.json 必须是非空 list[str]")

    return data


def _load_checkpoint(path: Path, device: torch.device) -> dict[str, Any]:
    """
    读取 best_model.pt checkpoint。

    本函数只加载 checkpoint 字典，不执行 forward，不修改任何训练产物。
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"模型权重文件不存在: {path}")

    checkpoint = torch.load(path, map_location=device)

    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint must be a dict")

    if "model_state_dict" not in checkpoint:
        raise ValueError("checkpoint missing model_state_dict")

    return checkpoint


def _build_model_from_manifest(manifest: ArtifactManifest) -> torch.nn.Module:
    """
    根据 manifest 元信息构造时序模型。
    """
    expected_model_class = SUPPORTED_RUNTIME_MODELS.get(manifest.model_name)
    if expected_model_class is None:
        supported = ", ".join(sorted(SUPPORTED_RUNTIME_MODELS.keys()))
        raise ValueError(
            f"不支持的运行时模型: {manifest.model_name}，当前支持: {supported}"
        )

    if expected_model_class != manifest.model_class:
        raise ValueError(
            "manifest 中 model_name 与 model_class 不匹配: "
            f"model_name={manifest.model_name}, "
            f"expected_model_class={expected_model_class}, "
            f"actual_model_class={manifest.model_class}"
        )

    return build_sequence_model(
        model_name=manifest.model_name,
        input_dim=manifest.input_dim,
        hidden_dim=manifest.hidden_dim,
        num_layers=manifest.num_layers,
        dropout=manifest.dropout,
    )


def _load_calibrator_if_enabled(
    manifest: ArtifactManifest,
) -> tuple[IsotonicRiskCalibrator | None, bool, str | None]:
    """
    如果 manifest 中启用了 calibration，则加载 calibrator.pkl。

    没有 calibration 字段或 enabled=false 时保持向后兼容，不报错。
    """
    calibration = manifest.raw.get("calibration")

    if calibration is None:
        return None, False, None

    if not isinstance(calibration, dict):
        raise ValueError("manifest calibration field must be a dict")

    if calibration.get("enabled") is not True:
        return None, False, None

    method = calibration.get("method")
    if method not in SUPPORTED_CALIBRATION_METHODS:
        raise ValueError(f"unsupported calibration method: {method}")

    calibrator_file = calibration.get("calibrator")
    if not isinstance(calibrator_file, str) or not calibrator_file:
        raise ValueError("calibration.enabled=true but calibrator field is missing")

    calibrator_path = Path(calibrator_file)
    if not calibrator_path.is_absolute():
        calibrator_path = manifest.model_dir / calibrator_path

    if not calibrator_path.exists():
        raise FileNotFoundError(f"calibrator file not found: {calibrator_path}")

    calibrator = IsotonicRiskCalibrator.load(calibrator_path)

    return calibrator, True, method


def _load_uncertainty_config(
    manifest: ArtifactManifest,
) -> tuple[bool, str | None, int]:
    """
    从 manifest 中读取 uncertainty 配置。

    没有 uncertainty 字段时保持向后兼容，不影响 predict_with_uncertainty 方法调用。
    """
    uncertainty = manifest.raw.get("uncertainty")

    if uncertainty is None:
        return False, None, 30

    if not isinstance(uncertainty, dict):
        raise ValueError("manifest uncertainty field must be a dict")

    if uncertainty.get("enabled") is not True:
        return False, None, 30

    method = uncertainty.get("method")
    if method not in SUPPORTED_UNCERTAINTY_METHODS:
        raise ValueError(f"unsupported uncertainty method: {method}")

    mc_samples = uncertainty.get("mc_samples", 30)
    _validate_runtime_mc_samples(mc_samples)

    return True, method, int(mc_samples)


def _validate_runtime_mc_samples(mc_samples: int) -> None:
    """
    校验运行时 MC-Dropout 采样次数。
    """
    if isinstance(mc_samples, bool) or not isinstance(mc_samples, int):
        raise ValueError("mc_samples must be a positive integer")

    if mc_samples <= 0:
        raise ValueError("mc_samples must be a positive integer")

    if mc_samples > 1000:
        raise ValueError("mc_samples must be <= 1000 to avoid slow inference")


def _mps_available() -> bool:
    return bool(
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    )