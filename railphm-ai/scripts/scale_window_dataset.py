"""
读取已经完成 train / val / test 划分的窗口数据集，
只用训练集样本计算每个特征的 mean / std
再用这组训练集统计量对完整 X.npy 做 z-score 标准化，
最后生成一个新的标准化数据集目录。
python scripts/scale_window_dataset.py \
  --input-dir data/datasets/bilstm_attention_h1_full_features/raw_window_w30_s1_h1 \
  --output-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1 \
  --overwrite \
  --delete-input-after-success
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# 读取 JSON 文件
def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

# 保存 JSON 文件
def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 创建标准化后的数据集目录
def prepare_output_dir(output_dir: Path, overwrite: bool):
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"输出目录已存在: {output_dir}，如需覆盖请使用 --overwrite")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "splits").mkdir(parents=True, exist_ok=True)

# 校验输入数据集是否完整
def validate_dataset_dir(dataset_dir: Path):
    # 输入数据集必须具备的文件
    required_files = [
        dataset_dir / "X.npy", # 读取 X.npy，对 X 做标准化
        dataset_dir / "y.npy",
        dataset_dir / "feature_columns.json",
        dataset_dir / "window_manifest.csv",
        dataset_dir / "dataset_summary.json",
        dataset_dir / "splits" / "train_indices.npy", # 标准化参数只能从训练集样本中计算
        dataset_dir / "splits" / "val_indices.npy",
        dataset_dir / "splits" / "test_indices.npy",
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(f"缺少必要文件: {path}")

# 训练集计算标准化参数
def fit_standard_scaler(X: np.ndarray, train_indices: np.ndarray):
    """
    只使用训练集样本统计每个 feature 的 mean/std。

    X shape:
    [num_samples, window_size, feature_dim]

    对 train 样本的所有时间步一起统计：
    train_X.reshape(-1, feature_dim)
    """
    train_X = X[train_indices]
    train_flat = train_X.reshape(-1, X.shape[2]).astype(np.float64)

    mean = train_flat.mean(axis=0)
    std = train_flat.std(axis=0)

    # 避免除 0。常数特征缩放后置为 0。
    safe_std = np.where(std == 0, 1.0, std)

    return mean, std, safe_std


# 分块标准化完整 X.npy数据集
def transform_in_chunks(
    X: np.ndarray,
    mean: np.ndarray,
    safe_std: np.ndarray,
    chunk_size: int,
) -> np.ndarray:
    # 分块 transform，降低峰值内存。
    X_scaled = np.empty_like(X, dtype=np.float32)
    total = X.shape[0]

    for start in range(0, total, chunk_size):
        end = min(start + chunk_size, total)
        chunk = X[start:end].astype(np.float32, copy=False)
        # 标准化公式：X_scaled = (X - mean) / std
        X_scaled[start:end] = ((chunk - mean.reshape(1, 1, -1)) / safe_std.reshape(1, 1, -1)).astype(np.float32)

    return X_scaled

# 复制不需要改变的文件
def copy_required_metadata(input_dir: Path, output_dir: Path):
    for filename in [
        # 复制这三个文件：
        "y.npy", # 标签没变
        "feature_columns.json", # 特征列顺序没变
        "window_manifest.csv", # 样本追溯信息没变
    ]:
        shutil.copy2(input_dir / filename, output_dir / filename)

    for filename in [
        # 复制划分文件
        "train_indices.npy",
        "val_indices.npy",
        "test_indices.npy",
        "split_summary.json",
    ]:
        src = input_dir / "splits" / filename
        if src.exists():
            shutil.copy2(src, output_dir / "splits" / filename)

def _is_relative_to(child: Path, parent: Path) -> bool:
    """
    判断 child 是否位于 parent 目录内部。
    """
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False

def validate_delete_input_paths(input_dir: Path, output_dir: Path) -> None:
    """
    校验删除 input_dir 是否安全。
    只允许在 input_dir 和 output_dir 完全独立时删除 input_dir。
    防止 output_dir 位于 input_dir 内部，删除 input_dir 连同新数据集一起删除。
    """
    input_resolved = input_dir.resolve()
    output_resolved = output_dir.resolve()

    if input_resolved == output_resolved:
        raise ValueError("启用 --delete-input-after-success 时，input-dir 不能与 output-dir 相同")

    if _is_relative_to(output_resolved, input_resolved):
        raise ValueError(
            "启用 --delete-input-after-success 时，output-dir 不能位于 input-dir 内部，"
            "否则删除 input-dir 会连同新生成的数据集一起删除"
        )
    
def delete_input_dir_after_success(input_dir: Path) -> None:
    """
    标准化数据集成功生成后删除输入目录。
    """
    if not input_dir.exists():
        return

    if not input_dir.is_dir():
        raise NotADirectoryError(f"input_dir 不是目录，无法删除: {input_dir}")

    shutil.rmtree(input_dir)

def main():
    parser = argparse.ArgumentParser()
    # 参数1: 输入目录
    parser.add_argument("--input-dir", type=Path, required=True, help="未做 segment 内 min-max 的 raw window dataset")
    # 参数 2：输出目录
    parser.add_argument("--output-dir", type=Path, required=True, help="缩放后的新数据集目录")
    # 参数 3：标准化方法
    parser.add_argument("--method", type=str, default="standard", choices=["standard"], help="当前仅支持 standard")
    # 参数 4：分块大小
    parser.add_argument("--chunk-size", type=int, default=20000, help="分块 transform 的样本数")
    # 参数 5：覆盖输出目录
    parser.add_argument("--overwrite", action="store_true")
    # 删除旧文件
    parser.add_argument(
        "--delete-input-after-success",
        action="store_true",
        help="标准化数据集成功生成后删除 input-dir，用于清理中间数据目录",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir

    if args.delete_input_after_success:
        validate_delete_input_paths(input_dir, output_dir)

    validate_dataset_dir(input_dir)
    prepare_output_dir(output_dir, overwrite=args.overwrite)

    print(f"Loading dataset from: {input_dir}")
    X = np.load(input_dir / "X.npy")
    y = np.load(input_dir / "y.npy")
    train_indices = np.load(input_dir / "splits" / "train_indices.npy")
    val_indices = np.load(input_dir / "splits" / "val_indices.npy")
    test_indices = np.load(input_dir / "splits" / "test_indices.npy")
    feature_columns = load_json(input_dir / "feature_columns.json")
    old_summary = load_json(input_dir / "dataset_summary.json")

    if X.ndim != 3:
        raise ValueError("X 必须为三维数组 [num_samples, window_size, feature_dim]")

    if y.ndim != 1:
        raise ValueError("y 必须为一维数组")

    if X.shape[0] != y.shape[0]:
        raise ValueError("X 与 y 样本数不一致")

    if X.shape[2] != len(feature_columns):
        raise ValueError("X feature_dim 与 feature_columns 数量不一致")

    print("Fitting scaler on train split only...")
    # 拟合标准化参数
    mean, std, safe_std = fit_standard_scaler(X, train_indices)

    print("Transforming full X with train-fitted scaler...")
    # 标准化完整 X
    X_scaled = transform_in_chunks(
        X=X,
        mean=mean,
        safe_std=safe_std,
        chunk_size=args.chunk_size,
    )

    if not np.isfinite(X_scaled).all():
        raise ValueError("缩放后的 X 存在 NaN 或 inf")

    print(f"Saving scaled X to: {output_dir / 'X.npy'}")
    # 保存新的 X.npy
    np.save(output_dir / "X.npy", X_scaled)

    copy_required_metadata(input_dir, output_dir)

    scaler_summary = {
        "method": args.method,
        "fit_scope": "train_split_only",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "X_shape": [int(v) for v in X.shape],
        "feature_columns": feature_columns,
        "mean": [float(v) for v in mean.tolist()],
        "std": [float(v) for v in std.tolist()],
        "safe_std": [float(v) for v in safe_std.tolist()],
        "zero_std_feature_indices": [int(i) for i in np.flatnonzero(std == 0).tolist()],
        "zero_std_feature_columns": [
            feature_columns[int(i)] for i in np.flatnonzero(std == 0).tolist()
        ],
        "train_samples": int(len(train_indices)),
        "val_samples": int(len(val_indices)),
        "test_samples": int(len(test_indices)),
        "notes": [
            "Scaler is fitted only on train_indices to avoid validation/test leakage.",
            "All splits are transformed using the same train-fitted statistics.",
        ],
    }

    save_json(output_dir / "scaler_summary.json", scaler_summary)

    new_summary = dict(old_summary)
    new_summary["scaling"] = {
        "method": args.method,
        "fit_scope": "train_split_only",
        "scaler_summary": "scaler_summary.json",
        "source_dataset_dir": str(input_dir),
    }
    new_summary["X_shape"] = [int(v) for v in X_scaled.shape]
    new_summary["y_shape"] = [int(v) for v in y.shape]
    new_summary["feature_dim"] = int(X_scaled.shape[2])

    save_json(output_dir / "dataset_summary.json", new_summary)

    print("Scaled dataset created successfully.")
    print(f"output_dir: {output_dir}")
    print(f"X_shape: {X_scaled.shape}")
    print(f"train_samples: {len(train_indices)}")
    print(f"val_samples: {len(val_indices)}")
    print(f"test_samples: {len(test_indices)}")

    if args.delete_input_after_success:
        print(f"Deleting input dataset directory: {input_dir}")
        delete_input_dir_after_success(input_dir)
        print("Input dataset directory deleted successfully.")


if __name__ == "__main__":
    main()