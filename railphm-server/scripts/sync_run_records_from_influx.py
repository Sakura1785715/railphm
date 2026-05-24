"""
从 InfluxDB 同步运行记录池。

脚本只负责命令行参数和 app context，聚合与写库逻辑在 RunRecordSyncService。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.service.run_record_sync_service import RunRecordSyncService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync RailPHM run records from InfluxDB.")
    parser.add_argument("--start-time", required=True, help="开始时间，格式 YYYY-MM-DD HH:mm:ss")
    parser.add_argument("--end-time", required=True, help="结束时间，格式 YYYY-MM-DD HH:mm:ss")
    parser.add_argument("--device-codes", default=None, help="逗号分隔的设备编号，如 ATP001,ATP002")
    parser.add_argument("--measurement", default=None, help="InfluxDB measurement，默认使用配置")
    parser.add_argument("--limit-segments", type=int, default=None, help="最多同步的片段数")
    return parser.parse_args()


def parse_device_codes(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def main() -> None:
    args = parse_args()
    app = create_app()
    with app.app_context():
        summary = RunRecordSyncService.sync_from_influx(
            start_time=args.start_time,
            end_time=args.end_time,
            device_codes=parse_device_codes(args.device_codes),
            measurement=args.measurement,
            limit_segments=args.limit_segments,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
