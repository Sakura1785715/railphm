"""
实现 WindowDataset、load_dataset_arrays、create_data_loaders，
负责读取窗口数据集、校验数组合法性，并生成 PyTorch DataLoader。
"""
from pathlib import Path
from typing import Dict, Union

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset


ArrayDict = Dict[str, np.ndarray]
PathLike = Union[str, Path]


class WindowDataset(Dataset):
    """
    ATP 窗口样本数据集。

    X: [num_samples, window_size, feature_dim]
    y: [num_samples]
    indices: 当前数据集使用的样本下标
    """

    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
        indices: np.ndarray,
        flatten: bool = True,
    ) -> None:
        self.X = np.asarray(X)
        self.y = np.asarray(y)
        self.indices = np.asarray(indices)
        self.flatten = flatten

        self._validate_arrays()

    def __len__(self) -> int:
        return int(len(self.indices))

    def __getitem__(self, item: int):
        sample_index = int(self.indices[item])
        feature = self.X[sample_index]

        if self.flatten:
            feature = feature.reshape(-1)

        feature_tensor = torch.as_tensor(feature, dtype=torch.float32)
        label_tensor = torch.as_tensor(self.y[sample_index], dtype=torch.float32)
        return feature_tensor, label_tensor

    def _validate_arrays(self) -> None:
        if self.X.ndim != 3:
            raise ValueError("X 必须为三维数组 [num_samples, window_size, feature_dim]")

        if self.y.ndim != 1:
            raise ValueError("y 必须为一维数组 [num_samples]")

        if self.X.shape[0] != self.y.shape[0]:
            raise ValueError("X 与 y 的样本数不一致")

        _validate_indices(self.indices, self.X.shape[0], split_name="indices")


def load_dataset_arrays(dataset_dir: PathLike) -> ArrayDict:
    """
    从窗口数据集目录读取 X/y 和 train/val/test split indices。
    """
    root_dir = Path(dataset_dir)

    if not root_dir.exists():
        raise FileNotFoundError(f"数据集目录不存在: {root_dir}")

    if not root_dir.is_dir():
        raise NotADirectoryError(f"dataset_dir 必须是目录: {root_dir}")

    required_files = {
        "X": root_dir / "X.npy",
        "y": root_dir / "y.npy",
        "train_indices": root_dir / "splits" / "train_indices.npy",
        "val_indices": root_dir / "splits" / "val_indices.npy",
        "test_indices": root_dir / "splits" / "test_indices.npy",
    }

    for file_path in required_files.values():
        if not file_path.exists():
            relative_path = file_path.relative_to(root_dir)
            raise FileNotFoundError(f"缺少数据集文件: {relative_path}")

    X = np.load(required_files["X"], allow_pickle=False)
    y = np.load(required_files["y"], allow_pickle=False)
    train_indices = np.load(required_files["train_indices"], allow_pickle=False)
    val_indices = np.load(required_files["val_indices"], allow_pickle=False)
    test_indices = np.load(required_files["test_indices"], allow_pickle=False)

    _validate_X_y(X, y)
    _validate_indices(train_indices, X.shape[0], split_name="train_indices")
    _validate_indices(val_indices, X.shape[0], split_name="val_indices")
    _validate_indices(test_indices, X.shape[0], split_name="test_indices")

    return {
        "X": X,
        "y": y,
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
    }


def create_data_loaders(
    dataset_dir: PathLike,
    batch_size: int = 256,
    flatten: bool = True,
    num_workers: int = 0,
):
    """
    创建 baseline 训练可用的 train/val/test DataLoader。
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size 必须为正整数")

    if isinstance(num_workers, bool) or not isinstance(num_workers, int) or num_workers < 0:
        raise ValueError("num_workers 必须为非负整数")

    arrays = load_dataset_arrays(dataset_dir)
    X = arrays["X"]
    y = arrays["y"]

    train_dataset = WindowDataset(X, y, arrays["train_indices"], flatten=flatten)
    val_dataset = WindowDataset(X, y, arrays["val_indices"], flatten=flatten)
    test_dataset = WindowDataset(X, y, arrays["test_indices"], flatten=flatten)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )

    return train_loader, val_loader, test_loader


def _validate_X_y(X: np.ndarray, y: np.ndarray) -> None:
    if X.ndim != 3:
        raise ValueError("X 必须为三维数组 [num_samples, window_size, feature_dim]")

    if y.ndim != 1:
        raise ValueError("y 必须为一维数组 [num_samples]")

    if X.shape[0] != y.shape[0]:
        raise ValueError("X 与 y 的样本数不一致")

    if not np.isfinite(X).all():
        raise ValueError("X 中存在 NaN 或 inf")

    if np.issubdtype(y.dtype, np.floating) and np.isnan(y).any():
        raise ValueError("y 中存在 NaN")

    unique_labels = np.unique(y)
    if not np.isin(unique_labels, [0, 1]).all():
        raise ValueError("y 只能包含 0/1 标签")


def _validate_indices(indices: np.ndarray, sample_count: int, split_name: str) -> None:
    if indices.ndim != 1:
        raise ValueError(f"{split_name} 必须为一维数组")

    if not np.issubdtype(indices.dtype, np.integer):
        raise ValueError(f"{split_name} 必须为整数索引数组")

    if indices.size == 0:
        return

    if indices.min() < 0 or indices.max() >= sample_count:
        raise ValueError(f"{split_name} 存在越界索引")