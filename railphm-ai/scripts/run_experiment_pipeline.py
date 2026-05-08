#!/usr/bin/env python3
"""
RailPHM 统一实验流程。
此脚本是一个协调器。它读取 JSON 配置，解析路径和阶段选择，然后将稳定的工作流步骤委派给现有脚本。
它不会更改标签、模型定义、预处理规则或 /infer 行为。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STAGES = [
    "build",
    "inspect",
    "split",
    "scale",
    "condition",
    "augment",
    "train",
    "threshold",
    "evaluate",
    "diagnose",
]

PROGRAM_DEFAULT_CONFIG: dict[str, Any] = {
    "experiment_name": "bilstm_attention_h1_full_features",
    "segments_dir": "data/processed/atp_segments",
    "dataset_root": "data/datasets",
    "output_root": "outputs/sequence_models",
    "window": {
        "window_size": 30,
        "stride": 1,
        "prediction_horizon": 1,
    },
    "feature": {
        "profile": "full_features",
    },
    "split": {
        "strategy": "segment_id",
        "train_ratio": 0.7,
        "val_ratio": 0.15,
        "test_ratio": 0.15,
        "seed": 42,
    },
    "scale": {
        "enabled": True,
        "fit_split": "train",
    },
    "condition": {
        "enabled": True,
        "k": 3,
        "fit_split": "train",
    },
    "model": {
        "name": "bilstm_attention",
        "epochs": 10,
        "batch_size": 64,
        "learning_rate": 0.001,
        "hidden_dim": 64,
        "dropout": 0.3,
    },
    "threshold": {
        "default_threshold": 0.5,
        "search_on": "val",
        "metric": "f1",
        "min": 0.01,
        "max": 0.99,
        "step": 0.01,
    },
    "diagnosis": {
        "high_fp_enabled": True,
        "top_fp": 10,
    },
    "run": {
        "overwrite": False,
        "skip_existing": True,
        "dry_run": False,
        "stop_on_error": True,
    },
}


class PipelineError(RuntimeError):
    """User-facing pipeline error."""


@dataclass
class StageResult:
    stage: str
    status: str
    elapsed_seconds: float
    summary: str


@dataclass
class PipelineContext:
    config: dict[str, Any]
    config_path: Path | None
    paths: dict[str, Path]
    selected_stages: list[str]
    dry_run: bool
    overwrite: bool
    skip_existing: bool
    executed_stages: list[str]
    skipped_stages: list[str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the RailPHM AI experiment pipeline from one JSON config."
    )
    parser.add_argument("--config", type=Path, default=None, help="JSON 配置文件路径")
    parser.add_argument("--experiment-name", type=str, default=None)
    parser.add_argument("--segments-dir", type=str, default=None)
    parser.add_argument("--dataset-root", type=str, default=None)
    parser.add_argument("--output-root", type=str, default=None)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--stride", type=int, default=None)
    parser.add_argument("--prediction-horizon", type=int, default=None)
    parser.add_argument("--feature-profile", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument("--condition-k", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true", default=None)
    parser.add_argument("--skip-existing", action="store_true", default=None)
    parser.add_argument("--dry-run", action="store_true", default=None)
    parser.add_argument("--stage-from", type=str, default=None)
    parser.add_argument("--stage-to", type=str, default=None)
    parser.add_argument("--only-stage", type=str, default=None)
    parser.add_argument("--disable-scale", action="store_true", default=False)
    parser.add_argument("--disable-condition", action="store_true", default=False)
    parser.add_argument("--disable-diagnosis", action="store_true", default=False)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_json_config(config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        return {}
    resolved_path = resolve_path(config_path)
    if not resolved_path.exists():
        raise PipelineError(f"配置文件不存在: {display_path(resolved_path)}")
    try:
        return json.loads(resolved_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError(f"配置文件不是合法 JSON: {display_path(resolved_path)} ({exc})") from exc


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    config = deep_merge(PROGRAM_DEFAULT_CONFIG, load_json_config(args.config))
    original_prediction_horizon = config["window"]["prediction_horizon"]

    if args.experiment_name is not None:
        config["experiment_name"] = args.experiment_name
    if args.segments_dir is not None:
        config["segments_dir"] = args.segments_dir
    if args.dataset_root is not None:
        config["dataset_root"] = args.dataset_root
    if args.output_root is not None:
        config["output_root"] = args.output_root
    if args.window_size is not None:
        config["window"]["window_size"] = args.window_size
    if args.stride is not None:
        config["window"]["stride"] = args.stride
    if args.prediction_horizon is not None:
        config["window"]["prediction_horizon"] = args.prediction_horizon
        if args.experiment_name is None:
            config["experiment_name"] = replace_horizon_token(
                str(config["experiment_name"]),
                old_horizon=int(original_prediction_horizon),
                new_horizon=int(args.prediction_horizon),
            )
    if args.feature_profile is not None:
        config["feature"]["profile"] = args.feature_profile
    if args.model is not None:
        config["model"]["name"] = args.model
    if args.epochs is not None:
        config["model"]["epochs"] = args.epochs
    if args.batch_size is not None:
        config["model"]["batch_size"] = args.batch_size
    if args.learning_rate is not None:
        config["model"]["learning_rate"] = args.learning_rate
    if args.condition_k is not None:
        config["condition"]["k"] = args.condition_k
    if args.overwrite:
        config["run"]["overwrite"] = True
    if args.skip_existing:
        config["run"]["skip_existing"] = True
    if args.dry_run:
        config["run"]["dry_run"] = True
    if args.disable_scale:
        config["scale"]["enabled"] = False
    if args.disable_condition:
        config["condition"]["enabled"] = False
    if args.disable_diagnosis:
        config["diagnosis"]["high_fp_enabled"] = False

    validate_config(config)
    return config


def replace_horizon_token(experiment_name: str, old_horizon: int, new_horizon: int) -> str:
    old_token = f"h{int(old_horizon)}"
    new_token = f"h{int(new_horizon)}"
    return "_".join(new_token if part == old_token else part for part in experiment_name.split("_"))


def validate_config(config: dict[str, Any]) -> None:
    if not str(config["experiment_name"]).strip():
        raise PipelineError("experiment_name 不能为空")
    if config["split"]["strategy"] != "segment_id":
        raise PipelineError("split.strategy 当前仅支持 segment_id，不能使用随机窗口划分")
    if config["scale"]["fit_split"] != "train":
        raise PipelineError("scale.fit_split 必须为 train，避免验证集/测试集泄漏")
    if config["condition"]["fit_split"] != "train":
        raise PipelineError("condition.fit_split 必须为 train，避免验证集/测试集泄漏")
    if config["threshold"]["search_on"] != "val":
        raise PipelineError("threshold.search_on 必须为 val，禁止使用 test 集选择阈值")
    if config["threshold"]["metric"] not in {"f1", "precision", "recall"}:
        raise PipelineError("threshold.metric 仅支持 f1、precision、recall")

    for key in ["window_size", "stride", "prediction_horizon"]:
        value = config["window"][key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PipelineError(f"window.{key} 必须为正整数")

    for key in ["epochs", "batch_size", "hidden_dim"]:
        value = config["model"][key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PipelineError(f"model.{key} 必须为正整数")

    learning_rate = config["model"]["learning_rate"]
    if isinstance(learning_rate, bool) or not isinstance(learning_rate, (int, float)) or learning_rate <= 0:
        raise PipelineError("model.learning_rate 必须大于 0")

    dropout = config["model"]["dropout"]
    if isinstance(dropout, bool) or not isinstance(dropout, (int, float)) or not 0 <= float(dropout) < 1:
        raise PipelineError("model.dropout 必须满足 0 <= dropout < 1")

    condition_k = config["condition"]["k"]
    if isinstance(condition_k, bool) or not isinstance(condition_k, int) or condition_k <= 0:
        raise PipelineError("condition.k 必须为正整数")

    threshold_min = float(config["threshold"]["min"])
    threshold_max = float(config["threshold"]["max"])
    threshold_step = float(config["threshold"]["step"])
    default_threshold = float(config["threshold"]["default_threshold"])
    if not 0 < threshold_min < threshold_max < 1:
        raise PipelineError("threshold.min/max 必须满足 0 < min < max < 1")
    if threshold_step <= 0:
        raise PipelineError("threshold.step 必须大于 0")
    if not 0 < default_threshold < 1:
        raise PipelineError("threshold.default_threshold 必须位于 0 到 1 之间")


def resolve_stage_selection(
    stage_from: str | None = None,
    stage_to: str | None = None,
    only_stage: str | None = None,
) -> list[str]:
    if only_stage is not None and (stage_from is not None or stage_to is not None):
        raise PipelineError("--only-stage 不能与 --stage-from / --stage-to 同时使用")

    if only_stage is not None:
        validate_stage_name(only_stage)
        return [only_stage]

    start_index = 0
    end_index = len(STAGES) - 1

    if stage_from is not None:
        validate_stage_name(stage_from)
        start_index = STAGES.index(stage_from)
    if stage_to is not None:
        validate_stage_name(stage_to)
        end_index = STAGES.index(stage_to)
    if start_index > end_index:
        raise PipelineError("--stage-from 不能晚于 --stage-to")

    return STAGES[start_index : end_index + 1]


def validate_stage_name(stage: str) -> None:
    if stage not in STAGES:
        allowed = ", ".join(STAGES)
        raise PipelineError(f"非法 stage: {stage}。可选 stage: {allowed}")


def resolve_paths(config: dict[str, Any]) -> dict[str, Path]:
    experiment_name = str(config["experiment_name"])
    dataset_root = resolve_path(config["dataset_root"])
    output_root = resolve_path(config["output_root"])
    condition_k = int(config["condition"]["k"])

    base_dataset_dir = dataset_root / experiment_name
    window_dataset_dir = base_dataset_dir / "window_dataset"
    scaled_dataset_dir = base_dataset_dir / "train_scaled"
    condition_source_dir = scaled_dataset_dir if config["scale"]["enabled"] else window_dataset_dir
    condition_dataset_dir = base_dataset_dir / f"{condition_source_dir.name}_condition_k{condition_k}"

    if config["condition"]["enabled"]:
        training_dataset_dir = condition_dataset_dir
    elif config["scale"]["enabled"]:
        training_dataset_dir = scaled_dataset_dir
    else:
        training_dataset_dir = window_dataset_dir

    return {
        "segments_dir": resolve_path(config["segments_dir"]),
        "dataset_root": dataset_root,
        "output_root": output_root,
        "base_dataset_dir": base_dataset_dir,
        "window_dataset_dir": window_dataset_dir,
        "scaled_dataset_dir": scaled_dataset_dir,
        "condition_source_dir": condition_source_dir,
        "condition_dataset_dir": condition_dataset_dir,
        "training_dataset_dir": training_dataset_dir,
        "model_output_dir": output_root / experiment_name,
        "threshold_summary_file": output_root / experiment_name / "threshold_summary.json",
        "val_predictions_file": output_root / experiment_name / "val_predictions.csv",
        "evaluation_summary_file": output_root / experiment_name / "evaluation_summary.json",
        "test_predictions_file": output_root / experiment_name / "test_predictions.csv",
    }


def resolve_path(path_like: str | Path) -> Path:
    path = Path(path_like).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def print_pipeline_start(ctx: PipelineContext) -> None:
    print("=" * 72)
    print("RailPHM experiment pipeline")
    print("=" * 72)
    print(f"experiment_name: {ctx.config['experiment_name']}")
    print(f"config_path: {display_path(ctx.config_path) if ctx.config_path else '<program defaults>'}")
    print(f"enabled_stages: {', '.join(ctx.selected_stages)}")
    print("resolved_paths:")
    for key in [
        "segments_dir",
        "window_dataset_dir",
        "scaled_dataset_dir",
        "condition_dataset_dir",
        "training_dataset_dir",
        "model_output_dir",
    ]:
        print(f"  {key}: {display_path(ctx.paths[key])}")
    print("resolved_config:")
    print(json.dumps(ctx.config, ensure_ascii=False, indent=2))
    print("=" * 72)


def print_pipeline_end(ctx: PipelineContext, status: str, elapsed_seconds: float) -> None:
    print("=" * 72)
    print("RailPHM experiment pipeline finished")
    print("=" * 72)
    print(f"pipeline_status: {status}")
    print(f"executed_stages: {', '.join(ctx.executed_stages) or '<none>'}")
    print(f"skipped_stages: {', '.join(ctx.skipped_stages) or '<none>'}")
    print(f"elapsed_seconds: {elapsed_seconds:.2f}")
    print(f"model_output_dir: {display_path(ctx.paths['model_output_dir'])}")
    print(f"dataset_dir: {display_path(ctx.paths['training_dataset_dir'])}")
    print("=" * 72)


def required_files_exist(base_dir: Path, relative_files: list[str]) -> bool:
    return all((base_dir / relative_file).exists() for relative_file in relative_files)


def any_required_file_exists(base_dir: Path, relative_files: list[str]) -> bool:
    return any((base_dir / relative_file).exists() for relative_file in relative_files)


def build_complete(ctx: PipelineContext) -> bool:
    if not required_files_exist(
        ctx.paths["window_dataset_dir"],
        [
            "X.npy",
            "y.npy",
            "feature_columns.json",
            "window_manifest.csv",
            "dataset_summary.json",
        ],
    ):
        return False
    try:
        summary = read_json(ctx.paths["window_dataset_dir"] / "dataset_summary.json")
    except Exception:
        return False
    window_cfg = ctx.config["window"]
    feature_cfg = ctx.config["feature"]
    return (
        int(summary.get("window_size", -1)) == int(window_cfg["window_size"])
        and int(summary.get("stride", -1)) == int(window_cfg["stride"])
        and int(summary.get("prediction_horizon", -1)) == int(window_cfg["prediction_horizon"])
        and str(summary.get("feature_profile", "")) == str(feature_cfg["profile"])
    )


def inspect_complete(ctx: PipelineContext) -> bool:
    return (ctx.paths["window_dataset_dir"] / "inspection_summary.json").exists()


def split_complete(ctx: PipelineContext) -> bool:
    if not required_files_exist(
        ctx.paths["window_dataset_dir"],
        [
            "splits/train_indices.npy",
            "splits/val_indices.npy",
            "splits/test_indices.npy",
            "splits/split_summary.json",
        ],
    ):
        return False
    try:
        summary = read_json(ctx.paths["window_dataset_dir"] / "splits" / "split_summary.json")
    except Exception:
        return False
    split_cfg = ctx.config["split"]
    return (
        summary.get("split_strategy") == "segment_id"
        and math.isclose(float(summary.get("train_ratio", -1)), float(split_cfg["train_ratio"]))
        and math.isclose(float(summary.get("val_ratio", -1)), float(split_cfg["val_ratio"]))
        and math.isclose(float(summary.get("test_ratio", -1)), float(split_cfg["test_ratio"]))
        and int(summary.get("seed", -1)) == int(split_cfg["seed"])
        and not bool(summary.get("leakage_check", {}).get("has_segment_leakage", True))
    )


def scale_complete(ctx: PipelineContext) -> bool:
    if not required_files_exist(
        ctx.paths["scaled_dataset_dir"],
        [
            "X.npy",
            "y.npy",
            "feature_columns.json",
            "window_manifest.csv",
            "dataset_summary.json",
            "scaler_summary.json",
            "splits/train_indices.npy",
            "splits/val_indices.npy",
            "splits/test_indices.npy",
            "splits/split_summary.json",
        ],
    ):
        return False
    try:
        summary = read_json(ctx.paths["scaled_dataset_dir"] / "scaler_summary.json")
    except Exception:
        return False
    return (
        summary.get("method") == "standard"
        and summary.get("fit_scope") == "train_split_only"
        and path_matches(summary.get("input_dir"), ctx.paths["window_dataset_dir"])
    )


def condition_complete(ctx: PipelineContext) -> bool:
    if not required_files_exist(
        ctx.paths["condition_source_dir"],
        [
            "condition_labels.npy",
            "condition_manifest.csv",
            "condition_summary.json",
            "condition_model.pkl",
        ],
    ):
        return False
    try:
        summary = read_json(ctx.paths["condition_source_dir"] / "condition_summary.json")
    except Exception:
        return False
    return (
        int(summary.get("n_clusters", -1)) == int(ctx.config["condition"]["k"])
        and int(summary.get("seed", -1)) == int(ctx.config["split"]["seed"])
        and summary.get("fit_scope") == "train_split_only"
        and path_matches(summary.get("dataset_dir"), ctx.paths["condition_source_dir"])
    )


def augment_complete(ctx: PipelineContext) -> bool:
    if not required_files_exist(
        ctx.paths["condition_dataset_dir"],
        [
            "X.npy",
            "y.npy",
            "feature_columns.json",
            "window_manifest.csv",
            "dataset_summary.json",
            "condition_augmented_summary.json",
            "splits/train_indices.npy",
            "splits/val_indices.npy",
            "splits/test_indices.npy",
        ],
    ):
        return False
    try:
        summary = read_json(ctx.paths["condition_dataset_dir"] / "condition_augmented_summary.json")
    except Exception:
        return False
    return (
        int(summary.get("n_clusters", -1)) == int(ctx.config["condition"]["k"])
        and path_matches(summary.get("input_dir"), ctx.paths["condition_source_dir"])
        and path_matches(summary.get("output_dir"), ctx.paths["condition_dataset_dir"])
    )


def train_complete(ctx: PipelineContext) -> bool:
    if not required_files_exist(
        ctx.paths["model_output_dir"],
        [
            "best_model.pt",
            "training_config.json",
            "sequence_model_report.json",
            "metrics_history.csv",
            "test_predictions.csv",
        ],
    ):
        return False
    return training_config_matches_current_pipeline(ctx)


def training_config_matches_current_pipeline(ctx: PipelineContext) -> bool:
    config_path = ctx.paths["model_output_dir"] / "training_config.json"
    try:
        data = read_json(config_path)
    except Exception:
        return False

    expected_dataset_dir = ctx.paths["training_dataset_dir"].resolve()
    actual_dataset_dir = resolve_path(data.get("dataset_dir", "")).resolve()
    if actual_dataset_dir != expected_dataset_dir:
        return False

    model_cfg = ctx.config["model"]
    threshold_cfg = ctx.config["threshold"]
    expected_values = {
        "model": str(model_cfg["name"]),
        "epochs": int(model_cfg["epochs"]),
        "batch_size": int(model_cfg["batch_size"]),
        "lr": float(model_cfg["learning_rate"]),
        "hidden_dim": int(model_cfg["hidden_dim"]),
        "dropout": float(model_cfg["dropout"]),
        "threshold": float(threshold_cfg["default_threshold"]),
    }
    for key, expected_value in expected_values.items():
        if key not in data:
            return False
        actual_value = data[key]
        if isinstance(expected_value, float):
            if not math.isclose(float(actual_value), expected_value, rel_tol=1e-9, abs_tol=1e-12):
                return False
        elif actual_value != expected_value:
            return False

    return True


def threshold_complete(ctx: PipelineContext) -> bool:
    return ctx.paths["threshold_summary_file"].exists() and ctx.paths["val_predictions_file"].exists()


def evaluate_complete(ctx: PipelineContext) -> bool:
    return ctx.paths["evaluation_summary_file"].exists()


def managed_stage(
    ctx: PipelineContext,
    stage: str,
    input_dir: Path | None,
    output_dir: Path | None,
    key_params: dict[str, Any],
    complete: Callable[[PipelineContext], bool],
    exists_any: Callable[[PipelineContext], bool],
    action: Callable[[], str],
) -> StageResult:
    start_time = time.perf_counter()
    print()
    print(f"[START] {stage}")
    if input_dir is not None:
        print(f"input_dir: {display_path(input_dir)}")
    if output_dir is not None:
        print(f"output_dir: {display_path(output_dir)}")
    print("key_params:")
    print(json.dumps(key_params, ensure_ascii=False, indent=2, default=str))

    if ctx.dry_run:
        summary = action()
        elapsed = time.perf_counter() - start_time
        ctx.skipped_stages.append(stage)
        print(f"[DONE] {stage}")
        print(f"elapsed_seconds: {elapsed:.2f}")
        print(f"summary: dry-run only; {summary}")
        return StageResult(stage=stage, status="dry-run", elapsed_seconds=elapsed, summary=summary)

    if complete(ctx) and ctx.skip_existing and not ctx.overwrite:
        elapsed = time.perf_counter() - start_time
        ctx.skipped_stages.append(stage)
        print(f"[SKIP] {stage}")
        print("reason: required outputs already exist and skip_existing=true")
        return StageResult(stage=stage, status="skipped", elapsed_seconds=elapsed, summary="outputs complete")

    if exists_any(ctx) and not complete(ctx) and not ctx.overwrite:
        raise PipelineError(
            f"{stage} 输出已存在但不完整。请手动检查 {display_path(output_dir or PROJECT_ROOT)}，"
            "或使用 --overwrite 明确覆盖。"
        )

    if complete(ctx) and not ctx.overwrite:
        raise PipelineError(f"{stage} 输出已存在。请使用 --skip-existing 跳过，或使用 --overwrite 覆盖。")

    summary = action()
    if not complete(ctx):
        raise PipelineError(f"{stage} 执行结束后完整性检查仍未通过，请检查终端输出。")

    elapsed = time.perf_counter() - start_time
    ctx.executed_stages.append(stage)
    print(f"[DONE] {stage}")
    print(f"elapsed_seconds: {elapsed:.2f}")
    print(f"summary: {summary}")
    return StageResult(stage=stage, status="done", elapsed_seconds=elapsed, summary=summary)


def run_command(command: list[str], dry_run: bool) -> str:
    printable_command = " ".join(str(item) for item in command)
    print(f"command: {printable_command}")
    if dry_run:
        return printable_command
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(command, cwd=PROJECT_ROOT, check=True, env=env)
    return printable_command


def maybe_overwrite_arg(ctx: PipelineContext) -> list[str]:
    return ["--overwrite"] if ctx.overwrite else []


def stage_build(ctx: PipelineContext) -> StageResult:
    cfg = ctx.config
    command = [
        sys.executable,
        "scripts/build_window_dataset.py",
        "--segments-dir",
        display_path(ctx.paths["segments_dir"]),
        "--output-dir",
        display_path(ctx.paths["window_dataset_dir"]),
        "--window-size",
        str(cfg["window"]["window_size"]),
        "--stride",
        str(cfg["window"]["stride"]),
        "--horizon",
        str(cfg["window"]["prediction_horizon"]),
        "--feature-profile",
        str(cfg["feature"]["profile"]),
        "--verbose",
        *maybe_overwrite_arg(ctx),
    ]
    return managed_stage(
        ctx,
        stage="build",
        input_dir=ctx.paths["segments_dir"],
        output_dir=ctx.paths["window_dataset_dir"],
        key_params={
            "window_size": cfg["window"]["window_size"],
            "stride": cfg["window"]["stride"],
            "prediction_horizon": cfg["window"]["prediction_horizon"],
            "feature_profile": cfg["feature"]["profile"],
        },
        complete=build_complete,
        exists_any=lambda c: any_required_file_exists(
            c.paths["window_dataset_dir"],
            ["X.npy", "y.npy", "feature_columns.json", "window_manifest.csv", "dataset_summary.json"],
        ),
        action=lambda: run_command(command, dry_run=ctx.dry_run),
    )


def stage_inspect(ctx: PipelineContext) -> StageResult:
    command = [
        sys.executable,
        "scripts/inspect_dataset.py",
        "--dataset-dir",
        display_path(ctx.paths["window_dataset_dir"]),
    ]
    return managed_stage(
        ctx,
        stage="inspect",
        input_dir=ctx.paths["window_dataset_dir"],
        output_dir=ctx.paths["window_dataset_dir"],
        key_params={"output_file": "inspection_summary.json"},
        complete=inspect_complete,
        exists_any=lambda c: (c.paths["window_dataset_dir"] / "inspection_summary.json").exists(),
        action=lambda: run_command(command, dry_run=ctx.dry_run),
    )


def stage_split(ctx: PipelineContext) -> StageResult:
    cfg = ctx.config
    command = [
        sys.executable,
        "scripts/split_dataset.py",
        "--dataset-dir",
        display_path(ctx.paths["window_dataset_dir"]),
        "--train-ratio",
        str(cfg["split"]["train_ratio"]),
        "--val-ratio",
        str(cfg["split"]["val_ratio"]),
        "--test-ratio",
        str(cfg["split"]["test_ratio"]),
        "--seed",
        str(cfg["split"]["seed"]),
        *maybe_overwrite_arg(ctx),
    ]
    return managed_stage(
        ctx,
        stage="split",
        input_dir=ctx.paths["window_dataset_dir"],
        output_dir=ctx.paths["window_dataset_dir"] / "splits",
        key_params=cfg["split"],
        complete=split_complete,
        exists_any=lambda c: any_required_file_exists(
            c.paths["window_dataset_dir"],
            [
                "splits/train_indices.npy",
                "splits/val_indices.npy",
                "splits/test_indices.npy",
                "splits/split_summary.json",
            ],
        ),
        action=lambda: run_command(command, dry_run=ctx.dry_run),
    )


def stage_scale(ctx: PipelineContext) -> StageResult:
    if not ctx.config["scale"]["enabled"]:
        return skip_disabled_stage(ctx, "scale", "scale.enabled=false")
    command = [
        sys.executable,
        "scripts/scale_window_dataset.py",
        "--input-dir",
        display_path(ctx.paths["window_dataset_dir"]),
        "--output-dir",
        display_path(ctx.paths["scaled_dataset_dir"]),
        "--method",
        "standard",
        *maybe_overwrite_arg(ctx),
    ]
    return managed_stage(
        ctx,
        stage="scale",
        input_dir=ctx.paths["window_dataset_dir"],
        output_dir=ctx.paths["scaled_dataset_dir"],
        key_params=ctx.config["scale"],
        complete=scale_complete,
        exists_any=lambda c: any_required_file_exists(
            c.paths["scaled_dataset_dir"],
            ["X.npy", "y.npy", "feature_columns.json", "dataset_summary.json", "scaler_summary.json"],
        ),
        action=lambda: run_command(command, dry_run=ctx.dry_run),
    )


def stage_condition(ctx: PipelineContext) -> StageResult:
    if not ctx.config["condition"]["enabled"]:
        return skip_disabled_stage(ctx, "condition", "condition.enabled=false")
    cfg = ctx.config
    command = [
        sys.executable,
        "scripts/cluster_conditions.py",
        "--dataset-dir",
        display_path(ctx.paths["condition_source_dir"]),
        "--n-clusters",
        str(cfg["condition"]["k"]),
        "--seed",
        str(cfg["split"]["seed"]),
        "--verbose",
        *maybe_overwrite_arg(ctx),
    ]
    return managed_stage(
        ctx,
        stage="condition",
        input_dir=ctx.paths["condition_source_dir"],
        output_dir=ctx.paths["condition_source_dir"],
        key_params=cfg["condition"],
        complete=condition_complete,
        exists_any=lambda c: any_required_file_exists(
            c.paths["condition_source_dir"],
            ["condition_labels.npy", "condition_manifest.csv", "condition_summary.json", "condition_model.pkl"],
        ),
        action=lambda: run_command(command, dry_run=ctx.dry_run),
    )


def stage_augment(ctx: PipelineContext) -> StageResult:
    if not ctx.config["condition"]["enabled"]:
        return skip_disabled_stage(ctx, "augment", "condition.enabled=false")
    command = [
        sys.executable,
        "scripts/build_condition_augmented_dataset.py",
        "--input-dir",
        display_path(ctx.paths["condition_source_dir"]),
        "--output-dir",
        display_path(ctx.paths["condition_dataset_dir"]),
        "--verbose",
        *maybe_overwrite_arg(ctx),
    ]
    return managed_stage(
        ctx,
        stage="augment",
        input_dir=ctx.paths["condition_source_dir"],
        output_dir=ctx.paths["condition_dataset_dir"],
        key_params={"condition_k": ctx.config["condition"]["k"]},
        complete=augment_complete,
        exists_any=lambda c: any_required_file_exists(
            c.paths["condition_dataset_dir"],
            ["X.npy", "y.npy", "feature_columns.json", "dataset_summary.json", "condition_augmented_summary.json"],
        ),
        action=lambda: run_command(command, dry_run=ctx.dry_run),
    )


def stage_train(ctx: PipelineContext) -> StageResult:
    cfg = ctx.config
    command = [
        sys.executable,
        "scripts/train_sequence_model.py",
        "--dataset-dir",
        display_path(ctx.paths["training_dataset_dir"]),
        "--output-dir",
        display_path(ctx.paths["model_output_dir"]),
        "--model",
        str(cfg["model"]["name"]),
        "--epochs",
        str(cfg["model"]["epochs"]),
        "--batch-size",
        str(cfg["model"]["batch_size"]),
        "--lr",
        str(cfg["model"]["learning_rate"]),
        "--seed",
        str(cfg["split"]["seed"]),
        "--device",
        "auto",
        "--threshold",
        str(cfg["threshold"]["default_threshold"]),
        "--hidden-dim",
        str(cfg["model"]["hidden_dim"]),
        "--num-layers",
        "1",
        "--dropout",
        str(cfg["model"]["dropout"]),
        "--best-metric",
        "val_auc",
        *maybe_overwrite_arg(ctx),
    ]
    return managed_stage(
        ctx,
        stage="train",
        input_dir=ctx.paths["training_dataset_dir"],
        output_dir=ctx.paths["model_output_dir"],
        key_params=cfg["model"],
        complete=train_complete,
        exists_any=lambda c: any_required_file_exists(
            c.paths["model_output_dir"],
            ["best_model.pt", "training_config.json", "sequence_model_report.json", "metrics_history.csv", "test_predictions.csv"],
        ),
        action=lambda: run_command(command, dry_run=ctx.dry_run),
    )


def stage_threshold(ctx: PipelineContext) -> StageResult:
    def action() -> str:
        if ctx.dry_run:
            print("action: infer val probabilities from best_model.pt and search thresholds on val only")
            return "would search best threshold on validation split only"
        summary = run_threshold_search(ctx)
        return f"best_val_threshold={summary['best_threshold']:.4f}, metric={summary['best_metric_value']:.6f}"

    return managed_stage(
        ctx,
        stage="threshold",
        input_dir=ctx.paths["model_output_dir"],
        output_dir=ctx.paths["model_output_dir"],
        key_params=ctx.config["threshold"],
        complete=threshold_complete,
        exists_any=lambda c: c.paths["threshold_summary_file"].exists() or c.paths["val_predictions_file"].exists(),
        action=action,
    )


def stage_evaluate(ctx: PipelineContext) -> StageResult:
    def action() -> str:
        if ctx.dry_run:
            print("action: evaluate test predictions at default threshold and best validation threshold")
            return "would evaluate test split with fixed and best-val thresholds"
        summary = run_test_evaluation(ctx)
        return (
            "test_default_f1="
            f"{summary['test_at_default_threshold']['f1']:.6f}, "
            "test_best_val_f1="
            f"{summary['test_at_best_val_threshold']['f1']:.6f}"
        )

    return managed_stage(
        ctx,
        stage="evaluate",
        input_dir=ctx.paths["model_output_dir"],
        output_dir=ctx.paths["model_output_dir"],
        key_params={
            "default_threshold": ctx.config["threshold"]["default_threshold"],
            "best_threshold_source": "threshold_summary.json",
        },
        complete=evaluate_complete,
        exists_any=lambda c: c.paths["evaluation_summary_file"].exists(),
        action=action,
    )


def stage_diagnose(ctx: PipelineContext) -> StageResult:
    if not ctx.config["diagnosis"]["high_fp_enabled"]:
        return skip_disabled_stage(ctx, "diagnose", "diagnosis.high_fp_enabled=false")

    start_time = time.perf_counter()
    print()
    print("[START] diagnose")
    print(f"input_dir: {display_path(ctx.paths['model_output_dir'])}")
    print(f"output_dir: <terminal only>")
    print("key_params:")
    print(json.dumps(ctx.config["diagnosis"], ensure_ascii=False, indent=2))

    if ctx.dry_run:
        elapsed = time.perf_counter() - start_time
        ctx.skipped_stages.append("diagnose")
        print("[DONE] diagnose")
        print(f"elapsed_seconds: {elapsed:.2f}")
        print("summary: dry-run only; would print high FP segment top N")
        return StageResult("diagnose", "dry-run", elapsed, "would print high FP segment top N")

    summary = run_high_fp_diagnosis(ctx)
    elapsed = time.perf_counter() - start_time
    ctx.executed_stages.append("diagnose")
    print("[DONE] diagnose")
    print(f"elapsed_seconds: {elapsed:.2f}")
    print(f"summary: {summary}")
    return StageResult("diagnose", "done", elapsed, summary)


def skip_disabled_stage(ctx: PipelineContext, stage: str, reason: str) -> StageResult:
    start_time = time.perf_counter()
    print()
    print(f"[SKIP] {stage}")
    print(f"reason: {reason}")
    elapsed = time.perf_counter() - start_time
    ctx.skipped_stages.append(stage)
    return StageResult(stage=stage, status="skipped", elapsed_seconds=elapsed, summary=reason)


def generate_thresholds(min_value: float, max_value: float, step: float) -> list[float]:
    values: list[float] = []
    current = float(min_value)
    epsilon = step / 10.0
    while current <= float(max_value) + epsilon:
        values.append(round(current, 10))
        current += float(step)
    return values


def run_threshold_search(ctx: PipelineContext) -> dict[str, Any]:
    predictions = infer_split_predictions(ctx, split_name="val")
    write_prediction_rows(ctx.paths["val_predictions_file"], predictions)

    y_true = [int(row["y_true"]) for row in predictions]
    y_prob = [float(row["y_prob"]) for row in predictions]
    threshold_cfg = ctx.config["threshold"]
    metric_name = str(threshold_cfg["metric"])
    candidates = generate_thresholds(
        float(threshold_cfg["min"]),
        float(threshold_cfg["max"]),
        float(threshold_cfg["step"]),
    )

    best_threshold = candidates[0]
    best_metrics = compute_binary_metrics(y_true, y_prob, threshold=best_threshold)
    best_metric_value = float(best_metrics[metric_name])

    for threshold in candidates[1:]:
        metrics = compute_binary_metrics(y_true, y_prob, threshold=threshold)
        value = float(metrics[metric_name])
        if value > best_metric_value:
            best_threshold = threshold
            best_metric_value = value
            best_metrics = metrics

    summary = {
        "search_on": "val",
        "metric": metric_name,
        "threshold_min": float(threshold_cfg["min"]),
        "threshold_max": float(threshold_cfg["max"]),
        "threshold_step": float(threshold_cfg["step"]),
        "candidate_count": len(candidates),
        "best_threshold": float(best_threshold),
        "best_metric_value": float(best_metric_value),
        "best_val_metrics": best_metrics,
        "val_predictions_file": display_path(ctx.paths["val_predictions_file"]),
        "note": "Threshold is selected on validation split only. Test split is not used for threshold selection.",
    }
    write_json(ctx.paths["threshold_summary_file"], summary)

    print("Validation threshold search finished.")
    print(f"best_val_threshold: {best_threshold:.4f}")
    print_metrics(best_metrics)
    return summary


def run_test_evaluation(ctx: PipelineContext) -> dict[str, Any]:
    threshold_summary_path = ctx.paths["threshold_summary_file"]
    if not threshold_summary_path.exists():
        raise PipelineError("缺少 threshold_summary.json。请先运行 threshold 阶段。")

    threshold_summary = read_json(threshold_summary_path)
    test_predictions_path = ctx.paths["test_predictions_file"]
    if not test_predictions_path.exists():
        raise PipelineError("缺少 test_predictions.csv。请先运行 train 阶段。")

    rows = read_prediction_rows(test_predictions_path)
    y_true = [int(row["y_true"]) for row in rows]
    y_prob = [float(row["y_prob"]) for row in rows]

    default_threshold = float(ctx.config["threshold"]["default_threshold"])
    best_threshold = float(threshold_summary["best_threshold"])
    default_metrics = compute_binary_metrics(y_true, y_prob, threshold=default_threshold)
    best_metrics = compute_binary_metrics(y_true, y_prob, threshold=best_threshold)

    summary = {
        "test_predictions_file": display_path(test_predictions_path),
        "default_threshold": default_threshold,
        "best_val_threshold": best_threshold,
        "test_at_default_threshold": default_metrics,
        "test_at_best_val_threshold": best_metrics,
        "note": "best_val_threshold comes from validation split threshold search only.",
    }
    write_json(ctx.paths["evaluation_summary_file"], summary)

    print("Test evaluation finished.")
    print(f"default_threshold: {default_threshold:.4f}")
    print_metrics(default_metrics)
    print(f"best_val_threshold: {best_threshold:.4f}")
    print_metrics(best_metrics)
    return summary


def infer_split_predictions(ctx: PipelineContext, split_name: str) -> list[dict[str, Any]]:
    try:
        import numpy as np
        import torch
        from app.models import build_sequence_model
        from app.training.train_sequence_model import resolve_device
    except Exception as exc:  # pragma: no cover - exercised only in real model runs
        raise PipelineError(f"模型推理依赖不可用，请确认 torch 等训练依赖已安装: {exc}") from exc

    dataset_dir = ctx.paths["training_dataset_dir"]
    model_output_dir = ctx.paths["model_output_dir"]
    training_config = read_json(model_output_dir / "training_config.json")

    X = np.load(dataset_dir / "X.npy", allow_pickle=False)
    y = np.load(dataset_dir / "y.npy", allow_pickle=False)
    indices = np.load(dataset_dir / "splits" / f"{split_name}_indices.npy", allow_pickle=False)

    device = resolve_device(str(training_config.get("device", "auto")))
    model = build_sequence_model(
        model_name=str(training_config["model"]),
        input_dim=int(X.shape[2]),
        hidden_dim=int(training_config.get("hidden_dim", ctx.config["model"]["hidden_dim"])),
        num_layers=int(training_config.get("num_layers", 1)),
        dropout=float(training_config.get("dropout", ctx.config["model"]["dropout"])),
    ).to(device)

    checkpoint = torch.load(model_output_dir / "best_model.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    batch_size = int(ctx.config["model"]["batch_size"])
    threshold = float(ctx.config["threshold"]["default_threshold"])
    rows: list[dict[str, Any]] = []

    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start : start + batch_size]
            features = torch.as_tensor(X[batch_indices], dtype=torch.float32, device=device)
            logits = model(features).view(-1)
            probs = torch.sigmoid(logits).detach().cpu().numpy()

            for offset, sample_index in enumerate(batch_indices.tolist()):
                y_prob = float(probs[offset])
                rows.append(
                    {
                        "sample_order": int(start + offset),
                        "sample_index": int(sample_index),
                        "y_true": int(y[int(sample_index)]),
                        "y_prob": y_prob,
                        "y_pred": int(y_prob >= threshold),
                    }
                )

    return rows


def compute_binary_metrics(y_true_values: list[int], y_prob_values: list[float], threshold: float) -> dict[str, Any]:
    y_true = [int(value) for value in y_true_values]
    y_prob = [float(value) for value in y_prob_values]
    if len(y_true) != len(y_prob):
        raise PipelineError("y_true 与 y_prob 长度不一致")
    if not y_true:
        raise PipelineError("指标计算输入为空")

    y_pred = [1 if value >= threshold else 0 for value in y_prob]
    tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 1 and pred == 1)
    fp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 0 and pred == 1)
    tn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 0 and pred == 0)
    fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 1 and pred == 0)

    precision = float(tp / (tp + fp)) if tp + fp else 0.0
    recall = float(tp / (tp + fn)) if tp + fn else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    accuracy = float((tp + tn) / len(y_true))
    brier_score = float(sum((prob - truth) ** 2 for truth, prob in zip(y_true, y_prob)) / len(y_true))
    auc = compute_auc(y_true, y_prob)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auc": auc,
        "brier_score": brier_score,
        "threshold": float(threshold),
        "positive_count": int(sum(y_true)),
        "negative_count": int(len(y_true) - sum(y_true)),
        "predicted_positive_count": int(sum(y_pred)),
        "predicted_negative_count": int(len(y_pred) - sum(y_pred)),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def compute_auc(y_true: list[int], y_prob: list[float]) -> float | None:
    positive_count = sum(1 for value in y_true if value == 1)
    negative_count = sum(1 for value in y_true if value == 0)
    if positive_count == 0 or negative_count == 0:
        return None

    pairs = sorted(zip(y_prob, y_true), key=lambda item: item[0])
    rank_sum = 0.0
    rank = 1
    index = 0
    while index < len(pairs):
        tie_end = index + 1
        while tie_end < len(pairs) and pairs[tie_end][0] == pairs[index][0]:
            tie_end += 1
        average_rank = (rank + tie_end) / 2.0
        for pair_index in range(index, tie_end):
            if pairs[pair_index][1] == 1:
                rank_sum += average_rank
        rank = tie_end + 1
        index = tie_end

    auc = (rank_sum - positive_count * (positive_count + 1) / 2.0) / (positive_count * negative_count)
    return float(auc)


def print_metrics(metrics: dict[str, Any]) -> None:
    confusion = metrics["confusion_matrix"]
    auc_text = "None" if metrics["auc"] is None else f"{metrics['auc']:.6f}"
    print(
        "metrics: "
        f"precision={metrics['precision']:.6f}, "
        f"recall={metrics['recall']:.6f}, "
        f"f1={metrics['f1']:.6f}, "
        f"auc={auc_text}, "
        f"brier={metrics['brier_score']:.6f}, "
        f"TP={confusion['tp']}, "
        f"FP={confusion['fp']}, "
        f"TN={confusion['tn']}, "
        f"FN={confusion['fn']}"
    )


def run_high_fp_diagnosis(ctx: PipelineContext) -> str:
    test_predictions_path = ctx.paths["test_predictions_file"]
    manifest_path = ctx.paths["training_dataset_dir"] / "window_manifest.csv"
    test_indices_path = ctx.paths["training_dataset_dir"] / "splits" / "test_indices.npy"

    missing = [
        path
        for path in [test_predictions_path, manifest_path, test_indices_path]
        if not path.exists()
    ]
    if missing:
        print("[SKIP] diagnose")
        print("reason: 缺少诊断所需文件")
        for path in missing:
            print(f"- {display_path(path)}")
        return "diagnose skipped because required files are missing"

    try:
        import numpy as np
        import pandas as pd
    except Exception as exc:  # pragma: no cover - runtime dependency guard
        print("[SKIP] diagnose")
        print(f"reason: 诊断依赖不可用: {exc}")
        return "diagnose skipped because pandas/numpy is unavailable"

    rows = read_prediction_rows(test_predictions_path)
    manifest = pd.read_csv(manifest_path, encoding="utf-8-sig")
    test_indices = np.load(test_indices_path, allow_pickle=False)

    threshold = float(ctx.config["threshold"]["default_threshold"])
    if ctx.paths["threshold_summary_file"].exists():
        threshold = float(read_json(ctx.paths["threshold_summary_file"]).get("best_threshold", threshold))

    records: list[dict[str, Any]] = []
    for row in rows:
        if "sample_index" in row and row["sample_index"] != "":
            sample_index = int(row["sample_index"])
        else:
            sample_order = int(row["sample_order"])
            if sample_order >= len(test_indices):
                continue
            sample_index = int(test_indices[sample_order])
        if sample_index >= len(manifest):
            continue
        manifest_row = manifest.iloc[sample_index]
        y_true = int(row["y_true"])
        y_prob = float(row["y_prob"])
        records.append(
            {
                "segment_id": manifest_row.get("segment_id", ""),
                "segment_file": manifest_row.get("segment_file", ""),
                "y_true": y_true,
                "is_fp": int(y_true == 0 and y_prob >= threshold),
            }
        )

    if not records:
        print("No prediction records available for diagnosis.")
        return "no prediction records"

    frame = pd.DataFrame(records)
    grouped = []
    for (segment_id, segment_file), group in frame.groupby(["segment_id", "segment_file"], dropna=False):
        total_samples = int(len(group))
        fp_count = int(group["is_fp"].sum())
        pos_count = int(group["y_true"].sum())
        grouped.append(
            {
                "segment_id": segment_id,
                "segment_file": segment_file,
                "fp_count": fp_count,
                "fp_ratio": float(fp_count / total_samples) if total_samples else 0.0,
                "pos_count": pos_count,
                "pos_ratio": float(pos_count / total_samples) if total_samples else 0.0,
                "total_samples": total_samples,
            }
        )

    grouped.sort(key=lambda item: (item["fp_count"], item["fp_ratio"]), reverse=True)
    top_n = int(ctx.config["diagnosis"]["top_fp"])
    print(f"High FP segment top {top_n} at threshold={threshold:.4f}")
    print("rank\tsegment_id\tsegment_file\tfp_count\tfp_ratio\tpos_count\tpos_ratio\ttotal_samples")
    for rank, item in enumerate(grouped[:top_n], start=1):
        print(
            f"{rank}\t{item['segment_id']}\t{item['segment_file']}\t"
            f"{item['fp_count']}\t{item['fp_ratio']:.6f}\t"
            f"{item['pos_count']}\t{item['pos_ratio']:.6f}\t{item['total_samples']}"
        )
    return f"printed top {min(top_n, len(grouped))} high FP segments"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def path_matches(raw_path: Any, expected_path: Path) -> bool:
    if raw_path is None:
        return False
    try:
        return resolve_path(str(raw_path)).resolve() == expected_path.resolve()
    except Exception:
        return False


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_prediction_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["sample_order", "sample_index", "y_true", "y_prob", "y_pred"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_prediction_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def execute_stage(ctx: PipelineContext, stage: str) -> StageResult:
    handlers: dict[str, Callable[[PipelineContext], StageResult]] = {
        "build": stage_build,
        "inspect": stage_inspect,
        "split": stage_split,
        "scale": stage_scale,
        "condition": stage_condition,
        "augment": stage_augment,
        "train": stage_train,
        "threshold": stage_threshold,
        "evaluate": stage_evaluate,
        "diagnose": stage_diagnose,
    }
    return handlers[stage](ctx)


def main(argv: list[str] | None = None) -> int:
    started_at = time.perf_counter()
    args = parse_args(argv)
    config_path = resolve_path(args.config) if args.config else None

    try:
        config = resolve_config(args)
        selected_stages = resolve_stage_selection(
            stage_from=args.stage_from,
            stage_to=args.stage_to,
            only_stage=args.only_stage,
        )
        paths = resolve_paths(config)
        ctx = PipelineContext(
            config=config,
            config_path=config_path,
            paths=paths,
            selected_stages=selected_stages,
            dry_run=bool(config["run"]["dry_run"]),
            overwrite=bool(config["run"]["overwrite"]),
            skip_existing=bool(config["run"]["skip_existing"]),
            executed_stages=[],
            skipped_stages=[],
        )

        print_pipeline_start(ctx)
        for stage in selected_stages:
            try:
                execute_stage(ctx, stage)
            except subprocess.CalledProcessError as exc:
                print(f"[ERROR] {stage}")
                print(f"error_message: command exited with code {exc.returncode}")
                print("suggested_action: 检查该阶段输入文件和上方脚本输出；如需覆盖旧结果，请显式使用 --overwrite。")
                if config["run"]["stop_on_error"]:
                    raise
            except Exception as exc:
                print(f"[ERROR] {stage}")
                print(f"error_message: {exc}")
                print("suggested_action: 检查该阶段输入/输出路径；不完整旧结果请手动清理或使用 --overwrite。")
                if config["run"]["stop_on_error"]:
                    raise

        print_pipeline_end(ctx, status="success", elapsed_seconds=time.perf_counter() - started_at)
        return 0
    except PipelineError as exc:
        print(f"[ERROR] pipeline")
        print(f"error_message: {exc}")
        return 2
    except subprocess.CalledProcessError:
        return 1
    except Exception as exc:
        print(f"[ERROR] pipeline")
        print(f"error_message: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
