# RailPHM

高铁列控设备故障预测与健康管理系统（RailPHM）

## 项目简介

RailPHM 是面向高铁列控设备的故障预测与健康管理系统。本项目以 ATP 车载监测数据为核心，围绕设备运行状态监测、故障风险预测、设备健康度评估、告警管理、数据可视化和后台管理展开开发。

当前项目是毕业设计工程实现，仍处于 mock 数据搭建业务逻辑的初始阶段。后端、AI mock 服务和前端页面已经形成较完整的最小业务闭环，但真实 MySQL、InfluxDB 和真实模型推理尚未接入。

## 项目结构

```text
railphm
├── railphm-server              # Flask 后端主服务，提供统一 API、业务编排和 mock Repository
├── railphm-ai                  # 独立 AI mock 推理服务，用于跑通后端到模型服务的调用链路
├── railphm-web                 # Vue 3 + Vite 前端子项目，提供主业务页面和数据可视化
├── sql                         # MySQL DDL 与 InfluxDB measurement 设计说明
├── docs                        # 开发任务规划等项目文档
└── railphm-目录结构说明.md      # 项目目录结构说明文档
```

## 子项目说明

### railphm-server

`railphm-server` 是 Flask 后端主服务，负责统一 API 服务、业务服务编排、统一响应与异常处理，并提供设备、监测、预测、告警、认证等接口。当前后端通过 AI Client 调用 `railphm-ai` mock 推理服务，再在后端侧完成风险分数校验、健康度计算和告警级别映射。

当前后端采用 mock Repository，不连接真实 MySQL 或 InfluxDB。

### railphm-ai

`railphm-ai` 是独立 AI mock 推理服务，提供：

- `GET /health`
- `POST /infer`

该服务用于跑通 `railphm-web -> railphm-server -> railphm-ai` 的“假模型真流程”。当前不包含真实模型训练、真实模型加载、真实数据库访问，也未实现 Bi-LSTM + Attention、K-means 工况划分或 MC-Dropout 推理。

### railphm-web

`railphm-web` 是 Vue 3 + Vite 前端子项目。当前已完成登录页、Dashboard、系统联通测试、设备台账、设备详情、运行监测、风险预测、告警中心和 404 页面，并已完成路由守卫、Axios 请求层、ECharts 图表展示和页面间业务跳转。

### sql

`sql` 目录包含 MySQL 核心业务表 DDL 与 InfluxDB measurement 设计说明。当前主要用于数据库结构设计落地和后续真实接库准备，代码运行阶段尚未真正接入数据库查询。

## 当前开发进度

### 后端与 AI 服务

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
- 认证与登录接口已完成 mock 版本，包括验证码、登录、当前用户和退出。
- 设备台账新增与编辑接口已完成 mock 版本，并通过角色控制限制管理员操作。
- 告警状态更新接口已完成 mock 版本，并通过角色控制限制运维用户和管理员操作。

### 前端

- Task 18 - 前端基础启动与路由框架已完成。
- Task 19 - 仪表盘首页已完成。
- Task 20 - 设备台账页面已完成。
- Task 21 - 接入 ECharts 与通用图表组件已完成。
- Task 22 - 运行监测页面已完成。
- Task 23 - 风险预测趋势页面已完成。
- Task 24 - 告警中心页面已完成。
- Task 25 - 设备详情页增强已完成。
- 登录页与路由守卫已完成。
- 前端主业务页面链路已形成：设备台账 -> 设备详情 -> 运行监测 / 风险预测 / 告警记录。

## 当前系统能力

1. 后端主服务启动能力。
2. AI mock 服务独立启动能力。
3. 前端项目启动能力。
4. 统一响应封装和统一异常处理。
5. mock 登录、验证码、当前用户和退出能力。
6. 基础角色控制能力。
7. 设备台账查询、详情、新增、编辑能力。
8. 历史监测数据查询能力。
9. 风险最新结果查询、历史趋势查询能力。
10. 后端调用 AI mock 推理能力。
11. 风险分数到健康度、告警级别的业务映射能力。
12. 告警列表、详情、状态更新能力。
13. Dashboard 首页展示能力。
14. 设备台账页面展示、筛选、分页、详情跳转能力。
15. 设备详情页业务入口能力。
16. 运行监测页面 ECharts 曲线展示能力。
17. 风险预测页面趋势展示和 mock 推理演示能力。
18. 告警中心筛选、分页、详情查看与状态更新入口能力。

## 当前仍未完成

1. 尚未接入真实 MySQL Repository。
2. 尚未接入真实 InfluxDB 查询。
3. 尚未接入真实 Bi-LSTM + Attention 模型。
4. 尚未实现真实 K-means 工况划分。
5. 尚未实现真实保序回归概率校准。
6. 尚未实现真实 MC-Dropout 多次推理。
7. 预测结果尚未形成真实持久化闭环。
8. 当前鉴权仍为 mock 版本，不是生产级安全方案。

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
- ECharts

### 数据库

- MySQL
- InfluxDB

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

### 启动前端

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

### 后端

```bash
cd railphm-server
pytest
```

### AI 服务

```bash
cd railphm-ai
pytest
```

### 前端

```bash
cd railphm-web
npm run build
```

当前 `railphm-web/package.json` 未配置 lint 或单元测试脚本。

## 后续开发计划

阶段 1：本地 CSV 输入
阶段 2：真实数据预处理
阶段 3：滑动窗口构造
阶段 4：过渡版风险计算
阶段 5：K-means 工况识别替换占位逻辑
阶段 6：Bi-LSTM + Attention 模型训练与推理
阶段 7：保序回归概率校准
阶段 8：MC-Dropout 不确定性估计
阶段 9：预测结果写入 MySQL
阶段 10：从 InfluxDB 读取真实时序数据


