"""
为默认 Bi-LSTM+Attention 模型输出目录生成一个统一的模型产物清单 model_artifact_manifest.json
生成路径：
outputs/sequence_models/bilstm_attention_h1_full_features/model_artifact_manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    "best_model.pt",
    "training_config.json",
    "sequence_model_report.json",
    "threshold_summary.json",
    "evaluation_summary.json",
    "feature_columns.json",
}

OPTIONAL_FILES = {
    "metrics_history.csv",
    "val_predictions.csv",
    "test_predictions.csv",
}


class ManifestBuildError(RuntimeError):
    """Raised when model artifact manifest cannot be built safely."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build RailPHM model_artifact_manifest.json from existing model outputs."
    )
    parser.add_argument(
        "--model-dir",
        required=True,
        type=Path,
        help="模型输出目录，例如 outputs/sequence_models/bilstm_attention_h1_full_features",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="允许覆盖已存在的 model_artifact_manifest.json",
    )
    return parser


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestBuildError(f"JSON 文件解析失败: {path.name}, error={exc}") from None


def validate_model_dir(model_dir: Path) -> Path:
    model_dir = Path(model_dir)

    if not model_dir.exists():
        raise ManifestBuildError(f"model_dir 不存在: {model_dir}")

    if not model_dir.is_dir():
        raise ManifestBuildError(f"model_dir 不是目录: {model_dir}")

    return model_dir


def validate_required_files(model_dir: Path) -> list[str]:
    missing_required = sorted(
        file_name for file_name in REQUIRED_FILES if not (model_dir / file_name).exists()
    )
    if missing_required:
        raise ManifestBuildError(
            "模型产物目录缺少必需文件: " + ", ".join(missing_required)
        )

    missing_optional = sorted(
        file_name for file_name in OPTIONAL_FILES if not (model_dir / file_name).exists()
    )
    return missing_optional


def extract_threshold(threshold_summary: dict[str, Any]) -> float:
    if "best_threshold" in threshold_summary:
        threshold = threshold_summary["best_threshold"]
    elif "best_val_threshold" in threshold_summary:
        threshold = threshold_summary["best_val_threshold"]
    else:
        raise ManifestBuildError(
            "threshold_summary.json 缺少 best_threshold 或 best_val_threshold"
        )

    threshold_value = _as_float(threshold, "threshold")

    if not 0 < threshold_value < 1:
        raise ManifestBuildError(
            f"threshold 必须位于 0 到 1 之间，当前为 {threshold_value}"
        )

    return threshold_value


def build_threshold_source(threshold_summary: dict[str, Any]) -> str:
    search_on = str(threshold_summary.get("search_on", "val"))
    metric = str(threshold_summary.get("metric", "f1"))

    if search_on == "val":
        split_name = "validation"
    else:
        split_name = search_on

    return f"{split_name}_best_{metric}"


def extract_model_metadata(model_dir: Path) -> dict[str, Any]:
    training_config = load_json(model_dir / "training_config.json")
    sequence_model_report = load_json(model_dir / "sequence_model_report.json")
    threshold_summary = load_json(model_dir / "threshold_summary.json")
    load_json(model_dir / "evaluation_summary.json")

    feature_columns = load_json(model_dir / "feature_columns.json")
    feature_columns = _validate_feature_columns(feature_columns)

    model_name = _required_str(training_config, "model", "training_config.json")

    report_model = sequence_model_report.get("model", {})
    config_model = training_config.get("model_config", {})

    model_class = None
    if isinstance(report_model, dict):
        model_class = report_model.get("name")
    if not model_class and isinstance(config_model, dict):
        model_class = config_model.get("name")
    if not isinstance(model_class, str) or not model_class:
        raise ManifestBuildError(
            "无法读取模型类名：请检查 sequence_model_report.json 的 model.name "
            "或 training_config.json 的 model_config.name"
        )

    window_size = _required_positive_int(training_config, "window_size", "training_config.json")
    feature_dim = _required_positive_int(training_config, "feature_dim", "training_config.json")
    input_dim = _required_positive_int(training_config, "input_dim", "training_config.json")
    hidden_dim = _required_positive_int(training_config, "hidden_dim", "training_config.json")
    num_layers = _required_positive_int(training_config, "num_layers", "training_config.json")
    dropout = _required_dropout(training_config, "dropout", "training_config.json")

    if len(feature_columns) != feature_dim:
        raise ManifestBuildError(
            "feature_columns 数量与 training_config.json 中的 feature_dim 不一致: "
            f"feature_columns={len(feature_columns)}, feature_dim={feature_dim}"
        )

    threshold = extract_threshold(threshold_summary)
    threshold_source = build_threshold_source(threshold_summary)

    dataset_dir = _required_str(training_config, "dataset_dir", "training_config.json")
    output_dir = training_config.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir:
        output_dir = str(model_dir)

    condition_feature_columns = [
        column for column in feature_columns if column.startswith("condition_")
    ]

    return {
        "model_name": model_name,
        "model_class": model_class,
        "window_size": window_size,
        "feature_dim": feature_dim,
        "input_dim": input_dim,
        "hidden_dim": hidden_dim,
        "num_layers": num_layers,
        "dropout": dropout,
        "threshold": threshold,
        "threshold_source": threshold_source,
        "dataset_dir": dataset_dir,
        "output_dir": output_dir,
        "feature_columns": feature_columns,
        "condition_feature_columns": condition_feature_columns,
    }


def build_manifest(model_dir: Path) -> dict[str, Any]:
    model_dir = validate_model_dir(model_dir)
    missing_optional = validate_required_files(model_dir)
    metadata = extract_model_metadata(model_dir)

    feature_columns = metadata["feature_columns"]

    return {
        "model_version": model_dir.name,
        "model_name": metadata["model_name"],
        "model_class": metadata["model_class"],
        "window_size": metadata["window_size"],
        "feature_dim": metadata["feature_dim"],
        "input_dim": metadata["input_dim"],
        "hidden_dim": metadata["hidden_dim"],
        "num_layers": metadata["num_layers"],
        "dropout": metadata["dropout"],
        "threshold": metadata["threshold"],
        "threshold_source": metadata["threshold_source"],
        "dataset_dir": metadata["dataset_dir"],
        "output_dir": metadata["output_dir"],
        "feature_columns_count": len(feature_columns),
        "feature_columns_preview": feature_columns[:3],
        "condition_feature_columns": metadata["condition_feature_columns"],
        "artifacts": {
            "model_weight": "best_model.pt",
            "training_config": "training_config.json",
            "sequence_model_report": "sequence_model_report.json",
            "threshold_summary": "threshold_summary.json",
            "evaluation_summary": "evaluation_summary.json",
            "metrics_history": "metrics_history.csv",
            "val_predictions": "val_predictions.csv",
            "test_predictions": "test_predictions.csv",
            "feature_columns": "feature_columns.json",
        },
        "checks": {
            "required_files_exist": True,
            "feature_dim_matches_feature_columns": True,
            "threshold_in_valid_range": True,
            "optional_files_missing": missing_optional,
        },
        "notes": [
            "This manifest is generated from existing training artifacts.",
            "Model weights are not loaded during manifest generation.",
            "Probability calibration and MC-Dropout are not included in this stage.",
        ],
    }


def save_manifest(path: Path, manifest: dict[str, Any], overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise ManifestBuildError(
            f"model_artifact_manifest.json 已存在: {path}。如需覆盖，请添加 --overwrite。"
        )

    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_success_summary(model_dir: Path, manifest: dict[str, Any], manifest_path: Path) -> None:
    condition_features = manifest.get("condition_feature_columns", [])
    condition_text = ", ".join(condition_features) if condition_features else "(none)"

    print("=" * 60)
    print("RailPHM model artifact manifest builder")
    print("=" * 60)
    print(f"model_dir: {model_dir}")
    print(f"model_version: {manifest['model_version']}")
    print(f"model_name: {manifest['model_name']}")
    print(f"model_class: {manifest['model_class']}")
    print(f"window_size: {manifest['window_size']}")
    print(f"feature_dim: {manifest['feature_dim']}")
    print(f"threshold: {manifest['threshold']}")
    print(f"feature_columns_count: {manifest['feature_columns_count']}")
    print(f"condition_features: {condition_text}")

    optional_missing = manifest.get("checks", {}).get("optional_files_missing", [])
    if optional_missing:
        print(f"[WARN] optional files missing: {', '.join(optional_missing)}")

    print()
    print("Manifest created:")
    print(manifest_path)
    print("=" * 60)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        model_dir = validate_model_dir(args.model_dir)
        manifest = build_manifest(model_dir)
        manifest_path = model_dir / "model_artifact_manifest.json"
        save_manifest(manifest_path, manifest, overwrite=args.overwrite)
        print_success_summary(model_dir, manifest, manifest_path)
        return 0
    except ManifestBuildError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] 构建 model_artifact_manifest.json 失败: {exc}", file=sys.stderr)
        return 1


def _validate_feature_columns(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ManifestBuildError("feature_columns.json 必须是非空 list[str]")

    if not all(isinstance(item, str) and item for item in value):
        raise ManifestBuildError("feature_columns.json 必须是非空 list[str]")

    return value


def _required_str(data: dict[str, Any], key: str, source_name: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestBuildError(f"{source_name} 缺少有效字符串字段: {key}")
    return value


def _required_positive_int(data: dict[str, Any], key: str, source_name: str) -> int:
    if key not in data:
        raise ManifestBuildError(f"{source_name} 缺少字段: {key}")

    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManifestBuildError(f"{source_name} 中 {key} 必须为正整数，当前为 {value}")

    return int(value)


def _required_dropout(data: dict[str, Any], key: str, source_name: str) -> float:
    if key not in data:
        raise ManifestBuildError(f"{source_name} 缺少字段: {key}")

    value = _as_float(data[key], key)
    if not 0 <= value < 1:
        raise ManifestBuildError(f"{source_name} 中 dropout 必须满足 0 <= dropout < 1，当前为 {value}")

    return value


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ManifestBuildError(f"{name} 必须为数字，不能为 bool")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ManifestBuildError(f"{name} 必须为数字，当前为 {value}") from None

    if number != number or number in {float("inf"), float("-inf")}:
        raise ManifestBuildError(f"{name} 必须为有限数字，当前为 {value}")

    return number


if __name__ == "__main__":
    raise SystemExit(main())