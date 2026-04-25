# railphm-web

高铁列控设备故障预测与健康管理系统（RailPHM）- 前端子项目

## 项目定位

`railphm-web` 是 RailPHM 系统的前端子项目，基于 Vue 3 + Vite 实现，主要用于展示设备运行状态、故障风险结果、健康度信息、告警记录和后台管理页面。

当前阶段前端已完成基础工程、路由框架、统一请求层、Dashboard 首页、设备台账页面、设备详情页、运行监测页面、风险预测趋势页面和告警中心页面。系统已经能够基于后端 mock 接口完成设备查询、运行监测、风险趋势展示、mock 推理演示、告警筛选与告警详情查看等核心前端业务流程。

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
- 设备详情页增强
- ECharts 图表基础能力
- 通用图表组件封装
- 运行监测页面
- 风险预测趋势页面
- mock 推理演示入口
- 告警中心页面
- 告警详情查看
- 设备相关页面间的业务跳转
- 404 页面

## 当前页面说明

| 路由 | 页面 | 当前状态 |
|---|---|---|
| `/` | Dashboard 首页 | 已完成 |
| `/health` | 系统联通测试页 | 已完成 |
| `/devices` | 设备台账页面 | 已完成 |
| `/devices/:id` | 设备详情页面 | 已完成增强，作为设备业务入口 |
| `/monitor` | 运行监测页面 | 已完成 |
| `/predictions` | 风险预测页面 | 已完成 |
| `/alerts` | 告警中心页面 | 已完成 |
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

当前已接入 ECharts，并通过原生实例封装通用图表组件，用于运行监测曲线、风险趋势曲线和健康度趋势曲线展示。

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

### 运行监测接口

```text
GET /api/v1/monitor/series
```

用于 `/monitor` 运行监测页面，支持 `device_id`、`start_time`、`end_time` 查询参数，并基于后端返回的 `series` 动态渲染监测曲线。当前展示指标以后端返回为准，例如 Speed、Mileage、RunDistance。

### 风险结果接口

```text
GET /api/v1/predictions/latest
GET /api/v1/predictions/history
POST /api/v1/predictions/infer
```

用于 Dashboard 首页、设备详情页和 `/predictions` 风险预测页面。其中 `/predictions` 页面已接入最新风险结果、历史风险趋势、健康度趋势和 mock 推理演示功能。

### 告警接口

```text
GET /api/v1/alerts
GET /api/v1/alerts/{alert_id}
```

用于 Dashboard 首页、设备详情页和 `/alerts` 告警中心页面。告警中心页面已支持告警列表、等级筛选、状态筛选、设备编号筛选、分页和告警详情查看。

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
- 当前图表组件用于运行监测、风险趋势和健康度趋势页面
- Task 21 不改变现有业务页面功能

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
- 支持从设备详情页携带 `device_id` 跳转后自动填充查询条件

### Task 23：风险预测趋势页面开发

已完成。

完成内容：

- 新增 `/predictions` 风险预测趋势页面
- 将 `/predictions` 从占位页面切换为真实业务页面
- 新增风险预测相关前端接口封装
- 接入 `GET /api/v1/predictions/latest`
- 接入 `GET /api/v1/predictions/history`
- 接入 `POST /api/v1/predictions/infer`
- 展示最新风险分数、健康度、风险波动、模型版本和分析窗口
- 基于历史风险结果绘制风险趋势折线图
- 基于历史风险结果绘制健康度趋势折线图
- 增加“触发一次 mock 推理”功能，用于演示 `railphm-web -> railphm-server -> railphm-ai` 调用链路
- 推理结果单独展示，不默认写入历史趋势，避免造成持久化误解
- 支持 AI 服务不可用时展示错误提示
- 支持 loading、error、empty 和参数缺失提示
- 支持从设备详情页携带 `device_id` 跳转后自动填充查询条件

### Task 24：告警中心页面开发

已完成。

完成内容：

- 新增 `/alerts` 告警中心页面
- 将 `/alerts` 从占位页面切换为真实业务页面
- 新增告警相关前端接口封装
- 接入 `GET /api/v1/alerts`
- 接入 `GET /api/v1/alerts/{alert_id}`
- 支持告警列表展示
- 支持告警等级筛选：HIGH、MEDIUM、LOW
- 支持告警状态筛选：PENDING、PROCESSING、RESOLVED
- 支持设备编号筛选
- 支持分页查看
- 支持点击告警记录查看详情
- 告警等级和告警状态已使用标签样式区分
- 告警详情区展示告警对象、告警来源、风险结果关联和处理信息等字段
- 已针对告警中心页面进行界面修复，优化了表格挤压、字段映射、时间换行、详情区域占比和操作入口可见性等问题
- 支持 loading、error、empty 和详情未选择状态
- 支持从设备详情页携带 `device_id` 跳转后自动填充筛选条件

### Task 25：设备详情页增强

已完成。

完成内容：

- 增强 `/devices/:id` 设备详情页面
- 设备详情页从基础信息展示页升级为设备业务入口页
- 接入 `GET /api/v1/devices/{device_id}` 获取设备基础信息
- 接入 `GET /api/v1/predictions/latest` 获取当前设备最新风险结果
- 接入 `GET /api/v1/alerts` 获取当前设备最近告警记录
- 展示设备 ID、车号、ATP 类型、配属铁路局和设备状态
- 展示最新风险分数、健康度、风险波动、模型版本和分析窗口
- 展示最近告警记录摘要
- 风险结果为空时显示友好空状态
- 最近告警为空时显示友好空状态
- 风险接口或告警接口异常时采用局部错误状态，不影响设备基础信息展示
- 增加快捷入口：
  - 查看运行监测
  - 查看风险趋势
  - 查看告警记录
- 快捷入口跳转时会携带当前 `device_id`
- `/monitor`、`/predictions`、`/alerts` 已支持从 URL query 中读取 `device_id` 并初始化筛选条件
- 设备不存在或设备 ID 非法时显示统一错误状态，并提供返回设备台账入口

## 页面间业务链路

当前前端已经形成较完整的设备业务链路：

```text
设备台账 /devices
        ↓
设备详情 /devices/:id
        ↓
运行监测 /monitor?device_id={device_id}
风险趋势 /predictions?device_id={device_id}
告警记录 /alerts?device_id={device_id}
```

该链路使设备台账不再只是静态列表，而是成为进入设备监测、风险分析和告警查看的统一入口，更符合高铁列控设备故障预测与健康管理系统的业务使用方式。

## 后续开发计划

前端后续可继续推进以下任务：

```text
Task 27：前端主业务页面联调复核
Task 28：页面细节优化与毕业设计截图整理
Task 29：真实数据库与真实模型接入后的前端适配
```

其中 Task 23、Task 24 和 Task 25 已完成，当前前端主业务页面已经基本成型。后续重点不再是新增大量页面，而是围绕接口联调、页面稳定性、视觉一致性和论文展示效果继续打磨。

## 当前阶段说明

当前前端已经具备基础页面、设备台账、设备详情、运行监测、风险预测和告警中心等核心业务页面。系统能够基于后端 mock 数据完成从设备查看、监测数据展示、风险趋势分析到告警记录查看的前端业务闭环。

当前项目仍然以 mock 数据和接口联调为主，尚未全面接入真实 MySQL、InfluxDB 和真实模型推理结果。前端开发应继续保持现有接口结构稳定，不要提前引入过多复杂状态管理。后续接入真实数据源时，应优先保持当前页面结构和接口封装方式不变，仅对数据来源和字段适配进行渐进式替换。
