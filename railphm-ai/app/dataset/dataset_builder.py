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

    本类不负责：
    - 模型训练；
    - train/val/test 划分；
    - 替换 /infer；
    - 连接 MySQL 或 InfluxDB。
    """

    def __init__(
        self,
        segment_loader: SegmentLoader | None = None,
        feature_processor: FeatureProcessor | None = None,
    ):
        self.segment_loader = segment_loader or SegmentLoader()
        self.feature_processor = feature_processor or FeatureProcessor()

    # 核心函数：csv转换为数据集
    def build(
        self,
        segments_dir: Path,
        output_dir: Path,
        window_size: int = DEFAULT_WINDOW_SIZE,
        stride: int = DEFAULT_STRIDE,
        prediction_horizon: int = DEFAULT_PREDICTION_HORIZON,
        overwrite: bool = False,
        skip_invalid_segments: bool = True,
    ) -> dict[str, Any]:
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
        used_segment_count = 0

        missing_feature_columns: set[str] = set()
        all_nan_feature_columns: set[str] = set()

        feature_columns = self.feature_processor.get_feature_columns()
        feature_dim = len(feature_columns)

        for file_path in segment_files:
            try:
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

            all_X.append(window_result.X)
            all_y.append(window_result.y)
            manifest_records.extend(window_result.manifest_records)
            used_segment_count += 1

        X, y = self._concat_results(
            all_X=all_X,
            all_y=all_y,
            window_size=window_size,
            feature_dim=feature_dim,
        )

        self._write_outputs(
            output_dir=output_dir,
            X=X,
            y=y,
            feature_columns=feature_columns,
            manifest_records=manifest_records,
        )

        positive_count = int(y.sum()) if y.size > 0 else 0
        total_windows = int(y.shape[0])
        negative_count = total_windows - positive_count

        summary = build_dataset_summary(
            segments_dir=segments_dir,
            output_dir=output_dir,
            window_size=window_size,
            stride=stride,
            prediction_horizon=prediction_horizon,
            total_segment_files=total_segment_files,
            used_segment_count=used_segment_count,
            skipped_segments=skipped_segments,
            total_windows=total_windows,
            positive_count=positive_count,
            negative_count=negative_count,
            feature_dim=feature_dim,
            feature_columns=feature_columns,
            X_shape=X.shape,
            y_shape=y.shape,
            missing_feature_columns=missing_feature_columns,
            all_nan_feature_columns=all_nan_feature_columns,
        )

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

        X = np.concatenate(all_X, axis=0).astype(np.float32, copy=False)
        y = np.concatenate(all_y, axis=0).astype(np.int64, copy=False)

        return X, y

    def _write_outputs(
        self,
        *,
        output_dir: Path,
        X: np.ndarray,
        y: np.ndarray,
        feature_columns: list[str],
        manifest_records: list[dict[str, Any]],
    ) -> None:
        np.save(output_dir / "X.npy", X)
        np.save(output_dir / "y.npy", y)
        self._write_json(output_dir / "feature_columns.json", feature_columns)

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