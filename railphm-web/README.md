# railphm-web

高铁列控设备故障预测与健康管理系统（RailPHM）- 前端子项目

## 项目定位

`railphm-web` 是 RailPHM 系统的前端子项目，基于 Vue 3 + Vite 实现，主要用于展示设备运行状态、故障风险结果、设备健康度、告警记录和后台管理页面。

当前前端已经完成登录页、路由守卫、统一请求层、Dashboard 首页、系统联通测试、设备台账、设备详情、运行监测、风险预测趋势和告警中心页面。系统能够基于后端 mock 接口完成设备查询、运行监测、风险趋势展示、mock 推理演示、告警筛选、告警详情查看和部分状态更新等核心前端业务流程。

## 当前已完成能力

- Vue 3 + Vite 基础工程搭建。
- Vue Router 路由配置。
- `/login` 登录页面。
- 路由守卫，未登录访问业务页会跳转到登录页。
- Axios 请求层封装和 Bearer token 注入。
- Vite 开发代理配置。
- 基础 Layout 与导航结构。
- 系统联通测试页。
- Dashboard 首页。
- 设备台账页面。
- 设备新增与编辑弹窗入口，按 mock 角色控制展示。
- 设备详情页增强。
- ECharts 图表基础能力。
- 通用图表组件封装。
- 运行监测页面。
- 风险预测趋势页面。
- mock 推理演示入口。
- 告警中心页面。
- 告警详情查看。
- 告警状态更新入口。
- 设备相关页面间的业务跳转。
- 404 页面。

## 当前页面说明

| 路由 | 页面 | 当前状态 |
|---|---|---|
| `/login` | 登录页面 | 已完成 |
| `/` | Dashboard 首页 | 已完成 |
| `/health` | 系统联通测试页 | 已完成 |
| `/devices` | 设备台账页面 | 已完成 |
| `/devices/:id` | 设备详情页面 | 已完成增强，作为设备业务入口 |
| `/monitor` | 运行监测页面 | 已完成 |
| `/predictions` | 风险预测页面 | 已完成 |
| `/alerts` | 告警中心页面 | 已完成 |
| 其他路径 | 404 页面 | 已完成 |

## 页面间业务链路

当前前端主业务链路为：

```text
登录 /login
    ↓
Dashboard /
    ↓
设备台账 /devices
    ↓
设备详情 /devices/:id
    ↓
运行监测 /monitor?device_id={device_id}
风险预测 /predictions?device_id={device_id}
告警中心 /alerts?device_id={device_id}
```

该链路使设备台账成为进入设备监测、风险分析和告警查看的统一入口。

## 当前目录结构

```text
railphm-web
├── index.html
├── package.json
├── vite.config.js
└── src
    ├── api
    │   ├── alert.js
    │   ├── auth.js
    │   ├── device.js
    │   ├── health.js
    │   ├── http.js
    │   ├── monitor.js
    │   └── prediction.js
    ├── components
    │   ├── chart
    │   ├── common
    │   ├── dashboard
    │   └── device
    ├── constants
    ├── layouts
    ├── router
    ├── styles
    ├── utils
    └── views
```

## 技术栈

- Vue 3
- Vite
- Vue Router
- Axios
- ECharts

## 启动方式

### 安装依赖

```bash
cd railphm-web
npm install
```

### 启动开发服务

```bash
npm run dev
```

默认开发地址：

```text
http://127.0.0.1:5173
```

### 构建测试

```bash
npm run build
```

### 本地预览构建结果

```bash
npm run preview
```

当前 `package.json` 未配置 lint 或单元测试脚本。

## 接口联调说明

前端请求基础路径由环境变量控制：

```text
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://127.0.0.1:5000
```

当前 Vite 代理会将 `/api` 请求转发到后端主服务。例如前端请求：

```text
/api/v1/devices
```

实际会代理到：

```text
http://127.0.0.1:5000/api/v1/devices
```

## 当前已接入接口

### 认证接口

```text
GET  /api/v1/auth/captcha
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout
```

用于登录页、登录态保存、当前用户识别和退出登录。当前鉴权为 mock token 方案。

### 健康检查

```text
GET /api/v1/health
```

用于系统联通测试页和 Dashboard 首页服务状态展示。

### 设备接口

```text
GET  /api/v1/devices
POST /api/v1/devices
GET  /api/v1/devices/{device_id}
PUT  /api/v1/devices/{device_id}
```

用于设备台账页面、设备详情页和 Dashboard 首页设备概况展示。新增与编辑能力当前通过 mock 角色控制，仅管理员可操作。

### 运行监测接口

```text
GET /api/v1/monitor/series
```

用于 `/monitor` 运行监测页面，支持 `device_id`、`start_time`、`end_time` 查询参数，并基于后端返回的 `series` 动态渲染监测曲线。当前展示指标以后端返回为准，例如 `Speed`、`Mileage`、`RunDistance`。

### 风险结果接口

```text
GET  /api/v1/predictions/latest
GET  /api/v1/predictions/history
POST /api/v1/predictions/infer
```

用于 Dashboard 首页、设备详情页和 `/predictions` 风险预测页面。其中 `/predictions` 页面已接入最新风险结果、历史风险趋势、健康度趋势和 mock 推理演示功能。

### 告警接口

```text
GET   /api/v1/alerts
GET   /api/v1/alerts/{alert_id}
PATCH /api/v1/alerts/{alert_id}/status
```

用于 Dashboard 首页、设备详情页和 `/alerts` 告警中心页面。告警中心页面已支持告警列表、等级筛选、状态筛选、设备编号筛选、分页、告警详情查看和状态更新入口。

## 当前页面开发进度

### Task 18：前端基础启动与路由框架

已完成。

完成内容：

- Vue 3 + Vite 工程初始化。
- Vue Router 路由接入。
- 基础 Layout。
- Axios 请求层封装。
- `/health` 联通测试页。
- Vite 代理配置。
- `/login` 登录页和路由守卫。

### Task 19：仪表盘首页

已完成。

当前 Dashboard 首页展示：

- 系统服务状态。
- 设备总数。
- 告警数量。
- 默认设备健康概况。
- 最新风险结果摘要。
- 快速跳转入口。
- 风险结果结构化明细。

### Task 20：设备台账页面

已完成。

当前设备台账页面支持：

- 设备列表展示。
- 设备编号筛选。
- 车号筛选。
- 设备状态筛选。
- 分页。
- 设备详情跳转。
- 管理员新增设备。
- 管理员编辑设备。
- 加载状态。
- 空数据状态。
- 错误重试。

### Task 21：接入 ECharts 与通用图表组件

已完成。

完成内容：

- 已接入 ECharts 依赖。
- 已新增通用图表组件 `BaseChart`。
- 已新增通用折线趋势组件 `LineTrendChart`。
- 已新增单指标趋势组件 `MetricTrendChart`。
- 图表组件支持 loading、empty、error 和 normal 状态。
- 图表组件支持响应式 resize，并在卸载时释放 ECharts 实例。
- 当前图表组件用于运行监测、风险趋势和健康度趋势页面。

### Task 22：运行监测页面

已完成。

完成内容：

- 新增 `/monitor` 运行监测页面。
- 新增 `GET /api/v1/monitor/series` 前端接口封装。
- 支持 `device_id`、`start_time`、`end_time` 查询。
- 默认查询参数匹配当前后端 mock 数据时间范围。
- 基于后端返回 `series` 动态渲染多指标趋势图和单指标趋势图。
- 当前展示指标以后端返回为准，例如 `Speed`、`Mileage`、`RunDistance`。
- 支持 loading、error、empty 和参数缺失提示。
- 支持从设备详情页携带 `device_id` 跳转后自动填充查询条件。

### Task 23：风险预测趋势页面开发

已完成。

完成内容：

- 新增 `/predictions` 风险预测趋势页面。
- 新增风险预测相关前端接口封装。
- 接入 `GET /api/v1/predictions/latest`。
- 接入 `GET /api/v1/predictions/history`。
- 接入 `POST /api/v1/predictions/infer`。
- 展示最新风险分数、健康度、风险波动、模型版本和分析窗口。
- 基于历史风险结果绘制风险趋势折线图。
- 基于历史风险结果绘制健康度趋势折线图。
- 增加“触发一次 mock 推理”功能，用于演示 `railphm-web -> railphm-server -> railphm-ai` 调用链路。
- 推理结果单独展示，不默认写入历史趋势，避免造成持久化误解。
- 支持 AI 服务不可用时展示错误提示。
- 支持 loading、error、empty 和参数缺失提示。
- 支持从设备详情页携带 `device_id` 跳转后自动填充查询条件。

### Task 24：告警中心页面开发

已完成。

完成内容：

- 新增 `/alerts` 告警中心页面。
- 新增告警相关前端接口封装。
- 接入 `GET /api/v1/alerts`。
- 接入 `GET /api/v1/alerts/{alert_id}`。
- 接入 `PATCH /api/v1/alerts/{alert_id}/status`。
- 支持告警列表展示。
- 支持告警等级筛选：`HIGH`、`MEDIUM`、`LOW`。
- 支持告警状态筛选：`PENDING`、`PROCESSING`、`RESOLVED`。
- 支持设备编号筛选。
- 支持分页查看。
- 支持点击告警记录查看详情。
- 支持告警状态更新入口。
- 告警等级和告警状态已使用标签样式区分。
- 支持 loading、error、empty 和详情未选择状态。
- 支持从设备详情页携带 `device_id` 跳转后自动填充筛选条件。

### Task 25：设备详情页增强

已完成。

完成内容：

- 增强 `/devices/:id` 设备详情页面。
- 设备详情页从基础信息展示页升级为设备业务入口页。
- 接入 `GET /api/v1/devices/{device_id}` 获取设备基础信息。
- 接入 `GET /api/v1/predictions/latest` 获取当前设备最新风险结果。
- 接入 `GET /api/v1/alerts` 获取当前设备最近告警记录。
- 展示设备 ID、车号、ATP 类型、配属铁路局和设备状态。
- 展示最新风险分数、健康度、风险波动、模型版本和分析窗口。
- 展示最近告警记录摘要。
- 风险结果为空时显示友好空状态。
- 最近告警为空时显示友好空状态。
- 风险接口或告警接口异常时采用局部错误状态，不影响设备基础信息展示。
- 增加快捷入口：查看运行监测、查看风险趋势、查看告警记录。
- 快捷入口跳转时会携带当前 `device_id`。
- `/monitor`、`/predictions`、`/alerts` 已支持从 URL query 中读取 `device_id` 并初始化筛选条件。
- 设备不存在或设备 ID 非法时显示统一错误状态，并提供返回设备台账入口。

## 当前阶段说明

当前前端已经具备登录、Dashboard、设备台账、设备详情、运行监测、风险预测和告警中心等核心业务页面。系统能够基于后端 mock 数据完成从登录、设备查看、监测数据展示、风险趋势分析到告警记录查看的前端业务闭环。

当前前端仍依赖后端 mock 接口，真实 MySQL、InfluxDB 和真实 AI 模型接入后，需要继续复核字段、状态枚举、错误提示和页面展示效果。

## 后续开发计划

- 前后端主业务页面联调复核。
- 页面细节优化与毕业设计截图整理。
- 真实数据库与真实模型接入后的前端适配。
- 系统测试文档与论文第六章测试结果对齐。
