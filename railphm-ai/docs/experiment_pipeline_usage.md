# RailPHM AI 统一实验流程使用说明

## 1. 文档目的

本文档用于说明 `railphm-ai` 统一实验入口的使用方式，面向后续维护 RailPHM 毕业设计项目的开发者。

文档覆盖以下内容：

- 如何准备 Python 运行环境；
- 如何确认原始 ATP segment CSV 路径；
- 如何使用 dry-run 检查流程和配置；
- 如何正式跑完整实验流程；
- 如何只跑某个阶段；
- 如何从失败阶段继续执行；
- 如何临时修改 `window_size`、`stride`、`prediction_horizon`、`model` 等参数；
- 如何查看训练结果和预测输出；
- 如何安全清理生成的数据集和模型输出；
- 常见错误的排查方法。

本文档只描述工程使用方式，不改变实验逻辑、模型结构、标签规则或数据处理口径。

## 2. 当前统一入口文件

统一实验入口文件：

```text
scripts/run_experiment_pipeline.py
```

默认配置文件：

```text
configs/experiment_pipeline.json
```

最常用运行命令：

```bash
cd railphm-ai
python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json
```

该命令会按照配置文件串联执行：

```text
build -> inspect -> split -> scale -> condition -> augment -> train -> threshold -> evaluate -> diagnose
```

## 3. 推荐运行环境

从项目根目录进入：

```bash
cd /Users/hannn/Desktop/railphm
```

激活 Python 虚拟环境示例：

```bash
source railphm-server/.venv/bin/activate
```

进入 `railphm-ai`：

```bash
cd railphm-ai
```

说明：

- 上面的路径是当前开发机器上的示例，其他机器可按实际项目路径调整；
- 只要当前 Python 环境能运行 `railphm-ai` 的 `pytest` 和训练脚本即可；
- 如果 threshold 或 train 阶段提示缺少 `torch`，说明当前环境不是训练环境，需要切换到安装了 PyTorch 的虚拟环境。

## 4. 原始数据目录说明

配置文件中的 `segments_dir` 用于指定原始 ATP segment CSV 目录。

如果原始数据放在项目内，可以检查：

```bash
ls data/processed/atp_segments | head
```

如果原始数据放在外部目录，可以检查：

```bash
ls "你的/atp_segments_v1/路径" | head
```

目录中应包含类似下面的文件：

```text
segment_*.csv
```

注意：

- 不要删除原始 segment CSV 目录；
- `data/datasets/` 和 `outputs/` 是实验产物，必要时可以重新生成；
- `data/processed/` 如果存放原始或中间清洗数据，不应随意删除；
- 修改 `segments_dir` 后，建议先运行 dry-run 确认路径解析正确。

## 5. 配置文件说明

默认配置文件位于：

```text
configs/experiment_pipeline.json
```

关键配置项如下：

| 配置项 | 作用 |
|---|---|
| `experiment_name` | 实验名称，用于生成数据集目录和模型输出目录 |
| `segments_dir` | 原始 ATP segment CSV 目录 |
| `dataset_root` | 生成的数据集根目录，默认 `data/datasets` |
| `output_root` | 模型训练输出根目录，默认 `outputs/sequence_models` |
| `window.window_size` | 滑动窗口长度 |
| `window.stride` | 滑动窗口步长 |
| `window.prediction_horizon` | 预测目标时刻距离，表示窗口结束后第 H 个目标时刻 |
| `feature.profile` | 特征配置名称，例如 `full_features` |
| `split.train_ratio` | 训练集 segment 比例 |
| `split.val_ratio` | 验证集 segment 比例 |
| `split.test_ratio` | 测试集 segment 比例 |
| `split.seed` | segment 级划分随机种子 |
| `scale.enabled` | 是否执行 train-only 标准化 |
| `condition.enabled` | 是否执行 K-means 工况划分和工况增强 |
| `condition.k` | K-means 工况聚类数量 |
| `model.name` | 训练模型名称，例如 `bilstm_attention` |
| `model.epochs` | 训练轮数 |
| `model.batch_size` | batch size |
| `model.learning_rate` | 学习率 |
| `model.hidden_dim` | LSTM hidden dimension |
| `model.dropout` | dropout 概率 |
| `threshold.default_threshold` | 默认固定阈值，通常为 `0.5` |
| `threshold.search_on` | 阈值搜索数据集，必须为 `val` |
| `threshold.metric` | 阈值搜索指标，默认 `f1` |
| `diagnosis.high_fp_enabled` | 是否打印高误报 segment 诊断 |
| `run.skip_existing` | 已有完整输出时是否跳过该阶段 |
| `run.overwrite` | 是否允许覆盖已有输出 |
| `run.dry_run` | 是否只打印流程，不实际执行 |

默认配置代表：

```text
window_size = 30
stride = 1
prediction_horizon = 1
model = bilstm_attention
feature_profile = full_features
condition_k = 3
```

## 6. 完整流程阶段说明

| 阶段 | 命令阶段名 | 作用 | 主要输入 | 主要输出 |
|---|---|---|---|---|
| 构建窗口数据集 | `build` | 从 segment CSV 构造 `X`、`y` 和窗口追溯信息 | segment CSV | `X.npy`、`y.npy`、`window_manifest.csv`、`dataset_summary.json` |
| 数据集检查 | `inspect` | 检查 `X`、`y`、manifest、summary 是否一致 | `window_dataset` | `inspection_summary.json` 或终端检查结果 |
| 数据集划分 | `split` | 按 `segment_id` 划分 train / val / test | `window_dataset` | `train_indices.npy`、`val_indices.npy`、`test_indices.npy`、`split_summary.json` |
| 标准化 | `scale` | 只用 train 拟合 scaler，并转换全量数据 | `window_dataset` | `train_scaled` 数据集、`scaler_summary.json` |
| 工况聚类 | `condition` | 使用 K-means 划分运行工况 | `train_scaled` | `condition_labels.npy`、`condition_summary.json`、`condition_model.pkl` |
| 工况增强 | `augment` | 拼接 condition one-hot 特征 | `train_scaled` | `train_scaled_condition_k3` 数据集 |
| 模型训练 | `train` | 训练 LSTM / Bi-LSTM / Attention 模型 | 增强数据集 | `best_model.pt`、`metrics_history.csv`、`test_predictions.csv`、`sequence_model_report.json` |
| 阈值搜索 | `threshold` | 只在 val 集搜索最佳阈值 | `best_model.pt` 和验证集数据 | `best_val_threshold`、`threshold_summary.json` |
| 测试评估 | `evaluate` | 在 test 集上使用固定阈值和 best-val 阈值评估 | `test_predictions.csv` | Precision、Recall、F1、AUC、Brier、`evaluation_summary.json` |
| 高 FP 诊断 | `diagnose` | 打印高误报 segment Top N | `test_predictions.csv`、`window_manifest.csv` | 终端高 FP 表格 |

## 7. dry-run 检查流程

dry-run 不会真正构建数据集或训练模型，只打印解析后的配置、路径和阶段命令。

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --dry-run
```

合格输出应包含：

- `experiment_name`
- `enabled_stages`
- `resolved_paths`
- `resolved_config`
- `build`
- `inspect`
- `split`
- `scale`
- `condition`
- `augment`
- `train`
- `threshold`
- `evaluate`
- `diagnose`

建议在正式运行前始终先执行 dry-run，确认 `segments_dir`、`experiment_name` 和输出目录符合预期。

## 8. 正式跑完整流程

正式运行命令：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json
```

该命令会实际执行：

```text
build -> inspect -> split -> scale -> condition -> augment -> train -> threshold -> evaluate -> diagnose
```

默认配置对应：

```text
window_size = 30
stride = 1
prediction_horizon = 1
model = bilstm_attention
feature_profile = full_features
condition_k = 3
```

完整流程会生成数据集、模型权重、训练历史、测试预测和评估摘要。训练阶段可能耗时较长，运行前应确认当前 Python 环境安装了 `torch`。

## 9. 从某个阶段继续执行

如果某个阶段失败，不应盲目从头重跑。可以从失败阶段继续执行。

从 threshold 继续：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --stage-from threshold
```

从 train 继续：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --stage-from train
```

只跑 train：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --only-stage train
```

只跑 build 到 split：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --stage-to split
```

从 scale 跑到 evaluate：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --stage-from scale \
  --stage-to evaluate
```

阶段顺序固定为：

```text
build -> inspect -> split -> scale -> condition -> augment -> train -> threshold -> evaluate -> diagnose
```

## 10. 命令行参数覆盖配置文件

命令行参数优先级高于 JSON 配置。临时实验可以不修改配置文件，直接在命令行覆盖关键字段。

临时跑 h5：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --prediction-horizon 5
```

临时改模型：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --model bilstm_attention
```

临时改训练轮数：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --epochs 20
```

临时改 batch size：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --batch-size 128
```

临时改学习率：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --learning-rate 0.0005
```

注意：修改 `prediction_horizon`、模型或特征配置时，应确认 `experiment_name` 能区分不同实验，避免不同实验输出混在同一目录中。

## 11. 常用命令总表

| 目的 | 命令 |
|---|---|
| 检查配置和流程 | `python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json --dry-run` |
| 跑完整流程 | `python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json` |
| 只跑训练 | `python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json --only-stage train` |
| 从阈值搜索继续 | `python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json --stage-from threshold` |
| 只构建到划分 | `python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json --stage-to split` |
| 跑 h5 | `python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json --prediction-horizon 5` |
| 覆盖已有结果重跑 | `python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json --overwrite` |

## 12. skip_existing 与 overwrite 说明

`run.skip_existing=true` 时，如果某个阶段的输出完整且关键配置匹配，该阶段会跳过，并打印 `[SKIP]`。

`run.overwrite=true` 或命令行添加 `--overwrite` 时，允许覆盖已有输出。

常见规则：

- 输出完整且 `skip_existing=true`：跳过该阶段；
- 输出不存在：执行该阶段；
- 输出已存在但不完整：报错，提示手动清理或使用 `--overwrite`；
- 输出完整但配置不匹配：不应静默复用，需要检查实验名或覆盖策略。

不建议无脑使用 `--overwrite`。覆盖前应确认不会误删需要保留的训练结果。

## 13. 安全清理生成物

以下目录是可重新生成的实验产物：

```text
data/datasets/
outputs/
```

如需重新干净跑一遍，可以删除：

```bash
rm -rf data/datasets
rm -rf outputs
```

不要删除：

```text
data/processed/
原始 atp_segments_v1/
configs/
scripts/
app/
tests/
```

删除 `data/datasets/` 和 `outputs/` 后，可以重新使用完整流程命令生成数据集与模型输出。

## 14. 跑完后如何查看结果

默认模型输出路径：

```text
outputs/sequence_models/bilstm_attention_h1_full_features
```

查看输出目录：

```bash
ls outputs/sequence_models/bilstm_attention_h1_full_features
```

查看训练报告：

```bash
python -m json.tool outputs/sequence_models/bilstm_attention_h1_full_features/sequence_model_report.json | less
```

查看预测结果：

```bash
head outputs/sequence_models/bilstm_attention_h1_full_features/test_predictions.csv
```

查看训练历史：

```bash
head outputs/sequence_models/bilstm_attention_h1_full_features/metrics_history.csv
```

常见输出文件：

| 文件 | 作用 |
|---|---|
| `best_model.pt` | 最优模型权重 |
| `metrics_history.csv` | 每个 epoch 的训练和验证指标 |
| `test_predictions.csv` | 测试集预测概率和标签 |
| `training_config.json` | 训练配置 |
| `sequence_model_report.json` | 模型训练和测试报告 |
| `threshold_summary.json` | 验证集阈值搜索结果 |
| `evaluation_summary.json` | 测试集固定阈值和 best-val 阈值评估结果 |

## 15. 常见问题排查

### 问题 1：No module named 'app'

这是 Python 导入路径问题，通常发生在脚本没有把 `railphm-ai` 项目根目录加入 `sys.path`，或 subprocess 没有设置 `cwd` / `PYTHONPATH`。

处理方式：

- 确认从 `railphm-ai` 目录运行；
- 确认 `scripts/run_experiment_pipeline.py` 已处理 `PROJECT_ROOT`；
- 如果前置阶段已经完成，可以从失败阶段继续：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --stage-from threshold
```

### 问题 2：输出目录已存在

处理方式：

- 使用默认 `skip_existing` 跳过完整阶段；
- 使用 `--overwrite` 覆盖重跑；
- 或手动删除对应 `data/datasets/实验名` 或 `outputs/sequence_models/实验名`。

### 问题 3：找不到 segment CSV

处理方式：

- 检查 `segments_dir`；
- 使用 `ls` 命令确认目录下有 `segment_*.csv`；
- 修改 `configs/experiment_pipeline.json` 中的 `segments_dir`。

示例：

```bash
ls "你的/atp_segments_v1/路径" | head
```

### 问题 4：threshold 阶段失败

如果训练已经完成，不需要从头跑。

处理方式：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --stage-from threshold
```

如果错误是缺少 `torch`，需要切换到训练所用的 Python 虚拟环境。

### 问题 5：训练太慢

处理方式：

- 先使用 `--dry-run` 检查配置；
- 调试时可以临时减少 `--epochs`；
- 最终实验不建议随意改动参数，避免实验口径不一致。

示例：

```bash
python scripts/run_experiment_pipeline.py \
  --config configs/experiment_pipeline.json \
  --epochs 3
```

## 16. 与论文实验口径的一致性说明

默认配置对应论文主实验口径：

```text
window_size = 30
stride = 1
prediction_horizon = 1
model = bilstm_attention
feature_profile = full_features
condition_k = 3
```

标签逻辑保持为：

```text
窗口结束后第 H 个目标时刻的“报警部位”是否非空。
```

实验约束：

- 不使用 future-horizon 区间标签；
- 不把未来 H 秒内任意报警合并成正样本；
- 不使用 test 集选择阈值；
- 不随机窗口划分；
- 使用 `segment_id` 划分 train / val / test，以避免滑动窗口数据泄漏；
- 标准化和 K-means 工况划分都只使用 train 集拟合参数。

## 17. 运行测试

开发或修改统一入口脚本后，建议先运行：

```bash
pytest tests/test_run_experiment_pipeline.py
```

核心测试：

```bash
pytest tests/test_dataset_builder.py
pytest tests/test_infer.py
pytest tests/test_health.py
```

完整测试：

```bash
pytest
```

如果系统 Python 缺少 `torch`，完整测试可能在训练或模型相关测试收集阶段失败。此时应切换到安装了训练依赖的虚拟环境。

## 18. 最终检查清单

- [ ] 已确认原始 segment CSV 存在；
- [ ] 已 dry-run 检查配置；
- [ ] 已确认 `window_size` / `stride` / `prediction_horizon`；
- [ ] 已确认 `experiment_name`；
- [ ] 已正式运行完整流程；
- [ ] 已查看 `sequence_model_report.json`；
- [ ] 已查看 `test_predictions.csv`；
- [ ] 已保存或记录核心指标；
- [ ] 未删除原始 segment 数据。

## 19. 默认模型运行时产物固化说明

完成统一实验流程后，默认 Bi-LSTM+Attention 模型的训练产物位于：

```text
outputs/sequence_models/bilstm_attention_h1_full_features
```

当前系统将该目录作为 `railphm-ai` 默认模型运行时目录。该目录用于后续模型加载、单窗口风险预测、概率校准、MC-Dropout 不确定性估计以及 `/infer` 真实推理接入。

### 19.1 模型运行时必要产物

默认模型目录下应至少包含以下文件：

```text
best_model.pt
training_config.json
sequence_model_report.json
threshold_summary.json
evaluation_summary.json
metrics_history.csv
val_predictions.csv
test_predictions.csv
feature_columns.json
model_artifact_manifest.json
```

其中，`best_model.pt` 为训练得到的最优模型权重；`training_config.json` 用于恢复模型结构；`threshold_summary.json` 用于记录验证集最优阈值；`feature_columns.json` 用于保存模型输入特征顺序；`model_artifact_manifest.json` 用于统一描述模型运行时需要加载的产物。

### 19.2 当前默认模型配置

当前默认模型为：

```text
model_version = bilstm_attention_h1_full_features
model_name = bilstm_attention
model_class = BiLSTMAttentionClassifier
window_size = 30
feature_dim = 23
input_dim = 23
hidden_dim = 64
num_layers = 1
dropout = 0.3
threshold = 0.26
```

模型输入为单个滑动窗口样本，形状为：

```text
[30, 23]
```

其中，`30` 表示窗口长度，`23` 表示每个时间步的输入特征数。

### 19.3 当前模型输入特征

当前默认模型使用 23 维输入特征，字段顺序由模型目录下的 `feature_columns.json` 固定。当前字段如下：

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
信号机ID.1
信号机里程.1
行别.3
线路编号.3
运行方向
室外温度
湿度
condition_0
condition_1
condition_2
```

其中，前 20 个字段来自 ATP 原始监测数据中的运行状态、线路、应答器、信号机和环境信息；最后 3 个字段为 K-means 工况划分后追加的 one-hot 工况特征。

需要注意的是，`报警部位` 字段仅用于构造窗口标签，不作为模型输入特征，以避免标签泄露。

### 19.4 模型产物检查

可使用以下命令检查默认模型产物是否齐全：

```bash
cd railphm-ai

MODEL_DIR="outputs/sequence_models/bilstm_attention_h1_full_features"

echo "== Check required artifact files =="
for f in \
  best_model.pt \
  training_config.json \
  sequence_model_report.json \
  threshold_summary.json \
  evaluation_summary.json \
  metrics_history.csv \
  val_predictions.csv \
  test_predictions.csv \
  feature_columns.json \
  model_artifact_manifest.json
do
  if [ -f "$MODEL_DIR/$f" ]; then
    echo "[OK] $f"
  else
    echo "[MISSING] $f"
  fi
done
```

如果全部显示 `[OK]`，说明默认模型运行时产物已经齐全。

### 19.5 生成模型产物清单

如果模型目录中尚未生成 `model_artifact_manifest.json`，可执行：

```bash
python scripts/build_model_artifact_manifest.py \
  --model-dir outputs/sequence_models/bilstm_attention_h1_full_features \
  --overwrite
```

生成后，模型运行时加载器将以 `model_artifact_manifest.json` 作为统一入口，读取模型配置、权重路径、阈值信息和特征字段顺序。

### 19.6 模型运行时加载能力

当前阶段已新增 `app/runtime` 运行时模块，用于承载训练产物加载和模型推理相关能力：

```text
app/runtime/artifact_manifest.py
app/runtime/model_loader.py
```

其中，`ArtifactManifest` 负责读取和校验 `model_artifact_manifest.json`；`SequenceModelRuntime` 负责根据 manifest 构造模型、加载 `best_model.pt` 权重，并提供单窗口预测能力。

当前已实现的核心能力包括：

```text
ArtifactManifest.load(model_dir)
SequenceModelRuntime.from_model_dir(model_dir)
SequenceModelRuntime.predict_proba(window)
```

### 19.7 单窗口预测输入输出

`predict_proba(window)` 接收一个 `numpy.ndarray` 类型的窗口样本，输入形状必须为：

```text
(30, 23)
```

输出字段包括：

```text
risk_raw
risk_score
threshold
predicted_label
model_version
model_name
```

当前阶段尚未接入概率校准，因此：

```text
risk_score = risk_raw
```

后续完成概率校准后，`risk_raw` 将表示模型原始输出概率，`risk_score` 将表示校准后的风险分数。

### 19.8 当前阶段边界

当前模型运行时固化阶段只完成以下内容：

```text
训练产物整理
feature_columns.json 固化
model_artifact_manifest.json 生成
ArtifactManifest 读取与校验
SequenceModelRuntime 模型加载
单窗口确定性预测
```

当前阶段尚未完成：

```text
概率校准
MC-Dropout 不确定性估计
/infer 真实推理接入
MySQL 风险结果落库
健康度映射
告警等级生成
前端真实结果展示
```

这些内容将在后续阶段继续开发。
