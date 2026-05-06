# railphm-server

高铁列控设备故障预测与健康管理系统（RailPHM）- 后端主服务

## 项目定位

`railphm-server` 是 RailPHM 的 Flask 后端主服务，负责统一 API、业务服务编排、mock Repository 数据访问、AI mock 服务调用、健康度计算和告警等级映射。

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

`latest` 和 `history` 当前查询 mock 风险结果。`infer` 会调用 `railphm-ai` 的 `POST /infer`，再由后端按规则补齐 `health_score` 和 `alert_level`。

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

后端通过 `app/clients/ai_client.py` 调用 `railphm-ai` 的 `POST /infer`。AI mock 服务返回风险分数、风险波动、工况标签和时间窗口等模型侧字段；后端负责校验字段、限制风险分数范围、计算健康度，并映射告警等级。

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
