"""
把已经构建好的窗口数据集划分成训练集、验证集、测试集
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# 划分训练集、验证集、测试集。保存一次数据集划分后的结果
@dataclass
class DatasetSplitResult:
    """
    数据集划分结果。
    train_indices / val_indices / test_indices:
        对应 X.npy / y.npy 第一维的样本索引。
    summary:
        划分统计信息，会同时写入 split_summary.json。
    """
    train_indices: np.ndarray
    val_indices: np.ndarray
    test_indices: np.ndarray
    # summary 保存划分统计信息
    summary: dict[str, Any] 


class DatasetSplitBuilder:
    """
    RailPHM 数据集划分器。 
    根据 window_manifest.csv 里的 segment_id
    """
    def split(
        self,
        dataset_dir: Path, # 已经构建好的窗口数据集目录，里面应该有 y.npy 和 window_manifest.csv
        output_dir: Path | None = None, # 划分结果输出目录。如果不传，默认是 dataset_dir / "splits"。
        # 划分比例
        train_ratio: float = 0.7, # 训练集 segment 比例，默认 0.7。
        val_ratio: float = 0.15, #  验证集 segment 比例，默认 0.15。
        test_ratio: float = 0.15, # 测试集 segment 比例，默认 0.15。
        seed: int = 42, # 随机种子，默认 42。用于保证每次划分结果可复现。
        overwrite: bool = False, # 如果输出目录已经存在，是否覆盖。
    ) -> DatasetSplitResult:
        dataset_dir = Path(dataset_dir)
        output_dir = Path(output_dir) if output_dir is not None else dataset_dir / "splits"

        self._validate_ratios(train_ratio, val_ratio, test_ratio)
        self._validate_dataset_dir(dataset_dir)
        self._prepare_output_dir(output_dir, overwrite=overwrite)

        y = np.load(dataset_dir / "y.npy")
        # 读取窗口追溯文件
        manifest = pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig")

        if "segment_id" not in manifest.columns:
            raise ValueError("window_manifest.csv 缺少 segment_id，无法按 segment 划分")

        if len(manifest) != y.shape[0]:
            raise ValueError(
                f"manifest 行数与 y 样本数不一致: manifest={len(manifest)}, y={y.shape[0]}"
            )

        # 从 manifest 中提取所有有效的 segment_id
        segment_ids = sorted(manifest["segment_id"].dropna().unique().tolist()) 
        if not segment_ids:
            raise ValueError("manifest 中没有有效 segment_id")
        
        # 调用 _split_segments()，把所有 segment_id 分成三组：
        train_segments, val_segments, test_segments = self._split_segments(
            segment_ids=segment_ids,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            seed=seed,
        )

        train_indices = self._indices_for_segments(manifest, train_segments)
        val_indices = self._indices_for_segments(manifest, val_segments)
        test_indices = self._indices_for_segments(manifest, test_segments)

        # 检查三个索引集合是否完整覆盖全部样本
        self._validate_index_coverage(
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            total_samples=y.shape[0],
        )
        
        # 构建划分摘要
        summary = self._build_summary(
            dataset_dir=dataset_dir, 
            output_dir=output_dir,
            y=y, # 
            manifest=manifest,
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            train_segments=train_segments,
            val_segments=val_segments,
            test_segments=test_segments,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )
        # 保存索引
        np.save(output_dir / "train_indices.npy", train_indices)
        np.save(output_dir / "val_indices.npy", val_indices)
        np.save(output_dir / "test_indices.npy", test_indices)
        # 把划分摘要写成 JSON 文件
        (output_dir / "split_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return DatasetSplitResult(
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            summary=summary,
        )

    def _validate_ratios(
        self,
        train_ratio: float,
        val_ratio: float,
        test_ratio: float,
    ) -> None:
        ratios = [train_ratio, val_ratio, test_ratio]

        if any(r <= 0 for r in ratios):
            raise ValueError("train_ratio、val_ratio、test_ratio 都必须大于 0")

        ratio_sum = train_ratio + val_ratio + test_ratio
        if abs(ratio_sum - 1.0) > 1e-6:
            raise ValueError(
                f"train_ratio + val_ratio + test_ratio 必须等于 1，当前为 {ratio_sum}"
            )

    def _validate_dataset_dir(self, dataset_dir: Path) -> None:
        if not dataset_dir.exists():
            raise FileNotFoundError(f"数据集目录不存在: {dataset_dir}")

        required_files = [
            "y.npy",
            "window_manifest.csv",
        ]

        for file_name in required_files:
            if not (dataset_dir / file_name).exists():
                raise FileNotFoundError(f"数据集缺少必要文件: {file_name}")

    def _prepare_output_dir(self, output_dir: Path, overwrite: bool) -> None:
        if output_dir.exists():
            if not overwrite:
                raise FileExistsError(
                    f"划分输出目录已存在: {output_dir}。如需覆盖，请设置 overwrite=True 或使用 --overwrite。"
                )

            for file_path in output_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()

        output_dir.mkdir(parents=True, exist_ok=True)
    
    # 按 segment_id 划分
    def _split_segments(
        self,
        segment_ids: list[str],
        train_ratio: float,
        val_ratio: float,
        seed: int,
    ) -> tuple[set[str], set[str], set[str]]:
        rng = np.random.default_rng(seed) # 创建 NumPy 随机数生成器。
        shuffled = np.array(segment_ids, dtype=object) # 把 segment_id 列表转成 NumPy 数组
        rng.shuffle(shuffled) # 随机打乱 segment 顺序

        total_segments = len(shuffled)

        train_count = int(total_segments * train_ratio)
        val_count = int(total_segments * val_ratio)

        # 保证三个集合至少有一个 segment。
        train_count = max(train_count, 1)
        val_count = max(val_count, 1)

        if train_count + val_count >= total_segments:
            val_count = max(1, total_segments - train_count - 1)

        test_count = total_segments - train_count - val_count
        if test_count <= 0:
            raise ValueError("segment 数量过少，无法划分 train/val/test")
        # 集合id
        train_segments = set(shuffled[:train_count].tolist())
        val_segments = set(shuffled[train_count : train_count + val_count].tolist())
        test_segments = set(shuffled[train_count + val_count :].tolist())

        return train_segments, val_segments, test_segments


    def _indices_for_segments(
        self,
        manifest: pd.DataFrame,
        segment_ids: set[str],
    ) -> np.ndarray:
        mask = manifest["segment_id"].isin(segment_ids)
        indices = np.flatnonzero(mask.to_numpy())

        return indices.astype(np.int64)

    def _validate_index_coverage(
        self,
        *,
        train_indices: np.ndarray,
        val_indices: np.ndarray,
        test_indices: np.ndarray,
        total_samples: int,
    ) -> None:
        all_indices = np.concatenate([train_indices, val_indices, test_indices])

        if all_indices.shape[0] != total_samples:
            raise ValueError(
                f"划分后样本总数不等于原始样本数: split={all_indices.shape[0]}, total={total_samples}"
            )

        unique_count = np.unique(all_indices).shape[0]
        if unique_count != total_samples:
            raise ValueError(
                f"划分索引存在重复或遗漏: unique={unique_count}, total={total_samples}"
            )

        if all_indices.min() < 0 or all_indices.max() >= total_samples:
            raise ValueError("划分索引越界")

    def _build_summary(
        self,
        *,
        dataset_dir: Path,
        output_dir: Path,
        y: np.ndarray,
        manifest: pd.DataFrame,
        train_indices: np.ndarray,
        val_indices: np.ndarray,
        test_indices: np.ndarray,
        train_segments: set[str],
        val_segments: set[str],
        test_segments: set[str],
        train_ratio: float,
        val_ratio: float,
        test_ratio: float,
        seed: int,
    ) -> dict[str, Any]:
        return {
            "dataset_dir": str(dataset_dir), # 数据集路径
            "output_dir": str(output_dir), # 数据集路径
            "split_strategy": "segment_id", # 划分策略
            "train_ratio": train_ratio, # 划分比例
            "val_ratio": val_ratio, 
            "test_ratio": test_ratio, 
            "seed": seed, # 随机种子
            "total_samples": int(y.shape[0]), # 总样本数
            "total_segments": int(manifest["segment_id"].nunique()), # 总 segment 数
            "train": self._split_part_summary(
                name="train",
                indices=train_indices,
                segment_ids=train_segments,
                y=y,
            ),
            "val": self._split_part_summary(
                name="val",
                indices=val_indices,
                segment_ids=val_segments,
                y=y,
            ),
            "test": self._split_part_summary(
                name="test",
                indices=test_indices,
                segment_ids=test_segments,
                y=y,
            ),
            "leakage_check": self._build_leakage_check(
                train_segments=train_segments,
                val_segments=val_segments,
                test_segments=test_segments,
            ),
        }

    def _split_part_summary(
        self,
        *,
        name: str,
        indices: np.ndarray,
        segment_ids: set[str],
        y: np.ndarray,
    ) -> dict[str, Any]:
        y_part = y[indices]
        sample_count = int(indices.shape[0])
        positive_count = int(y_part.sum()) if sample_count > 0 else 0
        negative_count = sample_count - positive_count
        positive_ratio = positive_count / sample_count if sample_count > 0 else 0.0

        return {
            "name": name,
            "sample_count": sample_count,
            "segment_count": len(segment_ids),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "positive_ratio": positive_ratio,
            "indices_file": f"{name}_indices.npy",
        }

    def _build_leakage_check(
        self,
        *,
        train_segments: set[str],
        val_segments: set[str],
        test_segments: set[str],
    ) -> dict[str, Any]:
        train_val_overlap = train_segments.intersection(val_segments)
        train_test_overlap = train_segments.intersection(test_segments)
        val_test_overlap = val_segments.intersection(test_segments)

        return {
            "train_val_overlap_count": len(train_val_overlap),
            "train_test_overlap_count": len(train_test_overlap),
            "val_test_overlap_count": len(val_test_overlap),
            "has_segment_leakage": bool(train_val_overlap or train_test_overlap or val_test_overlap),
        }