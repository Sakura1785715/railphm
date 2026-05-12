# RailPHM 预测模块真实数据驱动开发任务计划书

## 一、当前阶段定位

当前系统已经完成了 mock 阶段的前后端业务链路。`railphm-server` 现在已经可以通过 `/api/v1/predictions/infer` 调用 `railphm-ai` 的推理服务，并在 server 侧完成 `risk_score -> health_score -> alert_level` 的业务解释。这个职责划分应继续保留，AI 服务负责风险预测，server 负责健康度映射和告警等级判断。

接下来要做的不是推翻当前结构，而是把 `railphm-ai` 内部从“固定 mock 推理结果”升级为“基于本地 ATP CSV 数据的真实预测流程骨架”。

本阶段目标可以概括为一句话：

> 让 `/infer` 接口真正读取 ATP 连续时间片段 CSV，经过预处理、窗口构造和过渡版风险计算后，返回标准风险预测结果。

---

## 二、本阶段开发目标

本阶段开发目标是完成：

> `railphm-ai` 真实数据输入与预测流程骨架

具体包括：

1. 支持从本地 CSV 文件读取 ATP 连续时间片段数据；
2. 支持解析 `datetime` 字段，并按照时间顺序整理数据；
3. 支持基础数据预处理，包括缺失值处理、数值字段筛选、归一化等；
4. 支持根据 `ts_end` 和 `window_minutes` 构造预测时间窗口；
5. 支持基于真实数据特征计算过渡版 `risk_score`；
6. 支持返回 `risk_score`、`risk_std`、`condition_label`、`model_version` 等标准字段；
7. 保持 `railphm-server` 现有 `AIClient` 调用方式不变；
8. 保持前端风险预测页面可以继续正常展示结果。

---

## 三、本阶段暂不开发内容

为了避免任务过大，本阶段暂时不做以下内容：

1. 暂不训练真实 Bi-LSTM + Attention 模型；
2. 暂不加载真实 `.pt / .pth` 模型权重；
3. 暂不实现正式 K-means 聚类模型文件加载；
4. 暂不实现保序回归概率校准；
5. 暂不实现 MC-Dropout 多次随机推理；
6. 暂不从 InfluxDB 读取真实时序数据；
7. 暂不强制将预测结果写入 MySQL；
8. 暂不改动 `railphm-web` 的页面结构。

但是，代码结构必须为这些后续能力预留替换点，不能写成一次性脚本。

---

## 四、总体开发原则

本阶段开发必须遵守以下原则。

### 4.1 接口不乱改

`railphm-server` 当前依赖 `railphm-ai` 返回 `device_id`、`ts_end`、`window_minutes`、`window_start_time`、`window_end_time`、`condition_label`、`risk_score`、`risk_std`、`model_version` 等字段，后续不能随意删改这些字段。`AIClient` 当前已经把这些字段作为必要字段校验，因此本阶段必须继续兼容。

### 4.2 风险分数必须来自真实 CSV 数据

可以暂时不用 Bi-LSTM，但不能继续用 `device_id % 3` 这种固定 mock 方式。现在 `railphm-ai` 的 mock repository 是根据设备 ID 返回固定风险画像，这一步需要被替换。

### 4.3 健康度和告警等级继续放在 server 侧

`railphm-ai` 只输出风险分数和不确定性估计字段，`health_score` 和 `alert_level` 仍由 `railphm-server` 计算。当前 server 侧已有稳定规则，应该继续保留。

### 4.4 按小任务逐步推进，每步完成后测试

继续使用你现在的 vibe coding 模式，每完成一个任务都跑对应测试，不要一次性大改。

---

## 五、建议目录结构

建议在 `railphm-ai/app` 下新增 `ml` 目录：

```text
railphm-ai/app/ml/
├── __init__.py
├── data_loader.py
├── preprocess.py
├── window_builder.py
├── condition_recognizer.py
├── transitional_risk_model.py
├── predictor.py
└── postprocess.py
```

每个文件职责如下：

| 文件 | 职责 |
|---|---|
| `data_loader.py` | 根据配置读取本地 ATP CSV 文件 |
| `preprocess.py` | 完成时间解析、排序、缺失值处理、字段筛选、归一化 |
| `window_builder.py` | 根据 `ts_end` 和 `window_minutes` 构造预测窗口 |
| `condition_recognizer.py` | 先实现规则版工况识别，后续替换 K-means |
| `transitional_risk_model.py` | 基于真实数据特征计算过渡版风险分数 |
| `predictor.py` | 串联完整预测流程 |
| `postprocess.py` | 统一裁剪风险分数、生成标准输出字段 |

这个目录结构后续可以自然演进：

```text
transitional_risk_model.py
    ↓ 后续替换
bilstm_attention_model.py
```

```text
condition_recognizer.py
    ↓ 后续替换内部逻辑
K-means 工况识别
```

```text
postprocess.py
    ↓ 后续扩展
保序回归概率校准 + MC-Dropout 不确定性估计
```

---

## 六、详细开发任务拆分

### Task 1：建立预测模块基础目录与配置

#### 目标

为真实预测模块建立独立目录结构和配置入口，不直接把代码堆在 `InferService` 或 `InferRepository` 中。

#### 开发内容

新增：

```text
railphm-ai/app/ml/__init__.py
railphm-ai/app/ml/data_loader.py
railphm-ai/app/ml/preprocess.py
railphm-ai/app/ml/window_builder.py
railphm-ai/app/ml/condition_recognizer.py
railphm-ai/app/ml/transitional_risk_model.py
railphm-ai/app/ml/predictor.py
railphm-ai/app/ml/postprocess.py
```

同时在配置中增加本地 CSV 数据目录，例如：

```text
LOCAL_CSV_DATA_DIR
DEFAULT_CSV_FILE
MODEL_VERSION = transitional-stat-risk-v1
```

#### 验收标准

1. 新增目录结构清晰；
2. 项目启动不报错；
3. 原有 `/health` 和 `/infer` 接口不受影响；
4. `pytest` 原有测试不应大面积失败。

---

### Task 2：实现本地 CSV 数据读取能力

#### 目标

让 `railphm-ai` 能够读取真实 ATP CSV 文件，而不是继续依赖固定 mock 数据。

#### 开发内容

在 `data_loader.py` 中实现 `CSVDataLoader` 类。

建议方法：

```text
load_by_device_and_time(device_id, ts_end, window_minutes)
load_csv_file(file_path)
```

现阶段可以先采用简单策略：

1. 从配置目录中读取一个默认 CSV 文件；
2. 后续再扩展为按 `device_id` 映射不同 CSV；
3. 如果文件不存在，抛出业务异常；
4. 如果 CSV 为空，抛出业务异常；
5. 如果缺少 `datetime` 字段，抛出业务异常。

#### 验收标准

1. 能成功读取本地 CSV；
2. CSV 为空时返回明确错误；
3. CSV 文件不存在时返回明确错误；
4. 缺少 `datetime` 字段时返回明确错误；
5. 不再在数据读取阶段生成固定 `risk_score`。

---

### Task 3：实现时间字段解析与基础预处理

#### 目标

将原始 CSV 数据整理成可用于预测的连续时序数据。

#### 开发内容

在 `preprocess.py` 中实现 `ATPPreprocessor` 类。

处理流程建议为：

1. 解析 `datetime` 字段；
2. 删除 `datetime` 无法解析的行；
3. 按 `datetime` 升序排序；
4. 去除重复时间点；
5. 筛选数值型特征字段；
6. 对缺失值进行线性插值；
7. 对仍无法填充的缺失值使用前向/后向填充；
8. 对数值字段进行 min-max 归一化；
9. 返回预处理后的 `DataFrame` 和预处理统计信息。

预处理统计信息建议包括：

```text
row_count
feature_count
missing_rate
start_time
end_time
selected_features
```

#### 验收标准

1. 输入乱序 CSV 后，输出按 `datetime` 升序；
2. 缺失值能够被处理；
3. 能返回有效数值特征；
4. 能输出 `missing_rate` 等统计信息；
5. 如果有效数据行不足，应返回明确错误。

---

### Task 4：实现预测时间窗口构造

#### 目标

根据 `/infer` 入参中的 `ts_end` 和 `window_minutes`，从 CSV 数据中截取对应时间窗口。

#### 开发内容

在 `window_builder.py` 中实现 `WindowBuilder` 类。

核心逻辑：

```text
window_end_time = ts_end
window_start_time = ts_end - window_minutes
```

从预处理后的数据中筛选：

```text
datetime >= window_start_time
datetime <= window_end_time
```

需要处理异常情况：

1. 时间窗口内没有数据；
2. 时间窗口内数据点太少；
3. `ts_end` 超出 CSV 数据时间范围；
4. `window_minutes` 非法。

#### 验收标准

1. 能按时间窗口截取数据；
2. 返回窗口开始时间和结束时间；
3. 数据不足时返回明确错误；
4. 不破坏现有 `/infer` 入参格式。

---

### Task 5：实现规则版工况识别占位

#### 目标

先保留论文中的工况识别概念，返回 `condition_label`，后续再替换为 K-means。

#### 开发内容

在 `condition_recognizer.py` 中实现 `ConditionRecognizer` 类。

现阶段可以用规则版：

1. 平均速度较高且波动较小：`high_speed_cruise`
2. 速度整体下降：`station_deceleration`
3. 速度整体上升：`station_acceleration`
4. 其他情况：`mixed_condition`

注意：这里是占位实现，类名和方法名要为后续 K-means 替换保留空间。

#### 验收标准

1. 每次推理都能返回 `condition_label`；
2. `condition_label` 来自窗口数据，而不是固定写死；
3. 后续替换 K-means 时不需要改 `/infer` 接口。

---

### Task 6：实现过渡版风险计算

#### 目标

用真实 CSV 时间窗口数据计算 `risk_score`，替代当前固定 mock 风险分数。

#### 开发内容

在 `transitional_risk_model.py` 中实现 `TransitionalRiskModel` 类。

建议基于以下指标计算风险：

1. 缺失率 `missing_rate`；
2. 速度波动 `speed_volatility`；
3. 等级变化频率 `level_change_rate`；
4. 里程或运行距离连续性 `distance_continuity_score`；
5. 时间间隔异常 `time_gap_score`；

输出：

```text
risk_score: 0 到 1 的浮点数
risk_std: 过渡版不确定性估计
risk_features: 可选，用于调试和测试
```

注意：`risk_score` 必须经过裁剪，保证在 `[0, 1]` 范围内。

#### 验收标准

1. `risk_score` 不再是固定值；
2. 不同 CSV 或不同时间窗口应可能得到不同 `risk_score`；
3. `risk_score` 始终在 0 到 1 之间；
4. `risk_std` 始终为非负数；
5. 输出字段能够被 `railphm-server AIClient` 正常校验。

---

### Task 7：实现预测流程编排器 Predictor

#### 目标

将数据读取、预处理、窗口构造、工况识别、风险计算和结果后处理串联起来。

#### 开发内容

在 `predictor.py` 中实现 `ATPRiskPredictor` 类。

流程如下：

```text
ATPRiskPredictor.predict(device_id, ts_end, window_minutes)
    ↓
CSVDataLoader 读取 CSV
    ↓
ATPPreprocessor 预处理
    ↓
WindowBuilder 构造窗口
    ↓
ConditionRecognizer 识别工况
    ↓
TransitionalRiskModel 计算风险分数
    ↓
Postprocessor 生成标准返回结果
```

#### 验收标准

1. Predictor 能独立完成一次完整预测；
2. 返回字段完整；
3. 错误通过 `BusinessException` 统一抛出；
4. 逻辑不直接散落在 `InferService` 中。

---

### Task 8：改造 `/infer` 服务逻辑

#### 目标

将 `InferService` 从调用固定 mock repository，改为调用真实预测流程编排器。

#### 开发内容

修改：

```text
railphm-ai/app/service/infer_service.py
```

原逻辑大致是：

```text
参数校验
    ↓
InferRepository.infer()
    ↓
返回固定 mock 结果
```

改造后：

```text
参数校验
    ↓
ATPRiskPredictor.predict()
    ↓
返回真实数据驱动结果
```

可以暂时保留 `InferRepository`，但不再作为主推理逻辑使用。也可以将其标记为 legacy mock，避免误用。

#### 验收标准

1. `POST /infer` 入参不变；
2. `POST /infer` 返回结构不变；
3. 返回 `risk_score` 来自 CSV 计算；
4. `railphm-server /api/v1/predictions/infer` 能继续正常调用；
5. 前端风险预测页面不需要改动即可展示结果。

---

### Task 9：补充 AI 服务测试

#### 目标

用测试固定真实预测模块的核心行为。

#### 新增或修改测试

建议新增：

```text
railphm-ai/tests/test_data_loader.py
railphm-ai/tests/test_preprocess.py
railphm-ai/tests/test_window_builder.py
railphm-ai/tests/test_condition_recognizer.py
railphm-ai/tests/test_transitional_risk_model.py
railphm-ai/tests/test_predictor.py
railphm-ai/tests/test_infer_real_csv.py
```

测试重点：

1. 正常 CSV 推理成功；
2. CSV 文件不存在；
3. CSV 缺少 `datetime`；
4. 时间窗口内无数据；
5. `window_minutes` 非法；
6. `risk_score` 范围合法；
7. `condition_label` 存在；
8. 返回字段满足 server `AIClient` 要求。

#### 验收标准

```bash
cd railphm-ai
pytest
```

测试通过。

---

### Task 10：联调 `railphm-server` 与 `railphm-ai`

#### 目标

验证后端主服务调用真实数据驱动的 AI 推理链路是否正常。

#### 联调步骤

启动 AI 服务：

```bash
cd railphm-ai
python run.py
```

启动 server 服务：

```bash
cd railphm-server
python run.py
```

调用 server 接口：

```text
POST /api/v1/predictions/infer
```

请求体示例：

```json
{
  "device_id": 1,
  "ts_end": "2025-04-01 10:30:00",
  "window_minutes": 10
}
```

期望返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "device_id": 1,
    "window_start_time": "...",
    "window_end_time": "...",
    "condition_label": "...",
    "risk_score": 0.0,
    "risk_std": 0.0,
    "health_score": 0.0,
    "alert_level": "...",
    "model_version": "transitional-stat-risk-v1"
  }
}
```

注意：`health_score` 和 `alert_level` 是 server 侧补充的，不是 AI 服务最终职责。

#### 验收标准

1. server 能正常调用 AI 服务；
2. AI 服务返回真实 CSV 驱动结果；
3. server 能继续计算 `health_score` 和 `alert_level`；
4. 前端风险预测页面可以显示推理结果；
5. 原有 server 测试不应大面积失败。

---

## 七、本阶段最终交付物

本阶段完成后，仓库应新增或改造以下内容：

1. `railphm-ai/app/ml/` 预测模块目录；
2. CSV 数据读取模块；
3. 数据预处理模块；
4. 时间窗口构造模块；
5. 工况识别占位模块；
6. 过渡版风险计算模块；
7. 预测流程编排器；
8. `/infer` 接口真实数据驱动改造；
9. AI 服务相关 pytest 测试；
10. README 或开发记录中补充本阶段说明。

---

## 八、开发完成后的项目状态

完成本阶段后，你的项目状态可以表述为：

RailPHM 当前已完成基于本地 ATP CSV 数据的故障风险预测流程骨架。

系统能够读取连续时间片段数据，完成基础预处理、时间窗口构造、工况识别和过渡版风险评分，并通过 `railphm-ai /infer` 接口向 `railphm-server` 返回标准预测结果。

当前 `risk_score` 已不再由固定 mock 数据生成，而是由真实监测数据片段中的统计特征计算得到。

后续将继续在该流程基础上替换 K-means 工况划分、Bi-LSTM+Attention 模型推理、保序回归概率校准和 MC-Dropout 不确定性估计。

这段话后续可以写进 README 或阶段开发记录里。

---

## 九、后续阶段预留路线

本阶段完成后，下一阶段建议依次做：

1. 阶段二：K-means 工况识别真实实现
2. 阶段三：Bi-LSTM + Attention 训练脚本与模型保存
3. 阶段四：模型加载与真实推理替换过渡版风险计算
4. 阶段五：保序回归概率校准
5. 阶段六：MC-Dropout 不确定性估计
6. 阶段七：预测结果写入 MySQL
7. 阶段八：从 InfluxDB 读取 ATP 时序数据

这样路线最稳，不会让项目变成一坨临时代码。

---

## 十、最终建议

兄弟，下一步任务名称就定为：

> 任务：`railphm-ai` 预测模块真实数据驱动骨架开发

任务目标不要写成“完成 Bi-LSTM 故障预测模型”，因为这个目标太大，也容易导致代码失控。现在更准确的目标应该是：

> 在保持现有 `/infer` 接口和前后端调用链路稳定的前提下，将 `railphm-ai` 从固定 mock 推理改造为基于本地 ATP CSV 数据的真实预测流程骨架，为后续接入 K-means、Bi-LSTM+Attention、保序回归和 MC-Dropout 预留工程基础。

这一步做完，你的预测模块就真正从 mock 阶段跨到真实开发阶段了。
