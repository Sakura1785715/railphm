# railphm-server

高铁列控设备故障预测与健康管理系统 (RailPHM) - 后端主服务

## 当前状态
- Task 1 - 最小 Flask 启动入口已完成。
- Task 2 - 最小配置管理能力已实现。

### 开发进度说明
- **Task 3 已完成**: 实现了基于 `app/core/response.py` 的统一 JSON 响应封装 (`success_response`, `error_response`)。
- **Task 4 已完成**: 已使用 Flask Blueprint 正式注册 `/api/v1/health` 接口，作为系统基础健康度探针。服务启动后可通过 `GET /api/v1/health` 获取标准状态响应（原 Task 3 用于测试的临时探针 `/__probe/response` 已在此阶段清理）。
- **Task 5 已完成**: 已使用 Flask Blueprint 正式注册 `/api/v1/system` 接口，作为系统管理探针。服务启动后可通过 `GET /api/v1/system` 获取标准状态响应

- ### 异常处理说明
当前已启用全局统一异常处理，任何错误（404/500/业务异常）均会返回标准化 JSON。
存在 `/__probe/business-error` 和 `/__probe/runtime-error` 两个临时接口，仅供开发阶段调试使用，勿用于生产环境。