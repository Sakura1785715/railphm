# railphm-ai

`railphm-ai` 是 RailPHM 毕设项目中的独立 AI 服务。当前阶段定位为最小可运行的 mock inference service，用于先跑通“假模型真流程”，而不是接入真实模型训练或真实推理框架。

## 当前阶段定位

- 提供独立 HTTP 服务
- 暴露 `GET /health` 健康检查接口
- 暴露 `POST /infer` mock 推理接口
- 返回稳定、可预测的 mock 推理结果
- 代码结构预留未来替换为真实模型推理逻辑的空间

当前版本不包含：

- 真实模型训练
- 真实模型加载
- 数据库访问
- 消息队列
- 复杂鉴权与部署逻辑

## 项目结构

```text
railphm-ai/
├── app/
│   ├── api/
│   │   ├── health/
│   │   └── infer/
│   ├── core/
│   ├── repository/
│   ├── schema/
│   └── service/
├── tests/
├── run.py
├── requirements.txt
└── pytest.ini
```

## 安装依赖

推荐使用虚拟环境：

```bash
cd railphm-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 启动服务

```bash
cd railphm-ai
python run.py
```

默认启动地址：

- Host: `127.0.0.1`
- Port: `5001`

如需修改，可通过环境变量覆盖：

```bash
APP_HOST=0.0.0.0 APP_PORT=5001 python run.py
```

## 运行测试

```bash
cd railphm-ai
pytest
```

## 接口说明

### GET /health

用于服务健康检查。

示例响应：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "service": "railphm-ai",
    "status": "running",
    "version": "0.1.0"
  }
}
```

### POST /infer

用于执行 mock 推理。

请求头：

```text
Content-Type: application/json
```

请求体：

```json
{
  "device_id": 1,
  "ts_end": "2026-04-19 10:05:00",
  "window_minutes": 5
}
```

字段说明：

- `device_id`：必填，整数
- `ts_end`：必填，时间字符串，格式必须为 `YYYY-MM-DD HH:mm:ss`
- `window_minutes`：必填，正整数

成功响应示例：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "device_id": 1,
    "ts_end": "2026-04-19 10:05:00",
    "window_minutes": 5,
    "window_start_time": "2026-04-19 10:00:00",
    "window_end_time": "2026-04-19 10:05:00",
    "condition_label": "abnormal-trend",
    "risk_score": 0.82,
    "risk_std": 0.07,
    "health_score": 68.5,
    "alert_level": "HIGH",
    "model_version": "mock-bilstm-attention-v1"
  }
}
```

失败响应统一格式：

```json
{
  "code": 400,
  "message": "具体错误信息",
  "data": null
}
```

## mock 逻辑说明

当前 mock 结果基于 `device_id % 3` 做稳定映射，不使用随机数，便于前后端联调与测试复现：

- `device_id % 3 == 1`：高风险设备画像
- `device_id % 3 == 2`：中风险设备画像
- `device_id % 3 == 0`：低风险设备画像

其中：

- `window_start_time` 根据 `ts_end - window_minutes` 计算
- `model_version` 当前固定为 `mock-bilstm-attention-v1`
- `alert_level` 当前仅作为 demo 联调用的临时衍生字段

注意：未来更合理的设计是由 `railphm-server` 基于模型输出和业务规则统一判定告警等级，而不是由 AI 模型直接决定 `alert_level`。

## 如何替换为真实模型

后续如果需要接入真实模型，建议优先替换以下位置：

1. `app/repository/infer_repository.py`
   将当前 mock 结果生成逻辑替换为真实模型推理调用。
2. `app/service/infer_service.py`
   保留参数校验与业务编排，在这里组织预处理、推理和后处理流程。
3. `app/schema/infer_schema.py`
   如果真实模型输入输出格式变化，可在此处扩展请求与响应 schema。

这样可以尽量保持 API 路由层稳定，减少对外接口变动。
