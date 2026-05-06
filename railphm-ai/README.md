# railphm-ai

`railphm-ai` 是 RailPHM 项目中的独立 AI 服务子模块，主要负责高铁列控设备故障风险预测相关能力。当前阶段已经从最初的 mock inference service，推进到真实 ATP segment 数据驱动的数据集构建、数据集质量检查以及按 `segment_id` 的无泄露训练集划分阶段。

本模块当前仍不直接承担健康度映射和告警等级判定。健康度计算、告警等级映射等业务解释规则由 `railphm-server` 侧统一处理。`railphm-ai` 现阶段重点负责风险预测相关的 AI 服务接口、数据集构建和后续模型训练准备。

## 当前阶段定位

当前 `railphm-ai` 的开发目标是先跑通从 ATP 原始监测数据到模型训练数据的基础链路，为后续 Bi-LSTM + Attention 故障风险预测模型训练和真实推理接入做准备。

当前已经完成：

```text
1. 最小 Flask AI 服务启动。
2. /health 健康检查接口。
3. /infer mock 推理接口。
4. mock 风险结果稳定返回。
5. ATP segment CSV 数据读取模块。
6. 模型输入特征处理模块。
7. 滑动窗口数据集构建模块。
8. 数据集质量检查模块。
9. 按 segment_id 划分 train / val / test，避免滑动窗口数据泄露。
10. 数据集构建、检查和划分脚本命令行入口。
```

当前尚未完成：

```text
1. Bi-LSTM + Attention 模型训练。
2. Attention 结构实现。
3. 模型评估指标计算。
4. 模型文件保存与加载。
5. /infer 接口接入真实模型。
6. InfluxDB 在线时序数据查询。
7. 在线推理窗口构造。
8. 保序回归概率校准。
9. MC-Dropout 不确定性估计。
```

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
│   │   ├── dataset_summary.py
│   │   ├── dataset_inspector.py
│   │   └── split_builder.py
│   ├── repository/
│   ├── schema/
│   └── service/
├── scripts/
│   ├── build_window_dataset.py
│   ├── inspect_dataset.py
│   ├── split_dataset.py
│   └── README.md
├── tests/
├── run.py
├── requirements.txt
└── pytest.ini
```

## 开发环境

推荐使用虚拟环境：

```bash
cd railphm-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

当前依赖至少包括：

```text
Flask==3.0.3
pytest==8.3.5
pandas
numpy
```

其中，`Flask` 用于提供 AI 服务接口，`pytest` 用于自动化测试，`pandas` 和 `numpy` 用于 ATP segment 数据读取、特征处理、窗口构造、数据集检查和训练集划分。

## AI 服务启动

启动 `railphm-ai` 服务：

```bash
cd railphm-ai
python run.py
```

默认服务地址：

```text
http://127.0.0.1:5001
```

当前服务接口包括：

```text
GET  /health
POST /infer
```

注意：`python run.py` 只负责启动 AI 服务，不会自动构建数据集。数据集构建、质量检查和训练集划分属于离线任务，需要通过 `scripts/` 目录下的脚本单独执行。

## Task 1：mock inference service 已完成

当前 `/infer` 接口仍为 mock 推理接口，用于先打通 `railphm-server` 与 `railphm-ai` 之间的调用链路。

当前 mock 推理逻辑基于 `device_id % 3` 返回稳定结果，不使用随机数，便于接口联调和测试复现。

当前 `/infer` 请求示例：

```json
{
  "device_id": 1,
  "ts_end": "2026-04-19 10:05:00",
  "window_minutes": 5
}
```

当前 `/infer` 返回字段主要包括：

```text
device_id
ts_end
window_minutes
window_start_time
window_end_time
condition_label
risk_score
risk_std
model_version
```

其中，`risk_score` 是 AI 服务返回给 `railphm-server` 的核心风险结果。健康度 `health_score` 和告警等级 `alert_level` 由 `railphm-server` 侧根据业务规则计算，不直接由 AI 服务决定。

## Task 2：数据集构建模块已完成

### 任务目标

Task 2 的目标是将已经按“数据时间”连续递增切分得到的 ATP segment CSV 文件，构造为后续模型训练可使用的滑动窗口数据集。

当前构建流程为：

```text
segment_*.csv
  ↓
SegmentLoader 完整读取 CSV
  ↓
FeatureProcessor 提取模型输入特征
  ↓
WindowBuilder 构造滑动窗口 X/y
  ↓
WindowDatasetBuilder 汇总并输出数据集文件
```

### 数据输入

当前真实数据已经被切分为：

```text
1980 个连续时间片段文件
```

文件名示例：

```text
segment_000003_20150109112305.csv
```

原始 CSV 中存在多个同名中文字段，例如多个“报警部位”。pandas 读取后会自动转换为：

```text
报警部位
报警部位.1
报警部位.2
```

本模块只使用 pandas 读入后的第一列 `报警部位` 作为标签来源，不使用 `报警部位.1` 和 `报警部位.2` 作为标签。

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

`报警部位.1` 和 `报警部位.2` 不参与标签构造，也不进入模型输入 `X`。

### 模型输入与元信息

模型输入 `X` 只使用 `app/dataset/feature_config.py` 中配置的数值特征字段，并会进行数值化、缺失值处理和 segment 内 min-max 归一化。

第一版默认数值特征字段共 25 个：

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

### 输出文件

数据集构建输出目录：

```text
data/datasets/window_w30_s1_h1/
```

当前已生成：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
```

文件含义：

```text
X.npy
模型输入滑动窗口数据，shape = [num_samples, window_size, feature_dim]。

y.npy
二分类标签，shape = [num_samples]，取值只能为 0 或 1。

feature_columns.json
记录 X 最后一维对应的特征字段顺序。

window_manifest.csv
记录每个窗口样本的来源 segment、窗口行号、目标行号、目标时间、标签、车号、车次、ATP 类型、铁路局、唯一标识等追溯信息。

dataset_summary.json
记录本次数据集构建的统计信息，包括 segment 数量、窗口数量、正负样本数量、正样本比例、X/y shape、缺失字段和跳过文件等。
```

### 真实数据集构建结果

当前使用 1980 个真实 segment 文件完成构建，结果如下：

```text
total_segment_files   : 1980
used_segment_count    : 1980
skipped_segment_count : 0
total_windows         : 325800
positive_count        : 134460
negative_count        : 191340
positive_ratio        : 0.412707
feature_dim           : 25
X_shape               : [325800, 30, 25]
y_shape               : [325800]
manifest rows         : 325800
unique y              : [0, 1]
missing_feature_columns : []
all_nan_feature_columns : []
```

该结果说明：

```text
1. 1980 个 segment 文件全部成功读取并使用。
2. 没有 segment 被跳过。
3. 构造窗口数量与理论估算一致。
4. X/y/window_manifest.csv 三者样本数量完全对齐。
5. 标签为合法二分类标签。
6. 特征列无缺失，无全空列。
```

## Task 3：数据集检查与无泄露划分已完成

### Task 3-1：数据集质量检查已完成

当前已实现：

```text
app/dataset/dataset_inspector.py
scripts/inspect_dataset.py
```

数据集检查内容包括：

```text
1. X.npy、y.npy、feature_columns.json、window_manifest.csv、dataset_summary.json 是否存在。
2. X 是否为三维数组。
3. y 是否为一维数组。
4. X/y/manifest 行数是否一致。
5. summary 中 total_windows 是否与 y 样本数一致。
6. y 是否只包含 0 和 1。
7. X 是否存在 NaN。
8. X 是否存在 inf。
9. X 数值范围是否在 0 到 1。
10. feature_dim 是否等于 feature_columns 数量。
11. manifest 是否包含 sample_id、segment_id、target_time、label 等必要字段。
12. manifest 是否误写入司机手机号等敏感字段。
```

真实数据集检查结果：

```text
is_valid             : True
errors               : []
warnings             : ["不同 segment 的窗口样本数差异较大: min_samples_per_segment=7, max_samples_per_segment=252"]
X_shape              : [325800, 30, 25]
y_shape              : [325800]
manifest_rows        : 325800
feature_dim          : 25
feature_column_count : 25
unique_y             : [0, 1]
positive_count       : 134460
negative_count       : 191340
positive_ratio       : 0.412707
X_min                : 0.0
X_max                : 1.0
has_nan              : False
has_inf              : False
segment_count        : 1980
samples_per_segment_min  : 7
samples_per_segment_max  : 252
samples_per_segment_mean : 164.54545454545453
```

其中 warning 来源于不同 segment 原始长度不同，属于正常现象，不影响后续使用。

### Task 3-2：按 segment_id 划分 train / val / test 已完成

当前已实现：

```text
app/dataset/split_builder.py
scripts/split_dataset.py
```

划分策略：

```text
按 segment_id 划分 train / val / test。
同一个 segment_id 下的全部窗口样本只能进入一个集合。
不允许同一个 segment 同时出现在训练集、验证集或测试集中。
```

默认划分比例：

```text
train_ratio = 0.70
val_ratio   = 0.15
test_ratio  = 0.15
seed         = 42
```

注意：比例按 `segment_id` 数量划分，不是直接按窗口样本数量随机划分。这样可以避免滑动窗口高度重叠导致的数据泄露。

当前真实数据集划分结果：

```text
训练集：
sample_count   : 227080
segment_count  : 1386
positive_count : 93076
negative_count : 134004
positive_ratio : 0.409882

验证集：
sample_count   : 51058
segment_count  : 297
positive_count : 21933
negative_count : 29125
positive_ratio : 0.429570

测试集：
sample_count   : 47662
segment_count  : 297
positive_count : 19451
negative_count : 28211
positive_ratio : 0.408103

总样本数：
227080 + 51058 + 47662 = 325800

泄露检查：
train_val_overlap_count  : 0
train_test_overlap_count : 0
val_test_overlap_count   : 0
has_segment_leakage      : False
```

当前已生成：

```text
data/datasets/window_w30_s1_h1/splits/
├── train_indices.npy
├── val_indices.npy
├── test_indices.npy
└── split_summary.json
```

`train_indices.npy`、`val_indices.npy` 和 `test_indices.npy` 不复制窗口数据，只保存样本索引。后续训练时可通过索引从 `X.npy` 和 `y.npy` 中取出对应样本。

## 当前数据目录说明

当前数据集目录结构如下：

```text
data/datasets/window_w30_s1_h1/
├── X.npy
├── y.npy
├── feature_columns.json
├── window_manifest.csv
├── dataset_summary.json
├── inspection_summary.json
└── splits/
    ├── train_indices.npy
    ├── val_indices.npy
    ├── test_indices.npy
    └── split_summary.json
```

其中：

```text
dataset_summary.json
由 build_window_dataset.py 生成，记录窗口数据集构建结果。

inspection_summary.json
由 inspect_dataset.py 生成，记录数据集质量检查结果。

split_summary.json
由 split_dataset.py 生成，记录 train / val / test 划分结果。
```

## 脚本使用说明

脚本使用方式统一记录在：

```text
scripts/README.md
```

当前主要脚本包括：

```text
scripts/build_window_dataset.py
scripts/inspect_dataset.py
scripts/split_dataset.py
```

## 测试

运行全部测试：

```bash
cd railphm-ai
pytest
```

测试目标包括：

```text
1. /health 接口行为稳定。
2. /infer mock 推理接口行为稳定。
3. SegmentLoader 能正确读取 segment CSV。
4. FeatureProcessor 能正确生成模型输入特征。
5. WindowBuilder 能正确构造滑动窗口和二分类标签。
6. WindowDatasetBuilder 能正确输出 X.npy、y.npy、window_manifest.csv 等文件。
7. DatasetInspector 能正确检查数据集质量。
8. DatasetSplitBuilder 能按 segment_id 完成无泄露划分。
```

## 数据管理注意事项

数据集构建会产生本地数据文件和较大的 NumPy 数组文件，不应提交到 GitHub。建议根目录 `.gitignore` 包含：

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
忽略 NumPy 大数组文件，例如 X.npy、y.npy、train_indices.npy、val_indices.npy 和 test_indices.npy。
```

## 关于 InfluxDB 的阶段说明

论文设计中，ATP 监测时序数据最终由 InfluxDB 存储。当前阶段为了优先跑通预测模块真实数据链路，先使用本地 ATP segment CSV 作为离线数据来源，完成数据集构建、质量检查和训练集划分。

该实现不改变论文中 InfluxDB 作为系统时序数据存储方案的设计。后续接入在线推理时，可将数据读取层替换为 InfluxDB 查询结果，并保持 `FeatureProcessor`、`WindowBuilder` 和模型推理接口尽量不变。

当前阶段可理解为：

```text
CSV：开发阶段、实验阶段、离线训练阶段的数据来源。
InfluxDB：系统运行阶段、在线查询阶段、部署阶段的数据来源。
```

## 下一步开发计划

下一阶段建议进入模型训练准备与 baseline 开发：

```text
Task 4：模型训练 baseline 开发
```

建议继续按小任务推进：

```text
Task 4-1：实现训练数据加载器，基于 X.npy、y.npy 和 train/val/test indices 读取数据。
Task 4-2：实现最小 baseline 模型，例如 Logistic Regression / MLP / 简单 LSTM，用于验证数据集可训练。
Task 4-3：实现训练指标输出，包括 accuracy、precision、recall、F1、AUC 等。
Task 4-4：保存 baseline 训练结果和评估报告。
Task 4-5：再进入 Bi-LSTM + Attention 模型实现。
```

在进入 Bi-LSTM + Attention 前，建议先用简单 baseline 验证数据是否能被模型学习，避免直接上复杂模型后难以定位问题。
