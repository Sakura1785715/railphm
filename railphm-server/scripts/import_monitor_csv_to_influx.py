"""
把 CSV 文件里的 ATP 运行监测数据导入 InfluxDB
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict#
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import BaseConfig  

# 字段映射表
FIELD_ALIASES = {
    "source_time": ("数据时间", "DataTime", "data_time", "source_time"),
    "speed": ("速度", "Speed", "speed"),
    "mileage": ("里程", "Mileage", "mileage"),
    # "condition_label": ("工况标签", "condition_label", "condition_name", "工况", "condition"),
    "atp_type": ("ATP类型", "atp_type"),
    "source_car_no": ("车号", "TrainID", "source_car_no"),
    "source_train_no": ("车次", "source_train_no"),
    "source_driver_id": ("司机号", "driver_id", "source_driver_id"),
    "source_unique_id": ("唯一标识", "source_unique_id"),
    "line_id": ("线路编号", "line_id"),
    "direction": ("行别", "运行方向", "direction"),
    "station_name": ("站名", "station_name"),
    "balise_id": ("应答器编号", "balise_id"),
    "balise_mileage": ("应答器里程", "balise_mileage"),
    "balise_type": ("应答器类型", "balise_type"),
    "signal_id": ("信号机ID", "signal_id"),
    "signal_name": ("信号机名称", "signal_name"),
    "signal_mileage": ("信号机里程", "signal_mileage"),
    "longitude": ("经度", "longitude"),
    "latitude": ("纬度", "latitude"),
    "outdoor_temperature": ("室外温度", "outdoor_temperature"),
    "weather": ("天气信息", "weather"),
    "road_condition": ("路况信息", "road_condition"),
    "humidity": ("湿度", "humidity"),
    "alarm_part": ("报警部位", "alarm_part"),
}
# CSV必须存在的字段
REQUIRED_FIELDS = ("source_time", "speed", "mileage")

# 要转成数字的字段
NUMERIC_FIELDS = {
    "speed",
    "mileage",
    "balise_mileage",
    "signal_mileage",
    "longitude",
    "latitude",
    "outdoor_temperature",
    "humidity",
}

# 标签字段（tag):InfluxDB查询时可以根据这些条件过滤
TAG_FIELDS = ("device_code", "source_segment", "atp_type", "line_id", "direction")

# 数值字段（field): 用于展示数据
FIELD_FIELDS = tuple(
    field
    for field in FIELD_ALIASES
    if field not in {"source_time", "atp_type", "line_id", "direction"}
)



@dataclass
class SegmentChunk:
    source_name: str
    rows: list[dict[str, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import RailPHM monitor CSV data into InfluxDB.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input-file", type=Path, help="单个 CSV 文件路径")
    input_group.add_argument("--input-dir", type=Path, help="segment CSV 文件目录")
    parser.add_argument("--device-codes", default="ATP001,ATP002,ATP003")
    parser.add_argument("--demo-start-time", required=True, help="演示起始时间，格式 YYYY-MM-DD HH:mm:ss")
    parser.add_argument("--chunk-size", type=int, default=1000, help="单文件切片行数")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset-measurement", action="store_true")
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--influx-url", default=os.getenv("INFLUXDB_URL", BaseConfig.INFLUXDB_URL))
    parser.add_argument("--influx-token", default=os.getenv("INFLUXDB_TOKEN", BaseConfig.INFLUXDB_TOKEN))
    parser.add_argument("--influx-org", default=os.getenv("INFLUXDB_ORG", BaseConfig.INFLUXDB_ORG))
    parser.add_argument("--influx-bucket", default=os.getenv("INFLUXDB_BUCKET", BaseConfig.INFLUXDB_BUCKET))
    parser.add_argument(
        "--measurement",
        default=os.getenv("MONITOR_MEASUREMENT", BaseConfig.MONITOR_MEASUREMENT),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # 传一个演示开始时间
    demo_start_time = datetime.strptime(args.demo_start_time, "%Y-%m-%d %H:%M:%S")
    # 每个设备都从这个演示时间开始写数据
    device_codes = [item.strip() for item in args.device_codes.split(",") if item.strip()]
    if not device_codes:
        raise ValueError("device-codes 不能为空")

    chunks = load_chunks(args)
    validate_required_columns(chunks)

    summary = {
        "file_count": len({chunk.source_name.split("#", 1)[0] for chunk in chunks}),
        "total_rows": 0,
        "written_points": 0,
        "skipped": Counter(),
        "device_counts": Counter(),
        "device_ranges": defaultdict(lambda: {"start": None, "end": None}),
        "condition_counts": defaultdict(Counter),
    }

    client = None
    write_api = None
    if not args.dry_run:
        if not args.influx_url or not args.influx_token or not args.influx_org:
            raise ValueError("InfluxDB url/token/org 配置不能为空")
        client = InfluxDBClient(
            url=args.influx_url,
            token=args.influx_token,
            org=args.influx_org,
            timeout=BaseConfig.INFLUXDB_TIMEOUT,
        )
        if args.reset_measurement:
            client.delete_api().delete(
                start="1970-01-01T00:00:00Z",
                stop="2100-01-01T00:00:00Z",
                predicate=f'_measurement="{args.measurement}"',
                bucket=args.influx_bucket,
                org=args.influx_org,
            )
        write_api = client.write_api(write_options=SYNCHRONOUS)

    device_next_time = {device_code: demo_start_time for device_code in device_codes}
    batch: list[Point] = []

    try:
        for chunk_index, chunk in enumerate(chunks):
            device_code = device_codes[chunk_index % len(device_codes)]
            points = build_points_for_chunk(
                chunk=chunk,
                device_code=device_code,
                start_time=device_next_time[device_code],
                measurement=args.measurement,
                summary=summary,
            )
            if points:
                device_next_time[device_code] = points[-1]["sample_time"] + timedelta(seconds=1)

            for point_info in points:
                point = point_info["point"]
                batch.append(point)
                if not args.dry_run and len(batch) >= args.batch_size:
                    write_api.write(bucket=args.influx_bucket, org=args.influx_org, record=batch)
                    batch.clear()

        if batch and not args.dry_run:
            write_api.write(bucket=args.influx_bucket, org=args.influx_org, record=batch)
    finally:
        if client is not None:
            client.close()

    print_summary(summary, args)

# 读取 CSV 并切片
def load_chunks(args: argparse.Namespace) -> list[SegmentChunk]:
    # 传的是单个文件：按 chunk-size 切片
    if args.input_file:
        rows = read_csv_rows(args.input_file, args.encoding)
        return split_rows_into_chunks(args.input_file.name, rows, args.chunk_size)

    files = sorted(args.input_dir.glob("*.csv"))
    if args.limit_files:
        files = files[: args.limit_files]
    # 传的是目录，目录里只有一个 CSV：按 chunk-size 切片
    if len(files) == 1:
        rows = read_csv_rows(files[0], args.encoding)
        return split_rows_into_chunks(files[0].name, rows, args.chunk_size)

    return [
        # 传的是目录，目录里有多个 CSV：每个 CSV 文件就是一个 chunk
        SegmentChunk(source_name=file_path.stem, rows=read_csv_rows(file_path, args.encoding))
        for file_path in files
    ]


def read_csv_rows(path: Path, encoding: str) -> list[dict[str, str]]:
    with path.open("r", encoding=encoding, newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def split_rows_into_chunks(source_name: str, rows: list[dict[str, str]], chunk_size: int) -> list[SegmentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk-size 必须为正整数")
    chunks = []
    for start in range(0, len(rows), chunk_size):
        chunk_no = start // chunk_size + 1
        chunks.append(
            SegmentChunk(
                source_name=f"{Path(source_name).stem}#chunk_{chunk_no:04d}",
                rows=rows[start : start + chunk_size],
            )
        )
    return chunks


def validate_required_columns(chunks: list[SegmentChunk]) -> None:
    if not chunks:
        raise ValueError("未找到可导入的 CSV 数据")
    columns = set()
    for row in chunks[0].rows[:1]:
        columns.update(row.keys())
    missing = [
        field
        for field in REQUIRED_FIELDS
        if not any(alias in columns for alias in FIELD_ALIASES[field])
    ]
    if missing:
        raise ValueError(f"CSV 缺少核心字段: {', '.join(missing)}")


# 把行数据变成 InfluxDB 点
def build_points_for_chunk(
    chunk: SegmentChunk,
    device_code: str,
    start_time: datetime,
    measurement: str,
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    point_infos = []
    time_cursor = start_time
    source_times = [parse_source_time(get_value(row, FIELD_ALIASES["source_time"])) for row in chunk.rows]

    for index, row in enumerate(chunk.rows):
        summary["total_rows"] += 1
        # 统一字段名
        normalized = normalize_row(row)
        # 检查必填字段
        missing = [field for field in REQUIRED_FIELDS if normalized.get(field) in (None, "")]
        if missing:
            summary["skipped"][f"missing_{','.join(missing)}"] += 1
            continue
        # 构造 InfluxDB 点
        point = Point(measurement).tag("device_code", device_code).tag("source_segment", chunk.source_name)
        for tag in TAG_FIELDS:
            if tag == "device_code" or tag == "source_segment":
                continue
            value = normalized.get(tag)
            if value not in (None, ""):
                point = point.tag(tag, str(value))

        point = point.field("source_time", normalized["source_time"])
        for field in FIELD_FIELDS:
            value = normalized.get(field)
            if value not in (None, ""):
                point = point.field(field, value)
        # 设置时间戳
        point = point.time(time_cursor, WritePrecision.S)

        summary["written_points"] += 1
        summary["device_counts"][device_code] += 1
        condition_label = normalized.get("condition_label")
        if condition_label:
            summary["condition_counts"][device_code][condition_label] += 1
        update_time_range(summary["device_ranges"][device_code], time_cursor)
        point_infos.append({"point": point, "sample_time": time_cursor})
        time_cursor += timedelta(seconds=1)

    return point_infos


def normalize_row(row: dict[str, str]) -> dict[str, Any]:
    normalized = {}
    for field, aliases in FIELD_ALIASES.items():
        value = get_value(row, aliases)
        if value in (None, ""):
            continue
        normalized[field] = to_number(value) if field in NUMERIC_FIELDS else str(value).strip()
    return normalized


def get_value(row: dict[str, str], aliases: Iterable[str]) -> str | None:
    for alias in aliases:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def parse_source_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def infer_step_seconds(source_times: list[datetime | None], index: int) -> timedelta:
    current_time = source_times[index]
    next_time = source_times[index + 1] if index + 1 < len(source_times) else None
    if current_time and next_time:
        delta = (next_time - current_time).total_seconds()
        if 0 < delta <= 300:
            return timedelta(seconds=delta)
    return timedelta(seconds=1)


def to_number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def update_time_range(time_range: dict[str, Any], sample_time: datetime) -> None:
    formatted = sample_time.strftime("%Y-%m-%d %H:%M:%S")
    if time_range["start"] is None:
        time_range["start"] = formatted
    time_range["end"] = formatted


def print_summary(summary: dict[str, Any], args: argparse.Namespace) -> None:
    print("导入摘要")
    print(f"输入文件数量: {summary['file_count']}")
    print(f"总读取行数: {summary['total_rows']}")
    print(f"成功写入点数: {summary['written_points']}")
    print(f"跳过行数及原因: {dict(summary['skipped'])}")
    print(f"InfluxDB bucket: {args.influx_bucket}")
    print(f"measurement: {args.measurement}")
    print("设备写入统计:")
    for device_code, count in summary["device_counts"].items():
        print(f"  {device_code}: {count}")
        print(f"    时间范围: {summary['device_ranges'][device_code]}")
        print(f"    工况分布: {dict(summary['condition_counts'][device_code])}")
    if args.dry_run:
        print("dry-run: 未写入 InfluxDB")


if __name__ == "__main__":
    main()
