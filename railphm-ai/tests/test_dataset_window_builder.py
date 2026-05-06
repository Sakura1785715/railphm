# tests/test_dataset_window_builder.py

from pathlib import Path

import numpy as np
import pandas as pd

from app.dataset.segment_loader import SegmentData
from app.dataset.window_builder import WindowBuilder


def _make_segment_data(row_count: int = 35) -> SegmentData:
    times = pd.date_range("2015-01-09 11:23:05", periods=row_count, freq="s")

    df = pd.DataFrame(
        {
            "数据时间": [time.strftime("%Y%m%d%H%M%S") for time in times],
            "报警部位": ["" for _ in range(row_count)],
            "报警部位.1": ["" for _ in range(row_count)],
            "报警部位.2": ["" for _ in range(row_count)],
            "ATP类型": ["CTCS-3" for _ in range(row_count)],
            "车号": ["3001003" for _ in range(row_count)],
            "车次": ["G1001" for _ in range(row_count)],
            "配属铁路局": ["北京局" for _ in range(row_count)],
            "途经铁路局": ["北京局" for _ in range(row_count)],
            "是否是跨天车次": [False for _ in range(row_count)],
            "司机号": ["D001" for _ in range(row_count)],
            "唯一标识": [f"uid-{i}" for i in range(row_count)],
            "司机手机号": ["13800000000" for _ in range(row_count)],
        }
    )

    return SegmentData(
        segment_id="segment_000001_20150109112305",
        file_name="segment_000001_20150109112305.csv",
        file_path=Path("segment_000001_20150109112305.csv"),
        df=df,
        parsed_time=pd.Series(times, name="数据时间"),
        start_time=times[0],
        end_time=times[-1],
        row_count=row_count,
        is_time_continuous=True,
    )


def test_window_builder_builds_expected_windows_and_shapes():
    segment = _make_segment_data(row_count=35)
    feature_matrix = np.arange(35 * 3, dtype=np.float32).reshape(35, 3)

    builder = WindowBuilder(window_size=30, stride=1, prediction_horizon=1)
    result = builder.build_windows(feature_matrix, segment)

    assert result.X.shape == (5, 30, 3)
    assert result.y.shape == (5,)
    assert result.X.dtype == np.float32
    assert result.y.dtype == np.int64

    # 第一个窗口应取第 0～29 行，target_row 是第 30 行。
    np.testing.assert_array_equal(result.X[0], feature_matrix[0:30])
    assert result.manifest_records[0]["window_start_row"] == 0
    assert result.manifest_records[0]["window_end_row"] == 29
    assert result.manifest_records[0]["target_row"] == 30

    # target 行不得进入第一个 X。
    assert not np.array_equal(result.X[0][-1], feature_matrix[30])


def test_window_builder_label_uses_only_first_alarm_column():
    segment = _make_segment_data(row_count=35)

    # 第一个窗口 target_row=30。
    # 第一列“报警部位”非空，所以第一个 y 应为 1。
    segment.df.loc[30, "报警部位"] = "车载主机"

    # 第二个窗口 target_row=31。
    # 这里只让 报警部位.1 和 报警部位.2 非空，但第一列“报警部位”为空。
    # 所以第二个 y 必须仍然为 0。
    segment.df.loc[31, "报警部位"] = ""
    segment.df.loc[31, "报警部位.1"] = "不应影响标签"
    segment.df.loc[31, "报警部位.2"] = "也不应影响标签"

    feature_matrix = np.ones((35, 3), dtype=np.float32)

    builder = WindowBuilder(window_size=30, stride=1, prediction_horizon=1)
    result = builder.build_windows(feature_matrix, segment)

    assert result.y[0] == 1
    assert result.y[1] == 0
    assert result.manifest_records[0]["target_label_value"] == "车载主机"


def test_window_builder_manifest_keeps_business_metadata_without_phone():
    segment = _make_segment_data(row_count=35)
    segment.df.loc[30, "报警部位"] = "应答器信息接收单元"
    segment.df.loc[30, "ATP类型"] = "CTCS-3"
    segment.df.loc[30, "车号"] = "3001003"
    segment.df.loc[30, "车次"] = "G1001"
    segment.df.loc[30, "唯一标识"] = "target-uid-30"

    feature_matrix = np.ones((35, 3), dtype=np.float32)

    builder = WindowBuilder(window_size=30, stride=1, prediction_horizon=1)
    result = builder.build_windows(feature_matrix, segment)

    record = result.manifest_records[0]

    assert record["sample_id"] == "segment_000001_20150109112305_000000_000030"
    assert record["segment_id"] == "segment_000001_20150109112305"
    assert record["segment_file"] == "segment_000001_20150109112305.csv"
    assert record["target_ATP类型"] == "CTCS-3"
    assert record["target_车号"] == "3001003"
    assert record["target_车次"] == "G1001"
    assert record["target_唯一标识"] == "target-uid-30"
    assert record["window_start_车号"] == "3001003"
    assert record["window_start_车次"] == "G1001"
    assert record["window_start_唯一标识"] == "uid-0"

    # manifest 不应写入个人敏感信息。
    assert "司机手机号" not in record
    assert "target_司机手机号" not in record


def test_window_builder_returns_empty_result_for_short_segment():
    segment = _make_segment_data(row_count=20)
    feature_matrix = np.ones((20, 3), dtype=np.float32)

    builder = WindowBuilder(window_size=30, stride=1, prediction_horizon=1)
    result = builder.build_windows(feature_matrix, segment)

    assert result.X.shape == (0, 30, 3)
    assert result.y.shape == (0,)
    assert result.manifest_records == []