from pathlib import Path

import pytest

from scripts import run_experiment_pipeline as pipeline


def test_config_file_can_be_loaded():
    config = pipeline.deep_merge(
        pipeline.PROGRAM_DEFAULT_CONFIG,
        pipeline.load_json_config(Path("configs/experiment_pipeline.json")),
    )

    assert config["experiment_name"] == "bilstm_attention_h1_full_features"
    assert config["threshold"]["search_on"] == "val"


def test_cli_overrides_json_config():
    args = pipeline.parse_args(
        [
            "--config",
            "configs/experiment_pipeline.json",
            "--prediction-horizon",
            "5",
            "--model",
            "bilstm_attention",
            "--epochs",
            "3",
        ]
    )

    config = pipeline.resolve_config(args)

    assert config["window"]["prediction_horizon"] == 5
    assert config["model"]["name"] == "bilstm_attention"
    assert config["model"]["epochs"] == 3


def test_only_stage_returns_single_stage():
    assert pipeline.resolve_stage_selection(only_stage="train") == ["train"]


def test_stage_from_returns_suffix():
    assert pipeline.resolve_stage_selection(stage_from="scale") == [
        "scale",
        "condition",
        "augment",
        "train",
        "threshold",
        "evaluate",
        "diagnose",
    ]


def test_stage_to_returns_prefix():
    assert pipeline.resolve_stage_selection(stage_to="split") == ["build", "inspect", "split"]


def test_stage_range_returns_middle():
    assert pipeline.resolve_stage_selection(stage_from="scale", stage_to="evaluate") == [
        "scale",
        "condition",
        "augment",
        "train",
        "threshold",
        "evaluate",
    ]


def test_illegal_stage_raises_clear_error():
    with pytest.raises(pipeline.PipelineError, match="非法 stage"):
        pipeline.resolve_stage_selection(only_stage="bad_stage")


def test_dry_run_does_not_create_output_dirs(tmp_path):
    dataset_root = tmp_path / "datasets"
    output_root = tmp_path / "outputs"

    exit_code = pipeline.main(
        [
            "--config",
            "configs/experiment_pipeline.json",
            "--dataset-root",
            str(dataset_root),
            "--output-root",
            str(output_root),
            "--dry-run",
            "--only-stage",
            "build",
        ]
    )

    assert exit_code == 0
    assert not dataset_root.exists()
    assert not output_root.exists()


def test_completeness_check_returns_false_for_missing_files(tmp_path):
    args = pipeline.parse_args(
        [
            "--config",
            "configs/experiment_pipeline.json",
            "--dataset-root",
            str(tmp_path / "datasets"),
            "--output-root",
            str(tmp_path / "outputs"),
        ]
    )
    config = pipeline.resolve_config(args)
    ctx = pipeline.PipelineContext(
        config=config,
        config_path=None,
        paths=pipeline.resolve_paths(config),
        selected_stages=[],
        dry_run=False,
        overwrite=False,
        skip_existing=True,
        executed_stages=[],
        skipped_stages=[],
    )

    assert pipeline.build_complete(ctx) is False
