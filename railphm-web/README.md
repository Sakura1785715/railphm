# railphm-web

高铁列控设备故障预测与健康管理系统（RailPHM）- 前端子项目

## 项目定位

`railphm-web` 是 RailPHM 系统的前端子项目，基于 Vue 3 + Vite 实现，主要用于展示设备运行状态、故障风险结果、健康度信息、告警记录和后台管理页面。

当前阶段前端已完成基础工程、路由框架、统一请求层、Dashboard 首页、设备台账页面、设备详情入口和运行监测页面。风险预测和告警中心页面已经预留路由入口，后续将逐步接入完整业务页面。

## 当前已完成能力

当前前端已完成：

- Vue 3 + Vite 基础工程搭建
- Vue Router 路由配置
- Axios 请求层封装
- Vite 开发代理配置
- 基础 Layout 与导航结构
- 系统联通测试页
- Dashboard 首页
- 设备台账页面
- 设备详情入口
- ECharts 图表基础能力
- 通用图表组件封装
- 运行监测页面
- 风险预测占位路由
- 告警中心占位路由
- 404 页面

## 当前页面说明

| 路由 | 页面 | 当前状态 |
|---|---|---|
| `/` | Dashboard 首页 | 已完成 |
| `/health` | 系统联通测试页 | 已完成 |
| `/devices` | 设备台账页面 | 已完成 |
| `/devices/:id` | 设备详情页面 | 已完成基础入口 |
| `/monitor` | 运行监测页面 | 已完成 |
| `/predictions` | 风险预测页面 | 占位，待 Task 23 开发 |
| `/alerts` | 告警中心页面 | 占位，待 Task 24 开发 |
| 其他路径 | 404 页面 | 已完成 |

## 当前目录结构

```text
railphm-web
├── index.html
├── package.json
├── vite.config.js
└── src
    ├── api
    │   ├── alert.js
    │   ├── device.js
    │   ├── health.js
    │   ├── http.js
    │   ├── monitor.js
    │   └── prediction.js
    ├── components
    │   ├── chart
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

当前已接入 ECharts，并通过原生实例封装通用图表组件，用于支撑后续运行监测曲线、风险趋势曲线和健康度趋势曲线展示。

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

## 接口联调说明

前端请求基础路径由环境变量控制：

```text
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://127.0.0.1:5000
```

当前 Vite 代理会将 `/api` 请求转发到后端主服务。

例如前端请求：

```text
/api/v1/devices
```

实际会代理到：

```text
http://127.0.0.1:5000/api/v1/devices
```

## 当前已接入接口

### 健康检查

```text
GET /api/v1/health
```

用于系统联通测试页和 Dashboard 首页服务状态展示。

### 设备接口

```text
GET /api/v1/devices
GET /api/v1/devices/{device_id}
```

用于设备台账页面、设备详情页和 Dashboard 首页设备概况展示。

### 风险结果接口

```text
GET /api/v1/predictions/latest
GET /api/v1/predictions/history
```

当前 Dashboard 首页已使用最新风险结果接口展示默认设备健康概况。风险趋势页面将在后续任务中进一步接入历史风险结果。

### 告警接口

```text
GET /api/v1/alerts
GET /api/v1/alerts/{alert_id}
```

当前 Dashboard 首页已使用告警列表接口展示告警数量。告警中心页面将在后续任务中完整接入。

### 运行监测接口

```text
GET /api/v1/monitor/series
```

用于 `/monitor` 运行监测页面，支持 `device_id`、`start_time`、`end_time` 查询参数，并基于后端返回的 `series` 动态渲染监测曲线。当前展示指标以后端返回为准，例如 Speed、Mileage、RunDistance。

## 当前页面开发进度

### Task 18：前端基础启动与路由框架

已完成。

完成内容：

- Vue 3 + Vite 工程初始化
- Vue Router 路由接入
- 基础 Layout
- Axios 请求层封装
- `/health` 联通测试页
- Vite 代理配置

### Task 19：仪表盘首页

已完成。

当前 Dashboard 首页展示：

- 系统服务状态
- 设备总数
- 告警数量
- 默认设备健康概况
- 最新风险结果摘要
- 快速跳转入口
- 风险结果结构化明细

### Task 20：设备台账页面

已完成。

当前设备台账页面支持：

- 设备列表展示
- 设备编号筛选
- 车号筛选
- 设备状态筛选
- 分页
- 设备详情跳转
- 加载状态
- 空数据状态
- 错误重试

### Task 21：接入 ECharts 与通用图表组件

已完成。

完成内容：

- 已接入 ECharts 依赖
- 已新增通用图表组件 `BaseChart`
- 已新增通用折线趋势组件 `LineTrendChart`
- 已新增单指标趋势组件 `MetricTrendChart`
- 图表组件支持 loading、empty、error 和 normal 状态
- 图表组件支持响应式 resize，并在卸载时释放 ECharts 实例
- 当前图表组件用于后续运行监测、风险趋势和健康度趋势页面
- Task 21 不改变现有业务页面功能，不提前实现 Task 22、Task 23 或 Task 24

### Task 22：运行监测页面

已完成。

完成内容：

- 新增 `/monitor` 运行监测页面
- 新增 `GET /api/v1/monitor/series` 前端接口封装
- 支持 `device_id`、`start_time`、`end_time` 查询
- 默认查询参数匹配当前后端 mock 数据时间范围
- 基于后端返回 `series` 动态渲染多指标趋势图和单指标趋势图
- 当前展示指标以后端返回为准，例如 Speed、Mileage、RunDistance
- 支持 loading、error、empty 和参数缺失提示
- Task 22 不改变 Dashboard、设备台账、设备详情和系统联通测试页功能

## 后续开发计划

前端后续优先完成以下任务：

```text
Task 23：风险预测趋势页面开发
Task 24：告警中心页面开发
Task 25：设备详情页增强
Task 26：前端 README 与页面说明更新
```

Task 21 和 Task 22 已完成，后续将继续推进风险趋势曲线、健康度趋势曲线和告警中心业务页面。

## 当前阶段说明

当前前端已经具备基础页面、设备业务页面和运行监测可视化页面。`/predictions` 和 `/alerts` 当前仍为占位入口，后续将逐步替换为真实业务页面。

当前项目仍然以 mock 数据和接口联调为主，尚未全面接入真实 MySQL、InfluxDB 和真实模型推理结果。前端开发应优先保持现有接口结构稳定，不要提前引入过多复杂状态管理。
