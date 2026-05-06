# railphm-ai

高铁列控设备故障预测与健康管理系统（RailPHM）- AI mock 推理服务

## 项目定位

`railphm-ai` 是 RailPHM 毕设项目中的独立 AI 服务。当前阶段定位为最小可运行的 mock inference service，用于先跑通“假模型真流程”，即让 `railphm-web -> railphm-server -> railphm-ai` 的调用链路先稳定可用。

当前服务不训练模型、不加载真实模型、不访问数据库，也不实现真实 K-means 工况划分、Bi-LSTM + Attention 推理或 MC-Dropout 多次推理。

## 当前开发进度

- Task 15 - `railphm-ai` 最小 mock 推理服务已完成。
- Task 16 - 已被 `railphm-server` 调用，形成 `railphm-web -> railphm-server -> railphm-ai` 的 mock 推理链路。
- Task 17 - 后端已基于风险结果完成健康度与告警等级映射，AI 服务返回字段需保持稳定。

## 当前接口能力

### GET /health

用于 AI 服务健康检查。

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

请求体：

```json
{
  "device_id": 1,
  "ts_end": "2026-04-19 10:05:00",
  "window_minutes": 5
}
```

当前 AI 服务原始响应字段为：

- `device_id`
- `ts_end`
- `window_minutes`
- `window_start_time`
- `window_end_time`
- `condition_label`
- `risk_score`
- `risk_std`
- `model_version`

示例响应：

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
    "model_version": "mock-bilstm-attention-v1"
  }
}
```

注意：当前 `health_score` 和 `alert_level` 不由 `railphm-ai` 直接返回，而是在 `railphm-server` 的 `PredictionService` 中根据 `risk_score` 统一计算。前端通过后端 `POST /api/v1/predictions/infer` 获取的最终推理响应会包含 `health_score` 和 `alert_level`。

## mock 逻辑说明

当前 mock 结果基于 `device_id % 3` 做稳定映射，不使用随机数，便于前后端联调与测试复现：

- `device_id % 3 == 1`：高风险设备画像，`risk_score = 0.82`
- `device_id % 3 == 2`：中风险设备画像，`risk_score = 0.52`
- `device_id % 3 == 0`：低风险设备画像，`risk_score = 0.21`

其中：

- `window_start_time` 根据 `ts_end - window_minutes` 计算。
- `window_end_time` 与 `ts_end` 对齐。
- `model_version` 当前固定来自配置，默认值为 `mock-bilstm-attention-v1`。

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

## 启动与测试

### 安装依赖

```bash
cd railphm-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 启动服务

```bash
cd railphm-ai
python run.py
```

默认地址：

```text
http://127.0.0.1:5001
```

### 运行测试

```bash
cd railphm-ai
pytest
```

当前测试覆盖健康检查、全局 404/方法错误处理、mock 推理分支、时间窗口计算和参数校验。

## 后续替换方向

后续真实模型接入时，应尽量保持 `POST /infer` 的接口契约稳定，逐步替换内部实现：

1. 加载训练好的 Bi-LSTM + Attention 模型。
2. 接入真实工况识别结果。
3. 支持 MC-Dropout 多次推理。
4. 返回不确定性估计结果。
5. 与后端保持字段契约稳定，由后端继续统一健康度与告警等级规则。

当前上述能力均未完成。
# railphm-ai

`railphm-ai` 是 RailPHM 毕设项目中的独立 AI 服务。当前阶段主要承担两个职责：一是作为最小可运行的 mock inference service，用于先跑通“假模型真流程”；二是提供 ATP segment 数据集构建模块，为后续 Bi-LSTM + Attention 模型训练、真实推理接入和实验分析准备标准化窗口数据。

当前版本仍不包含真实模型训练和真实模型推理，`/infer` 接口保持 mock 推理行为。数据集构建模块属于离线预处理能力，不会在 `python run.py` 启动服务时自动执行。

## 当前阶段定位

- 提供独立 HTTP 服务。
- 暴露 `GET /health` 健康检查接口。
- 暴露 `POST /infer` mock 推理接口。
- 返回稳定、可预测的 mock 推理结果，便于与 `railphm-server` 联调。
- 新增 ATP segment 数据集构建模块，用于从已切分 CSV 构造滑动窗口训练样本。
- 代码结构预留未来替换为真实模型推理逻辑的空间。

当前版本不包含：

- 真实模型训练。
- 真实 Bi-LSTM + Attention 推理。
- 真实模型加载。
- train/val/test 数据集划分。
- 数据库访问。
- 消息队列。
- 复杂鉴权与部署逻辑。

## 项目结构

```text
railphm-ai/
├── app/
│   ├── api/
│   │   ├── health/
│   │   └── infer/
│   ├── core/
│   ├── dataset/
│   │   ├── __init__.py
│   │   ├── feature_config.py
│   │   ├── segment_loader.py
│   │   ├── feature_processor.py
│   │   ├── window_builder.py
│   │   ├── dataset_builder.py
│   │   └── dataset_summary.py
│   ├── repository/
│   ├── schema/
│   └── service/
├── scripts/
│   └── build_window_dataset.py
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

`requirements.txt` 至少应包含：

```txt
Flask==3.0.3
pytest==8.3.5
pandas
numpy
```

其中，`pandas` 和 `numpy` 用于 ATP segment 数据读取、特征处理、窗口构造和 `X.npy / y.npy` 输出。

## 启动 AI 服务

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

注意：`python run.py` 只负责启动 AI 服务，不会自动构建数据集。数据集构建属于离线任务，需要通过 `scripts/build_window_dataset.py` 单独执行。

## 运行测试

```bash
cd railphm-ai
pytest
```

该命令会运行当前 AI 服务相关测试和数据集构建模块测试，确保 `/health`、`/infer` 原有行为不被破坏，同时验证 `SegmentLoader`、`FeatureProcessor`、`WindowBuilder` 和 `WindowDatasetBuilder` 的功能正确性。

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

- `device_id`：必填，整数。
- `ts_end`：必填，时间字符串，格式必须为 `YYYY-MM-DD HH:mm:ss`。
- `window_minutes`：必填，正整数。

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

## mock 推理逻辑说明

当前 mock 结果基于 `device_id % 3` 做稳定映射，不使用随机数，便于前后端联调与测试复现：

- `device_id % 3 == 1`：高风险设备画像。
- `device_id % 3 == 2`：中风险设备画像。
- `device_id % 3 == 0`：低风险设备画像。

其中：

- `window_start_time` 根据 `ts_end - window_minutes` 计算。
- `model_version` 当前固定为 `mock-bilstm-attention-v1`。
- `railphm-ai` 当前只负责返回风险分数、风险波动、工况标签和模型版本等推理结果。
- 健康度 `health_score` 和告警等级 `alert_level` 的最终业务解释由 `railphm-server` 侧完成。

后续如果接入真实模型，建议优先替换：

1. `app/repository/infer_repository.py`：将当前 mock 结果生成逻辑替换为真实模型推理调用。
2. `app/service/infer_service.py`：保留参数校验与业务编排，在这里组织预处理、推理和后处理流程。
3. `app/schema/infer_schema.py`：如果真实模型输入输出格式变化，可在此处扩展请求与响应 schema。

这样可以尽量保持 API 路由层稳定，减少对外接口变动。

## 数据集构建模块

`railphm-ai` 已新增 ATP segment 数据集构建模块，用于将已经按“数据时间”连续递增切分得到的 `segment_*.csv` 文件转换为后续模型训练可使用的滑动窗口数据集。

本模块当前只负责数据集构建，不负责模型训练，不负责替换 `/infer` 接口，也不访问 MySQL 或 InfluxDB。当前 `/health` 和 `/infer` mock 推理服务仍保持原有行为。

### 数据输入

数据集构建模块读取已经切分好的 ATP segment CSV 文件，默认输入目录建议为：

```bash
data/processed/atp_segments
```

文件名格式示例：

```text
segment_000003_20150109112305.csv
```

读取层会完整读取 CSV 中的全部字段，不会在读取阶段删除业务字段。原始 CSV 中存在多个同名中文字段，例如多个“报警部位”，pandas 读取后会自动转换为：

```text
报警部位
报警部位.1
报警部位.2
```

本模块只使用第一列 `报警部位` 作为标签来源，不使用 `报警部位.1` 和 `报警部位.2` 作为标签。

### 预测任务定义

当前数据集构建任务定义为：

```text
基于同一连续 segment 内的历史 ATP 监测时间窗，预测下一时刻是否出现 ATP 报警风险。
```

默认参数为：

```text
window_size = 30
stride = 1
prediction_horizon = 1
time_col = 数据时间
label_col = 报警部位
```

窗口构造规则为：

```text
第 1～30 行预测第 31 行
第 2～31 行预测第 32 行
第 3～32 行预测第 33 行
以此类推
```

窗口只会在单个 segment 内部构造，不会跨 segment 构造。

### 标签规则

标签 `y` 是二分类标签，只能取值为 `0` 或 `1`：

```text
y = 1：目标时刻第一列“报警部位”非空
y = 0：目标时刻第一列“报警部位”为空
```

注意：

```text
报警部位.1
报警部位.2
```

不会参与标签构造，也不会进入模型输入 `X`。

### 模型输入与元信息

模型输入 `X` 只使用 `app/dataset/feature_config.py` 中配置的数值特征字段，并会进行数值化、缺失值处理和 segment 内 min-max 归一化。

第一版默认数值特征字段包括：

```text
速度
里程
运行距离
行别
线路编号
应答器编号
应答器里程
行别.1
线路编号.1
信号机ID
信号机里程
行别.2
线路编号.2
经度
纬度
信号机ID.1
信号机里程.1
行别.3
线路编号.3
经度.1
纬度.1
司机操作是否合规
运行方向
室外温度
湿度
```

以下字段不会进入模型输入 `X`：

```text
报警部位
报警部位.1
报警部位.2
唯一标识
司机名
司机手机号
司机操作
路况信息
等级
制动信息
紧急制动速度
常用制动速度
```

车号、车次、ATP 类型、铁路局、司机号、唯一标识等字段不会进入模型输入，但会写入 `window_manifest.csv`，用于样本追溯、系统展示和后续问题排查。

司机名、司机手机号默认不写入 `window_manifest.csv`。

### 模块文件说明

```text
app/dataset/feature_config.py
集中定义时间字段、标签字段、默认窗口参数、模型输入字段、模型排除字段和 manifest 元信息字段。

app/dataset/segment_loader.py
负责完整读取单个 segment CSV，自动处理常见中文编码，解析“数据时间”，检查原始行顺序是否严格 1 秒递增。

app/dataset/feature_processor.py
负责从完整 DataFrame 中抽取模型输入字段，转为数值，处理缺失值，并进行 segment 内 min-max 归一化。

app/dataset/window_builder.py
负责在单个 segment 内构造滑动窗口 X、二分类标签 y，以及每个窗口样本对应的 manifest 追溯记录。

app/dataset/dataset_builder.py
负责主流程编排，批量处理 segment 文件，汇总所有窗口样本，并输出 X.npy、y.npy、feature_columns.json、window_manifest.csv 和 dataset_summary.json。

app/dataset/dataset_summary.py
负责生成数据集构建统计信息。
```

## 构建窗口数据集

### 命令行入口

数据集构建使用以下脚本：

```bash
python scripts/build_window_dataset.py
```

查看帮助：

```bash
python scripts/build_window_dataset.py --help
```

### 默认构建命令

在 `railphm-ai` 目录下执行：

```bash
python scripts/build_window_dataset.py \
  --segments-dir /Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/代码/atp_segments \
  --output-dir data/datasets/window_w30_s1_h1 \
  --window-size 30 \
  --stride 3 \
  --horizon 1 \
  --overwrite \
  --verbose
```

参数说明：

```text
--segments-dir
已切分的 segment CSV 文件目录。

--output-dir
窗口数据集输出目录。

--window-size
历史窗口长度，默认 30。

--stride
滑动窗口步长，默认 1。

--horizon / --prediction-horizon
预测步长，默认 1，表示预测下一时刻。

--overwrite
输出目录已存在时允许覆盖。

--skip-invalid-segments
默认开启，遇到无法读取、时间不连续或无法生成窗口的 segment 时跳过并记录。

--no-skip-invalid-segments
遇到异常 segment 时直接终止构建。

--verbose
输出更详细的构建信息。
```

### 修改窗口参数

例如将步长从 `1` 改为 `3`：

```bash
python scripts/build_window_dataset.py \
  --segments-dir data/processed/atp_segments \
  --output-dir data/datasets/window_w30_s3_h1 \
  --window-size 30 \
  --stride 3 \
  --horizon 1 \
  --overwrite \
  --verbose
```

建议输出目录名称同步体现参数：

```text
window_w30_s1_h1
window_w30_s3_h1
window_w60_s1_h1
```

其中：

```text
w30 表示 window_size = 30
s1 表示 stride = 1
h1 表示 prediction_horizon = 1
```

## 输出文件

默认输出目录示例：

```bash
data/datasets/window_w30_s1_h1
```

构建完成后会生成：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
```

文件说明：

```text
X.npy
模型输入数据，shape = [num_samples, window_size, feature_dim]。

y.npy
二分类标签，shape = [num_samples]，取值只能为 0 或 1。

feature_columns.json
记录 X 最后一维对应的特征字段顺序。

window_manifest.csv
记录每个窗口样本的来源 segment、窗口行号、目标行号、目标时间、标签、车号、车次、ATP 类型、铁路局、唯一标识等追溯信息。

dataset_summary.json
记录本次数据集构建的统计信息，包括 segment 数量、窗口数量、正负样本数量、正样本比例、X/y shape、缺失字段和跳过文件等。
```

### 检查构建结果

构建完成后，可以执行：

```bash
python - <<'PY'
from pathlib import Path
import json
import numpy as np
import pandas as pd

output_dir = Path("data/datasets/window_w30_s1_h1")

X = np.load(output_dir / "X.npy")
y = np.load(output_dir / "y.npy")
manifest = pd.read_csv(output_dir / "window_manifest.csv", encoding="utf-8-sig")
summary = json.loads((output_dir / "dataset_summary.json").read_text(encoding="utf-8"))

print("X shape:", X.shape)
print("y shape:", y.shape)
print("manifest rows:", len(manifest))
print("total_windows:", summary["total_windows"])
print("positive_count:", summary["positive_count"])
print("negative_count:", summary["negative_count"])
print("positive_ratio:", summary["positive_ratio"])
print("feature_dim:", summary["feature_dim"])
PY
```

重点检查：

```text
X.shape[0] 是否等于 y.shape[0]
window_manifest.csv 行数是否等于 y.shape[0]
y 是否只包含 0 和 1
dataset_summary.json 中 total_windows 是否符合预期
```

## 开发与数据管理注意事项

数据集构建会产生本地数据文件和较大的 NumPy 数组文件，不应提交到 GitHub。建议根目录 `.gitignore` 包含以下内容：

```gitignore
# RailPHM AI generated datasets
railphm-ai/data/datasets/
railphm-ai/data/processed/
*.npy
```

含义如下：

```text
railphm-ai/data/processed/
用于存放切分后的 segment CSV 文件，例如 data/processed/atp_segments/。这些文件来自原始数据处理结果，通常体积较大，不应提交。

railphm-ai/data/datasets/
用于存放构建后的窗口数据集，包括 X.npy、y.npy、feature_columns.json、window_manifest.csv 和 dataset_summary.json，不应提交。

*.npy
忽略 NumPy 大数组文件，例如 X.npy 和 y.npy。
```

当前数据集构建模块暂不做 train/val/test 划分。由于滑动窗口之间高度重叠，后续划分训练集、验证集和测试集时，应按 `segment_id` 进行划分，不能随机按窗口样本划分，否则容易造成数据泄露。

## 本阶段已完成能力总结

当前 `railphm-ai` 已具备以下能力：

```text
1. 作为独立 Flask AI 服务启动。
2. 提供 /health 健康检查接口。
3. 提供 /infer mock 推理接口。
4. 使用稳定 mock 风险画像返回 risk_score、risk_std、condition_label 和 model_version。
5. 完整读取 ATP segment CSV。
6. 自动解析“数据时间”字段并检查 1 秒连续性。
7. 从完整 DataFrame 中抽取模型输入数值特征。
8. 明确排除“报警部位”“报警部位.1”“报警部位.2”等标签相关字段，防止数据泄露。
9. 将缺失值处理、数值化和 segment 内 min-max 归一化封装在 FeatureProcessor 中。
10. 在单个 segment 内构造滑动窗口，不跨 segment。
11. 只使用目标时刻第一列“报警部位”生成 0/1 标签。
12. 输出 X.npy、y.npy、feature_columns.json、window_manifest.csv 和 dataset_summary.json。
13. 提供 scripts/build_window_dataset.py 命令行入口。
14. 提供 pytest 测试保障数据集构建模块行为稳定。
```

## 后续开发建议

后续建议按以下顺序继续推进：

1. 使用真实的 1980 个 segment 文件执行一次完整数据集构建，检查 `dataset_summary.json` 中的窗口数量、正负样本比例、缺失字段和跳过文件情况。
2. 新增数据集检查脚本，统计 `y` 的类别分布、不同车号/不同 segment 的样本分布。
3. 基于 `window_manifest.csv` 按 `segment_id` 进行 train/val/test 划分，避免滑动窗口重叠造成数据泄露。
4. 在划分后的数据集上实现 Bi-LSTM + Attention 训练流程。
5. 保存模型、特征列顺序和归一化策略，为后续 `/infer` 接入真实推理做准备。
