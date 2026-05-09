"""
SequenceModelRuntime 运行时加载器测试。

本测试覆盖以下能力：
1. 运行设备解析；
2. feature_columns.json 读取；
3. SequenceModelRuntime 从临时模型目录加载 Bi-LSTM+Attention 模型；
4. 单窗口 predict_proba 确定性预测；
5. 概率校准器可选加载；
6. 启用校准后 risk_score 使用校准概率；
7. 未启用校准时保持 risk_score = risk_raw 的兼容逻辑。

测试使用 tmp_path 构造临时模型目录和临时 checkpoint，不依赖真实 outputs 目录，
不依赖真实 best_model.pt，不修改真实训练产物。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from app.calibration import IsotonicRiskCalibrator
from app.models import build_sequence_model
from app.runtime.model_loader import (
    SequenceModelRuntime,
    load_feature_columns,
    resolve_runtime_device,
)


def write_json(path: Path, data: object) -> None:
    """写入 JSON 文件，保留中文内容。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_feature_columns(count: int = 23) -> list[str]:
    """构造测试用特征字段列表，末尾保留 condition one-hot 字段。"""
    if count < 3:
        return [f"feature_{index}" for index in range(count)]

    base_count = count - 3
    return [f"feature_{index}" for index in range(base_count)] + [
        "condition_0",
        "condition_1",
        "condition_2",
    ]


def make_manifest_data(
    *,
    model_dir_name: str,
    hidden_dim: int = 8,
    dropout: float = 0.1,
    feature_dim: int = 23,
    feature_columns_count: int = 23,
    threshold: float = 0.26,
) -> dict:
    """构造测试用 model_artifact_manifest.json 内容。"""
    return {
        "model_version": model_dir_name,
        "model_name": "bilstm_attention",
        "model_class": "BiLSTMAttentionClassifier",
        "window_size": 30,
        "feature_dim": feature_dim,
        "input_dim": feature_dim,
        "hidden_dim": hidden_dim,
        "num_layers": 1,
        "dropout": dropout,
        "threshold": threshold,
        "dataset_dir": "data/datasets/test_dataset",
        "output_dir": f"outputs/sequence_models/{model_dir_name}",
        "feature_columns_count": feature_columns_count,
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
        },
    }


def make_model_dir(
    tmp_path: Path,
    *,
    hidden_dim: int = 8,
    dropout: float = 0.1,
    feature_dim: int = 23,
    feature_columns: list[str] | None = None,
    checkpoint: dict | None = None,
) -> Path:
    """构造测试用模型目录，包含 manifest、feature_columns 和 checkpoint。"""
    model_dir = tmp_path / "bilstm_attention_h1_full_features"
    model_dir.mkdir()

    feature_columns = (
        feature_columns
        if feature_columns is not None
        else make_feature_columns(feature_dim)
    )

    write_json(
        model_dir / "training_config.json",
        {
            "model": "bilstm_attention",
            "dataset_dir": "data/datasets/test_dataset",
            "output_dir": f"outputs/sequence_models/{model_dir.name}",
            "window_size": 30,
            "feature_dim": feature_dim,
            "input_dim": feature_dim,
            "hidden_dim": hidden_dim,
            "num_layers": 1,
            "dropout": dropout,
            "model_config": {
                "name": "BiLSTMAttentionClassifier",
            },
        },
    )

    write_json(
        model_dir / "sequence_model_report.json",
        {
            "model": {
                "name": "BiLSTMAttentionClassifier",
            }
        },
    )

    write_json(
        model_dir / "threshold_summary.json",
        {
            "best_threshold": 0.26,
            "search_on": "val",
            "metric": "f1",
        },
    )

    write_json(model_dir / "evaluation_summary.json", {"task": "evaluation"})
    write_json(model_dir / "feature_columns.json", feature_columns)

    write_json(
        model_dir / "model_artifact_manifest.json",
        make_manifest_data(
            model_dir_name=model_dir.name,
            hidden_dim=hidden_dim,
            dropout=dropout,
            feature_dim=feature_dim,
            feature_columns_count=feature_dim,
        ),
    )

    if checkpoint is None:
        model = build_sequence_model(
            model_name="bilstm_attention",
            input_dim=feature_dim,
            hidden_dim=hidden_dim,
            num_layers=1,
            dropout=dropout,
        )
        checkpoint = {
            "model_state_dict": model.state_dict(),
            "model_config": model.get_config(),
            "epoch": 1,
            "best_metric": "val_auc",
            "best_metric_value": 0.5,
        }

    torch.save(checkpoint, model_dir / "best_model.pt")

    return model_dir


def make_calibrated_model_dir(
    tmp_path: Path,
    *,
    calibration_enabled: bool = True,
    calibration_method: str = "isotonic_regression",
    calibrator_missing: bool = False,
    calibrator_key_missing: bool = False,
) -> Path:
    """构造带 calibration 字段的测试用模型目录。"""
    model_dir = make_model_dir(tmp_path)

    manifest_path = model_dir / "model_artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    calibration = {
        "enabled": calibration_enabled,
        "method": calibration_method,
        "summary": "calibration_summary.json",
        "fit_split": "val",
        "calibrated_val_predictions": "calibrated_val_predictions.csv",
        "calibrated_test_predictions": "calibrated_test_predictions.csv",
    }

    if not calibrator_key_missing:
        calibration["calibrator"] = "calibrator.pkl"

    manifest["calibration"] = calibration
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if calibration_enabled and not calibrator_missing and not calibrator_key_missing:
        calibrator = IsotonicRiskCalibrator()
        calibrator.fit(
            y_true=[0, 0, 1, 1],
            y_prob=[0.1, 0.3, 0.7, 0.9],
        )
        calibrator.save(model_dir / "calibrator.pkl")

    return model_dir


def test_resolve_runtime_device_cpu() -> None:
    """device=cpu 时应返回 torch.device('cpu')。"""
    device = resolve_runtime_device("cpu")

    assert device == torch.device("cpu")


def test_resolve_runtime_device_invalid() -> None:
    """非法 device 应明确报错。"""
    with pytest.raises(ValueError, match="device"):
        resolve_runtime_device("bad-device")


def test_load_feature_columns_success(tmp_path: Path) -> None:
    """feature_columns.json 为非空 list[str] 时应读取成功。"""
    path = tmp_path / "feature_columns.json"
    write_json(path, ["速度", "里程", "condition_0"])

    cols = load_feature_columns(path)

    assert cols == ["速度", "里程", "condition_0"]


def test_load_feature_columns_invalid_type(tmp_path: Path) -> None:
    """feature_columns.json 不是 list[str] 时应报错。"""
    path = tmp_path / "feature_columns.json"
    write_json(path, {"bad": "value"})

    with pytest.raises(ValueError, match="feature_columns"):
        load_feature_columns(path)


def test_sequence_model_runtime_load_success(tmp_path: Path) -> None:
    """模型目录完整时，SequenceModelRuntime 应能成功加载模型。"""
    model_dir = make_model_dir(tmp_path)

    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    assert runtime.model_version == model_dir.name
    assert runtime.model_name == "bilstm_attention"
    assert runtime.model_class == "BiLSTMAttentionClassifier"
    assert runtime.window_size == 30
    assert runtime.feature_dim == 23
    assert runtime.threshold == 0.26
    assert len(runtime.feature_columns) == 23
    assert runtime.device == torch.device("cpu")
    assert runtime.model.training is False

    summary = runtime.summary()
    assert summary["model_version"] == model_dir.name
    assert summary["model_name"] == "bilstm_attention"
    assert summary["model_class"] == "BiLSTMAttentionClassifier"
    assert summary["window_size"] == 30
    assert summary["feature_dim"] == 23
    assert summary["threshold"] == 0.26
    assert summary["device"] == "cpu"
    assert summary["feature_columns_count"] == 23
    assert summary["calibration_enabled"] is False
    assert summary["calibration_method"] is None


def test_sequence_model_runtime_missing_state_dict(tmp_path: Path) -> None:
    """checkpoint 缺少 model_state_dict 时应报错。"""
    model_dir = make_model_dir(tmp_path, checkpoint={"bad": "value"})

    with pytest.raises(ValueError, match="model_state_dict"):
        SequenceModelRuntime.from_model_dir(model_dir, device="cpu")


def test_sequence_model_runtime_feature_columns_mismatch(tmp_path: Path) -> None:
    """feature_columns 数量与 feature_dim 不一致时应报错。"""
    model_dir = make_model_dir(
        tmp_path,
        feature_dim=23,
        feature_columns=make_feature_columns(22),
    )

    with pytest.raises(ValueError, match="feature_columns"):
        SequenceModelRuntime.from_model_dir(model_dir, device="cpu")


def test_predict_proba_success(tmp_path: Path) -> None:
    """predict_proba 应能对 shape=(30,23) 的窗口输出风险概率。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.random.randn(30, 23).astype("float32")

    result = runtime.predict_proba(window)

    assert 0 <= result["risk_raw"] <= 1
    assert 0 <= result["risk_score"] <= 1
    assert result["risk_score"] == pytest.approx(result["risk_raw"])
    assert result["threshold"] == 0.26
    assert result["predicted_label"] in {0, 1}
    assert result["model_version"] == runtime.model_version
    assert result["model_name"] == runtime.model_name
    assert result["window_size"] == 30
    assert result["feature_dim"] == 23
    assert result["calibration_enabled"] is False
    assert result["calibration_method"] is None
    assert runtime.model.training is False


def test_predict_proba_rejects_non_numpy(tmp_path: Path) -> None:
    """predict_proba 应拒绝非 numpy.ndarray 输入。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    with pytest.raises(ValueError, match="numpy.ndarray"):
        runtime.predict_proba([[0.0] * 23 for _ in range(30)])


def test_predict_proba_rejects_wrong_ndim(tmp_path: Path) -> None:
    """predict_proba 应拒绝三维输入。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((1, 30, 23), dtype=np.float32)

    with pytest.raises(ValueError, match="2D"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_wrong_window_size(tmp_path: Path) -> None:
    """predict_proba 应拒绝窗口长度不匹配的输入。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((20, 23), dtype=np.float32)

    with pytest.raises(ValueError, match="shape mismatch"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_wrong_feature_dim(tmp_path: Path) -> None:
    """predict_proba 应拒绝特征维度不匹配的输入。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((30, 22), dtype=np.float32)

    with pytest.raises(ValueError, match="shape mismatch"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_nan(tmp_path: Path) -> None:
    """predict_proba 应拒绝包含 NaN 的输入。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((30, 23), dtype=np.float32)
    window[0, 0] = np.nan

    with pytest.raises(ValueError, match="NaN or inf"):
        runtime.predict_proba(window)


def test_predict_proba_rejects_inf(tmp_path: Path) -> None:
    """predict_proba 应拒绝包含 inf 的输入。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.zeros((30, 23), dtype=np.float32)
    window[0, 0] = np.inf

    with pytest.raises(ValueError, match="NaN or inf"):
        runtime.predict_proba(window)


def test_runtime_without_calibration_keeps_raw_score(tmp_path: Path) -> None:
    """没有 calibration 字段时，应保持 risk_score = risk_raw 的旧逻辑。"""
    model_dir = make_model_dir(tmp_path)

    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    assert runtime.calibration_enabled is False
    assert runtime.calibrator is None
    assert runtime.calibration_method is None

    window = np.random.randn(30, 23).astype("float32")
    result = runtime.predict_proba(window)

    assert result["calibration_enabled"] is False
    assert result["calibration_method"] is None
    assert result["risk_score"] == pytest.approx(result["risk_raw"])
    assert 0 <= result["risk_score"] <= 1


def test_runtime_with_calibration_loads_calibrator(tmp_path: Path) -> None:
    """calibration.enabled=true 时，应加载 calibrator.pkl。"""
    model_dir = make_calibrated_model_dir(tmp_path)

    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    assert runtime.calibration_enabled is True
    assert runtime.calibration_method == "isotonic_regression"
    assert runtime.calibrator is not None

    summary = runtime.summary()
    assert summary["calibration_enabled"] is True
    assert summary["calibration_method"] == "isotonic_regression"


def test_predict_proba_with_calibration_outputs_calibrated_score(tmp_path: Path) -> None:
    """启用校准后，predict_proba 应输出校准后的 risk_score。"""
    model_dir = make_calibrated_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.random.randn(30, 23).astype("float32")
    result = runtime.predict_proba(window)

    assert 0 <= result["risk_raw"] <= 1
    assert 0 <= result["risk_score"] <= 1
    assert result["calibration_enabled"] is True
    assert result["calibration_method"] == "isotonic_regression"
    assert result["predicted_label"] in {0, 1}


def test_runtime_calibration_missing_file_raises(tmp_path: Path) -> None:
    """manifest 启用 calibration 但 calibrator.pkl 缺失时应报错。"""
    model_dir = make_calibrated_model_dir(
        tmp_path,
        calibration_enabled=True,
        calibrator_missing=True,
    )

    with pytest.raises(FileNotFoundError, match="calibrator"):
        SequenceModelRuntime.from_model_dir(model_dir, device="cpu")


def test_runtime_unsupported_calibration_method_raises(tmp_path: Path) -> None:
    """不支持的校准方法应报错。"""
    model_dir = make_calibrated_model_dir(
        tmp_path,
        calibration_enabled=True,
        calibration_method="platt_scaling",
    )

    with pytest.raises(ValueError, match="unsupported calibration method"):
        SequenceModelRuntime.from_model_dir(model_dir, device="cpu")


def test_runtime_calibration_enabled_missing_calibrator_key_raises(tmp_path: Path) -> None:
    """calibration.enabled=true 但缺少 calibrator 字段时应报错。"""
    model_dir = make_calibrated_model_dir(
        tmp_path,
        calibration_enabled=True,
        calibrator_key_missing=True,
    )

    with pytest.raises(ValueError, match="calibrator field"):
        SequenceModelRuntime.from_model_dir(model_dir, device="cpu")


def test_runtime_calibration_disabled_keeps_backward_compatible(tmp_path: Path) -> None:
    """calibration.enabled=false 时，应保持未校准兼容逻辑。"""
    model_dir = make_calibrated_model_dir(
        tmp_path,
        calibration_enabled=False,
    )

    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    assert runtime.calibration_enabled is False
    assert runtime.calibrator is None
    assert runtime.calibration_method is None

    window = np.random.randn(30, 23).astype("float32")
    result = runtime.predict_proba(window)

    assert result["calibration_enabled"] is False
    assert result["calibration_method"] is None
    assert result["risk_score"] == pytest.approx(result["risk_raw"])

def test_predict_with_uncertainty_without_calibration(tmp_path: Path) -> None:
    """未启用校准时，risk_score 应等于 risk_raw，risk_std 应等于 risk_raw_std。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.random.randn(30, 23).astype("float32")
    result = runtime.predict_with_uncertainty(window, mc_samples=5)

    assert 0 <= result["risk_raw"] <= 1
    assert 0 <= result["risk_score"] <= 1
    assert result["risk_raw_std"] >= 0
    assert result["risk_std"] >= 0
    assert result["risk_score"] == pytest.approx(result["risk_raw"])
    assert result["risk_std"] == pytest.approx(result["risk_raw_std"])
    assert result["uncertainty_enabled"] is True
    assert result["uncertainty_method"] == "mc_dropout"
    assert result["mc_samples"] == 5
    assert result["calibration_enabled"] is False
    assert result["predicted_label"] in {0, 1}


def test_predict_with_uncertainty_with_calibration(tmp_path: Path) -> None:
    """启用校准时，risk_score 和 risk_std 应基于校准后概率空间。"""
    model_dir = make_calibrated_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.random.randn(30, 23).astype("float32")
    result = runtime.predict_with_uncertainty(window, mc_samples=5)

    assert 0 <= result["risk_raw"] <= 1
    assert 0 <= result["risk_score"] <= 1
    assert result["risk_raw_std"] >= 0
    assert result["risk_std"] >= 0
    assert result["calibration_enabled"] is True
    assert result["calibration_method"] == "isotonic_regression"
    assert result["uncertainty_enabled"] is True
    assert result["uncertainty_method"] == "mc_dropout"
    assert result["mc_samples"] == 5
    assert result["predicted_label"] in {0, 1}


def test_predict_with_uncertainty_rejects_bad_mc_samples(tmp_path: Path) -> None:
    """mc_samples 非正整数或 bool 时应报错。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")
    window = np.random.randn(30, 23).astype("float32")

    for bad_mc_samples in [0, -1, True, "30"]:
        with pytest.raises(ValueError, match="mc_samples"):
            runtime.predict_with_uncertainty(window, mc_samples=bad_mc_samples)


def test_predict_with_uncertainty_rejects_bad_window(tmp_path: Path) -> None:
    """predict_with_uncertainty 应复用窗口输入校验逻辑。"""
    model_dir = make_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    with pytest.raises(ValueError, match="shape mismatch"):
        runtime.predict_with_uncertainty(
            np.zeros((20, 23), dtype=np.float32),
            mc_samples=5,
        )

    bad_window = np.zeros((30, 23), dtype=np.float32)
    bad_window[0, 0] = np.nan

    with pytest.raises(ValueError, match="NaN or inf"):
        runtime.predict_with_uncertainty(bad_window, mc_samples=5)


def test_predict_proba_still_works_after_uncertainty_call(tmp_path: Path) -> None:
    """调用 MC-Dropout 后，确定性 predict_proba 仍应可用。"""
    model_dir = make_calibrated_model_dir(tmp_path)
    runtime = SequenceModelRuntime.from_model_dir(model_dir, device="cpu")

    window = np.random.randn(30, 23).astype("float32")

    uncertainty_result = runtime.predict_with_uncertainty(window, mc_samples=5)
    deterministic_result = runtime.predict_proba(window)

    assert uncertainty_result["uncertainty_enabled"] is True
    assert 0 <= deterministic_result["risk_raw"] <= 1
    assert 0 <= deterministic_result["risk_score"] <= 1
    assert deterministic_result["calibration_enabled"] is True
    assert deterministic_result["calibration_method"] == "isotonic_regression"
    assert runtime.model.training is False