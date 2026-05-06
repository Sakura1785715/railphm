# tests/test_dataset_builder.py

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.dataset.dataset_builder import WindowDatasetBuilder


def _write_segment_csv(
    path: Path,
    *,
    row_count: int = 35,
    start_second: int = 5,
    break_time_at: int | None = None,
    first_target_alarm: str = "",
) -> None:
    """
    写一个测试用 segment CSV。

    表头故意包含三个重复的“报警部位”，用于模拟 pandas 读取后生成：
    报警部位、报警部位.1、报警部位.2。
    """

    header = [
        "报警部位",
        "报警部位",
        "报警部位",
        "数据时间",
        "ATP类型",
        "车号",
        "车次",
        "配属铁路局",
        "途经铁路局",
        "是否是跨天车次",
        "司机号",
        "唯一标识",
        "司机名",
        "司机手机号",
        "速度",
        "里程",
        "运行距离",
        "行别",
        "线路编号",
        "应答器编号",
        "应答器里程",
        "司机操作是否合规",
        "运行方向",
        "室外温度",
        "湿度",
    ]

    base_time = pd.Timestamp("2015-01-09 11:23:00") + pd.Timedelta(seconds=start_second)

    lines = [",".join(header)]

    for i in range(row_count):
        current_time = base_time + pd.Timedelta(seconds=i)

        if break_time_at is not None and i >= break_time_at:
            current_time += pd.Timedelta(seconds=1)

        alarm = first_target_alarm if i == 30 else ""
        alarm_1 = "不应影响标签" if i == 31 else ""
        alarm_2 = "也不应影响标签" if i == 31 else ""

        row = [
            alarm,
            alarm_1,
            alarm_2,
            current_time.strftime("%Y%m%d%H%M%S"),
            "CTCS-3",
            "3001003",
            "G1001",
            "北京局",
            "北京局",
            "False",
            "D001",
            f"uid-{path.stem}-{i}",
            "张三",
            "13800000000",
            100 + i,
            200 + i,
            300 + i,
            1,
            10,
            1000 + i,
            5000 + i,
            "True" if i % 2 == 0 else "False",
            1,
            20 + i % 3,
            50 + i % 5,
        ]

        lines.append(",".join(str(value) for value in row))

    path.write_text("\n".join(lines), encoding="utf-8-sig")


def test_dataset_builder_complete_flow_outputs_files(tmp_path):
    segments_dir = tmp_path / "segments"
    output_dir = tmp_path / "dataset"
    segments_dir.mkdir()

    _write_segment_csv(
        segments_dir / "segment_000001_20150109112305.csv",
        row_count=35,
        start_second=5,
        first_target_alarm="车载主机",
    )
    _write_segment_csv(
        segments_dir / "segment_000002_20150109112405.csv",
        row_count=35,
        start_second=65,
        first_target_alarm="",
    )

    builder = WindowDatasetBuilder()
    summary = builder.build(
        segments_dir=segments_dir,
        output_dir=output_dir,
        window_size=30,
        stride=1,
        prediction_horizon=1,
        overwrite=False,
        skip_invalid_segments=True,
    )

    assert (output_dir / "X.npy").exists()
    assert (output_dir / "y.npy").exists()
    assert (output_dir / "feature_columns.json").exists()
    assert (output_dir / "window_manifest.csv").exists()
    assert (output_dir / "dataset_summary.json").exists()

    X = np.load(output_dir / "X.npy")
    y = np.load(output_dir / "y.npy")

    # 每个 35 行 segment，在 window_size=30、horizon=1 时生成 5 个窗口。
    assert X.shape[0] == 10
    assert X.shape[1] == 30
    assert y.shape == (10,)

    assert summary["total_segment_files"] == 2
    assert summary["used_segment_count"] == 2
    assert summary["skipped_segment_count"] == 0
    assert summary["total_windows"] == 10
    assert summary["positive_count"] == 1
    assert summary["negative_count"] == 9
    assert summary["X_shape"] == list(X.shape)
    assert summary["y_shape"] == list(y.shape)

    feature_columns = json.loads((output_dir / "feature_columns.json").read_text(encoding="utf-8"))
    assert "报警部位" not in feature_columns
    assert "报警部位.1" not in feature_columns
    assert "报警部位.2" not in feature_columns
    assert "司机手机号" not in feature_columns

    manifest = pd.read_csv(output_dir / "window_manifest.csv", encoding="utf-8-sig")
    assert len(manifest) == 10
    assert "target_车号" in manifest.columns
    assert "target_车次" in manifest.columns
    assert "target_ATP类型" in manifest.columns
    assert "target_唯一标识" in manifest.columns
    assert "司机手机号" not in manifest.columns
    assert "target_司机手机号" not in manifest.columns

    saved_summary = json.loads((output_dir / "dataset_summary.json").read_text(encoding="utf-8"))
    assert saved_summary["total_windows"] == 10


def test_dataset_builder_skips_non_continuous_segment(tmp_path):
    segments_dir = tmp_path / "segments"
    output_dir = tmp_path / "dataset"
    segments_dir.mkdir()

    _write_segment_csv(
        segments_dir / "segment_000001_20150109112305.csv",
        row_count=35,
        start_second=5,
        break_time_at=10,
    )

    builder = WindowDatasetBuilder()
    summary = builder.build(
        segments_dir=segments_dir,
        output_dir=output_dir,
        window_size=30,
        stride=1,
        prediction_horizon=1,
        overwrite=False,
        skip_invalid_segments=True,
    )

    X = np.load(output_dir / "X.npy")
    y = np.load(output_dir / "y.npy")

    assert X.shape == (0, 30, len(summary["feature_columns"]))
    assert y.shape == (0,)
    assert summary["total_segment_files"] == 1
    assert summary["used_segment_count"] == 0
    assert summary["skipped_segment_count"] == 1
    assert summary["skipped_segments"][0]["reason"] == "time_not_continuous"


def test_dataset_builder_short_segment_generates_no_windows_and_is_recorded(tmp_path):
    segments_dir = tmp_path / "segments"
    output_dir = tmp_path / "dataset"
    segments_dir.mkdir()

    _write_segment_csv(
        segments_dir / "segment_000001_short.csv",
        row_count=20,
        start_second=5,
    )

    builder = WindowDatasetBuilder()
    summary = builder.build(
        segments_dir=segments_dir,
        output_dir=output_dir,
        window_size=30,
        stride=1,
        prediction_horizon=1,
        overwrite=False,
        skip_invalid_segments=True,
    )

    assert summary["total_segment_files"] == 1
    assert summary["used_segment_count"] == 0
    assert summary["total_windows"] == 0
    assert summary["skipped_segment_count"] == 1
    assert "no_windows_generated" in summary["skipped_segments"][0]["reason"]

    X = np.load(output_dir / "X.npy")
    y = np.load(output_dir / "y.npy")

    assert X.shape == (0, 30, len(summary["feature_columns"]))
    assert y.shape == (0,)


def test_dataset_builder_refuses_existing_output_without_overwrite(tmp_path):
    segments_dir = tmp_path / "segments"
    output_dir = tmp_path / "dataset"
    segments_dir.mkdir()
    output_dir.mkdir()

    _write_segment_csv(
        segments_dir / "segment_000001_20150109112305.csv",
        row_count=35,
        start_second=5,
    )

    builder = WindowDatasetBuilder()

    try:
        builder.build(
            segments_dir=segments_dir,
            output_dir=output_dir,
            window_size=30,
            stride=1,
            prediction_horizon=1,
            overwrite=False,
            skip_invalid_segments=True,
        )
    except FileExistsError as exc:
        assert "输出目录已存在" in str(exc)
    else:
        raise AssertionError("输出目录已存在且 overwrite=False 时应抛出 FileExistsError")