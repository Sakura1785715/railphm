import numpy as np
import pytest
import torch

from app.training.dataset_loader import (
    WindowDataset,
    create_data_loaders,
    load_dataset_arrays,
)


def _write_toy_dataset(root_dir):
    splits_dir = root_dir / "splits"
    splits_dir.mkdir(parents=True)

    X = np.random.rand(12, 4, 3).astype(np.float32)
    y = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1], dtype=np.int64)
    train_indices = np.array([0, 1, 2, 3, 4, 5], dtype=np.int64)
    val_indices = np.array([6, 7, 8], dtype=np.int64)
    test_indices = np.array([9, 10, 11], dtype=np.int64)

    np.save(root_dir / "X.npy", X)
    np.save(root_dir / "y.npy", y)
    np.save(splits_dir / "train_indices.npy", train_indices)
    np.save(splits_dir / "val_indices.npy", val_indices)
    np.save(splits_dir / "test_indices.npy", test_indices)

    return {
        "X": X,
        "y": y,
        "train_indices": train_indices,
        "val_indices": val_indices,
        "test_indices": test_indices,
    }


def test_load_dataset_arrays_success(tmp_path):
    expected = _write_toy_dataset(tmp_path)

    arrays = load_dataset_arrays(tmp_path)

    assert arrays["X"].shape == expected["X"].shape
    assert arrays["y"].shape == expected["y"].shape
    assert len(arrays["train_indices"]) == 6
    assert len(arrays["val_indices"]) == 3
    assert len(arrays["test_indices"]) == 3


def test_window_dataset_flatten_true(tmp_path):
    arrays = _write_toy_dataset(tmp_path)
    dataset = WindowDataset(
        arrays["X"],
        arrays["y"],
        arrays["train_indices"],
        flatten=True,
    )

    feature, label = dataset[0]

    assert feature.shape == torch.Size([12])
    assert feature.dtype == torch.float32
    assert label.dtype == torch.float32
    assert label.ndim == 0


def test_window_dataset_flatten_false(tmp_path):
    arrays = _write_toy_dataset(tmp_path)
    dataset = WindowDataset(
        arrays["X"],
        arrays["y"],
        arrays["train_indices"],
        flatten=False,
    )

    feature, label = dataset[0]

    assert feature.shape == torch.Size([4, 3])
    assert feature.dtype == torch.float32
    assert label.dtype == torch.float32


def test_create_data_loaders_success(tmp_path):
    _write_toy_dataset(tmp_path)

    train_loader, val_loader, test_loader = create_data_loaders(
        tmp_path,
        batch_size=2,
        flatten=True,
        num_workers=0,
    )

    assert len(train_loader.dataset) == 6
    assert len(val_loader.dataset) == 3
    assert len(test_loader.dataset) == 3

    batch_X, batch_y = next(iter(train_loader))
    assert batch_X.shape == torch.Size([2, 12])
    assert batch_X.dtype == torch.float32
    assert batch_y.shape == torch.Size([2])
    assert batch_y.dtype == torch.float32


def test_missing_required_file(tmp_path):
    _write_toy_dataset(tmp_path)
    (tmp_path / "X.npy").unlink()

    with pytest.raises(FileNotFoundError, match="缺少数据集文件: X.npy"):
        load_dataset_arrays(tmp_path)


def test_missing_split_file(tmp_path):
    _write_toy_dataset(tmp_path)
    (tmp_path / "splits" / "train_indices.npy").unlink()

    with pytest.raises(FileNotFoundError, match="缺少数据集文件: splits/train_indices.npy"):
        load_dataset_arrays(tmp_path)


def test_x_y_sample_count_mismatch(tmp_path):
    _write_toy_dataset(tmp_path)
    X = np.random.rand(11, 4, 3).astype(np.float32)
    np.save(tmp_path / "X.npy", X)

    with pytest.raises(ValueError, match="X 与 y 的样本数不一致"):
        load_dataset_arrays(tmp_path)


def test_invalid_x_dimension(tmp_path):
    _write_toy_dataset(tmp_path)
    X = np.random.rand(12, 3).astype(np.float32)
    np.save(tmp_path / "X.npy", X)

    with pytest.raises(ValueError, match="X 必须为三维数组"):
        load_dataset_arrays(tmp_path)


def test_invalid_y_dimension(tmp_path):
    _write_toy_dataset(tmp_path)
    y = np.array([[0], [1], [0], [1], [0], [1], [0], [1], [0], [1], [0], [1]])
    np.save(tmp_path / "y.npy", y)

    with pytest.raises(ValueError, match="y 必须为一维数组"):
        load_dataset_arrays(tmp_path)


def test_indices_out_of_range(tmp_path):
    _write_toy_dataset(tmp_path)
    np.save(tmp_path / "splits" / "train_indices.npy", np.array([0, 1, 999], dtype=np.int64))

    with pytest.raises(ValueError, match="train_indices 存在越界索引"):
        load_dataset_arrays(tmp_path)


def test_invalid_label_values(tmp_path):
    _write_toy_dataset(tmp_path)
    y = np.array([0, 1, 2, 1, 0, 1, 0, 1, 0, 1, 0, -1], dtype=np.int64)
    np.save(tmp_path / "y.npy", y)

    with pytest.raises(ValueError, match="y 只能包含 0/1 标签"):
        load_dataset_arrays(tmp_path)


def test_nan_or_inf_in_x(tmp_path):
    _write_toy_dataset(tmp_path)
    X = np.random.rand(12, 4, 3).astype(np.float32)
    X[0, 0, 0] = np.nan
    np.save(tmp_path / "X.npy", X)

    with pytest.raises(ValueError, match="X 中存在 NaN 或 inf"):
        load_dataset_arrays(tmp_path)

    X[0, 0, 0] = np.inf
    np.save(tmp_path / "X.npy", X)

    with pytest.raises(ValueError, match="X 中存在 NaN 或 inf"):
        load_dataset_arrays(tmp_path)