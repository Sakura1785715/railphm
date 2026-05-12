"""
MLP baseline 训练主流程。

1. 读取窗口数据集 X.npy、y.npy 和 train/val/test indices。
2. 构造 PyTorch DataLoader。
3. 自动推断 input_dim = window_size * feature_dim。
4. 创建 BaselineMLP。
5. 使用 BCEWithLogitsLoss 训练二分类模型。
6. 每个 epoch 记录 train_loss、val_loss 和验证集指标。
7. 根据验证集指标保存 best_model.pt。
8. 训练结束后加载最佳模型，在 train/val/test 上评估。
9. 输出 baseline_report.json、metrics_history.csv、training_config.json、test_predictions.csv。

- 本模块不实现 LSTM、Bi-LSTM、Attention、工况划分、概率校准或 MC-Dropout。
- 本模块不接入 /infer 真实推理。
"""

from __future__ import annotations

import json
import random
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from app.models import BaselineMLP
from app.training.dataset_loader import WindowDataset, load_dataset_arrays
from app.training.metrics import compute_binary_metrics


@dataclass
class BaselineTrainConfig:
    dataset_dir: Path
    output_dir: Path
    model: str = "mlp"
    epochs: int = 10
    batch_size: int = 256
    lr: float = 0.001
    seed: int = 42
    device: str = "auto"
    threshold: float = 0.5
    hidden_dims: Tuple[int, ...] = (128, 64)
    dropout: float = 0.2
    num_workers: int = 0
    overwrite: bool = False
    best_metric: str = "val_f1"


def train_baseline(config: BaselineTrainConfig) -> Dict[str, Any]:
    """
    执行 MLP baseline 训练、验证、测试与结果保存。

    返回：
        baseline_report.json 对应的普通 Python dict。
    """
    _validate_config(config)
    set_random_seed(config.seed)

    dataset_dir = Path(config.dataset_dir)
    output_dir = Path(config.output_dir)
    device = resolve_device(config.device)

    _prepare_output_dir(output_dir, overwrite=config.overwrite)

    arrays = load_dataset_arrays(dataset_dir)
    X = arrays["X"]
    y = arrays["y"]

    window_size = int(X.shape[1])
    feature_dim = int(X.shape[2])
    input_dim = int(window_size * feature_dim)

    train_dataset = WindowDataset(X, y, arrays["train_indices"], flatten=True)
    val_dataset = WindowDataset(X, y, arrays["val_indices"], flatten=True)
    test_dataset = WindowDataset(X, y, arrays["test_indices"], flatten=True)

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

    model = BaselineMLP(
        input_dim=input_dim,
        hidden_dims=config.hidden_dims,
        dropout=config.dropout,
    ).to(device)

    criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)

    save_json(output_dir / "training_config.json", _config_to_json_dict(config, device=device))

    history: List[Dict[str, Any]] = []
    best_epoch = 0
    best_metric_value = None

    for epoch in range(1, config.epochs + 1):
        train_loss = train_one_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            optimizer=optimizer,
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

    test_predictions = collect_predictions(
        model=model,
        loader=test_loader,
        device=device,
        threshold=config.threshold,
    )

    save_metrics_history(output_dir / "metrics_history.csv", history)
    test_predictions.to_csv(output_dir / "test_predictions.csv", index=False)

    report = {
        "task": "baseline_trainability_check",
        "model": model.get_config(),
        "dataset": {
            "dataset_dir": str(dataset_dir),
            "X_shape": [int(value) for value in X.shape],
            "y_shape": [int(value) for value in y.shape],
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
            "threshold": float(config.threshold),
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
            "test_predictions": "test_predictions.csv",
            "training_config": "training_config.json",
        },
        "notes": [],
    }

    save_json(output_dir / "baseline_report.json", report)

    return report


def set_random_seed(seed: int) -> None:
    """
    设置 Python、NumPy、PyTorch 随机种子。
    """
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
    model.train()

    total_loss = 0.0
    total_samples = 0

    for features, labels in loader:
        features = features.to(device=device, dtype=torch.float32)
        labels = labels.to(device=device, dtype=torch.float32).view(-1)

        optimizer.zero_grad()
        logits = model(features).view(-1)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()

        batch_size = int(labels.shape[0])
        total_loss += float(loss.detach().cpu().item()) * batch_size
        total_samples += batch_size

    if total_samples == 0:
        raise ValueError("训练集为空，无法训练 baseline 模型")

    return float(total_loss / total_samples)


def evaluate_model(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion,
    device: torch.device,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    在指定 DataLoader 上评估模型，返回 loss 和二分类指标。
    """
    model.eval()

    total_loss = 0.0
    total_samples = 0
    y_true_batches = []
    y_prob_batches = []

    with torch.no_grad():
        for features, labels in loader:
            features = features.to(device=device, dtype=torch.float32)
            labels = labels.to(device=device, dtype=torch.float32).view(-1)

            logits = model(features).view(-1)
            loss = criterion(logits, labels)
            probs = torch.sigmoid(logits)

            batch_size = int(labels.shape[0])
            total_loss += float(loss.detach().cpu().item()) * batch_size
            total_samples += batch_size

            y_true_batches.append(labels.detach().cpu())
            y_prob_batches.append(probs.detach().cpu())

    if total_samples == 0:
        raise ValueError("评估数据集为空，无法计算 baseline 指标")

    y_true = torch.cat(y_true_batches).numpy()
    y_prob = torch.cat(y_prob_batches).numpy()

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
    """
    保存 JSON 文件。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def save_metrics_history(path: Path, history: List[Dict[str, Any]]) -> None:
    """
    保存每个 epoch 的训练指标历史。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(history).to_csv(path, index=False)


def _validate_config(config: BaselineTrainConfig) -> None:
    if config.model != "mlp":
        raise ValueError("当前 baseline 训练仅支持 model='mlp'")

    if isinstance(config.epochs, bool) or not isinstance(config.epochs, int) or config.epochs <= 0:
        raise ValueError("epochs 必须为正整数")

    if isinstance(config.batch_size, bool) or not isinstance(config.batch_size, int) or config.batch_size <= 0:
        raise ValueError("batch_size 必须为正整数")

    if not isinstance(config.lr, (int, float)) or isinstance(config.lr, bool) or float(config.lr) <= 0:
        raise ValueError("lr 必须大于 0")

    if (
        not isinstance(config.threshold, (int, float))
        or isinstance(config.threshold, bool)
        or not 0 < float(config.threshold) < 1
    ):
        raise ValueError("threshold 必须位于 0 到 1 之间")

    if isinstance(config.num_workers, bool) or not isinstance(config.num_workers, int) or config.num_workers < 0:
        raise ValueError("num_workers 必须为非负整数")

    if config.best_metric not in {"val_f1", "val_auc", "val_loss"}:
        raise ValueError("best_metric 仅支持 val_f1、val_auc、val_loss")


def _prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"输出目录已存在: {output_dir}，如需覆盖请使用 --overwrite")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)


def _save_best_model(
    path: Path,
    model: BaselineMLP,
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
        elif isinstance(value, (np.integer,)):
            result[key] = int(value)
        elif isinstance(value, (np.floating,)):
            result[key] = float(value)
        elif isinstance(value, (int, float, str, bool)):
            result[key] = value
        else:
            result[key] = value

    return result


def _config_to_json_dict(config: BaselineTrainConfig, device: torch.device) -> Dict[str, Any]:
    data = asdict(config)
    data["dataset_dir"] = str(config.dataset_dir)
    data["output_dir"] = str(config.output_dir)
    data["hidden_dims"] = [int(value) for value in config.hidden_dims]
    data["resolved_device"] = str(device)
    return data


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _mps_available() -> bool:
    return bool(
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    )