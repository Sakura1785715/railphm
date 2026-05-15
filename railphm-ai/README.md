# RailPHM AI 子模块说明

`railphm-ai` 是 RailPHM 项目的 AI 推理与模型训练子模块，负责 ATP 车载监测数据的窗口数据集构建、数据集划分、标准化处理、工况划分、工况增强、时序风险预测模型训练，以及基于模型产物的运行时推理。

当前子模块的核心技术链路为：

```text
ATP 车载监测数据
  ↓
滑动窗口样本构建
  ↓
按 segment_id 划分 train / val / test
  ↓
基于训练集统计量进行标准化
  ↓
K-means 工况划分
  ↓
工况 one-hot 特征增强
  ↓
Bi-LSTM + Attention 风险预测模型训练
  ↓
保序回归概率校准
  ↓
MC-Dropout 不确定性估计
  ↓
Flask /infer 接口运行时推理
```

本目录已清理为只保留当前真实业务链路所需脚本。历史 baseline、诊断、实验汇总和统一实验流水线脚本已不再作为主流程维护。

---

## 1. 目录结构

当前 `railphm-ai` 主要目录含义如下：

```text
railphm-ai/
├── app/                         核心业务代码
│   ├── api/                     Flask API 路由
│   ├── calibration/             概率校准器
│   ├── condition/               工况特征提取与聚类
│   ├── core/                    配置
│   ├── dataset/                 数据特征配置
│   ├── models/                  时序模型结构
│   ├── repository/              推理数据读取
│   ├── runtime/                 模型产物加载与运行时推理
│   ├── schema/                  接口数据结构整理
│   ├── service/                 推理业务服务
│   ├── training/                训练核心逻辑
│   └── uncertainty/             MC-Dropout 不确定性估计
├── scripts/                     主链路命令行脚本
├── data/                        本地数据目录，通常不提交
├── outputs/                     模型训练输出目录，通常不提交
├── tests/                       测试目录
├── run.py                       Flask 服务启动入口
└── README.md                    本说明文件
```

---

## 2. scripts 目录保留脚本

当前 `scripts/` 目录只保留真实训练和推理链路相关脚本：

```text
scripts/
├── __init__.py
├── build_window_dataset.py
├── split_dataset.py
├── scale_window_dataset.py
├── cluster_conditions.py
├── build_condition_augmented_dataset.py
├── train_sequence_model.py
└── build_model_artifact_manifest.py
```

各脚本作用如下：

| 脚本 | 作用 |
|---|---|
| `build_window_dataset.py` | 从 ATP segment CSV 构建滑动窗口数据集 |
| `split_dataset.py` | 按 `segment_id` 划分训练集、验证集、测试集 |
| `scale_window_dataset.py` | 基于训练集统计量对窗口数据进行标准化 |
| `cluster_conditions.py` | 使用 K-means 对窗口样本进行工况划分 |
| `build_condition_augmented_dataset.py` | 将工况 one-hot 特征拼接到窗口特征中 |
| `train_sequence_model.py` | 训练 Bi-LSTM+Attention 等时序风险预测模型 |
| `build_model_artifact_manifest.py` | 生成运行时模型产物清单 `model_artifact_manifest.json` |

---

## 3. 默认实验口径

当前默认训练与推理口径为：

```text
window_size = 30
stride = 1
prediction_horizon = 1
condition_k = 3
model = bilstm_attention
```

含义如下：

```text
window_size = 30：每个样本窗口包含连续 30 个时间步；
stride = 1：滑动窗口每次向后移动 1 个时间步；
prediction_horizon = 1：使用窗口结束后的下一个时间步构造标签；
condition_k = 3：K-means 将运行状态划分为 3 类工况；
model = bilstm_attention：最终风险预测模型采用 Bi-LSTM + Attention。
```

---

## 4. 推荐数据与产物目录

当前推荐使用统一数据集目录：

```text
data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1
```

该目录在完成标准化、工况划分和工况 one-hot 增强后，作为最终训练数据集使用。

推荐模型输出目录：

```text
outputs/sequence_models/bilstm_attention_h1_full_features
```

该目录保存最终模型权重、训练配置、校准器、评估摘要和运行时 manifest。

`data/` 和 `outputs/` 通常应加入 `.gitignore`，不建议提交到远程仓库。

---

## 5. 环境准备

进入 `railphm-ai` 目录：

```bash
cd /Users/hannn/Desktop/railphm/railphm-ai
```

激活虚拟环境。若使用项目统一虚拟环境，可执行：

```bash
source /Users/hannn/Desktop/railphm/railphm-server/.venv/bin/activate
```

也可以根据本地实际环境调整路径。

---

## 6. 数据集构建与训练流程

### 6.1 构建滑动窗口数据集

```bash
python scripts/build_window_dataset.py   --segments-dir /path/to/atp_segments_v1   --output-dir data/datasets/bilstm_attention_h1_full_features/raw_window_w30_s1_h1   --window-size 30   --stride 1   --horizon 1   --feature-profile full_features   --overwrite   --verbose
```

输出文件包括：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
```

---

### 6.2 划分训练集、验证集和测试集

```bash
python scripts/split_dataset.py   --dataset-dir data/datasets/bilstm_attention_h1_full_features/raw_window_w30_s1_h1   --train-ratio 0.7   --val-ratio 0.15   --test-ratio 0.15   --seed 42   --overwrite
```

输出文件位于：

```text
splits/train_indices.npy
splits/val_indices.npy
splits/test_indices.npy
splits/split_summary.json
```

划分方式以 `segment_id` 为单位，避免同一连续片段中的高度相似窗口同时进入训练集和测试集。

---

### 6.3 标准化窗口数据集

```bash
python scripts/scale_window_dataset.py   --input-dir data/datasets/bilstm_attention_h1_full_features/raw_window_w30_s1_h1   --output-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --method standard   --overwrite
```

标准化参数只基于训练集样本拟合，验证集和测试集只执行 transform，避免数据泄露。

输出目录会保留原有数据集文件和 `splits/`，并新增：

```text
scaler_summary.json
```

---

### 6.4 执行 K-means 工况划分

```bash
python scripts/cluster_conditions.py   --dataset-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --n-clusters 3   --seed 42   --overwrite   --verbose
```

输出文件包括：

```text
condition_labels.npy
condition_manifest.csv
condition_summary.json
condition_model.pkl
```

其中 `condition_labels.npy` 是每个窗口样本对应的工况编号。

---

### 6.5 构建工况 one-hot 增强数据集

当前项目采用原地增强方式，直接在标准化数据集目录中更新 `X.npy` 和相关元信息：

```bash
python scripts/build_condition_augmented_dataset.py   --input-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --verbose
```

执行后，原始特征后会追加：

```text
condition_0
condition_1
condition_2
```

如果原始特征维度为 20，工况数为 3，则增强后：

```text
X.shape: [num_samples, 30, 23]
```

该步骤会生成或更新：

```text
X.npy
feature_columns.json
dataset_summary.json
condition_augmented_summary.json
```

---

### 6.6 训练 Bi-LSTM+Attention 时序模型

先用较小 epoch 跑通流程：

```bash
python scripts/train_sequence_model.py   --dataset-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --output-dir outputs/sequence_models/bilstm_attention_h1_full_features   --model bilstm_attention   --epochs 3   --batch-size 256   --lr 0.001   --seed 42   --device auto   --threshold 0.5   --hidden-dim 64   --num-layers 1   --dropout 0.2   --best-metric val_auc   --overwrite
```

正式训练可将 `--epochs` 改为 30：

```bash
python scripts/train_sequence_model.py   --dataset-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --output-dir outputs/sequence_models/bilstm_attention_h1_full_features   --model bilstm_attention   --epochs 30   --batch-size 256   --lr 0.001   --seed 42   --device auto   --threshold 0.5   --hidden-dim 64   --num-layers 1   --dropout 0.2   --best-metric val_auc   --overwrite
```

训练完成后，输出目录应包含：

```text
best_model.pt
training_config.json
metrics_history.csv
val_predictions.csv
test_predictions.csv
sequence_model_report.json
feature_columns.json
threshold_summary.json
evaluation_summary.json
calibrator.pkl
calibration_summary.json
```

其中：

```text
best_model.pt：验证集指标最优模型权重；
val_predictions.csv：验证集预测结果，用于阈值搜索和保序回归拟合；
test_predictions.csv：测试集预测结果；
threshold_summary.json：验证集最佳阈值；
calibrator.pkl：保序回归概率校准器；
calibration_summary.json：概率校准摘要；
evaluation_summary.json：最终评估摘要。
```

---

### 6.7 生成运行时模型产物清单

```bash
python scripts/build_model_artifact_manifest.py   --model-dir outputs/sequence_models/bilstm_attention_h1_full_features   --overwrite
```

生成：

```text
model_artifact_manifest.json
```

运行时会通过该文件加载：

```text
best_model.pt
feature_columns.json
calibrator.pkl
threshold
calibration 配置
uncertainty 配置
```

---

## 7. 启动 AI 服务

启动前建议确认默认配置：

```text
AI_MODEL_DIR = outputs/sequence_models/bilstm_attention_h1_full_features
AI_DATASET_DIR = data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1
AI_DEFAULT_MC_SAMPLES = 30
```

启动服务：

```bash
python run.py
```

如果需要临时指定模型目录和数据集目录，可以使用环境变量：

```bash
RAILPHM_AI_MODEL_DIR=outputs/sequence_models/bilstm_attention_h1_full_features RAILPHM_AI_DATASET_DIR=data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1 RAILPHM_AI_ENABLE_MOCK_FALLBACK=false python run.py
```

---

## 8. 调用 /infer 接口

另开一个终端执行：

```bash
curl -X POST http://127.0.0.1:5001/infer   -H "Content-Type: application/json"   -d '{
    "device_id": 1001,
    "ts_end": "2026-05-09 12:00:00",
    "window_minutes": 30,
    "sample_index": 0,
    "mc_samples": 30
  }'
```

正常情况下，返回结果应包含：

```json
{
  "data_source": "local_window_dataset",
  "model_name": "bilstm_attention",
  "model_version": "bilstm_attention_h1_full_features",
  "calibration_enabled": true,
  "calibration_method": "isotonic_regression",
  "uncertainty_enabled": true,
  "uncertainty_method": "mc_dropout",
  "mc_samples": 30
}
```

关键字段含义：

| 字段 | 含义 |
|---|---|
| `risk_raw` | MC-Dropout 多次前向传播得到的原始概率均值 |
| `risk_raw_std` | 原始概率标准差 |
| `risk_score` | 保序回归校准后的风险概率均值 |
| `risk_std` | 校准后概率标准差 |
| `threshold` | 验证集搜索得到的分类阈值 |
| `predicted_label` | 根据 `risk_score >= threshold` 得到的预测标签 |
| `calibration_enabled` | 是否启用保序回归概率校准 |
| `uncertainty_enabled` | 是否启用 MC-Dropout 不确定性估计 |
| `trace` | 样本追溯信息 |
| `y_true` | 本地窗口数据集中的真实标签 |

如果返回：

```text
data_source = mock_fallback
```

说明真实模型或数据集加载失败，需要优先检查：

```text
RAILPHM_AI_MODEL_DIR
RAILPHM_AI_DATASET_DIR
model_artifact_manifest.json
calibrator.pkl
feature_columns.json
```

---

## 9. 当前保留链路说明

当前项目不再维护以下脚本类型：

```text
baseline 训练脚本
baseline 分析脚本
数据泄露诊断脚本
随机标签 sanity check 脚本
feature ablation 汇总脚本
prediction_horizon 汇总脚本
统一实验 pipeline 配置脚本
单窗口 runtime 调试脚本
```

如需临时诊断，可直接在终端中编写一次性 Python 片段完成，不再将诊断脚本常驻项目目录。

---

## 10. 常见问题

### 10.1 为什么没有 configs 目录？

`configs/` 原本用于统一实验 pipeline 的 JSON 配置管理。当前项目已经移除统一实验 pipeline，改为保留清晰的 7 步主链路脚本，因此不再需要 `configs/`。

### 10.2 为什么没有 baseline 脚本？

当前最终模型已经确定为 Bi-LSTM+Attention，baseline 训练和分析脚本不再参与业务链路。项目只保留最终模型训练入口 `train_sequence_model.py`。

### 10.3 为什么工况增强直接写回标准化数据集目录？

当前项目已经确定后续训练和推理都使用工况增强后的数据集，不再保留未增强版本作为主流程输入。因此 `build_condition_augmented_dataset.py` 默认支持原地增强，减少数据冗余。

### 10.4 为什么 `risk_raw` 和 `risk_score` 可能不同？

`risk_raw` 是模型 sigmoid 后的原始概率均值；`risk_score` 是经过保序回归校准后的概率均值。启用校准后，二者可能不同。

### 10.5 为什么 `risk_std` 可能为 0？

如果 MC-Dropout 多次采样得到的原始概率经过保序回归后都被映射到同一个校准概率，例如全部映射到 1.0，则 `risk_std` 可能为 0。这不一定表示 MC-Dropout 没有执行，应同时查看 `risk_raw_std` 和 `mc_samples`。

---

## 11. 最小可用命令链路

从数据构建到运行时推理的最小链路如下：

```bash
python scripts/build_window_dataset.py   --segments-dir /path/to/atp_segments_v1   --output-dir data/datasets/bilstm_attention_h1_full_features/raw_window_w30_s1_h1   --window-size 30   --stride 1   --horizon 1   --feature-profile full_features   --overwrite   --verbose

python scripts/split_dataset.py   --dataset-dir data/datasets/bilstm_attention_h1_full_features/raw_window_w30_s1_h1   --train-ratio 0.7   --val-ratio 0.15   --test-ratio 0.15   --seed 42   --overwrite

python scripts/scale_window_dataset.py   --input-dir data/datasets/bilstm_attention_h1_full_features/raw_window_w30_s1_h1   --output-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --method standard   --overwrite

python scripts/cluster_conditions.py   --dataset-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --n-clusters 3   --seed 42   --overwrite   --verbose

python scripts/build_condition_augmented_dataset.py   --input-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --verbose

python scripts/train_sequence_model.py   --dataset-dir data/datasets/bilstm_attention_h1_full_features/scaled_window_w30_s1_h1   --output-dir outputs/sequence_models/bilstm_attention_h1_full_features   --model bilstm_attention   --epochs 30   --batch-size 256   --lr 0.001   --seed 42   --device auto   --threshold 0.5   --hidden-dim 64   --num-layers 1   --dropout 0.2   --best-metric val_auc   --overwrite

python scripts/build_model_artifact_manifest.py   --model-dir outputs/sequence_models/bilstm_attention_h1_full_features   --overwrite

python run.py
```
