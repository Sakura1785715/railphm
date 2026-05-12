from pathlib import Path

import pandas as pd
import pytest

from app.dataset.segment_loader import SegmentLoader


def _write_segment_csv(path: Path, rows: list[list[object]], duplicate_label_headers: bool = True) -> None:
    if duplicate_label_headers:
        header = [
            "报警部位",
            "报警部位",
            "报警部位",
            "数据时间",
            "ATP类型",
            "车号",
            "车次",
            "唯一标识",
            "速度",
            "里程",
            "运行距离",
        ]
    else:
        header = [
            "报警部位",
            "数据时间",
            "ATP类型",
            "车号",
            "车次",
            "唯一标识",
            "速度",
            "里程",
            "运行距离",
        ]

    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join("" if value is None else str(value) for value in row))

    path.write_text("\n".join(lines), encoding="utf-8-sig")


def test_segment_loader_loads_complete_csv_and_duplicate_label_columns(tmp_path):
    segment_path = tmp_path / "segment_000001_20150109112305.csv"

    rows = []
    for i in range(35):
        rows.append(
            [
                "" if i != 30 else "车载主机",
                "不应作为标签",
                "也不应作为标签",
                f"201501091123{5 + i:02d}",
                "CTCS-3",
                "3001003",
                "G1001",
                f"uid-{i}",
                100 + i,
                200 + i,
                300 + i,
            ]
        )

    _write_segment_csv(segment_path, rows)

    loader = SegmentLoader()
    segment = loader.load_segment(segment_path)

    assert segment.segment_id == "segment_000001_20150109112305"
    assert segment.file_name == "segment_000001_20150109112305.csv"
    assert segment.row_count == 35
    assert segment.start_time == pd.Timestamp("2015-01-09 11:23:05")
    assert segment.end_time == pd.Timestamp("2015-01-09 11:23:39")
    assert segment.is_time_continuous is True

    # pandas 会自动把重复列名改成 报警部位、报警部位.1、报警部位.2
    assert "报警部位" in segment.df.columns
    assert "报警部位.1" in segment.df.columns
    assert "报警部位.2" in segment.df.columns

    # 读取层必须完整保留字段，不应提前删列。
    assert "ATP类型" in segment.df.columns
    assert "车号" in segment.df.columns
    assert "车次" in segment.df.columns
    assert "唯一标识" in segment.df.columns


def test_segment_loader_marks_non_continuous_time(tmp_path):
    segment_path = tmp_path / "segment_000002_20150109112305.csv"

    rows = [
        ["", "", "", "20150109112305", "CTCS-3", "3001003", "G1001", "uid-0", 100, 200, 300],
        ["", "", "", "20150109112306", "CTCS-3", "3001003", "G1001", "uid-1", 101, 201, 301],
        # 中间跳过 11:23:07
        ["", "", "", "20150109112308", "CTCS-3", "3001003", "G1001", "uid-2", 102, 202, 302],
    ]

    _write_segment_csv(segment_path, rows)

    loader = SegmentLoader()
    segment = loader.load_segment(segment_path)

    assert segment.row_count == 3
    assert segment.is_time_continuous is False


def test_segment_loader_raises_when_time_column_missing(tmp_path):
    segment_path = tmp_path / "segment_000003_missing_time.csv"
    segment_path.write_text("速度,里程\n100,200\n", encoding="utf-8-sig")

    loader = SegmentLoader()

    with pytest.raises(ValueError, match="缺少时间字段"):
        loader.load_segment(segment_path)


def test_segment_loader_iter_segments_only_reads_segment_csv(tmp_path):
    valid_path = tmp_path / "segment_000001_20150109112305.csv"
    ignored_manifest = tmp_path / "segments_manifest.csv"
    ignored_summary = tmp_path / "split_summary.json"

    rows = []
    for i in range(2):
        rows.append(
            [
                "",
                "",
                "",
                f"201501091123{5 + i:02d}",
                "CTCS-3",
                "3001003",
                "G1001",
                f"uid-{i}",
                100 + i,
                200 + i,
                300 + i,
            ]
        )

    _write_segment_csv(valid_path, rows)
    ignored_manifest.write_text("should,not,read\n", encoding="utf-8")
    ignored_summary.write_text("{}", encoding="utf-8")

    loader = SegmentLoader()
    segments = list(loader.iter_segments(tmp_path))

    assert len(segments) == 1
    assert segments[0].file_name == valid_path.name