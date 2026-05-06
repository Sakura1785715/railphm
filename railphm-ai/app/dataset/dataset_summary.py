from datetime import datetime
from pathlib import Path
from typing import Any

from app.dataset.feature_config import (
    LABEL_COL,
    MANIFEST_METADATA_COLUMNS,
    TIME_COL,
)


def build_dataset_summary(
    *,
    segments_dir: Path,
    output_dir: Path,
    window_size: int,
    stride: int,
    prediction_horizon: int,
    total_segment_files: int,
    used_segment_count: int,
    skipped_segments: list[dict[str, Any]],
    total_windows: int,
    positive_count: int,
    negative_count: int,
    feature_dim: int,
    feature_columns: list[str],
    X_shape: tuple[int, ...],
    y_shape: tuple[int, ...],
    missing_feature_columns: set[str],
    all_nan_feature_columns: set[str],
) -> dict[str, Any]:
    """
    生成窗口数据集构建统计信息。

    这里只负责组织 summary 字典，不负责写文件。
    """

    positive_ratio = 0.0
    if total_windows > 0:
        positive_ratio = positive_count / total_windows

    return {
        "segments_dir": str(segments_dir),
        "output_dir": str(output_dir),
        "window_size": window_size,
        "stride": stride,
        "prediction_horizon": prediction_horizon,
        "time_col": TIME_COL,
        "label_col": LABEL_COL,
        "total_segment_files": total_segment_files,
        "used_segment_count": used_segment_count,
        "skipped_segment_count": len(skipped_segments),
        "skipped_segments": skipped_segments,
        "total_windows": total_windows,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "positive_ratio": positive_ratio,
        "feature_dim": feature_dim,
        "feature_columns": feature_columns,
        "X_shape": list(X_shape),
        "y_shape": list(y_shape),
        "missing_feature_columns": sorted(missing_feature_columns),
        "all_nan_feature_columns": sorted(all_nan_feature_columns),
        "manifest_metadata_columns": MANIFEST_METADATA_COLUMNS,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }