"""
Runtime sequence model loader.

This module provides SequenceModelRuntime for loading trained sequence model
artifacts from a RailPHM model output directory.

It reads ArtifactManifest, loads feature_columns.json, builds the configured
sequence model, restores model_state_dict from best_model.pt, moves the model
to the selected device, switches it to eval mode, and provides deterministic
single-window probability prediction.

This module intentionally does not implement probability calibration,
MC-Dropout, Flask /infer binding, database access, or training logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.models import build_sequence_model
from app.runtime.artifact_manifest import ArtifactManifest


DEFAULT_MODEL_VERSION = "bilstm_attention_h1_full_features"

SUPPORTED_RUNTIME_MODELS = {
    "bilstm_attention": "BiLSTMAttentionClassifier",
}


@dataclass
class SequenceModelRuntime:
    """
    Runtime wrapper for a loaded RailPHM sequence model.

    The class stores the loaded model and runtime metadata, and provides
    deterministic single-window probability prediction through predict_proba.
    Probability calibration and MC-Dropout are intentionally not included here.
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

    @classmethod
    def from_model_dir(
        cls,
        model_dir: str | Path,
        device: str = "auto",
    ) -> "SequenceModelRuntime":
        """
        Load model runtime from a model artifact directory.

        Steps:
        1. Load and validate ArtifactManifest.
        2. Load feature_columns.json.
        3. Build sequence model from manifest metadata.
        4. Load checkpoint model_state_dict.
        5. Move model to device and switch to eval mode.
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
        )

    def predict_proba(self, window: np.ndarray) -> dict[str, Any]:
        """
        Run deterministic single-window risk prediction.

        Args:
            window:
                numpy.ndarray with shape [window_size, feature_dim].
                For the default model, expected shape is [30, 23].

        Returns:
            dict containing risk_raw, risk_score, threshold, predicted_label,
            model_version and model_name.

        Notes:
            Current stage has no probability calibration, so risk_score equals
            risk_raw. Calibration and uncertainty estimation are later tasks.
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

        risk_score = risk_raw
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
        }

    def summary(self) -> dict[str, Any]:
        """
        Return lightweight runtime summary for debugging and API display.
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
        }

    def _validate_window(self, window: np.ndarray) -> np.ndarray:
        """
        Validate and convert a single input window to float32 numpy array.
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


def resolve_runtime_device(device: str) -> torch.device:
    """
    Resolve runtime torch device.

    Supported values:
    - auto
    - cpu
    - cuda
    - mps
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
    Load feature_columns.json as non-empty list[str].
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
    Load model checkpoint from best_model.pt.

    This function only loads the checkpoint dictionary. It does not run forward
    inference and does not modify any training artifact file.
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
    Build sequence model according to manifest metadata.
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


def _mps_available() -> bool:
    return bool(
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    )