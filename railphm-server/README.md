# railphm-server

高铁列控设备故障预测与健康管理系统（RailPHM）- 后端主服务

## 当前状态
- Task 1 - 最小 Flask 启动入口已完成。
- Task 2 - 最小配置管理能力已实现。
- Task 3 - 统一 JSON 响应封装已完成。
- Task 4 - `/api/v1/health` 健康检查接口已完成。
- Task 5 - `/api/v1/system` 系统管理探针接口已完成。
- Task 6 - 全局统一异常处理已完成。
- Task 7 - 日志初始化与扩展占位已完成。
- Task 8 - 最小自动化测试已完成。
- Task 9 - MySQL 核心业务表结构设计与 DDL 落地已完成。
- Task 10 - InfluxDB measurement 设计与落地测试已完成。

## 开发进度说明

### Task 3 已完成：统一响应封装
- 已实现基于 `app/core/response.py` 的统一 JSON 响应封装。
- 当前统一使用 `success_response` 和 `error_response` 返回标准化 JSON。
- 为后续接口开发提供了统一响应结构基础，便于前后端联调与异常处理收口。

### Task 4 已完成：健康检查接口
- 已使用 Flask Blueprint 正式注册 `/api/v1/health` 接口，作为系统基础健康探针。
- 服务启动后可通过 `GET /api/v1/health` 获取标准状态响应。
- 原开发阶段用于验证响应封装的临时探针接口 `/__probe/response` 已清理，不再作为正式能力保留。

### Task 5 已完成：系统管理探针接口
- 已使用 Flask Blueprint 正式注册 `/api/v1/system` 接口，作为系统管理探针。
- 服务启动后可通过 `GET /api/v1/system` 获取标准状态响应。
- 同时已补充 `GET /api/v1/system/ping` 接口，作为最小骨架阶段的联通性验证接口，并已纳入自动化测试。

### Task 6 已完成：全局统一异常处理
- 当前已启用全局统一异常处理机制。
- 任何错误（如 404、500、业务异常）均会返回标准化 JSON，保持接口返回风格一致。
- 当前保留 `/__probe/business-error` 和 `/__probe/runtime-error` 两个临时探针接口，仅用于开发阶段调试验证异常处理链路，不作为生产接口使用。

### Task 7 已完成：日志初始化与扩展占位
- 已补充日志初始化能力，服务启动过程具备统一、规范、可读的日志输出。
- 已完成 `app/core/logging.py` 设计与接入。
- 已完成 `app/extensions/__init__.py` 扩展初始化入口设计。
- 已为后续 MySQL / InfluxDB 接入预留初始化占位，但当前阶段不连接真实数据库。
- 即使数据库配置缺失，当前服务仍可正常启动，不影响最小骨架运行。

### Task 8 已完成：最小自动化测试
- 已接入 `pytest`，用于固定当前后端最小可运行骨架。
- 已完成基础测试夹具与最小测试入口配置。
- 已完成以下接口自动化测试：
  - `GET /api/v1/health`
  - `GET /api/v1/system/ping`
- 当前可在 `railphm-server` 目录下直接执行 `pytest` 完成最小回归验证。
- 该阶段测试已为后续接口扩展、重构和联调提供基础保障。

### Task 9 已完成：MySQL 核心业务表结构设计与 DDL 落地
- 已完成 MySQL 侧核心业务表结构设计，并落地到 `sql/mysql/ddl/` 目录。
- 当前已完成的 6 张核心业务表如下：
  - `phm_device`
  - `phm_maintenance_record`
  - `phm_monitor_segment`
  - `phm_risk_result`
  - `phm_alert_record`
  - `phm_user`
- 已补齐主键、外键与必要索引，保证表之间关联关系清晰。
- 当前设计严格遵循论文与需求文档中 MySQL 业务数据边界，不将监测时序点表错误落入 MySQL。
- 已完成本地建表验证，支持通过以下方式检查：
  - `SHOW TABLES;`
  - `DESC 表名;`
  - `SHOW CREATE TABLE 表名;`
- 当前 MySQL DDL 已可作为后续后端接口开发、假数据构造、后台管理功能和联调阶段的结构基础。

### Task 10 已完成：InfluxDB measurement 设计与落地测试
- 已完成 ATP 监测时序数据的 InfluxDB measurement 建模设计。
- 当前 measurement 设计已明确：
  - measurement 名称
  - tags
  - fields
  - timestamp
- 已将设计结果落地到 `sql/influxdb/` 目录中的说明文件，作为后续时序数据接入与接口开发依据。
- 当前设计已覆盖后续高频查询所需的关键维度与指标，能够支撑：
  - 按设备编号 + 时间范围查询监测数据
  - 按 `segment_id` 查询连续监测片段数据
  - 历史监测曲线查询
  - 关键指标（如速度、等级、温度、湿度）图形化展示
- 已完成 sample line protocol 设计、手工写入验证与查询验证。
- 当前 InfluxDB measurement 设计已可作为后续监测数据查询接口与可视化模块的时序存储基础。

## 异常处理说明
当前已启用全局统一异常处理，任何错误（404/500/业务异常）均会返回标准化 JSON。  
当前保留 `/__probe/business-error` 和 `/__probe/runtime-error` 两个临时接口，仅供开发阶段调试使用，勿用于生产环境。

## 当前阶段成果总结
截至目前，`railphm-server` 已完成第一阶段最小可运行骨架建设，以及第二阶段数据库基础建模的关键工作，形成了较为完整的后端基础能力闭环：

1. 已具备后端主服务启动能力。
2. 已具备基础配置管理能力。
3. 已具备统一响应封装能力。
4. 已具备健康检查与系统探针接口。
5. 已具备全局统一异常处理。
6. 已具备日志初始化与扩展占位能力。
7. 已具备最小自动化测试能力。
8. 已完成 MySQL 业务表结构设计与验证。
9. 已完成 InfluxDB 时序 measurement 设计与验证。

## 当前目录建设进展
当前后端已逐步形成以下核心基础模块：
- `run.py`：服务启动入口
- `app/core/`：响应封装、异常处理、日志等核心能力
- `app/extensions/`：扩展初始化入口
- `tests/`：最小自动化测试
- `sql/mysql/ddl/`：MySQL 核心业务表 DDL
- `sql/influxdb/`：InfluxDB measurement 设计说明与样例

## 下一阶段建议
在当前阶段完成后，后续可继续推进以下方向：
1. 基于 MySQL 表结构落地 ORM 模型或数据访问层。
2. 基于 InfluxDB measurement 落地监测数据查询接口。
3. 开始设备台账、监测片段、风险结果、告警记录等业务接口开发。
4. 为前端联调补充基础列表查询、详情查询与时间范围查询能力。
5. 在算法未正式接入前，可先使用 mock 数据或占位服务打通风险预测与健康评估链路。

## 说明
- 当前项目严格遵循“前后端分离 + AI 服务独立 + 双库协同（MySQL + InfluxDB）”的总体架构思路。
- MySQL 负责业务管理与关联型数据。
- InfluxDB 负责 ATP 高频监测时序数据。
- 当前阶段尚未接入真实算法推理流程，重点完成的是后端最小骨架、数据库基础结构和时序数据建模能力。
- 后续开发将继续围绕论文定义的“状态感知 - 风险预测 - 健康评估 - 告警展示 - 运维管理”闭环逐步推进。