# RailPHM AI Scripts 使用说明

本目录用于存放 `railphm-ai` 子模块中的数据集构建、数据检查、数据划分、数据标准化、模型训练和训练结果分析脚本。脚本主要服务于 RailPHM 故障风险预测模块的离线开发流程，用于将连续 ATP 监测片段 CSV 转换为模型可训练的窗口数据集，并完成 baseline 模型训练与结果输出。

当前项目中的原始仿真 ATP 片段数据统一存放在项目外部目录：

```bash
/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/仿真数据/atp_segments_v1
```

项目内部只保留由脚本生成的数据集和训练结果：

```text
railphm-ai/
├── data/
│   └── datasets/
│       ├── sim_window_w30_s5_h1_raw/
│       └── sim_window_w30_s5_h1_train_scaled/
├── outputs/
│   └── baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30/
└── scripts/
```

> 说明：`data/datasets/` 保存窗口数据集、划分结果和标准化后的训练数据；`outputs/` 保存模型训练产物和评估结果。外部仿真 CSV 不直接放入项目目录，以降低项目结构复杂度。

---

## 1. 运行环境准备

进入 `railphm-ai` 目录：

```bash
cd /Users/hannn/Desktop/railphm/railphm-ai
```

激活虚拟环境：

```bash
source /Users/hannn/Desktop/railphm/railphm-server/.venv/bin/activate
```

确认 Python 环境可用：

```bash
python --version
```

安装依赖：

```bash
pip install -r requirements.txt
```

---

## 2. 脚本功能说明

### 2.1 `build_window_dataset.py`

功能：  
从连续 ATP segment CSV 文件中构建滑动窗口数据集。

输入：

```text
segment_*.csv
```

输出：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
```

主要处理内容包括：

- 遍历 `segment_*.csv` 文件；
- 读取 ATP 连续监测片段；
- 检查时间连续性；
- 提取模型输入特征；
- 根据 `window_size`、`stride`、`horizon` 构造滑动窗口；
- 根据目标行报警字段生成 0/1 标签；
- 保存窗口样本矩阵 `X.npy` 和标签 `y.npy`；
- 保存窗口追溯信息 `window_manifest.csv`。

常用命令：

```bash
python scripts/build_window_dataset.py \
  --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/仿真数据/atp_segments_v1" \
  --output-dir data/datasets/sim_window_w30_s5_h1_raw \
  --window-size 30 \
  --stride 5 \
  --horizon 1 \
  --overwrite \
  --verbose
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--segments-dir` | 原始连续 ATP CSV 片段目录 |
| `--output-dir` | 窗口数据集输出目录 |
| `--window-size` | 每个窗口包含的时间步数量 |
| `--stride` | 滑动窗口步长 |
| `--horizon` | 预测目标距离窗口结束位置的时间步 |
| `--overwrite` | 如果输出目录已存在则覆盖 |
| `--verbose` | 输出详细构建信息 |

当前推荐配置：

```text
window_size = 30
stride = 5
horizon = 1
```

该配置含义为：使用过去 30 秒的 ATP 监测窗口，每 5 秒滑动一次，预测窗口结束后 1 秒的风险标签。

---

### 2.2 `inspect_dataset.py`

功能：  
检查已经构建好的窗口数据集是否可用于训练。

检查内容包括：

- `X.npy`、`y.npy` 是否存在；
- `X` 和 `y` 样本数是否一致；
- 是否存在 NaN 或 inf；
- 标签是否只包含 0/1；
- `feature_columns.json` 与 `X` 的特征维度是否一致；
- `window_manifest.csv` 行数是否与样本数一致；
- 正负样本比例；
- 每个 segment 的窗口数量分布。

常用命令：

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_raw
```

标准化后也建议再次检查：

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled
```

输出文件：

```text
inspection_summary.json
```

说明：  
如果使用 `standard` 标准化，`X_min` 和 `X_max` 不在 `[0, 1]` 范围内是正常现象。此时重点关注：

```text
is_valid = True
has_nan = False
has_inf = False
```

---

### 2.3 `split_dataset.py`

功能：  
按照 `segment_id` 对窗口数据集进行训练集、验证集和测试集划分。

该脚本不是随机按窗口样本划分，而是按 `segment_id` 划分，避免同一个连续片段中的窗口同时进入训练集和测试集。

输出：

```text
splits/
├── train_indices.npy
├── val_indices.npy
├── test_indices.npy
└── split_summary.json
```

常用命令：

```bash
python scripts/split_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_raw \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --seed 42 \
  --overwrite
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--dataset-dir` | 窗口数据集目录 |
| `--train-ratio` | 训练集比例 |
| `--val-ratio` | 验证集比例 |
| `--test-ratio` | 测试集比例 |
| `--seed` | 随机种子 |
| `--overwrite` | 覆盖已有 `splits/` 目录 |

推荐比例：

```text
train : val : test = 0.7 : 0.15 : 0.15
```

---

### 2.4 `scale_window_dataset.py`

功能：  
对窗口数据集进行标准化处理。

该脚本只使用训练集样本拟合 scaler，然后对 train、val、test 全量样本统一 transform，避免验证集和测试集统计信息泄露到训练阶段。

输入：

```text
raw dataset
```

输出：

```text
train_scaled dataset
```

常用命令：

```bash
python scripts/scale_window_dataset.py \
  --input-dir data/datasets/sim_window_w30_s5_h1_raw \
  --output-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --method standard \
  --overwrite
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--input-dir` | 原始窗口数据集目录 |
| `--output-dir` | 标准化后数据集输出目录 |
| `--method` | 标准化方式，当前推荐 `standard` |
| `--overwrite` | 覆盖已有输出目录 |

输出目录中会保留：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
inspection_summary.json
splits/
```

说明：  
当前推荐使用 `standard`，即基于训练集统计量进行标准化。标准化后数据可能包含负数，这是正常现象。

---

### 2.5 `train_baseline.py`

功能：  
训练 MLP baseline 模型，用于验证当前窗口数据集是否具有基本可训练性。

模型结构：

```text
Linear(input_dim, 128)
ReLU
Dropout(0.2)
Linear(128, 64)
ReLU
Dropout(0.2)
Linear(64, 1)
```

模型输出 logits，训练时使用 `BCEWithLogitsLoss`。

输入：

```text
X.npy
y.npy
splits/train_indices.npy
splits/val_indices.npy
splits/test_indices.npy
```

输出：

```text
best_model.pt
metrics_history.csv
test_predictions.csv
training_config.json
baseline_report.json
```

常用命令：

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --output-dir outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30 \
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

参数说明：

| 参数 | 说明 |
|---|---|
| `--dataset-dir` | 标准化后的训练数据集目录 |
| `--output-dir` | 训练结果输出目录 |
| `--model` | 当前支持 `mlp` |
| `--epochs` | 训练轮数 |
| `--batch-size` | 批大小 |
| `--lr` | 学习率 |
| `--seed` | 随机种子 |
| `--device` | 训练设备，支持 `auto`、`cpu`、`cuda`、`mps` |
| `--hidden-dims` | MLP 隐藏层维度 |
| `--dropout` | Dropout 比例 |
| `--best-metric` | 最优模型选择指标，推荐 `val_auc` |
| `--overwrite` | 覆盖已有输出目录 |

说明：  
当前数据集上，F1 对阈值较敏感，建议优先使用 `val_auc` 作为 best model 选择依据。

---

### 2.6 `analyze_baseline.py`

功能：  
分析 baseline 训练结果，汇总数据集信息、训练过程、最终指标和预测分布，并生成分析报告。

输入：

```text
baseline_report.json
metrics_history.csv
test_predictions.csv
dataset_summary.json
inspection_summary.json
split_summary.json
```

输出：

```text
baseline_analysis.json
baseline_analysis.md
```

常用命令：

```bash
python scripts/analyze_baseline.py \
  --run-dir outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30 \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --overwrite
```

说明：  
该脚本用于训练完成后的结果整理，便于记录开发过程和撰写实验分析。

---

### 2.7 `make_shuffled_label_dataset.py`

功能：  
构造随机标签数据集，用于 sanity check。

该脚本会复制一个已有数据集，然后随机打乱 `y.npy`，用于验证训练流程和评估流程是否存在严重 bug。

判断标准：

```text
如果随机打乱标签后 AUC 回到 0.5 左右：
说明训练流程基本正常。

如果随机打乱标签后 AUC 仍然很高：
说明训练或评估流程可能存在问题。
```

常用命令：

```bash
python scripts/make_shuffled_label_dataset.py \
  --input-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --output-dir data/datasets/sim_window_w30_s5_h1_train_scaled_y_shuffled \
  --seed 42 \
  --overwrite
```

然后训练随机标签数据集：

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled_y_shuffled \
  --output-dir outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_y_shuffled \
  --model mlp \
  --epochs 10 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --hidden-dims 128,64 \
  --dropout 0.2 \
  --best-metric val_auc \
  --overwrite
```

---

### 2.8 `split_dataset_by_label_seq.py`

功能：  
按照每个 segment 的标签序列模式进行诊断性划分，用于排查标签模板泄露。

该脚本主要用于历史异常排查，不作为正式训练流程的必要步骤。

适用场景：

```text
当模型在随机 segment split 下取得异常高指标时，
可用该脚本验证是否存在 label_seq 模板在 train/val/test 中重复出现的问题。
```

示例命令：

```bash
python scripts/split_dataset_by_label_seq.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_raw \
  --train-label-seqs 000000,1111111,010101 \
  --val-label-seqs 0000000,1001100 \
  --test-label-seqs 111110 \
  --overwrite
```

说明：  
该脚本主要用于数据诊断。对于当前已经去模板化后的仿真数据集，通常不需要作为常规训练流程执行。

---

## 3. 推荐完整流程

下面给出当前推荐的一套完整运行流程，从外部仿真 CSV 到最终 baseline 训练结果。

### 3.1 构建窗口数据集

```bash
python scripts/build_window_dataset.py \
  --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/仿真数据/atp_segments_v1" \
  --output-dir data/datasets/sim_window_w30_s5_h1_raw \
  --window-size 30 \
  --stride 5 \
  --horizon 1 \
  --overwrite \
  --verbose
```

预期输出：

```text
data/datasets/sim_window_w30_s5_h1_raw/
├── X.npy
├── y.npy
├── feature_columns.json
├── window_manifest.csv
└── dataset_summary.json
```

---

### 3.2 检查窗口数据集

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_raw
```

重点确认：

```text
is_valid = True
has_nan = False
has_inf = False
unique_y = [0, 1]
```

---

### 3.3 划分训练集、验证集和测试集

```bash
python scripts/split_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_raw \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --seed 42 \
  --overwrite
```

预期输出：

```text
data/datasets/sim_window_w30_s5_h1_raw/splits/
├── train_indices.npy
├── val_indices.npy
├── test_indices.npy
└── split_summary.json
```

---

### 3.4 基于训练集统计量标准化

```bash
python scripts/scale_window_dataset.py \
  --input-dir data/datasets/sim_window_w30_s5_h1_raw \
  --output-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --method standard \
  --overwrite
```

预期输出：

```text
data/datasets/sim_window_w30_s5_h1_train_scaled/
├── X.npy
├── y.npy
├── feature_columns.json
├── window_manifest.csv
├── dataset_summary.json
└── splits/
```

---

### 3.5 检查标准化后的数据集

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled
```

重点确认：

```text
is_valid = True
has_nan = False
has_inf = False
```

说明：  
`standard` 标准化后 `X_min` 可能小于 0，`X_max` 可能大于 1，属于正常现象。

---

### 3.6 训练 MLP baseline

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --output-dir outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30 \
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

训练过程中会输出每个 epoch 的指标，例如：

```text
Epoch 1/30 | train_loss=... | val_loss=... | val_f1=... | val_auc=...
```

训练结束后输出：

```text
outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30/
├── best_model.pt
├── metrics_history.csv
├── test_predictions.csv
├── training_config.json
└── baseline_report.json
```

---

### 3.7 分析 baseline 结果

```bash
python scripts/analyze_baseline.py \
  --run-dir outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30 \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --overwrite
```

预期输出：

```text
outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30/
├── baseline_analysis.json
└── baseline_analysis.md
```

---

## 4. 阈值诊断

MLP 输出的是概率分数，默认分类阈值为 `0.5`。如果模型 AUC 有一定提升，但 F1 较低，可能是阈值设置不合适。

可以使用下面命令检查不同阈值下的 precision、recall 和 F1：

```bash
python - <<'PY'
import pandas as pd

path = "outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30/test_predictions.csv"
df = pd.read_csv(path)

print("y_true ratio:", df["y_true"].mean())
print("y_prob describe:")
print(df["y_prob"].describe())
print()

for t in [0.1, 0.2, 0.3, 0.4, 0.5]:
    pred = (df["y_prob"] >= t).astype(int)
    tp = ((pred == 1) & (df["y_true"] == 1)).sum()
    fp = ((pred == 1) & (df["y_true"] == 0)).sum()
    fn = ((pred == 0) & (df["y_true"] == 1)).sum()

    precision = tp / (tp + fp) if tp + fp > 0 else 0
    recall = tp / (tp + fn) if tp + fn > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0

    print(
        f"threshold={t:.1f} "
        f"precision={precision:.4f} "
        f"recall={recall:.4f} "
        f"f1={f1:.4f} "
        f"predicted_positive={pred.mean():.4f}"
    )
PY
```

说明：  
AUC 反映模型排序能力，F1 受阈值影响较大。当前 baseline 阶段建议优先观察 AUC，同时结合阈值诊断分析 F1。

---

## 5. 当前推荐数据集命名规范

为避免目录混乱，建议按如下规则命名：

```text
sim_window_w{窗口长度}_s{步长}_h{预测距离}_raw
sim_window_w{窗口长度}_s{步长}_h{预测距离}_train_scaled
```

示例：

```text
sim_window_w30_s5_h1_raw
sim_window_w30_s5_h1_train_scaled
```

含义：

```text
w30：窗口长度为 30
s5：滑动步长为 5
h1：预测距离为 1
raw：未标准化窗口数据集
train_scaled：使用训练集统计量标准化后的数据集
```

---

## 6. 当前推荐输出目录命名规范

训练输出建议命名为：

```text
outputs/baseline_mlp_{dataset_name}_e{epochs}
```

示例：

```text
outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30
```

这样可以直接从目录名看出：

```text
模型：baseline_mlp
数据集：sim_window_w30_s5_h1_train_scaled
训练轮数：30
```

---

## 7. 常见问题

### 7.1 为什么检查数据集时提示 X 不在 [0, 1] 范围内？

如果数据集是 raw 数据，说明尚未标准化，需要执行 `scale_window_dataset.py`。

如果数据集已经使用 `standard` 标准化，则出现负数是正常现象，因为 standard scaler 会将特征转换为近似均值 0、标准差 1 的分布。此时重点检查：

```text
has_nan = False
has_inf = False
is_valid = True
```

---

### 7.2 为什么要先 split 再 scale？

因为标准化必须只使用训练集统计量。如果先对全量数据标准化，再划分 train/val/test，会把验证集和测试集的统计信息泄露到训练阶段。

正确顺序是：

```text
raw dataset
→ split_dataset.py
→ scale_window_dataset.py
→ train_baseline.py
```

---

### 7.3 为什么 baseline 结果不追求 1.0？

在故障风险预测任务中，过高的指标反而需要警惕。如果简单 MLP baseline 在验证集和测试集上轻松接近 1.0，通常需要排查：

```text
数据泄露
标签模板化
同源片段泄露
代理特征
训练评估流程错误
```

当前 baseline 的主要作用是验证数据集和训练流程是否具备基本可训练性，而不是作为最终模型效果结论。

---

### 7.4 什么时候可以进入 LSTM / Bi-LSTM / Attention？

当满足以下条件时，可以继续进入后续时序模型开发：

```text
数据集检查通过；
标签不再严重模板化；
随机标签 sanity check 正常；
MLP baseline 不再异常满分；
MLP baseline 存在一定可学习信号；
训练、验证、测试集划分无明显泄露。
```

后续建议顺序为：

```text
MLP baseline
→ LSTM baseline
→ Bi-LSTM
→ Bi-LSTM + Attention
→ MC-Dropout 不确定性估计
```

---

## 8. 一键顺序执行参考

下面是一组从数据集构建到模型训练和分析的完整命令，可按顺序执行。

```bash
cd /Users/hannn/Desktop/railphm/railphm-ai

source /Users/hannn/Desktop/railphm/railphm-server/.venv/bin/activate

python scripts/build_window_dataset.py \
  --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/仿真数据/atp_segments_v1" \
  --output-dir data/datasets/sim_window_w30_s5_h1_raw \
  --window-size 30 \
  --stride 5 \
  --horizon 1 \
  --overwrite \
  --verbose

python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_raw

python scripts/split_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_raw \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --seed 42 \
  --overwrite

python scripts/scale_window_dataset.py \
  --input-dir data/datasets/sim_window_w30_s5_h1_raw \
  --output-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --method standard \
  --overwrite

python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled

python scripts/train_baseline.py \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --output-dir outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30 \
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

python scripts/analyze_baseline.py \
  --run-dir outputs/baseline_mlp_sim_window_w30_s5_h1_train_scaled_e30 \
  --dataset-dir data/datasets/sim_window_w30_s5_h1_train_scaled \
  --overwrite
```

---

## 9. 当前阶段说明

当前脚本流程主要服务于 RailPHM 预测模块的数据集构建和 baseline 可训练性验证。MLP baseline 不是最终模型，而是用于确认数据处理流程、窗口构造逻辑、数据划分、标准化处理和训练评估流程能够正常运行。

后续在 baseline 流程稳定后，将继续推进：

```text
K-means 工况划分
LSTM baseline
Bi-LSTM
Bi-LSTM + Attention
MC-Dropout 不确定性估计
风险分数输出与健康度映射
```
