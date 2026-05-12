"""
滑动窗口构造层
把二维特征矩阵：[row_count, feature_dim]
进一步切成模型需要的三维时序样本：[num_windows, window_size, feature_dim]
"""
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.dataset.feature_config import LABEL_COL
from app.dataset.segment_loader import SegmentData


# 数据类（窗口构造结果对象）
@dataclass
class WindowBuildResult:
    """
    单个 segment 的窗口构造结果。
    X:
        shape = [num_windows, window_size, feature_dim]
    y:
        shape = [num_windows]
    manifest_records:
        每个窗口样本的来源、标签和业务追溯信息。
    """
    # 窗口特征数组[窗口数, 窗口大小, 特征数]
    X: np.ndarray
    # 标签数组[窗口数]，每个元素是 0 或 1。
    y: np.ndarray
    manifest_records: list[dict]


# 滑动窗口构造器
class WindowBuilder:
    """
    单个 segment 内的滑动窗口构造器。
    把 FeatureProcessor 得到的二维特征矩阵切成窗口样本
    职责：
    1. 只在当前 segment 内构造窗口；
    2. X 只包含窗口内前 window_size 行；
    3. y 只根据 target_index 行第一列“报警部位”是否非空生成；
    4. 生成 window_manifest 所需的追溯信息。
    """
    # 窗口大小、步长、往前多远预测（预警提前量）
    def __init__(self, window_size: int, stride: int, prediction_horizon: int):
        if window_size <= 0:
            raise ValueError("window_size 必须为正整数")
        if stride <= 0:
            raise ValueError("stride 必须为正整数")
        if prediction_horizon <= 0:
            raise ValueError("prediction_horizon 必须为正整数")

        self.window_size = int(window_size)
        self.stride = int(stride)
        self.prediction_horizon = int(prediction_horizon)

    def build_windows(
        self,
        feature_matrix: np.ndarray, # 生成的二维数值矩阵
        segment_data: SegmentData, # 生成的原始 segment 信息
    ) -> WindowBuildResult:
        if feature_matrix is None or not isinstance(feature_matrix, np.ndarray):
            raise ValueError("feature_matrix 必须为 numpy.ndarray")
        if feature_matrix.ndim != 2:
            raise ValueError("feature_matrix 必须为二维数组 [row_count, feature_dim]")
        
        # 读取矩阵行数（一个segment多少行数据）、列数（输入模型的特征数量）
        row_count, feature_dim = feature_matrix.shape
        # 检查 feature_matrix 的行数是否和原始 segment 的行数一致
        if row_count != segment_data.row_count:
            raise ValueError(
                "feature_matrix 行数必须与 segment_data.row_count 一致: "
                f"feature_matrix={row_count}, segment={segment_data.row_count}"
            )

        if LABEL_COL not in segment_data.df.columns:
            raise ValueError(f"segment 缺少标签字段 {LABEL_COL}: {segment_data.file_name}")
        
        # 计算构造至少一个窗口所需的最小行数
        min_required_rows = self.window_size + self.prediction_horizon
        # 如果当前 segment 行数不够，就返回空结果
        if row_count < min_required_rows:
            return self._empty_result(feature_dim)
        
        # 三个列表，存放每个窗口的特征、标签、追溯记录（开始时间结束时间），最后再合并
        X_list: list[np.ndarray] = []
        y_list: list[int] = []
        manifest_records: list[dict] = []

        # 计算窗口起始位置的上限
        max_start = row_count - self.window_size - self.prediction_horizon + 1

        for start in range(0, max_start, self.stride):
            window_start = start
            window_end = start + self.window_size - 1
            target_index = start + self.window_size + self.prediction_horizon - 1

            # 滑动窗口切片：从特征矩阵中切出当前窗口的输入特征。
            window_x = feature_matrix[window_start : window_start + self.window_size]
            # 从原始 DataFrame 中取出目标行的标签字段值
            target_label_value = segment_data.df.at[target_index, LABEL_COL]
            # 把目标行的“报警部位”转成二分类标签
            label = self._make_binary_label(target_label_value) # 报警部位为空 → 0 ，报警部位非空 → 1

            X_list.append(window_x)
            y_list.append(label)
            # 存放窗口样本的追溯信息
            manifest_records.append(
                self._build_manifest_record(
                    segment_data=segment_data,
                    window_start=window_start,
                    window_end=window_end,
                    target_index=target_index,
                    label=label,
                    target_label_value=target_label_value,
                )
            )

        # 把窗口列表转换成 NumPy 数组
        X = np.asarray(X_list, dtype=np.float32) # X.shape = [窗口数量，窗口大小，特征维度]
        y = np.asarray(y_list, dtype=np.int64) # y.shape = [标签数量（窗口数量）]

        return WindowBuildResult(
            X=X,
            y=y,
            manifest_records=manifest_records,
        )

    def _empty_result(self, feature_dim: int) -> WindowBuildResult:
        return WindowBuildResult(
            X=np.empty((0, self.window_size, feature_dim), dtype=np.float32),
            y=np.empty((0,), dtype=np.int64),
            manifest_records=[],
        )

    def _make_binary_label(self, value: Any) -> int:
        """
        标签规则：
        - 第一列“报警部位”非空：1
        - 第一列“报警部位”为空：0

        注意：
        这里不会检查“报警部位.1”或“报警部位.2”。
        """
        if value is None:
            return 0

        if pd.isna(value):
            return 0

        if isinstance(value, str) and not value.strip():
            return 0

        return 1
    
    # 为每一个窗口样本生成一条追溯记录
    def _build_manifest_record(
        self,
        segment_data: SegmentData,
        window_start: int,
        window_end: int,
        target_index: int,
        label: int,
        target_label_value: Any,
    ) -> dict:
        target_row = segment_data.df.iloc[target_index] # 目标标签行：提取目标时刻的车号、车次、铁路局、司机号、唯一标识等信息
        window_start_row = segment_data.df.iloc[window_start] # 保存窗口开始时刻的车号、车次、唯一标识等信息

        record = {
            "sample_id": f"{segment_data.segment_id}_{window_start:06d}_{target_index:06d}",
            "segment_id": segment_data.segment_id,
            "segment_file": segment_data.file_name,
            "window_start_row": window_start,
            "window_end_row": window_end,
            "target_row": target_index,
            "window_start_time": self._format_time(segment_data.parsed_time.iloc[window_start]),
            "window_end_time": self._format_time(segment_data.parsed_time.iloc[window_end]),
            "target_time": self._format_time(segment_data.parsed_time.iloc[target_index]),
            "label": label,
            "target_label_value": self._safe_value(target_label_value),
            "target_ATP类型": self._safe_value(target_row.get("ATP类型")),
            "target_车号": self._safe_value(target_row.get("车号")),
            "target_车次": self._safe_value(target_row.get("车次")),
            "target_配属铁路局": self._safe_value(target_row.get("配属铁路局")),
            "target_途经铁路局": self._safe_value(target_row.get("途经铁路局")),
            "target_是否是跨天车次": self._safe_value(target_row.get("是否是跨天车次")),
            "target_司机号": self._safe_value(target_row.get("司机号")),
            "target_唯一标识": self._safe_value(target_row.get("唯一标识")),
            "window_start_车号": self._safe_value(window_start_row.get("车号")),
            "window_start_车次": self._safe_value(window_start_row.get("车次")),
            "window_start_唯一标识": self._safe_value(window_start_row.get("唯一标识")),
        }

        return record

    def _format_time(self, value: Any) -> str:
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d %H:%M:%S")

        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return ""

        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _safe_value(self, value: Any) -> Any:
        if value is None:
            return ""

        if pd.isna(value):
            return ""

        return value