"""
读取并校验默认模型目录里的 model_artifact_manifest.json，
确认后续运行时加载模型所需的关键文件都可靠存在，
它本身不加载模型、不做推理
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST_FILENAME = "model_artifact_manifest.json"

REQUIRED_RUNTIME_ARTIFACTS = (
    "model_weight",
    "training_config",
    "sequence_model_report",
    "threshold_summary",
    "feature_columns",
)

OPTIONAL_RUNTIME_ARTIFACTS = (
    "evaluation_summary",
    "metrics_history",
    "val_predictions",
    "test_predictions",
)

REQUIRED_MANIFEST_FIELDS = (
    "model_version",
    "model_name",
    "model_class",
    "window_size",
    "feature_dim",
    "input_dim",
    "hidden_dim",
    "num_layers",
    "dropout",
    "threshold",
    "dataset_dir",
    "output_dir",
    "feature_columns_count",
    "artifacts",
)


@dataclass
class ArtifactManifest:
    """
    Parsed RailPHM model artifact manifest.

    The class only reads and validates model_artifact_manifest.json metadata.
    It does not load best_model.pt and does not create any model object.
    """

    model_dir: Path
    manifest_path: Path
    raw: dict[str, Any]
    model_version: str
    model_name: str
    model_class: str
    window_size: int
    feature_dim: int
    input_dim: int
    hidden_dim: int
    num_layers: int
    dropout: float
    threshold: float
    dataset_dir: str
    output_dir: str
    feature_columns_count: int
    artifacts: dict[str, str]
    checks: dict[str, object]

    @classmethod
    def load(cls, model_dir: str | Path) -> "ArtifactManifest":
        """
        Load and validate model_artifact_manifest.json from a model directory.
        """
        model_dir_path = Path(model_dir)

        if not model_dir_path.exists():
            raise FileNotFoundError(f"model_dir 不存在: {model_dir_path}")

        if not model_dir_path.is_dir():
            raise NotADirectoryError(f"model_dir 不是目录: {model_dir_path}")

        manifest_path = model_dir_path / DEFAULT_MANIFEST_FILENAME

        if not manifest_path.exists():
            raise FileNotFoundError(f"缺少模型产物清单文件: {manifest_path}")

        raw = _load_json(manifest_path)
        if not isinstance(raw, dict):
            raise ValueError(f"{DEFAULT_MANIFEST_FILENAME} 必须是 JSON object")

        _validate_required_manifest_fields(raw)

        artifacts = raw["artifacts"]
        if not isinstance(artifacts, dict):
            raise ValueError("manifest 字段 artifacts 必须是 dict[str, str]")

        normalized_artifacts = _validate_artifacts_dict(artifacts)

        checks = raw.get("checks", {})
        if not isinstance(checks, dict):
            raise ValueError("manifest 字段 checks 必须是 dict")

        manifest = cls(
            model_dir=model_dir_path,
            manifest_path=manifest_path,
            raw=raw,
            model_version=_require_non_empty_string(raw["model_version"], "model_version"),
            model_name=_require_non_empty_string(raw["model_name"], "model_name"),
            model_class=_require_non_empty_string(raw["model_class"], "model_class"),
            window_size=_require_positive_int(raw["window_size"], "window_size"),
            feature_dim=_require_positive_int(raw["feature_dim"], "feature_dim"),
            input_dim=_require_positive_int(raw["input_dim"], "input_dim"),
            hidden_dim=_require_positive_int(raw["hidden_dim"], "hidden_dim"),
            num_layers=_require_positive_int(raw["num_layers"], "num_layers"),
            dropout=_require_float_range(
                raw["dropout"],
                "dropout",
                min_value=0.0,
                max_value=1.0,
                include_min=True,
                include_max=False,
            ),
            threshold=_require_float_range(
                raw["threshold"],
                "threshold",
                min_value=0.0,
                max_value=1.0,
                include_min=False,
                include_max=False,
            ),
            dataset_dir=_require_non_empty_string(raw["dataset_dir"], "dataset_dir"),
            output_dir=_require_non_empty_string(raw["output_dir"], "output_dir"),
            feature_columns_count=_require_positive_int(
                raw["feature_columns_count"],
                "feature_columns_count",
            ),
            artifacts=normalized_artifacts,
            checks=checks,
        )

        manifest.validate_required_fields()
        manifest.validate_values()
        manifest.validate_required_files()

        return manifest

    def validate_required_fields(self) -> None:
        """
        Validate required top-level manifest fields.
        """
        _validate_required_manifest_fields(self.raw)

    def validate_values(self) -> None:
        """
        Validate parsed manifest values.
        """
        _require_non_empty_string(self.model_version, "model_version")
        _require_non_empty_string(self.model_name, "model_name")
        _require_non_empty_string(self.model_class, "model_class")

        _require_positive_int(self.window_size, "window_size")
        _require_positive_int(self.feature_dim, "feature_dim")
        _require_positive_int(self.input_dim, "input_dim")
        _require_positive_int(self.hidden_dim, "hidden_dim")
        _require_positive_int(self.num_layers, "num_layers")
        _require_positive_int(self.feature_columns_count, "feature_columns_count")

        _require_float_range(
            self.dropout,
            "dropout",
            min_value=0.0,
            max_value=1.0,
            include_min=True,
            include_max=False,
        )
        _require_float_range(
            self.threshold,
            "threshold",
            min_value=0.0,
            max_value=1.0,
            include_min=False,
            include_max=False,
        )

        if self.feature_columns_count != self.feature_dim:
            raise ValueError(
                "feature_columns_count 必须与 feature_dim 一致: "
                f"feature_columns_count={self.feature_columns_count}, "
                f"feature_dim={self.feature_dim}"
            )

    def validate_required_files(self) -> None:
        """
        Validate required runtime artifact keys and corresponding files.
        """
        for artifact_key in REQUIRED_RUNTIME_ARTIFACTS:
            if artifact_key not in self.artifacts:
                raise ValueError(f"artifacts 缺少运行时必需 key: {artifact_key}")

            artifact_path = self.get_path(artifact_key)
            if not artifact_path.exists():
                raise FileNotFoundError(
                    f"运行时必需文件不存在: key={artifact_key}, path={artifact_path}"
                )

    def get_path(self, artifact_key: str) -> Path:
        """
        Return artifact path by key.

        Relative artifact paths are resolved against model_dir.
        Absolute artifact paths are returned directly.
        """
        if artifact_key not in self.artifacts:
            raise KeyError(f"artifacts 中不存在 key: {artifact_key}")

        artifact_path = Path(self.artifacts[artifact_key])

        if artifact_path.is_absolute():
            return artifact_path

        return self.model_dir / artifact_path

    def to_dict(self) -> dict[str, Any]:
        """
        Return original manifest dict.
        """
        return dict(self.raw)

    def summary(self) -> dict[str, Any]:
        """
        Return a lightweight manifest summary for logs or debugging.
        """
        return {
            "model_version": self.model_version,
            "model_name": self.model_name,
            "model_class": self.model_class,
            "window_size": self.window_size,
            "feature_dim": self.feature_dim,
            "threshold": self.threshold,
            "model_weight_path": str(self.get_path("model_weight")),
            "feature_columns_path": str(self.get_path("feature_columns")),
        }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 文件解析失败: {path}, error={exc}") from None


def _validate_required_manifest_fields(raw: dict[str, Any]) -> None:
    missing_fields = [field for field in REQUIRED_MANIFEST_FIELDS if field not in raw]
    if missing_fields:
        raise ValueError("manifest 缺少必要字段: " + ", ".join(missing_fields))


def _validate_artifacts_dict(value: dict[Any, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}

    for key, artifact_path in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("artifacts 的 key 必须是非空字符串")

        if not isinstance(artifact_path, str) or not artifact_path:
            raise ValueError(f"artifacts[{key}] 必须是非空字符串路径")

        normalized[key] = artifact_path

    return normalized


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")

    return value


def _require_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} 必须是正整数，当前为 {value}")

    return int(value)


def _require_float_range(
    value: Any,
    field_name: str,
    min_value: float,
    max_value: float,
    *,
    include_min: bool,
    include_max: bool,
) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是数字，不能是 bool")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} 必须是数字，当前为 {value}") from None

    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{field_name} 必须是有限数字，当前为 {value}")

    lower_valid = number >= min_value if include_min else number > min_value
    upper_valid = number <= max_value if include_max else number < max_value

    if not lower_valid or not upper_valid:
        left = "[" if include_min else "("
        right = "]" if include_max else ")"
        raise ValueError(
            f"{field_name} 必须位于 {left}{min_value}, {max_value}{right}，当前为 {number}"
        )

    return number