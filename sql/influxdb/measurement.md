# InfluxDB Measurement 设计：atp_monitor_data

## 1. 业务描述
本 measurement 用于存储 ATP 车载设备的连续高频运行监测数据。
遵循双库协同架构：MySQL (`phm_monitor_segment`) 负责维护片段业务属性，InfluxDB (`atp_monitor_data`) 负责存储该片段下密集的时间序列点。

## 2. 数据模型 (Schema)
- **Measurement**: `atp_monitor_data`
- **Timestamp**: 时间戳 (毫秒级 Unix Timestamp，对应论文 `data_time`)

### 2.1 Tags (索引维度 - 字符串类型)
> **注意**：Tags 会建立倒排索引，用于 `WHERE` 或 `GROUP BY` 快速过滤。

| 字段名 | 含义 | 说明 |
| :--- | :--- | :--- |
| `device_id` | 设备ID | 从 MySQL 冗余，用于按设备快速拉取曲线 |
| `segment_id` | 片段ID | MySQL 连续监测片段表主键，核心关联枢纽 |
| `train_no` | 车次 | 从 MySQL 冗余，便于按车次宏观统计 |
| `line_id` | 线路编号 | 枚举值，低基数 |
| `direction` | 行别 | 枚举值 (如 "0": 上行, "1": 下行) |

### 2.2 Fields (测量值 - 无索引)
> **注意**：Fields 不建索引，支持数值聚合（如均值、最大值）或高维文本存储。Line Protocol 中整数必须带 `i` 后缀。

| 字段名 | 含义 | 类型 | 说明 |
| :--- | :--- | :--- | :--- |
| `speed` | 速度 | Float | 连续数值，核心监测特征 |
| `level_value` | 等级 | Integer | 连续/离散数值，写入需带 `i` (如 `3i`) |
| `mileage` | 里程 | Float | 连续数值 |
| `run_distance` | 运行距离 | Float | 连续数值 |
| `temperature` | 室外温度 | Float | 环境特征 |
| `humidity` | 湿度 | Float | 环境特征 |
| `balise_id` | 应答器编号 | String | 高基数文本，仅做展示附属 |
| `signal_id` | 信号机编号 | String | 高基数文本，仅做展示附属 |
| `atp_alarm_part`| 报警部位 | String | 文本状态描述 |
| `weather_info` | 天气信息 | String | 文本描述 |
| `source_uuid` | 源数据标识 | String | 极高基数，绝对禁止作为 Tag |

---

## 3. Line Protocol 样例 (写入示例)

使用 InfluxDB 行协议格式写入一条数据的标准示例：
*(时间戳采用毫秒精度：1776470400000 对应 2026-04-18 00:00:00 UTC)*

```text
atp_monitor_data,device_id=101,segment_id=20240418001,train_no=G123,line_id=1,direction=0 speed=310.5,level_value=3i,mileage=1250000.0,run_distance=5000.5,temperature=25.0,humidity=45.0,balise_id="B-1234",signal_id="S-5678",atp_alarm_part="none",weather_info="sunny",source_uuid="a1b2c3d4-e5f6-7890" 1776470400000