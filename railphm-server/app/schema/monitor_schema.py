from typing import List, Dict, Any

class MonitorSchema:
    """
    监测数据序列化 (Schema)
    """
    
    @staticmethod
    def format_to_series(device_id: int, start: str, end: str, raw_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        # 此处的 key 与原始 CSV 字典中的字段名保持一致 (如 Speed, Mileage)
        metrics_config = [
            {"key": "Speed", "name": "速度", "unit": "km/h"},
            {"key": "Mileage", "name": "里程", "unit": "m"},
            {"key": "RunDistance", "name": "运行距离", "unit": "m"}
        ]
        
        series_list = []
        for config in metrics_config:
            points = []
            for p in raw_points:
                if config["key"] in p:
                    # 将解析好的 datetime 对象格式化为前端所需的 YYYY-MM-DD HH:mm:ss
                    formatted_time = p["_parsed_datetime"].strftime("%Y-%m-%d %H:%M:%S")
                    points.append({
                        "time": formatted_time,
                        "value": p[config["key"]]
                    })
            
            series_list.append({
                # 返回给前端的 metric 标识推荐统一用小写
                "metric": config["key"].lower(),
                "name": config["name"],
                "unit": config["unit"],
                "points": points
            })
            
        return {
            "device_id": device_id,
            "start_time": start,
            "end_time": end,
            "series": series_list
        }