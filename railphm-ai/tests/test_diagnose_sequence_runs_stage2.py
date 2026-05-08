import importlib.util
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest


def _load_diagnose_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_sequence_runs.py"
    spec = importlib.util.spec_from_file_location("diagnose_sequence_runs", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _base_val_predictions():
    y_true = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    y_prob = [0.45, 0.42, 0.35, 0.32, 0.10, 0.40, 0.25, 0.20, 0.15, 0.05]

    return pd.DataFrame(
        {
            "sample_order": list(range(10)),
            "sample_index": list(range(100, 110)),
            "y_true": y_true,
            "y_prob": y_prob,
            "y_pred_05": [1 if value >= 0.5 else 0 for value in y_prob],
        }
    )


def _base_test_predictions():
    # test 上 0.7 可以更好，但 val 上 0.3 最优，用于验证 test 不参与 threshold 选择。
    y_true = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    y_prob = [0.90, 0.80, 0.70, 0.20, 0.10, 0.60, 0.50, 0.40, 0.30, 0.05]

    return pd.DataFrame(
        {
            "sample_order": list(range(10)),
            "sample_index": list(range(200, 210)),
            "y_true": y_true,
            "y_prob": y_prob,
            "y_pred_05": [1 if value >= 0.5 else 0 for value in y_prob],
        }
    )


def _write_predictions(output_dir: Path) -> None:
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)

    model_prefixes = [
        "lstm",
        "bilstm",
        "lstm_attention",
        "bilstm_attention",
    ]

    for prefix in model_prefixes:
        _base_val_predictions().to_csv(
            predictions_dir / f"{prefix}_val_predictions.csv",
            index=False,
        )
        _base_test_predictions().to_csv(
            predictions_dir / f"{prefix}_test_predictions.csv",
            index=False,
        )


def _args(output_dir: Path, save: bool = False, save_detail: bool = False, step: float = 0.1):
    return Namespace(
        stage="threshold",
        output_dir=output_dir,
        dataset_dir=None,
        lstm_run=None,
        bilstm_run=None,
        lstm_attention_run=None,
        bilstm_attention_run=None,
        threshold_step=step,
        device="cpu",
        save=save,
        save_detail=save_detail,
        verbose=True,
    )


def test_terminal_mode_does_not_generate_files(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    module.run_threshold_analysis(_args(output_dir, save=False))

    assert not (output_dir / "threshold_summary.csv").exists()
    assert not (output_dir / "diagnosis_stage2_threshold.json").exists()
    assert not (output_dir / "threshold_search_detail.csv").exists()
    assert not (output_dir / "diagnosis_stage2_threshold.md").exists()


def test_terminal_output_contains_core_tables(tmp_path, capsys):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    module.run_threshold_analysis(_args(output_dir, save=False))

    stdout = capsys.readouterr().out

    assert "Threshold Summary" in stdout
    assert "Best Val Threshold" in stdout
    assert "Global Judgement" in stdout
    assert "LSTM" in stdout
    assert "Bi-LSTM" in stdout
    assert "LSTM+Attention" in stdout
    assert "Bi-LSTM+Attention" in stdout


def test_best_threshold_selected_from_val(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    result = module.run_threshold_analysis(_args(output_dir, save=False, step=0.1))

    for row in result["summary"]:
        assert row["best_val_threshold"] == pytest.approx(0.3)


def test_test_split_does_not_select_threshold(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    result = module.run_threshold_analysis(_args(output_dir, save=False, step=0.1))

    # test 数据中 0.7 更有利，但必须仍使用 val 选出的 0.3。
    for row in result["summary"]:
        assert row["best_val_threshold"] == pytest.approx(0.3)


def test_y_prob_out_of_range_raises_error(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    bad_path = output_dir / "predictions" / "lstm_val_predictions.csv"
    df = pd.read_csv(bad_path)
    df.loc[0, "y_prob"] = 1.2
    df.to_csv(bad_path, index=False)

    with pytest.raises(ValueError, match="y_prob"):
        module.run_threshold_analysis(_args(output_dir, save=False))


def test_y_true_inconsistent_raises_error(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    bad_path = output_dir / "predictions" / "bilstm_val_predictions.csv"
    df = pd.read_csv(bad_path)
    df.loc[0, "y_true"] = 0 if int(df.loc[0, "y_true"]) == 1 else 1
    df.to_csv(bad_path, index=False)

    with pytest.raises(ValueError, match="y_true 不一致"):
        module.run_threshold_analysis(_args(output_dir, save=False))


def test_missing_prediction_file_raises_error(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    missing_path = output_dir / "predictions" / "bilstm_test_predictions.csv"
    missing_path.unlink()

    with pytest.raises(FileNotFoundError):
        module.run_threshold_analysis(_args(output_dir, save=False))


def test_threshold_grid_always_contains_05_when_step_is_007():
    module = _load_diagnose_module()

    thresholds = module.build_threshold_grid(0.07)

    assert 0.5 in thresholds


def test_tie_breaker_prefers_higher_recall():
    module = _load_diagnose_module()

    df = pd.DataFrame(
        {
            "sample_order": list(range(8)),
            "sample_index": list(range(8)),
            "y_true": [1, 1, 1, 1, 0, 0, 0, 0],
            "y_prob": [0.50, 0.45, 0.35, 0.32, 0.35, 0.34, 0.33, 0.31],
            "y_pred_05": [1, 0, 0, 0, 0, 0, 0, 0],
        }
    )

    threshold, metrics, _ = module.search_best_threshold_on_val(
        df,
        thresholds=[0.3, 0.4, 0.5],
    )

    assert threshold == pytest.approx(0.3)
    assert metrics["recall"] == pytest.approx(1.0)


def test_save_mode_generates_lightweight_files(tmp_path):
    module = _load_diagnose_module()
    output_dir = tmp_path / "diagnosis"
    _write_predictions(output_dir)

    module.run_threshold_analysis(_args(output_dir, save=True))

    assert (output_dir / "threshold_summary.csv").exists()
    assert (output_dir / "diagnosis_stage2_threshold.json").exists()
    assert not (output_dir / "threshold_search_detail.csv").exists()