"""
统一时序模型训练主流程。

本模块用于训练 LSTM / Bi-LSTM / LSTM+Attention / Bi-LSTM+Attention
四类时序故障风险预测模型。

"""

from __future__ import annotations

import json
import math
import random
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from app.models import build_sequence_model
from app.training.dataset_loader import WindowDataset, load_dataset_arrays
from app.training.metrics import compute_binary_metrics
from app.calibration import IsotonicRiskCalibrator

# 支持训练的模型
SUPPORTED_SEQUENCE_MODELS = {
    "lstm",
    "bilstm",
    "lstm_attention",
    "bilstm_attention",
}

# 定义评价指标
SUPPORTED_BEST_METRICS = {
    "val_f1",
    "val_auc",
    "val_loss", # 验证集上的二分类交叉熵损失
}


# 训练配置项
@dataclass
class SequenceTrainConfig:
    dataset_dir: Path # 窗口数据集目录：data/dataset
    output_dir: Path # 训练结果输出目录
    model: str = "bilstm_attention"
    epochs: int = 30
    batch_size: int = 256
    lr: float = 0.001
    seed: int = 42
    device: str = "auto"
    threshold: float = 0.5 # 风险概率转成 0/1 预测类别的阈值
    hidden_dim: int = 64 # 隐藏层维度，bi-lstm：64*2
    num_layers: int = 1
    dropout: float = 0.2
    num_workers: int = 0
    overwrite: bool = False
    best_metric: str = "val_auc"

# 主训练函数
def train_sequence_model(config: SequenceTrainConfig) -> Dict[str, Any]:
    """
    执行时序模型训练、验证、测试与结果保存。
    返回：
        sequence_model_report.json 对应的普通 Python dict。
    """
    # 校验配置是否合法
    _validate_config(config)
    # 设置随机种子
    set_random_seed(config.seed)

    dataset_dir = Path(config.dataset_dir)
    output_dir = Path(config.output_dir)
    # 训练设备 cuda->mps->cpu
    device = resolve_device(config.device)

    _prepare_output_dir(output_dir, overwrite=config.overwrite)

    # 加载窗口数据集
    arrays = load_dataset_arrays(dataset_dir)
    X = arrays["X"]
    y = arrays["y"]

    if X.ndim != 3:
        raise ValueError("X must be 3D: [num_samples, window_size, feature_dim]")

    window_size = int(X.shape[1])
    feature_dim = int(X.shape[2])
    # 输入bi-lstm的维度是每一个时间步的特征数量
    input_dim = feature_dim

    # 构建 Dataset
    train_dataset = WindowDataset(X, y, arrays["train_indices"], flatten=False)
    val_dataset = WindowDataset(X, y, arrays["val_indices"], flatten=False)
    test_dataset = WindowDataset(X, y, arrays["test_indices"], flatten=False)

    # 构建 DataLoader
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )

    # 创建模型
    model = build_sequence_model(
        model_name=config.model,
        input_dim=input_dim,
        hidden_dim=config.hidden_dim,
        num_layers=config.num_layers,
        dropout=config.dropout,
    ).to(device)

    # 定义损失函数和优化器
    criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)

    save_json(
        output_dir / "training_config.json", # 保存 training_config.json
        _config_to_json_dict(
            config=config,
            device=device,
            window_size=window_size,
            feature_dim=feature_dim,
            input_dim=input_dim,
            model_config=model.get_config(),
        ),
    )

    feature_columns_path = dataset_dir / "feature_columns.json"
    if not feature_columns_path.exists():
        raise FileNotFoundError(f"feature_columns.json 不存在: {feature_columns_path}")
    shutil.copy2(feature_columns_path, output_dir / "feature_columns.json")

    history: List[Dict[str, Any]] = []
    best_epoch = 0
    best_metric_value = None
    # 循环轮次训练
    for epoch in range(1, config.epochs + 1):
        """
        1. 训练一轮
        2. 在验证集上评估
        3. 判断是否保存最佳模型
        """
        train_loss = train_one_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion, # 损失函数
            optimizer=optimizer, # 优化器
            device=device,
        )

        val_metrics = evaluate_model(
            model=model,
            loader=val_loader,
            criterion=criterion,
            device=device,
            threshold=config.threshold,
        )

        current_metric_value = _get_selection_metric(
            val_metrics=val_metrics,
            best_metric=config.best_metric,
        )

        if _is_better_metric(
            current=current_metric_value,
            best=best_metric_value,
            best_metric=config.best_metric,
        ):
            best_epoch = epoch
            best_metric_value = current_metric_value
            _save_best_model(
                path=output_dir / "best_model.pt",
                model=model,
                epoch=epoch,
                best_metric=config.best_metric,
                best_metric_value=current_metric_value,
            )

        history_row = {
            "epoch": int(epoch),
            "train_loss": float(train_loss),
            "val_loss": float(val_metrics["loss"]),
            "val_accuracy": float(val_metrics["accuracy"]),
            "val_precision": float(val_metrics["precision"]),
            "val_recall": float(val_metrics["recall"]),
            "val_f1": float(val_metrics["f1"]),
            "val_auc": _to_optional_float(val_metrics["auc"]),
            "val_brier_score": float(val_metrics["brier_score"]),
        }
        history.append(history_row)

        val_auc_text = (
            f"{val_metrics['auc']:.4f}"
            if val_metrics["auc"] is not None
            else "None"
        )
        print(
            f"Epoch {epoch}/{config.epochs} | "
            f"train_loss={train_loss:.4f} | "
            f"val_loss={val_metrics['loss']:.4f} | "
            f"val_f1={val_metrics['f1']:.4f} | "
            f"val_auc={val_auc_text}"
        )

    best_model_path = output_dir / "best_model.pt"
    if not best_model_path.exists():
        raise RuntimeError("训练未能生成 best_model.pt，请检查训练集和验证集是否为空")

    checkpoint = torch.load(best_model_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    # ===== TEMP EXPERIMENT: evaluate on all samples without train/val/test split =====
    # 仅用于临时实验：把整个数据集一起输入 best_model 计算整体指标。
    # 实验结束后请删除本段，避免正式流程混淆 train/val/test 评价口径。
    all_indices = np.arange(int(y.shape[0]), dtype=np.int64)

    all_dataset = WindowDataset(
        X,
        y,
        all_indices,
        flatten=False,
    )

    all_loader = DataLoader(
        all_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )

    all_metrics = evaluate_model(
        model=model,
        loader=all_loader,
        criterion=criterion,
        device=device,
        threshold=config.threshold,
    )

    print("[TEMP EXPERIMENT] all_metrics:")
    print(json.dumps(_json_safe_metrics(all_metrics), ensure_ascii=False, indent=2))
    # ===== END TEMP EXPERIMENT =====
    train_metrics = evaluate_model(
        model=model,
        loader=train_loader,
        criterion=criterion,
        device=device,
        threshold=config.threshold,
    )
    val_metrics = evaluate_model(
        model=model,
        loader=val_loader,
        criterion=criterion,
        device=device,
        threshold=config.threshold,
    )
    test_metrics = evaluate_model(
        model=model,
        loader=test_loader,
        criterion=criterion,
        device=device,
        threshold=config.threshold,
    )

    # 使用 best_model 在验证集上收集原始概率，用于阈值搜索与概率校准
    val_predictions = collect_predictions(
        model=model,
        loader=val_loader,
        device=device,
        threshold=config.threshold,
    )

    # 基于验证集原始概率搜索最优二分类阈值
    threshold_summary = search_best_threshold(
        y_true=val_predictions["y_true"].to_numpy(),
        y_prob=val_predictions["y_prob"].to_numpy(),
        metric="f1",
        search_on="val",
    )
    best_threshold = float(threshold_summary["best_threshold"])

    # 使用验证集最佳阈值重新计算 train / val / test 指标
    train_metrics = evaluate_model(
        model=model,
        loader=train_loader,
        criterion=criterion,
        device=device,
        threshold=best_threshold,
    )

    val_metrics = evaluate_model(
        model=model,
        loader=val_loader,
        criterion=criterion,
        device=device,
        threshold=best_threshold,
    )

    test_metrics = evaluate_model(
        model=model,
        loader=test_loader,
        criterion=criterion,
        device=device,
        threshold=best_threshold,
    )

    # 重新生成带最佳阈值 y_pred 的验证集与测试集预测文件
    val_predictions = collect_predictions(
        model=model,
        loader=val_loader,
        device=device,
        threshold=best_threshold,
    )

    test_predictions = collect_predictions(
        model=model,
        loader=test_loader,
        device=device,
        threshold=best_threshold,
    )

    # 基于验证集拟合保序回归校准器，并保存 calibrator.pkl
    calibrator = IsotonicRiskCalibrator()
    val_y_true = val_predictions["y_true"].to_numpy()
    val_y_prob = val_predictions["y_prob"].to_numpy()
    calibrated_val_prob = calibrator.fit_transform(
        y_true=val_y_true,
        y_prob=val_y_prob,
    )
    calibrator.save(output_dir / "calibrator.pkl")
    calibration_summary = build_calibration_summary(
        y_true=val_y_true,
        y_prob=val_y_prob,
        calibrated_prob=calibrated_val_prob,
        threshold=best_threshold,
    )

    evaluation_summary = build_evaluation_summary(
        train_metrics=train_metrics,
        val_metrics=val_metrics,
        test_metrics=test_metrics,
        threshold_summary=threshold_summary,
        calibration_summary=calibration_summary,
    )
    save_metrics_history(output_dir / "metrics_history.csv", history)
    val_predictions.to_csv(output_dir / "val_predictions.csv", index=False)
    test_predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    save_json(output_dir / "threshold_summary.json", threshold_summary)
    save_json(output_dir / "calibration_summary.json", calibration_summary)
    save_json(output_dir / "evaluation_summary.json", evaluation_summary)

    report = {
        "task": "sequence_model_training",
        "model": model.get_config(),
        "dataset": {
            "dataset_dir": str(dataset_dir),
            "X_shape": [int(value) for value in X.shape],
            "y_shape": [int(value) for value in y.shape],
            "window_size": window_size,
            "feature_dim": feature_dim,
            "train_samples": int(len(train_dataset)),
            "val_samples": int(len(val_dataset)),
            "test_samples": int(len(test_dataset)),
        },
        "training": {
            "epochs": int(config.epochs),
            "batch_size": int(config.batch_size),
            "lr": float(config.lr),
            "seed": int(config.seed),
            "device": str(device),
            "threshold": float(best_threshold),
            "initial_threshold": float(config.threshold),
            "best_epoch": int(best_epoch),
            "best_metric": str(config.best_metric),
            "best_metric_value": _to_optional_float(best_metric_value),
        },
        "train_metrics": _json_safe_metrics(train_metrics),
        "val_metrics": _json_safe_metrics(val_metrics),
        "test_metrics": _json_safe_metrics(test_metrics),
        "artifacts": {
            "best_model": "best_model.pt",
            "metrics_history": "metrics_history.csv",
            "val_predictions": "val_predictions.csv",
            "test_predictions": "test_predictions.csv",
            "training_config": "training_config.json",
            "feature_columns": "feature_columns.json",
            "threshold_summary": "threshold_summary.json",
            "evaluation_summary": "evaluation_summary.json",
            "calibrator": "calibrator.pkl",
            "calibration_summary": "calibration_summary.json",
        },
        "notes": [ "Isotonic regression calibrator is fitted on validation predictions.",
                    "Best decision threshold is selected on validation split by F1.",
                    "MC-Dropout is configured at runtime through model_artifact_manifest.json.",
                    ],
    }

    save_json(output_dir / "sequence_model_report.json", report)

    return report


def set_random_seed(seed: int) -> None:
    """设置 Python、NumPy、PyTorch 随机种子。"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_device(device: str) -> torch.device:
    """
    解析训练设备。

    支持：
    - auto
    - cpu
    - cuda
    - mps
    """
    normalized_device = str(device).lower()

    if normalized_device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if _mps_available():
            return torch.device("mps")
        return torch.device("cpu")

    if normalized_device == "cpu":
        return torch.device("cpu")

    if normalized_device == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("指定 device=cuda，但当前环境不可用")
        return torch.device("cuda")

    if normalized_device == "mps":
        if not _mps_available():
            raise ValueError("指定 device=mps，但当前环境不可用")
        return torch.device("mps")

    raise ValueError("device 仅支持 auto、cpu、cuda、mps")


def train_one_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion,
    optimizer,
    device: torch.device,
) -> float:
    """
    训练一个 epoch，返回按样本数加权的平均 loss。
    """
    model.train() # 开启训练模式。Dropout生效

    total_loss = 0.0
    total_samples = 0

    for features, labels in loader:
        # 把输入数据移动到 CPU / GPU / MPS，并转成 float32
        features = features.to(device=device, dtype=torch.float32)  # features.shape = [batch_size, window_size, feature_dim]
        labels = labels.to(device=device, dtype=torch.float32).view(-1) # label.shape = [batch_size]

        optimizer.zero_grad() # 清空上一轮梯度
        logits = model(features).view(-1) # 模型前向传播
        loss = criterion(logits, labels) # 计算二分类损失
        loss.backward() # 反向传播，计算梯度
        optimizer.step() # 更新模型参数

        batch_size = int(labels.shape[0])
        total_loss += float(loss.detach().cpu().item()) * batch_size
        total_samples += batch_size

    if total_samples == 0:
        raise ValueError("训练集为空，无法训练时序模型")

    return float(total_loss / total_samples)


def evaluate_model(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion,
    device: torch.device,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """在指定 DataLoader 上评估模型，返回 loss 和二分类指标。"""
    # 评估。Dropout不再随机丢弃特征。
    model.eval()

    total_loss = 0.0
    total_samples = 0
    y_true_batches = []
    y_prob_batches = []

    # 关闭梯度计算，节省显存和计算量
    with torch.no_grad():
        for features, labels in loader:
            features = features.to(device=device, dtype=torch.float32)
            labels = labels.to(device=device, dtype=torch.float32).view(-1) 

            # # 得到原始输出
            logits = model(features).view(-1)
            loss = criterion(logits, labels)
            # 把 logit 转成风险概率
            probs = torch.sigmoid(logits)

            batch_size = int(labels.shape[0])
            total_loss += float(loss.detach().cpu().item()) * batch_size
            total_samples += batch_size

            # 收集所有 batch 的：y_true, y_prob
            y_true_batches.append(labels.detach().cpu())
            y_prob_batches.append(probs.detach().cpu())

    if total_samples == 0:
        raise ValueError("评估数据集为空，无法计算时序模型指标")

    y_true = torch.cat(y_true_batches).numpy()
    y_prob = torch.cat(y_prob_batches).numpy()

    # 计算评价指标
    metrics = compute_binary_metrics(
        y_true=y_true,
        y_prob=y_prob,
        threshold=threshold,
    )
    metrics["loss"] = float(total_loss / total_samples)

    return metrics


def collect_predictions(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    threshold: float = 0.5,
) -> pd.DataFrame:
    """
    收集测试集预测结果，用于保存 test_predictions.csv。

    当前 DataLoader 不返回 sample_id，因此使用 sample_order 表示测试集内部顺序。
    """
    model.eval()

    y_true_values = []
    y_prob_values = []

    with torch.no_grad():
        for features, labels in loader:
            features = features.to(device=device, dtype=torch.float32)
            logits = model(features).view(-1)
            probs = torch.sigmoid(logits)

            y_true_values.extend(labels.detach().cpu().numpy().tolist())
            y_prob_values.extend(probs.detach().cpu().numpy().tolist())

    y_prob_array = np.asarray(y_prob_values, dtype=np.float64)
    y_pred_array = (y_prob_array >= float(threshold)).astype(np.int64)

    return pd.DataFrame(
        {
            "sample_order": list(range(len(y_true_values))),
            "y_true": [int(value) for value in y_true_values],
            "y_prob": [float(value) for value in y_prob_array.tolist()],
            "y_pred": [int(value) for value in y_pred_array.tolist()],
        }
    )


def save_json(path: Path, data: Dict[str, Any]) -> None:
    """保存 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def save_metrics_history(path: Path, history: List[Dict[str, Any]]) -> None:
    """保存每个 epoch 的训练指标历史。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(history).to_csv(path, index=False)


def _validate_config(config: SequenceTrainConfig) -> None:
    if config.model not in SUPPORTED_SEQUENCE_MODELS:
        supported = ", ".join(sorted(SUPPORTED_SEQUENCE_MODELS))
        raise ValueError(f"model 仅支持: {supported}")

    if isinstance(config.epochs, bool) or not isinstance(config.epochs, int) or config.epochs <= 0:
        raise ValueError("epochs 必须为正整数")

    if (
        isinstance(config.batch_size, bool)
        or not isinstance(config.batch_size, int)
        or config.batch_size <= 0
    ):
        raise ValueError("batch_size 必须为正整数")

    if isinstance(config.lr, bool) or not isinstance(config.lr, (int, float)) or float(config.lr) <= 0:
        raise ValueError("lr 必须大于 0")

    if (
        isinstance(config.threshold, bool)
        or not isinstance(config.threshold, (int, float))
        or not 0 < float(config.threshold) < 1
    ):
        raise ValueError("threshold 必须位于 0 到 1 之间")

    if (
        isinstance(config.hidden_dim, bool)
        or not isinstance(config.hidden_dim, int)
        or config.hidden_dim <= 0
    ):
        raise ValueError("hidden_dim 必须为正整数")

    if (
        isinstance(config.num_layers, bool)
        or not isinstance(config.num_layers, int)
        or config.num_layers <= 0
    ):
        raise ValueError("num_layers 必须为正整数")

    if (
        isinstance(config.dropout, bool)
        or not isinstance(config.dropout, (int, float))
        or not math.isfinite(float(config.dropout))
        or float(config.dropout) < 0
        or float(config.dropout) >= 1
    ):
        raise ValueError("dropout 必须满足 0 <= dropout < 1")

    if (
        isinstance(config.num_workers, bool)
        or not isinstance(config.num_workers, int)
        or config.num_workers < 0
    ):
        raise ValueError("num_workers 必须为非负整数")

    if config.best_metric not in SUPPORTED_BEST_METRICS:
        supported = ", ".join(sorted(SUPPORTED_BEST_METRICS))
        raise ValueError(f"best_metric 仅支持: {supported}")

    if str(config.device).lower() not in {"auto", "cpu", "cuda", "mps"}:
        raise ValueError("device 仅支持 auto、cpu、cuda、mps")


def _prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"输出目录已存在: {output_dir}，如需覆盖请使用 --overwrite")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)


def _save_best_model(
    path: Path,
    model: torch.nn.Module,
    epoch: int,
    best_metric: str,
    best_metric_value: float,
) -> None:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_config": model.get_config(),
            "epoch": int(epoch),
            "best_metric": str(best_metric),
            "best_metric_value": float(best_metric_value),
        },
        path,
    )


def _get_selection_metric(val_metrics: Dict[str, Any], best_metric: str) -> float:
    if best_metric == "val_loss":
        return float(val_metrics["loss"])

    if best_metric == "val_auc":
        if val_metrics.get("auc") is not None:
            return float(val_metrics["auc"])
        return float(val_metrics["f1"])

    return float(val_metrics["f1"])


def _is_better_metric(current: float, best: float | None, best_metric: str) -> bool:
    if best is None:
        return True

    if best_metric == "val_loss":
        return current < best

    return current > best


def _json_safe_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    result = {}

    for key, value in metrics.items():
        if key == "confusion_matrix":
            result[key] = {name: int(count) for name, count in value.items()}
        elif key == "warnings":
            result[key] = [str(item) for item in value]
        elif value is None:
            result[key] = None
        elif isinstance(value, np.integer):
            result[key] = int(value)
        elif isinstance(value, np.floating):
            result[key] = float(value)
        elif isinstance(value, (int, float, str, bool)):
            result[key] = value
        else:
            result[key] = value

    return result


def _config_to_json_dict(
    config: SequenceTrainConfig,
    device: torch.device,
    window_size: int,
    feature_dim: int,
    input_dim: int,
    model_config: dict,
) -> Dict[str, Any]:
    data = asdict(config)
    data["dataset_dir"] = str(config.dataset_dir)
    data["output_dir"] = str(config.output_dir)
    data["resolved_device"] = str(device)
    data["window_size"] = int(window_size)
    data["feature_dim"] = int(feature_dim)
    data["input_dim"] = int(input_dim)
    data["model_config"] = model_config
    return data


def search_best_threshold(
    y_true: Any,
    y_prob: Any,
    metric: str = "f1",
    search_on: str = "val",
) -> Dict[str, Any]:
    """
    在验证集预测概率上搜索最优二分类阈值。

    当前默认按 F1 最大选择阈值。若多个阈值 F1 相同，保留先遇到的阈值。
    """
    y_true_array = np.asarray(y_true, dtype=np.int64)
    y_prob_array = np.asarray(y_prob, dtype=np.float64)

    if y_true_array.ndim != 1:
        raise ValueError("y_true must be 1D")
    if y_prob_array.ndim != 1:
        raise ValueError("y_prob must be 1D")
    if y_true_array.shape[0] != y_prob_array.shape[0]:
        raise ValueError("y_true and y_prob must have the same length")
    if y_true_array.shape[0] == 0:
        raise ValueError("validation predictions must not be empty")
    if not np.isin(y_true_array, [0, 1]).all():
        raise ValueError("y_true must contain only 0/1 labels")
    if not np.isfinite(y_prob_array).all():
        raise ValueError("y_prob must contain only finite values")
    if (y_prob_array < 0).any() or (y_prob_array > 1).any():
        raise ValueError("y_prob must be within [0, 1]")

    if metric != "f1":
        raise ValueError("当前阈值搜索仅支持 metric='f1'")

    candidate_thresholds = np.unique(
        np.concatenate(
            [
                np.linspace(0.01, 0.99, 99, dtype=np.float64),
                y_prob_array,
            ]
        )
    )

    best_threshold = 0.5
    best_metric_value = -1.0
    best_metrics: Dict[str, Any] | None = None

    for threshold in candidate_thresholds:
        metrics = compute_binary_metrics(
            y_true=y_true_array,
            y_prob=y_prob_array,
            threshold=float(threshold),
        )
        current_value = float(metrics["f1"])

        if current_value > best_metric_value:
            best_metric_value = current_value
            best_threshold = float(threshold)
            best_metrics = metrics

    if best_metrics is None:
        raise RuntimeError("failed to search best threshold")

    return {
        "best_threshold": float(best_threshold),
        "best_val_threshold": float(best_threshold),
        "search_on": str(search_on),
        "metric": str(metric),
        "best_metric_value": float(best_metric_value),
        "candidate_count": int(candidate_thresholds.shape[0]),
        "metrics_at_best_threshold": _json_safe_metrics(best_metrics),
        "notes": [
            "Threshold is selected on validation predictions.",
            "The selected threshold is used for final train/val/test binary metrics and runtime predicted_label.",
        ],
    }


def build_calibration_summary(
    y_true: Any,
    y_prob: Any,
    calibrated_prob: Any,
    threshold: float,
) -> Dict[str, Any]:
    """
    构建保序回归校准摘要。
    """
    y_true_array = np.asarray(y_true, dtype=np.int64)
    y_prob_array = np.asarray(y_prob, dtype=np.float64)
    calibrated_array = np.asarray(calibrated_prob, dtype=np.float64)

    if y_true_array.shape[0] != y_prob_array.shape[0]:
        raise ValueError("y_true and y_prob must have the same length")
    if y_prob_array.shape[0] != calibrated_array.shape[0]:
        raise ValueError("y_prob and calibrated_prob must have the same length")

    raw_metrics = compute_binary_metrics(
        y_true=y_true_array,
        y_prob=y_prob_array,
        threshold=threshold,
    )
    calibrated_metrics = compute_binary_metrics(
        y_true=y_true_array,
        y_prob=calibrated_array,
        threshold=threshold,
    )

    return {
        "enabled": True,
        "method": "isotonic_regression",
        "fit_split": "val",
        "input_probability": "y_prob",
        "output_probability": "calibrated_y_prob",
        "calibrator_file": "calibrator.pkl",
        "sample_count": int(y_true_array.shape[0]),
        "threshold": float(threshold),
        "raw_metrics": _json_safe_metrics(raw_metrics),
        "calibrated_metrics": _json_safe_metrics(calibrated_metrics),
        "brier_score_before": float(raw_metrics["brier_score"]),
        "brier_score_after": float(calibrated_metrics["brier_score"]),
        "notes": [
            "The calibrator is fitted on validation split predictions only.",
            "The calibrator maps raw sigmoid probabilities to calibrated risk probabilities.",
        ],
    }


def build_evaluation_summary(
    train_metrics: Dict[str, Any],
    val_metrics: Dict[str, Any],
    test_metrics: Dict[str, Any],
    threshold_summary: Dict[str, Any],
    calibration_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构建模型最终评估摘要。
    """
    return {
        "task": "sequence_model_evaluation",
        "threshold": {
            "best_threshold": float(threshold_summary["best_threshold"]),
            "search_on": threshold_summary.get("search_on", "val"),
            "metric": threshold_summary.get("metric", "f1"),
            "best_metric_value": threshold_summary.get("best_metric_value"),
        },
        "metrics": {
            "train": _json_safe_metrics(train_metrics),
            "val": _json_safe_metrics(val_metrics),
            "test": _json_safe_metrics(test_metrics),
        },
        "calibration": {
            "enabled": True,
            "method": "isotonic_regression",
            "summary_file": "calibration_summary.json",
            "calibrator_file": "calibrator.pkl",
            "brier_score_before": calibration_summary.get("brier_score_before"),
            "brier_score_after": calibration_summary.get("brier_score_after"),
        },
        "artifacts": {
            "threshold_summary": "threshold_summary.json",
            "calibration_summary": "calibration_summary.json",
            "calibrator": "calibrator.pkl",
            "val_predictions": "val_predictions.csv",
            "test_predictions": "test_predictions.csv",
        },
    }

def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _mps_available() -> bool:
    return bool(
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    )