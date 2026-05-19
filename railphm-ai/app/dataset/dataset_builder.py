"""
调度中心：
    SegmentLoader
    读取单个 segment CSV
            ↓
    FeatureProcessor
    把完整 DataFrame 转成 feature_matrix
            ↓
    WindowBuilder
    把 feature_matrix 切成滑动窗口 X/y
            ↓
    WindowDatasetBuilder
    汇总所有 segment，并写出 X.npy、y.npy、manifest、summary
"""
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.dataset.dataset_summary import build_dataset_summary
from app.dataset.feature_config import (
    DEFAULT_PREDICTION_HORIZON,
    DEFAULT_STRIDE,
    DEFAULT_WINDOW_SIZE,
)
from app.dataset.feature_processor import FeatureProcessor
from app.dataset.segment_loader import SegmentLoader
from app.dataset.window_builder import WindowBuilder


class WindowDatasetBuilder:
    """
    RailPHM 窗口数据集构建主编排类。

    职责：
    1. 遍历 segment CSV 文件；
    2. 调用 SegmentLoader 完整读取文件；
    3. 调用 FeatureProcessor 生成 feature_matrix；
    4. 调用 WindowBuilder 构造 X/y/manifest；
    5. 汇总所有 segment 的样本；
    6. 写出 X.npy、y.npy、feature_columns.json、window_manifest.csv、dataset_summary.json。
    """

    def __init__(
        self,
        segment_loader: SegmentLoader | None = None,
        feature_processor: FeatureProcessor | None = None,
    ):
        self.segment_loader = segment_loader or SegmentLoader()
        self.feature_processor = feature_processor or FeatureProcessor()

    # Core！！把一个目录里的 CSV segment 构建成完整窗口数据集
    def build(
        self,
        segments_dir: Path, # 输入目录，里面放 segment_*.csv
        output_dir: Path, # 输出目录，用于保存 X.npy、y.npy 等文件
        window_size: int = DEFAULT_WINDOW_SIZE, # 窗口大小，默认 30
        stride: int = DEFAULT_STRIDE, # 滑动步长，默认 1
        prediction_horizon: int = DEFAULT_PREDICTION_HORIZON, # 预测提前量，默认 1
        overwrite: bool = False, # 输出目录存在时是否覆盖
        skip_invalid_segments: bool = True, # 遇到坏的 segment 是否跳过
    ) -> dict[str, Any]: # 返回数据集摘要信息
        segments_dir = Path(segments_dir) 
        output_dir = Path(output_dir) 

        self._validate_input_dir(segments_dir)
        self._prepare_output_dir(output_dir, overwrite=overwrite)

        segment_files = sorted(segments_dir.glob("segment_*.csv"))
        total_segment_files = len(segment_files)

        window_builder = WindowBuilder(
            window_size=window_size,
            stride=stride,
            prediction_horizon=prediction_horizon,
        )

        all_X: list[np.ndarray] = []
        all_y: list[np.ndarray] = []
        manifest_records: list[dict[str, Any]] = []

        skipped_segments: list[dict[str, Any]] = []
        used_segment_count = 0 # 记录真正参与构建数据集的 segment 数量

        missing_feature_columns: set[str] = set()
        all_nan_feature_columns: set[str] = set()

        feature_columns = self.feature_processor.get_feature_columns()
        feature_dim = len(feature_columns)

        for file_path in segment_files:
            try:
                # 调用 SegmentLoader.load_segment() 得到 SegmentData。 其中包括pd: DataFrame
                segment_data = self.segment_loader.load_segment(file_path)
            except Exception as exc:
                if skip_invalid_segments:
                    skipped_segments.append(
                        {
                            "segment_file": file_path.name,
                            "reason": f"load_failed: {exc}",
                        }
                    )
                    continue
                raise

            if not segment_data.is_time_continuous:
                reason = "time_not_continuous"
                if skip_invalid_segments:
                    skipped_segments.append(
                        {
                            "segment_file": segment_data.file_name,
                            "reason": reason,
                        }
                    )
                    continue

                raise ValueError(f"segment 时间不连续: {segment_data.file_name}")
            
            # 调用 FeatureProcessor 处理当前 segment 的完整 DataFrame。 
            feature_result = self.feature_processor.transform(segment_data.df)

            missing_feature_columns.update(feature_result.missing_feature_columns)
            all_nan_feature_columns.update(feature_result.all_nan_feature_columns)

            window_result = window_builder.build_windows(
                feature_matrix=feature_result.feature_matrix,
                segment_data=segment_data,
            )

            if window_result.X.shape[0] == 0:
                skipped_segments.append(
                    {
                        "segment_file": segment_data.file_name,
                        "reason": (
                            "no_windows_generated: "
                            f"row_count={segment_data.row_count}, "
                            f"required={window_size + prediction_horizon}"
                        ),
                    }
                )
                continue
           
            all_X.append(window_result.X)  # 把当前 segment 的窗口特征数组加入总列表
            all_y.append(window_result.y)   # 把当前 segment 的标签数组加入总列表。
            manifest_records.extend(window_result.manifest_records) # 把当前 segment 的所有窗口追溯记录加入总 manifest 列表
            used_segment_count += 1

        # 汇总所有 segment 的 X/y
        X, y = self._concat_results(
            all_X=all_X,
            all_y=all_y,
            window_size=window_size,
            feature_dim=feature_dim,
        )

        # 写出主要输出文件
        self._write_outputs(
            output_dir=output_dir,
            X=X,
            y=y,
            feature_columns=feature_columns,
            manifest_records=manifest_records,
        )

        # 统计正负样本数量（目标行报警为正样本）
        positive_count = int(y.sum()) if y.size > 0 else 0
        total_windows = int(y.shape[0])
        negative_count = total_windows - positive_count

        # 构建数据集摘要
        summary = build_dataset_summary(
            segments_dir=segments_dir, # 输入目录
            output_dir=output_dir, # 输出目录
            window_size=window_size, # 窗口大小
            stride=stride, # 窗口步长
            prediction_horizon=prediction_horizon, # 预测提前量
            total_segment_files=total_segment_files, # 总 segment 文件数
            used_segment_count=used_segment_count, # 实际使用的 segment 数
            skipped_segments=skipped_segments, # 跳过的 segment 
            total_windows=total_windows, # 窗口样本总数
            positive_count=positive_count, # 正样本数量
            negative_count=negative_count, # 负样本数量
            feature_dim=feature_dim, # 特征维度
            feature_columns=feature_columns, # 特征列顺序
            X_shape=X.shape, # X.shape = [窗口数量，窗口大小，特征维度]
            y_shape=y.shape, # y.shape = [标签数量（窗口数量）]
            missing_feature_columns=missing_feature_columns, # 缺失字段
            all_nan_feature_columns=all_nan_feature_columns, # 全空字段
        )
        # 把数据集摘要写成 JSON 文件，路径为 output_dir/dataset_summary.json
        self._write_json(output_dir / "dataset_summary.json", summary)

        return summary

    def _validate_input_dir(self, segments_dir: Path) -> None:
        if not segments_dir.exists():
            raise FileNotFoundError(f"segments_dir 不存在: {segments_dir}")

        if not segments_dir.is_dir():
            raise ValueError(f"segments_dir 不是目录: {segments_dir}")

    def _prepare_output_dir(self, output_dir: Path, overwrite: bool) -> None:
        if output_dir.exists():
            if not overwrite:
                raise FileExistsError(
                    f"输出目录已存在: {output_dir}。如需覆盖，请设置 overwrite=True 或使用 --overwrite。"
                )

            shutil.rmtree(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

    # 把多个 segment 的结果拼接成总数据集
    def _concat_results(
        self,
        *,
        all_X: list[np.ndarray],
        all_y: list[np.ndarray],
        window_size: int,
        feature_dim: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        if not all_X:
            X = np.empty((0, window_size, feature_dim), dtype=np.float32)
            y = np.empty((0,), dtype=np.int64)
            return X, y
        # 把每一个 segment 生成的 X 和 y 拼接汇总
        X = np.concatenate(all_X, axis=0).astype(np.float32, copy=False)
        y = np.concatenate(all_y, axis=0).astype(np.int64, copy=False)

        return X, y
    
    # 写出主要数据集文件
    def _write_outputs(
        self,
        *,
        output_dir: Path,
        X: np.ndarray, # 窗口特征数组（模型输入）， 例如[325800, 30, 22]表示： 325800 个窗口样本，每个窗口 30 个时间点，每个时间点 22 个特征
        y: np.ndarray,
        feature_columns: list[str],
        manifest_records: list[dict[str, Any]],
    ) -> None:
        np.save(output_dir / "X.npy", X)
        np.save(output_dir / "y.npy", y)
        # 写出特征列顺序，说明X每一列数值表示什么
        self._write_json(output_dir / "feature_columns.json", feature_columns)
        # 把 manifest 写成 CSV 文件，保存窗口追溯信息
        manifest_df = pd.DataFrame(manifest_records)
        manifest_df.to_csv(
            output_dir / "window_manifest.csv",
            index=False,
            encoding="utf-8-sig",
        )

    def _write_json(self, file_path: Path, data: Any) -> None:
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )