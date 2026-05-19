from typing import List, Dict, Any


class MonitorSchema:
    """
    监测数据序列化 (Schema)
    对外输出稳定字段，不暴露 InfluxDB 原始 _field/_value 结构。
    """

    OUTPUT_FIELDS = (
        "sample_time",
        "source_time",
        "speed",
        "mileage",
        "condition_label",
        "atp_type",
        "source_car_no",
        "source_train_no",
        "source_driver_id",
        "source_unique_id",
        "line_id",
        "direction",
        "station_name",
        "balise_id",
        "balise_mileage",
        "balise_type",
        "signal_id",
        "signal_name",
        "signal_mileage",
        "longitude",
        "latitude",
        "outdoor_temperature",
        "weather",
        "road_condition",
        "humidity",
        "alarm_part",
    )

    @classmethod
    def dump_history(
        cls,
        device_code: str,
        start_time: str,
        end_time: str,
        rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        series = []
        for row in rows:
            item = {field: row.get(field) for field in cls.OUTPUT_FIELDS if field in row}
            series.append(item)

        return {
            "device_code": device_code,
            "start_time": start_time,
            "end_time": end_time,
            "count": len(series),
            "data_source": "influxdb",
            "series": series,
        }

    @classmethod
    def format_to_series(cls, device_id: int, start: str, end: str, raw_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """兼容旧调用入口，内部使用新 history 输出格式。"""
        return cls.dump_history(str(device_id), start, end, raw_points)
