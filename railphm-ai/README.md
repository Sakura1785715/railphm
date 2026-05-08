# RailPHM AI 开发与脚本使用说明

本文档用于记录 `railphm-ai` 子模块当前阶段的数据处理、工况划分、baseline 训练与对比分析流程。当前默认实验口径已经统一为 `window_size=30`、`stride=1`、`prediction_horizon=1`，后续预测模块相关实验默认基于该参数组合展开。

---

## 1. 基本信息

### 1.1 项目位置

进入 `railphm-ai` 子模块：

```bash
cd /Users/hannn/Desktop/railphm/railphm-ai
```

激活当前项目虚拟环境：

```bash
source /Users/hannn/Desktop/railphm/railphm-server/.venv/bin/activate
```

### 1.2 原始数据路径

当前 ATP 连续监测 CSV 片段统一存放在本地外部目录：

```bash
/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/仿真数据/atp_segments_v1
```

该目录下包含多个按时间段切分的 `segment_*.csv` 文件。每个 CSV 文件表示一段连续递增的 ATP 车载监测数据片段，后续窗口样本由这些连续片段构建而来。

### 1.3 项目内数据集目录

项目内部数据集默认保存在：

```bash
data/datasets/
```

该目录已加入 `.gitignore`，不会提交到远程仓库。因此远程 GitHub 看不到本地数据集是正常现象。后续所有实验以本地 `railphm-ai/data/datasets/` 下实际生成的数据为准。

### 1.4 当前默认实验参数

当前预测模块默认窗口参数为：

```text
window_size = 30
stride = 1
prediction_horizon = 1
```

含义如下：

```text
window_size = 30：每个窗口包含连续 30 个时间步；
stride = 1：窗口每次向后滑动 1 个时间步；
prediction_horizon = 1：使用窗口结束后的下一个时间步构造风险标签。
```

### 1.5 默认数据集命名

当前推荐的数据集命名如下：

```text
sim_window_w30_s1_h1_raw
sim_window_w30_s1_h1_train_scaled
sim_window_w30_s1_h1_train_scaled_condition_k3
```

含义如下：

```text
sim：仿真 ATP 数据集；
w30：窗口长度为 30；
s1：滑动步长为 1；
h1：预测距离为 1；
raw：未标准化的窗口数据集；
train_scaled：使用训练集统计量标准化后的窗口数据集；
condition_k3：加入 3 类 K-means 工况 one-hot 特征后的增强数据集。
```

### 1.6 默认训练输出目录

当前推荐的 baseline 输出目录如下：

```text
outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_e30
outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_condition_k3_e30
outputs/condition_baseline_compare_k3
```

含义如下：

```text
baseline_mlp：使用 MLP baseline；
sim_window_w30_s1_h1_train_scaled：原始标准化窗口数据集；
condition_k3：加入 3 类工况 one-hot 特征；
e30：训练 30 个 epoch；
condition_baseline_compare_k3：原始 baseline 与工况增强 baseline 的对比分析报告目录。
```

---

## 2. scripts 目录脚本说明

`railphm-ai/scripts/` 目录用于存放离线数据处理、数据检查、数据划分、标准化、baseline 训练、结果分析、工况划分和对比分析脚本。脚本只负责命令行入口和流程编排，核心逻辑尽量放在 `app/` 目录下，避免脚本中重复实现业务逻辑。

---

## 2.1 build_window_dataset.py

### 功能说明

`build_window_dataset.py` 用于从原始 ATP 连续监测 CSV 片段中构建滑动窗口数据集。

它会读取 `segment_*.csv` 文件，检查时间连续性，提取可用于模型输入的字段，根据 `window_size`、`stride` 和 `horizon` 构造窗口样本，并基于目标行的报警字段生成 0/1 风险标签。

### 输入

```text
原始 segment_*.csv 文件目录
```

### 输出

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
```

其中：

```text
X.npy：窗口特征数组，shape = [num_samples, window_size, feature_dim]；
y.npy：窗口标签数组，shape = [num_samples]；
feature_columns.json：X 第三维对应的特征字段顺序；
window_manifest.csv：窗口样本追溯信息；
dataset_summary.json：数据集构建统计信息。
```

### 常用命令

```bash
python scripts/build_window_dataset.py \
  --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/仿真数据/atp_segments_v1" \
  --output-dir data/datasets/sim_window_w30_s1_h1_raw \
  --window-size 30 \
  --stride 1 \
  --horizon 1 \
  --overwrite \
  --verbose
```

---

## 2.2 inspect_dataset.py

### 功能说明

`inspect_dataset.py` 用于检查窗口数据集是否可以进入后续训练流程。

它会检查 `X.npy`、`y.npy`、`feature_columns.json`、`window_manifest.csv`、`dataset_summary.json` 是否存在，并检查数组维度、样本数量、标签取值、NaN、inf、特征数量和 manifest 行数是否一致。

### 输入

```text
一个标准窗口数据集目录
```

### 输出

```text
inspection_summary.json
```

### 常用命令

检查 raw 数据集：

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_raw
```

检查标准化数据集：

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled
```

检查工况增强数据集：

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3
```

### 注意事项

如果数据集使用 `standard` 标准化，`X_min` 小于 0 或 `X_max` 大于 1 是正常现象。此时重点关注：

```text
is_valid = True
has_nan = False
has_inf = False
```

---

## 2.3 split_dataset.py

### 功能说明

`split_dataset.py` 用于按照 `segment_id` 划分训练集、验证集和测试集。

由于滑动窗口样本之间存在重叠，如果随机按窗口划分，容易导致同一连续片段中的相似窗口同时出现在训练集和测试集中。因此当前脚本采用 segment 级划分，同一个 `segment_id` 下的所有窗口样本只能进入 train、val、test 中的一个集合。

### 输入

```text
已经构建好的 raw 窗口数据集目录
```

### 输出

```text
splits/train_indices.npy
splits/val_indices.npy
splits/test_indices.npy
splits/split_summary.json
```

### 常用命令

```bash
python scripts/split_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_raw \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --seed 42 \
  --overwrite
```

### 验收重点

输出中应确认：

```text
has_segment_leakage = False
train_val_overlap_count = 0
train_test_overlap_count = 0
val_test_overlap_count = 0
```

---

## 2.4 scale_window_dataset.py

### 功能说明

`scale_window_dataset.py` 用于对窗口数据集进行标准化。

该脚本只使用训练集样本拟合标准化参数，然后使用同一组训练集统计量对 train、val、test 全部样本进行 transform，从而避免验证集和测试集统计信息泄露到训练阶段。

### 输入

```text
已经完成 split 的 raw 窗口数据集目录
```

### 输出

```text
标准化后的窗口数据集目录
```

输出目录中保留：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
splits/
```

并额外生成：

```text
scaler_summary.json
```

### 常用命令

```bash
python scripts/scale_window_dataset.py \
  --input-dir data/datasets/sim_window_w30_s1_h1_raw \
  --output-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --method standard \
  --overwrite
```

---

## 2.5 cluster_conditions.py

### 功能说明

`cluster_conditions.py` 用于对标准化后的窗口数据集执行 K-means 工况划分。

它会读取 `X.npy` 和 `feature_columns.json`，调用 `ConditionFeatureExtractor` 提取窗口级工况统计特征，再调用 `ConditionKMeansClusterer` 完成 K-means 聚类。聚类过程中，StandardScaler 和 KMeans 都只基于 `train_indices` 对应样本拟合，val/test 只参与 transform 和 predict。

### 输入

```text
标准化后的窗口数据集目录
```

### 输出

```text
condition_labels.npy
condition_manifest.csv
condition_summary.json
condition_model.pkl
```

其中：

```text
condition_labels.npy：每个窗口样本的 condition_id；
condition_manifest.csv：样本级工况追溯信息；
condition_summary.json：工况划分统计信息；
condition_model.pkl：工况划分模型摘要和聚类中心信息。
```

### 常用命令

```bash
python scripts/cluster_conditions.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --n-clusters 3 \
  --seed 42 \
  --overwrite \
  --verbose
```

### 当前默认工况数量

```text
n_clusters = 3
```

对应论文中的三类运行工况：

```text
高速巡航
进站减速
出站加速
```

---

## 2.6 build_condition_augmented_dataset.py

### 功能说明

`build_condition_augmented_dataset.py` 用于在已有工况划分结果基础上构造加入工况 one-hot 特征的增强窗口数据集。

它会读取 `condition_labels.npy`，将每个样本的 `condition_id` 转换为 one-hot 向量，并在该样本窗口的每个时间步上重复拼接到原始特征后面。

### 输入

```text
已经完成 K-means 工况划分的标准化窗口数据集目录
```

### 输出

```text
新的工况增强数据集目录
```

输出目录中包含：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
condition_labels.npy
condition_summary.json
condition_manifest.csv
condition_augmented_summary.json
splits/
```

### 拼接规则

原始数据：

```text
X.shape = [num_samples, window_size, feature_dim]
```

工况标签：

```text
condition_labels.shape = [num_samples]
```

若 `n_clusters = 3`，则 one-hot 后：

```text
condition_onehot.shape = [num_samples, 3]
```

扩展到每个时间步：

```text
condition_onehot_seq.shape = [num_samples, window_size, 3]
```

最终拼接：

```text
X_aug.shape = [num_samples, window_size, feature_dim + 3]
```

新增特征列固定命名为：

```text
condition_0
condition_1
condition_2
```

### 常用命令

```bash
python scripts/build_condition_augmented_dataset.py \
  --input-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --output-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --overwrite \
  --verbose
```

---

## 2.7 train_baseline.py

### 功能说明

`train_baseline.py` 用于训练 MLP baseline 模型。

该脚本读取标准窗口数据集目录中的 `X.npy`、`y.npy` 和 `splits/*.npy`，将窗口特征展平后输入 MLP 模型进行二分类训练。

当前 MLP baseline 的作用不是作为最终模型，而是验证数据集、标签构造、特征处理、数据划分和训练流程是否具备基本可训练性。

### 输入

```text
标准窗口数据集目录
```

该目录可以是：

```text
原始标准化数据集
工况 one-hot 增强数据集
```

### 输出

```text
best_model.pt
metrics_history.csv
test_predictions.csv
training_config.json
baseline_report.json
```

### 原始 baseline 训练命令

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --output-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_e30 \
  --model mlp \
  --epochs 30 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --hidden-dims 128,64 \
  --dropout 0.2 \
  --best-metric val_auc \
  --overwrite
```

### 工况增强 baseline 训练命令

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --output-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_condition_k3_e30 \
  --model mlp \
  --epochs 30 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --hidden-dims 128,64 \
  --dropout 0.2 \
  --best-metric val_auc \
  --overwrite
```

### 当前默认训练配置

```text
epochs = 30
batch_size = 256
lr = 0.001
seed = 42
device = auto
hidden_dims = 128,64
dropout = 0.2
best_metric = val_auc
```

---

## 2.8 analyze_baseline.py

### 功能说明

`analyze_baseline.py` 用于分析 baseline 训练结果。

它会读取某次 baseline 训练输出目录中的 `baseline_report.json`、`metrics_history.csv`、`test_predictions.csv`，并结合数据集侧的 `dataset_summary.json`、`inspection_summary.json`、`split_summary.json` 等信息，生成可读的训练分析报告。

### 输入

```text
baseline 训练输出目录
对应数据集目录
```

### 输出

```text
baseline_analysis.json
baseline_analysis.md
```

### 原始 baseline 分析命令

```bash
python scripts/analyze_baseline.py \
  --run-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_e30 \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --overwrite
```

### 工况增强 baseline 分析命令

```bash
python scripts/analyze_baseline.py \
  --run-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_condition_k3_e30 \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --overwrite
```

---

## 2.9 compare_condition_baseline.py

### 功能说明

`compare_condition_baseline.py` 用于比较原始 baseline 与加入工况 one-hot 后的 baseline。

它会读取两组 baseline 的训练结果，比较总体指标、训练曲线、测试集预测分布，并基于 `condition_labels.npy` 和 `test_indices.npy` 做按工况的测试集表现分析，最终给出工况划分是否值得保留的判断。

### 输入

```text
原始 baseline 输出目录
工况增强 baseline 输出目录
原始数据集目录
工况增强数据集目录
```

### 输出

```text
condition_baseline_compare.json
condition_baseline_compare.md
```

### 常用命令

```bash
python scripts/compare_condition_baseline.py \
  --baseline-a outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_e30 \
  --baseline-b outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_condition_k3_e30 \
  --dataset-a data/datasets/sim_window_w30_s1_h1_train_scaled \
  --dataset-b data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --output-dir outputs/condition_baseline_compare_k3 \
  --overwrite \
  --verbose
```

### 当前对比结论口径

在 `w30_s1_h1` 参数下，加入工况 one-hot 后，测试集 AUC、F1、Precision、Recall 和 Brier Score 均有改善。该结果可以说明 K-means 工况 one-hot 对 MLP baseline 有一定辅助作用，尤其对正样本识别指标提升更明显，但整体 AUC 提升幅度仍有限，后续仍需在 LSTM、Bi-LSTM 和 Bi-LSTM + Attention 模型中继续验证。

---

## 2.10 make_shuffled_label_dataset.py

### 功能说明

`make_shuffled_label_dataset.py` 用于构造随机标签数据集，主要用于 sanity check。

它会复制一个已有数据集，然后随机打乱 `y.npy`，用于验证训练流程是否存在严重泄露或评估错误。

### 输入

```text
一个已有窗口数据集目录
```

### 输出

```text
随机标签数据集目录
```

### 常用命令

```bash
python scripts/make_shuffled_label_dataset.py \
  --input-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --output-dir data/datasets/sim_window_w30_s1_h1_train_scaled_y_shuffled \
  --seed 42 \
  --overwrite
```

### 判断标准

```text
如果随机标签数据集训练后 AUC 回到 0.5 附近，说明训练与评估流程基本正常。
如果随机标签数据集训练后 AUC 仍然很高，说明可能存在数据泄露或训练评估流程问题。
```

---

## 2.11 split_dataset_by_label_seq.py

### 功能说明

`split_dataset_by_label_seq.py` 是一个诊断性划分脚本，用于排查标签序列模板泄露问题。

它可以按照每个 segment 的标签序列模式进行划分，避免同类标签模式同时出现在训练集和测试集中。该脚本主要用于历史异常排查，不作为当前默认训练流程的必要步骤。

### 适用场景

当模型在普通 segment split 下取得异常高指标时，可以用该脚本检查是否存在标签模板重复导致的泄露。

### 使用说明

该脚本不属于当前默认完整流程，一般不需要执行。只有在排查异常高指标或怀疑标签模板泄露时再使用。

---

## 3. 当前默认完整流程

下面给出从原始 CSV 到最终工况增强 baseline 对比分析的一套完整命令。默认参数统一使用：

```text
window_size = 30
stride = 1
horizon = 1
n_clusters = 3
epochs = 30
```

### 3.1 进入项目并激活环境

```bash
cd /Users/hannn/Desktop/railphm/railphm-ai

source /Users/hannn/Desktop/railphm/railphm-server/.venv/bin/activate
```

### 3.2 构建 raw 窗口数据集

```bash
python scripts/build_window_dataset.py \
  --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/仿真数据/atp_segments_v1" \
  --output-dir data/datasets/sim_window_w30_s1_h1_raw \
  --window-size 30 \
  --stride 1 \
  --horizon 1 \
  --overwrite \
  --verbose
```

### 3.3 检查 raw 数据集

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_raw
```

### 3.4 按 segment_id 划分 train / val / test

```bash
python scripts/split_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_raw \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --seed 42 \
  --overwrite
```

### 3.5 基于训练集统计量标准化

```bash
python scripts/scale_window_dataset.py \
  --input-dir data/datasets/sim_window_w30_s1_h1_raw \
  --output-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --method standard \
  --overwrite
```

### 3.6 检查标准化数据集

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled
```

### 3.7 执行 K-means 工况划分

```bash
python scripts/cluster_conditions.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --n-clusters 3 \
  --seed 42 \
  --overwrite \
  --verbose
```

### 3.8 构造工况 one-hot 增强数据集

```bash
python scripts/build_condition_augmented_dataset.py \
  --input-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --output-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --overwrite \
  --verbose
```

### 3.9 检查工况增强数据集

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3
```

额外确认最后三个特征：

```bash
python - <<'PY'
import json
from pathlib import Path
import numpy as np

dataset_dir = Path("data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3")
X = np.load(dataset_dir / "X.npy")
feature_columns = json.loads((dataset_dir / "feature_columns.json").read_text(encoding="utf-8"))

print("X_shape:", X.shape)
print("feature_dim:", X.shape[2])
print("last_features:", feature_columns[-3:])
PY
```

预期输出：

```text
last_features: ['condition_0', 'condition_1', 'condition_2']
```

### 3.10 训练原始 baseline

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --output-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_e30 \
  --model mlp \
  --epochs 30 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --hidden-dims 128,64 \
  --dropout 0.2 \
  --best-metric val_auc \
  --overwrite
```

### 3.11 分析原始 baseline

```bash
python scripts/analyze_baseline.py \
  --run-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_e30 \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled \
  --overwrite
```

### 3.12 训练工况增强 baseline

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --output-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_condition_k3_e30 \
  --model mlp \
  --epochs 30 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --hidden-dims 128,64 \
  --dropout 0.2 \
  --best-metric val_auc \
  --overwrite
```

### 3.13 分析工况增强 baseline

```bash
python scripts/analyze_baseline.py \
  --run-dir outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_condition_k3_e30 \
  --dataset-dir data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --overwrite
```

### 3.14 对比原始 baseline 与工况增强 baseline

```bash
python scripts/compare_condition_baseline.py \
  --baseline-a outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_e30 \
  --baseline-b outputs/baseline_mlp_sim_window_w30_s1_h1_train_scaled_condition_k3_e30 \
  --dataset-a data/datasets/sim_window_w30_s1_h1_train_scaled \
  --dataset-b data/datasets/sim_window_w30_s1_h1_train_scaled_condition_k3 \
  --output-dir outputs/condition_baseline_compare_k3 \
  --overwrite \
  --verbose
```

### 3.15 运行测试

```bash
pytest tests/test_condition_features.py
pytest tests/test_kmeans_cluster.py
pytest tests/test_cluster_conditions_script.py
pytest tests/test_build_condition_augmented_dataset.py
pytest tests/test_compare_condition_baseline.py
pytest
```

---

## 4. 当前实验结论记录

在 `w30_s1_h1` 参数下，已完成原始 baseline 与工况增强 baseline 对比。关键结果如下：

| 指标 | 原始 baseline | 工况增强 baseline | 变化 |
|---|---:|---:|---:|
| val AUC | 0.5979 | 0.6007 | +0.0028 |
| val F1 | 0.1517 | 0.2067 | +0.0550 |
| test AUC | 0.6236 | 0.6307 | +0.0070 |
| test F1 | 0.1300 | 0.2153 | +0.0853 |
| test Precision | 0.4702 | 0.4938 | +0.0236 |
| test Recall | 0.0754 | 0.1377 | +0.0623 |
| test Brier Score | 0.2226 | 0.2220 | -0.0006 |

由此可以得到当前阶段的谨慎结论：

```text
加入 K-means 工况 one-hot 特征后，MLP baseline 在测试集 AUC、F1、Precision、Recall 和 Brier Score 上均有改善。其中 F1 和 Recall 提升更明显，说明工况 one-hot 对正样本识别具有一定辅助作用；但 AUC 提升幅度仍然有限，因此后续仍需要在 LSTM、Bi-LSTM 和 Bi-LSTM + Attention 等时序模型中继续验证。
```

---

## 5. 注意事项

1. `data/datasets/` 和 `outputs/` 均为本地实验产物目录，通常不会提交到远程仓库。
2. 默认实验参数后续统一采用 `window_size=30`、`stride=1`、`horizon=1`。
3. 标准化必须在 split 之后进行，并且只能使用训练集统计量拟合 scaler。
4. K-means 工况划分必须只使用训练集样本拟合 scaler 和 KMeans，验证集和测试集只能 transform 和 predict。
5. 工况 one-hot 增强数据集只改变 `X.npy` 和 `feature_columns.json`，`y.npy`、`window_manifest.csv` 和 `splits/` 应保持不变。
6. MLP baseline 只是可训练性和特征有效性验证，不是最终模型。
7. 工况 one-hot 当前已经证明有一定作用，但提升幅度有限，论文表述应保持克制，避免写成“显著提升”。
