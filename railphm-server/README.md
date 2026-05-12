# railphm-server

高铁列控设备故障预测与健康管理系统（RailPHM）- 后端主服务

## 项目定位

`railphm-server` 是 RailPHM 的 Flask 后端主服务，负责统一 API、业务服务编排、mock Repository 数据访问、AI 推理服务调用、健康度计算和告警等级映射。

当前后端重点服务于毕业设计系统实现演示和前后端联调。代码已经形成 `API -> Service -> Repository -> Schema -> Response` 的分层结构，但数据层仍以 mock 数据为主，真实 MySQL 和 InfluxDB 尚未接入。

## 当前状态

- Task 1 - 最小 Flask 启动入口已完成。
- Task 2 - 最小配置管理能力已实现。
- Task 3 - 统一 JSON 响应封装已完成。
- Task 4 - `/api/v1/health` 健康检查接口已完成。
- Task 5 - `/api/v1/system/ping` 系统管理探针接口已完成。
- Task 6 - 全局统一异常处理已完成。
- Task 7 - 日志初始化与扩展占位已完成。
- Task 8 - 最小自动化测试已完成。
- Task 9 - MySQL 核心业务表结构设计与 DDL 落地已完成。
- Task 10 - InfluxDB measurement 设计与落地测试已完成。
- Task 11 - 设备管理接口骨架已完成。
- Task 12 - 历史监测数据查询接口骨架已完成。
- Task 13 - 风险结果查询接口骨架已完成。
- Task 14 - 告警列表接口骨架已完成。
- Task 15 - `railphm-ai` 最小 mock 推理服务已完成。
- Task 16 - 后端调用 AI mock 服务链路已完成。
- Task 17 - 健康度与告警映射规则已完成。
- mock 认证接口已完成，包括验证码、登录、当前用户和退出。
- 设备台账新增与编辑接口已完成 mock 版本，并限制为 `ADMIN` 角色。
- 告警状态更新接口已完成 mock 版本，并限制为 `OPS` 或 `ADMIN` 角色。

## 当前接口能力

### 健康检查

```text
GET /api/v1/health
```

### 系统探针

```text
GET /api/v1/system/ping
```

### 认证接口

```text
GET  /api/v1/auth/captcha
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout
```

当前认证为 mock 实现，内置 `ops` 和 `admin` 两类用户，通过固定 mock token 识别登录态。

### 设备接口

```text
GET  /api/v1/devices
POST /api/v1/devices
GET  /api/v1/devices/{device_id}
PUT  /api/v1/devices/{device_id}
```

设备列表支持 `device_id`、`car_no`、`device_status` 筛选和分页语义。新增、编辑接口当前基于内存 mock 数据实现，并要求 `ADMIN` 角色。

### 运行监测接口

```text
GET /api/v1/monitor/series
```

支持 `device_id`、`start_time`、`end_time` 查询参数。当前数据来自 mock 时序点，不查询真实 InfluxDB。

### 风险预测接口

```text
GET  /api/v1/predictions/latest
GET  /api/v1/predictions/history
POST /api/v1/predictions/infer
```

`latest` 和 `history` 当前查询 mock 风险结果。`infer` 会调用 `railphm-ai` 的 `POST /infer`，返回风险字段、健康度字段和本次推理的告警判定字段，但不写入历史趋势和告警记录。

### 实时仿真接口

```text
POST /api/v1/realtime/start
POST /api/v1/realtime/stop
POST /api/v1/realtime/reset
GET  /api/v1/realtime/state
GET  /api/v1/realtime/next
```

实时接口使用进程内状态模拟连续 ATP 监测数据流。`next` 每次按当前 `sample_index` 调用一次 `PredictionService.infer_prediction`，返回同口径的风险、健康度和告警判定结果，然后按 `step` 自动递增。该能力仅用于本地开发和演示，不启动后台线程，不使用 SSE/WebSocket，不写数据库。

### 告警接口

```text
GET   /api/v1/alerts
GET   /api/v1/alerts/{alert_id}
PATCH /api/v1/alerts/{alert_id}/status
```

告警列表支持分页、告警等级、告警状态和设备编号筛选。状态更新支持 `PENDING`、`PROCESSING`、`RESOLVED`，并要求 `OPS` 或 `ADMIN` 角色。

## 分层结构

当前后端采用以下分层方式：

```text
API -> Service -> Repository -> Schema -> Response
```

- `app/api/`：接收 HTTP 请求、读取参数、调用 Service。
- `app/service/`：完成参数校验、业务规则、流程编排。
- `app/repository/`：当前多数为 mock 数据访问层，后续替换为 MySQL / InfluxDB 查询。
- `app/schema/`：统一响应字段和 DTO 转换。
- `app/core/response.py`：统一 JSON 响应封装。
- `app/core/errors.py`：业务异常与全局异常处理。
- `app/core/auth.py`：mock token 解析与角色控制。

## 与 AI 服务的关系

后端通过 `app/clients/ai_client.py` 调用 `railphm-ai` 的 `POST /infer`。AI 服务地址和调用参数通过环境变量配置：

```text
AI_SERVICE_BASE_URL=http://127.0.0.1:5001
AI_INFER_PATH=/infer
AI_REQUEST_TIMEOUT_SECONDS=5
AI_ENABLE_FALLBACK=false
AI_DEFAULT_THRESHOLD=0.26
RISK_THRESHOLD_NORMAL=0.26
RISK_THRESHOLD_WARNING=0.45
RISK_THRESHOLD_CRITICAL=0.65
HEALTH_SCORE_DECIMALS=2
REALTIME_STREAM_ID=default
REALTIME_DEFAULT_DEVICE_ID=ATP001
REALTIME_DEFAULT_START_SAMPLE_INDEX=0
REALTIME_DEFAULT_END_SAMPLE_INDEX=
REALTIME_DEFAULT_STEP=1
REALTIME_DEFAULT_WINDOW_MINUTES=30
REALTIME_DEFAULT_MC_SAMPLES=20
REALTIME_DEFAULT_AUTO_WRAP=false
REALTIME_DEFAULT_TS_START=2026-05-01 10:00:00
REALTIME_TS_STEP_SECONDS=1
```

`POST /api/v1/predictions/infer` 会标准化返回 `risk_raw`、`risk_score`、`risk_std`、`threshold`、`predicted_label`、`model_version`、窗口时间、调试来源字段、健康度字段和本次推理的告警判定字段。AI 未返回 `threshold` 时，server 暂按 `AI_DEFAULT_THRESHOLD=0.26` 兜底；AI 不可用且 `AI_ENABLE_FALLBACK=true` 时，接口返回 `data_source=mock_fallback` 的 mock 结果。

即时推理接口的健康度映射规则为：

```text
health_score = round(100 * (1 - clipped_risk_score), HEALTH_SCORE_DECIMALS)
risk_score < 0.26          -> normal / 正常
0.26 <= risk_score < 0.45  -> attention / 关注
0.45 <= risk_score < 0.65  -> warning / 预警
risk_score >= 0.65         -> critical / 严重
```

即时推理接口的告警判定规则为：

```text
risk_score < 0.26          -> alert_generated=false / none / none
0.26 <= risk_score < 0.45  -> alert_generated=true  / low / unhandled
0.45 <= risk_score < 0.65  -> alert_generated=true  / medium / unhandled
risk_score >= 0.65         -> alert_generated=true  / high / unhandled
```

该阶段只返回告警判断和展示文案，不生成真实 `alert_id`，也不写入告警记录表。

`latest` 和 `history` 查询接口仍保留当前健康度与告警等级的后端规则：

当前健康度与告警等级的后端规则为：

```text
health_score = round((1 - risk_score) * 100, 1)
0 <= health_score <= 30    -> HIGH
30 < health_score <= 70    -> MEDIUM
70 < health_score <= 100   -> LOW
```

## 当前测试

`tests/` 目录已覆盖以下内容：

- 健康检查接口。
- 系统探针接口。
- 设备列表、详情、筛选、新增、编辑、权限控制和异常参数。
- 历史监测数据查询、时间参数校验和空结果结构。
- 风险最新结果、历史趋势、排序、参数校验和空结果结构。
- AI Client 字段校验和后端调用 AI mock 服务链路。
- 健康度计算和告警等级映射规则。
- 告警列表、详情、筛选、分页、状态更新和角色控制。
- 认证接口，包括验证码、登录、当前用户、退出和异常登录态。

## 启动与测试命令

### 启动服务

```bash
cd railphm-server
python run.py
```

默认地址：

```text
http://127.0.0.1:5000
```

### 运行测试

```bash
cd railphm-server
pytest
```

## 当前边界

1. 当前不连接真实 MySQL。
2. 当前不连接真实 InfluxDB。
3. 当前不加载真实模型。
4. 当前认证为 mock 版本，不是生产级安全方案。
5. 当前接口用于稳定前后端联调、系统实现演示和毕业设计开发记录。
