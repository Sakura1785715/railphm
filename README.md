# RailPHM

高铁列控设备故障预测与健康管理系统（RailPHM）

## 项目简介

RailPHM 是面向高铁列控设备的故障预测与健康管理系统。本项目以 ATP 车载监测数据为核心，围绕设备运行状态监测、故障风险预测、健康度评估、告警展示和后台管理等功能展开开发，目标是为运维人员提供设备状态感知、风险预警和辅助研判支持。

系统整体采用前后端分离架构，并将模型推理能力拆分为独立 AI 服务。当前项目由三个子项目组成：

```text
railphm
├── railphm-server   # 后端主服务
├── railphm-ai       # AI mock / 推理服务
└── railphm-web      # 前端子项目
```

## 子项目说明

### railphm-server

`railphm-server` 是系统后端主服务，基于 Flask 实现，主要负责：

- 统一 API 接口服务
- 统一 JSON 响应封装
- 全局异常处理
- 设备台账查询
- 历史监测数据查询
- 风险结果查询
- 告警记录查询
- 调用独立 AI 推理服务
- 根据风险分数计算健康度与告警级别

当前后端已形成较稳定的分层结构：

```text
API -> Service -> Repository -> Schema -> Response
```

### railphm-ai

`railphm-ai` 是独立 AI 服务。当前阶段定位为 mock inference service，用于先跑通“假模型真流程”，即先完成后端到 AI 服务的调用链路，后续再逐步替换为真实模型推理逻辑。

当前 AI 服务提供：

- `GET /health`
- `POST /infer`

### railphm-web

`railphm-web` 是前端子项目，基于 Vue 3 + Vite 实现，主要负责系统页面展示、接口联调和运维业务交互。

当前前端已完成：

- Vue 3 + Vite 基础工程
- Vue Router 路由
- Axios 请求层封装
- 基础 Layout
- Dashboard 首页
- 设备台账页面
- 设备详情入口
- 运行监测、风险预测、告警中心占位路由

## 当前开发进度

截至目前，项目已完成以下核心任务：

### 后端与 AI 服务

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
- Task 11 - 设备管理接口骨架已完成。
- Task 12 - 历史监测数据查询接口骨架已完成。
- Task 13 - 风险结果查询接口骨架已完成。
- Task 14 - 告警列表接口骨架已完成。
- Task 15 - `railphm-ai` 最小 mock 推理服务已完成。
- Task 16 - 后端调用 AI mock 服务链路已完成。
- Task 17 - 健康度与告警映射规则已完成。

### 前端

- Task 18 - 前端基础启动与路由框架已完成。
- Task 19 - 仪表盘首页已完成。
- Task 20 - 设备台账页面已完成。

## 当前系统能力

当前项目已形成从后端基础探针、设备查询、监测数据查询、风险结果查询、AI mock 推理调用、健康度映射、告警级别生成到前端首页和设备台账展示的最小业务闭环。

当前已具备：

1. 后端主服务启动能力。
2. AI mock 服务独立启动能力。
3. 前端项目启动能力。
4. 后端统一响应和统一异常处理能力。
5. 设备台账查询接口。
6. 历史监测数据查询接口。
7. 风险结果查询接口。
8. 告警记录查询接口。
9. 后端调用 AI mock 服务能力。
10. 风险分数到健康度、告警级别的业务映射能力。
11. Dashboard 首页展示能力。
12. 设备台账页面展示与筛选能力。
13. 设备详情入口。

## 技术栈

### 后端

- Python
- Flask
- Pytest
- Requests
- MySQL
- InfluxDB

### AI 服务

- Python
- Flask
- Pytest

### 前端

- Vue 3
- Vite
- Vue Router
- Axios

## 启动方式

### 启动后端主服务

```bash
cd railphm-server
python run.py
```

默认地址：

```text
http://127.0.0.1:5000
```

### 启动 AI mock 服务

```bash
cd railphm-ai
python run.py
```

默认地址：

```text
http://127.0.0.1:5001
```

### 启动前端服务

```bash
cd railphm-web
npm install
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

## 测试方式

### 后端测试

```bash
cd railphm-server
pytest
```

### AI 服务测试

```bash
cd railphm-ai
pytest
```

### 前端构建测试

```bash
cd railphm-web
npm run build
```

## 当前阶段说明

当前项目仍处于 mock 数据与前后端联调阶段。设备、监测数据、风险结果和告警记录目前主要通过 mock repository 提供，尚未全面接入真实 MySQL 与 InfluxDB。AI 服务当前也仍为 mock 推理服务，尚未接入真实神经网络模型、概率校准和 MC-Dropout 不确定性估计。

当前阶段的重点不是一次性完成真实数据库和真实模型接入，而是先保证系统接口结构、业务闭环和前端页面稳定，为后续真实数据源和真实模型替换打好基础。

## 后续开发方向

后续开发按照 `docs/development-task-plan.md` 中的任务规划继续推进，推荐优先顺序如下：

```text
Task 21：接入 ECharts 与通用图表组件
Task 22：运行监测页面开发
Task 23：风险预测趋势页面开发
Task 24：告警中心页面开发
Task 25：设备详情页增强
Task 26：前端 README 与页面说明更新
Task 27：告警状态更新接口
Task 28：告警中心前端接入状态更新
Task 29：设备台账新增与编辑接口
Task 30：设备台账前端新增与编辑
```

完成上述任务后，系统将具备较完整的前后端业务展示能力，可支撑大部分论文截图、功能测试和答辩演示。之后再逐步推进真实 MySQL、InfluxDB、真实 AI 推理、系统测试和最终交付。