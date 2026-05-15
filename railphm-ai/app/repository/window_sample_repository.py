from __future__ import annotations

import csv
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np


class WindowSampleRepository:
    """
    本地窗口样本仓储。

    只负责从已构建的数据集产物中读取单个窗口，不接入数据库，也不保存任何预测结果。
    X.npy / y.npy 使用 mmap 方式打开，避免接口进程一次性加载全部样本。
    """

    # 初始化仓储对象
    def __init__(self, dataset_dir: str | Path) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.x_path = self.dataset_dir / "X.npy" # dataset_dir/X.npy
        self.y_path = self.dataset_dir / "y.npy" # dataset_dir/y.npy
        self.manifest_path = self.dataset_dir / "window_manifest.csv" # dataset_dir/window_manifest.csv

        self._validate_dataset_files()
        self._x = np.load(self.x_path, mmap_mode="r")
        self._y = np.load(self.y_path, mmap_mode="r")
        self._validate_arrays()
    
    # 根据 sample_index 取出一个窗口样本
    def get_window_by_sample_index(self, sample_index: int) -> dict[str, Any]:
        self._validate_sample_index(sample_index)

        if sample_index >= self._x.shape[0]:
            raise IndexError(
                f"sample_index 越界: sample_index={sample_index}, "
                f"available_samples={self._x.shape[0]}"
            )
        #从 X.npy 取窗口：X[sample_index]
        window = np.asarray(self._x[sample_index], dtype=np.float32)
        # 从 y.npy 取真实标签: y[sample_index]
        y_true = self._normalize_label(self._y[sample_index])
        self._validate_window(window)
        # 返回结果被 infer_repository.py 使用
        return {
            "window": window, # 进入模型推理
            "y_true": y_true,
            "sample_index": int(sample_index),
            "trace": self._read_trace(sample_index),
        }

    def _validate_dataset_files(self) -> None:
        if not self.dataset_dir.exists():
            raise FileNotFoundError(f"dataset_dir 不存在: {self.dataset_dir}")
        if not self.dataset_dir.is_dir():
            raise NotADirectoryError(f"dataset_dir 不是目录: {self.dataset_dir}")
        if not self.x_path.exists():
            raise FileNotFoundError(f"X.npy 不存在: {self.x_path}")
        if not self.y_path.exists():
            raise FileNotFoundError(f"y.npy 不存在: {self.y_path}")

    def _validate_arrays(self) -> None:
        if self._x.ndim != 3:
            raise ValueError(f"X.npy 必须是三维数组，当前 shape={self._x.shape}")
        if self._y.ndim != 1:
            raise ValueError(f"y.npy 必须是一维数组，当前 shape={self._y.shape}")
        if self._x.shape[0] != self._y.shape[0]:
            raise ValueError(
                "X.npy 与 y.npy 样本数不一致: "
                f"X={self._x.shape[0]}, y={self._y.shape[0]}"
            )

    def _validate_sample_index(self, sample_index: int) -> None:
        if isinstance(sample_index, bool) or not isinstance(sample_index, Integral):
            raise ValueError("sample_index 必须为非负整数")
        if sample_index < 0:
            raise ValueError("sample_index 必须为非负整数")

    def _validate_window(self, window: np.ndarray) -> None:
        if window.ndim != 2:
            raise ValueError(f"window 必须是二维数组，当前 shape={window.shape}")
        if not np.isfinite(window).all():
            raise ValueError("window contains NaN or inf")

    def _read_trace(self, sample_index: int) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {}

        with self.manifest_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            for row_index, row in enumerate(reader):
                if row_index == sample_index:
                    return self._normalize_trace(row)

        return {}

    @staticmethod
    def _normalize_label(value: Any) -> int | float:
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, Integral):
            return int(value)
        return float(value)

    @staticmethod
    def _normalize_trace(row: dict[str, Any]) -> dict[str, Any]:
        trace = dict(row)
        if "label" in trace:
            try:
                trace["label"] = int(trace["label"])
            except (TypeError, ValueError):
                pass

        if "target_label_value" in trace and "target_alarm_value" not in trace:
            trace["target_alarm_value"] = trace["target_label_value"]

        return trace
