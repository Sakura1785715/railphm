# RailPHM 项目目录结构说明

## 1. 项目定位

RailPHM 是面向**高铁列控设备故障预测与健康管理**场景的毕业设计项目。
项目采用**前后端分离 + AI 服务独立**的工程结构，便于后续分别开展：

- 前端可视化页面开发
- 后端业务接口开发
- 模型训练与推理服务开发
- 数据库脚本与部署脚本管理
- 文档、测试、数据集、模型资产的统一沉淀

该目录结构适合毕业设计项目从 0 开发，也便于后期撰写：

- 需求文档
- 概要设计
- 数据库设计
- 接口文档
- 测试文档
- 部署文档

---

## 2. 顶层目录说明

### `docs/`
项目文档目录。

- `requirement/`：需求文档
- `design/`：概要设计、详细设计
- `api/`：接口文档
- `database/`：数据库设计说明
- `deploy/`：部署说明
- `test/`：测试文档
- `thesis-assets/`：论文配图、系统截图、答辩素材

### `scripts/`
项目脚本目录。

- `dev/`：本地开发启动脚本
- `deploy/`：部署脚本
- `data/`：数据导入、清洗、转换脚本
- `model/`：训练、推理、评估脚本

### `sql/`
数据库相关脚本目录。

- `mysql/ddl/`：MySQL 建表脚本
- `mysql/dml/`：初始化数据脚本
- `mysql/migration/`：数据库迁移脚本
- `influxdb/`：时序数据库相关脚本与样例数据

### `datasets/`
数据集目录。

- `raw/`：原始数据
- `interim/`：中间清洗数据
- `processed/`：训练/推理标准数据
- `demo/`：演示数据

### `models/`
模型资产目录。

- `checkpoints/`：模型权重
- `scalers/`：归一化器
- `clusterers/`：K-means 聚类模型
- `configs/`：模型配置文件
- `metadata/`：模型版本说明

### `logs/`
运行日志目录。

### `deploy/`
部署配置目录。

- `docker/`：Docker 配置
- `nginx/`：Nginx 配置
- `compose/`：docker-compose 配置

### `tests/`
集成测试目录。

- `api/`：接口测试
- `e2e/`：端到端测试
- `performance/`：性能测试

### `railphm-common/`
公共模块目录。

- `constants/`：常量定义
- `schemas/`：共享数据结构
- `utils/`：工具函数
- `exceptions/`：异常定义

### `railphm-server/`
后端主服务，建议使用 Flask。

主要职责：

- 提供 REST API
- 处理设备、监测数据、风险结果、健康度、告警、检修等业务
- 访问 MySQL / InfluxDB
- 调用 AI 推理服务

内部建议包含：

- `app/api/`：接口层
- `app/service/`：业务服务层
- `app/repository/`：数据访问层
- `app/model/`：实体对象
- `app/schema/`：请求/响应对象
- `app/core/`：配置、日志、鉴权、异常处理
- `app/tasks/`：定时任务
- `app/extensions/`：数据库、跨域等扩展初始化

### `railphm-ai/`
AI 与算法服务。

主要职责：

- 数据预处理
- K-means 工况识别
- Bi-LSTM + Attention 模型定义
- MC-Dropout 不确定性估计
- 健康度映射
- 训练与评估

### `railphm-web/`
前端系统，建议使用 Vue。

主要职责：

- 登录与权限页面
- 设备台账页面
- 监测数据展示页面
- 风险预测结果页面
- 健康度趋势页面
- 告警中心页面
- 仪表盘驾驶舱

---

## 3. 建议的开发顺序

建议从以下顺序推进：

1. 先搭建 `railphm-server` 后端基础框架
2. 再搭建 `railphm-web` 前端基础页面
3. 使用 `railphm-ai` 先实现 mock 推理接口
4. 再逐步替换为真实模型推理流程
5. 完成 MySQL 与 InfluxDB 的表结构和数据流转
6. 最后补齐测试、部署、答辩演示材料

---

## 4. 命名规范建议

### 项目命名

- 根项目：`railphm`
- 前端：`railphm-web`
- 后端：`railphm-server`
- AI 服务：`railphm-ai`
- 公共模块：`railphm-common`

### API 路径建议

统一使用：

- `/api/v1/devices`
- `/api/v1/monitor`
- `/api/v1/predictions`
- `/api/v1/health`
- `/api/v1/alerts`
- `/api/v1/maintenance`

### 数据库表命名建议

统一使用 `phm_` 前缀：

- `phm_device`
- `phm_monitor_segment`
- `phm_monitor_data`
- `phm_risk_result`
- `phm_alert_record`
- `phm_maintenance_record`
- `phm_user`

---

## 5. 适合毕业设计的优势

这套目录结构有以下优点：

1. 结构清晰，符合论文中的系统分层逻辑
2. 前后端、AI、数据库、文档、测试边界明确
3. 后续接入真实算法时不需要大改工程目录
4. 便于答辩时展示“系统模块 + 算法模块 + 数据模块”的完整性
5. 便于多人协作或阶段性提交代码

---

## 6. 后续建议

在目录创建完成后，建议下一步立即做三件事：

1. 初始化 Git 仓库与 `.gitignore`
2. 初始化 `railphm-server`、`railphm-web`、`railphm-ai` 三个子项目
3. 先跑通一个最小闭环：
   - 前端页面可访问
   - 后端接口可调用
   - AI 服务返回 mock 风险结果

