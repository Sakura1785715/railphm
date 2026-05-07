# scripts

本目录用于存放 `railphm-ai` 子模块中的离线任务脚本。这里的脚本主要服务于 ATP segment 数据集构建、数据集质量检查、train / val / test 划分，以及 baseline 模型可训练性验证。

需要注意的是，`scripts/` 目录下的脚本都属于离线开发和实验工具，不会在 `python run.py` 启动 AI 服务时自动执行。`python run.py` 只负责启动 Flask AI 服务；数据集构建、数据集检查、数据划分和 baseline 训练都需要通过本目录下的脚本手动执行。

## 当前脚本列表

```text
scripts/
├── build_window_dataset.py
├── inspect_dataset.py
├── split_dataset.py
├── train_baseline.py
└── README.md
```

各脚本作用如下：

```text
build_window_dataset.py
从已经切分好的 ATP segment CSV 文件构造滑动窗口数据集，生成 X.npy、y.npy、feature_columns.json、window_manifest.csv 和 dataset_summary.json。

inspect_dataset.py
检查已经构建好的窗口数据集是否可用，重点检查 X/y/manifest/summary 的一致性、标签合法性、NaN/inf、特征维度和敏感字段等问题。

split_dataset.py
按 segment_id 划分 train / val / test，避免滑动窗口重叠造成数据泄露，输出 train_indices.npy、val_indices.npy、test_indices.npy 和 split_summary.json。

train_baseline.py
训练 MLP baseline 模型，用于验证当前窗口数据集是否具备基本可训练性，输出 baseline_report.json、metrics_history.csv、training_config.json、best_model.pt 和 test_predictions.csv。
```

## 运行前准备

进入 `railphm-ai` 目录：

```bash
cd /Users/hannn/Desktop/railphm/railphm-ai
```

确认虚拟环境已激活：

```bash
source .venv/bin/activate
```

确认依赖已安装：

```bash
pip install -r requirements.txt
```

如果执行脚本时报：

```text
ModuleNotFoundError: No module named 'app'
```

说明 Python 没有正确识别 `railphm-ai` 项目根目录。当前脚本应在顶部加入 `PROJECT_ROOT` 和 `sys.path` 处理，正常情况下只要在 `railphm-ai` 目录下执行脚本即可。

## build_window_dataset.py

### 作用

`build_window_dataset.py` 用于从已经切分好的 ATP segment CSV 文件构造滑动窗口数据集。

输入为：

```text
segment_*.csv
```

输出为：

```text
X.npy
y.npy
feature_columns.json
window_manifest.csv
dataset_summary.json
```

当前默认任务定义为：

```text
使用同一 segment 内连续 30 个采样点作为模型输入，预测下一时刻第一列“报警部位”是否非空。
```

默认参数为：

```text
window_size = 30
stride = 1
prediction_horizon = 1
```

### 常用命令

```bash
python scripts/build_window_dataset.py \
  --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/代码/atp_segments" \
  --output-dir data/datasets/window_w30_s1_h1 \
  --window-size 30 \
  --stride 1 \
  --horizon 1 \
  --overwrite \
  --verbose
```

### 参数说明

```text
--segments-dir
已切分的 ATP segment CSV 文件目录。该目录下应包含 segment_*.csv 文件。

--output-dir
窗口数据集输出目录。

--window-size
历史窗口长度。默认 30，表示使用连续 30 个采样点作为模型输入。

--stride
滑动窗口步长。默认 1。步长越大，生成样本越少，窗口重叠越少。

--horizon / --prediction-horizon
预测步长。默认 1，表示预测下一时刻。

--overwrite
如果输出目录已存在，则删除旧目录后重新生成。

--skip-invalid-segments
默认开启。遇到无法读取、时间不连续或无法生成窗口的 segment 时跳过并记录。

--no-skip-invalid-segments
遇到异常 segment 时直接终止构建。

--verbose
输出更详细的构建信息，包括跳过文件、缺失字段和全空字段等。
```

### 输出目录命名建议

建议输出目录名称体现窗口参数，例如：

```text
window_w30_s1_h1
window_w30_s3_h1
window_w60_s1_h1
```

含义如下：

```text
w30 表示 window_size = 30
s1  表示 stride = 1
h1  表示 prediction_horizon = 1
```

## inspect_dataset.py

### 作用

`inspect_dataset.py` 用于检查已经构建好的窗口数据集是否可用。

它不会重新生成窗口，也不会修改 `X.npy`、`y.npy` 或 `window_manifest.csv`。它只读取已有数据集并做一致性检查，最后生成：

```text
inspection_summary.json
```

### 检查内容

主要检查：

```text
1. X.npy、y.npy、feature_columns.json、window_manifest.csv、dataset_summary.json 是否存在。
2. X 是否为三维数组。
3. y 是否为一维数组。
4. X/y/manifest 行数是否一致。
5. y 是否只包含 0 和 1。
6. X 是否存在 NaN。
7. X 是否存在 inf。
8. X 数值范围是否在 0 到 1。
9. X 特征维度是否等于 feature_columns 数量。
10. manifest 是否包含 sample_id、segment_id、target_time、label 等必要字段。
11. manifest 是否误写入司机手机号等敏感字段。
```

### 常用命令

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/window_w30_s1_h1
```

默认输出文件为：

```text
data/datasets/window_w30_s1_h1/inspection_summary.json
```

如需指定输出路径：

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/window_w30_s1_h1 \
  --output-file data/datasets/window_w30_s1_h1/inspection_summary.json
```

### 参数说明

```text
--dataset-dir
待检查的数据集目录。该目录下应包含 X.npy、y.npy、feature_columns.json、window_manifest.csv 和 dataset_summary.json。

--output-file
检查结果输出文件。默认写入 dataset_dir/inspection_summary.json。

--fail-on-warning
如果存在 warnings，也以非 0 状态码退出。默认不开启。
```

## split_dataset.py

### 作用

`split_dataset.py` 用于按 `segment_id` 划分 train / val / test。

它不会复制 `X.npy` 和 `y.npy`，而是输出索引文件：

```text
train_indices.npy
val_indices.npy
test_indices.npy
split_summary.json
```

这样做可以避免复制大数组文件，节省磁盘空间。

### 为什么必须按 segment_id 划分

滑动窗口之间高度重叠。如果随机按窗口样本划分，可能出现：

```text
训练集样本：第 1～30 行预测第 31 行
测试集样本：第 2～31 行预测第 32 行
```

这两个样本几乎完全重叠，会造成数据泄露。

因此，本项目采用按 `segment_id` 划分：

```text
同一个 segment_id 下的所有窗口样本，只能整体进入 train、val 或 test 中的一个集合。
```

### 常用命令

```bash
python scripts/split_dataset.py \
  --dataset-dir data/datasets/window_w30_s1_h1 \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --seed 42 \
  --overwrite
```

默认输出目录为：

```text
data/datasets/window_w30_s1_h1/splits/
```

输出文件为：

```text
train_indices.npy
val_indices.npy
test_indices.npy
split_summary.json
```

### 参数说明

```text
--dataset-dir
待划分的数据集目录。该目录下应包含 y.npy 和 window_manifest.csv。

--output-dir
划分结果输出目录。默认写入 dataset_dir/splits。

--train-ratio
训练集 segment 比例，默认 0.7。

--val-ratio
验证集 segment 比例，默认 0.15。

--test-ratio
测试集 segment 比例，默认 0.15。

--seed
随机种子，默认 42。seed 相同，划分结果可复现；seed 不同，会得到不同随机划分。

--overwrite
如果输出目录已存在，则覆盖旧划分文件。
```

## train_baseline.py

### 作用

`train_baseline.py` 用于训练 MLP baseline 模型，验证当前窗口数据集是否具备基本可训练性。

它会串联前面已经完成的训练相关模块：

```text
app/training/dataset_loader.py
读取 X.npy、y.npy 和 train/val/test indices，生成 PyTorch DataLoader。

app/models/baseline_mlp.py
定义 MLP baseline 模型，输入展平后的窗口特征，输出二分类 logits。

app/training/metrics.py
计算 accuracy、precision、recall、f1、auc、brier_score 和 confusion_matrix 等二分类指标。

app/training/train_baseline.py
实现训练主流程，包括训练、验证、测试、保存最优模型和生成报告。
```

本脚本当前只支持：

```text
model = mlp
```

它不会实现 LSTM、Bi-LSTM、Attention、工况划分、概率校准、MC-Dropout，也不会接入 `/infer` 真实推理。

### 输入数据要求

训练脚本要求数据集目录结构如下：

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
X.npy
形状为 [num_samples, window_size, feature_dim]。

y.npy
形状为 [num_samples]，标签只能为 0 或 1。

train_indices.npy / val_indices.npy / test_indices.npy
分别表示训练集、验证集和测试集使用的样本索引。
```

当前真实数据集大致为：

```text
X.shape = [325800, 30, 25]
y.shape = [325800]
positive_ratio ≈ 0.4127
```

因此 MLP baseline 的输入维度为：

```text
input_dim = window_size * feature_dim = 30 * 25 = 750
```

该 input_dim 会在训练主流程中根据 X.shape 自动推断，不需要手动传入。

### 常用命令

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/window_w30_s1_h1 \
  --output-dir outputs/baseline_mlp_w30_s1_h1 \
  --model mlp \
  --epochs 10 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --hidden-dims 128,64 \
  --dropout 0.2 \
  --best-metric val_f1 \
  --overwrite
```

### 参数说明

```text
--dataset-dir
窗口数据集目录。该目录下必须包含 X.npy、y.npy 和 splits/*.npy。

--output-dir
训练结果输出目录。建议不同模型、不同实验使用不同目录，避免覆盖旧结果。

--model
模型类型。当前只支持 mlp。

--epochs
训练轮数，默认 10。

--batch-size
batch 大小，默认 256。

--lr
学习率，默认 0.001。

--seed
随机种子，默认 42。用于保证模型初始化、数据打乱等过程尽量可复现。

--device
训练设备，默认 auto。可选值为 auto、cpu、cuda、mps。
auto 表示优先使用 cuda，其次 mps，最后 cpu。

--threshold
二分类阈值，默认 0.5。y_prob >= threshold 判为风险样本。

--hidden-dims
MLP 隐藏层维度，默认 128,64。可以改为 256,128,64 等形式。

--dropout
MLP dropout，默认 0.2。

--num-workers
DataLoader num_workers，默认 0。本地测试建议保持 0，稳定性更好。

--best-metric
最优模型选择指标，默认 val_f1。可选 val_f1、val_auc、val_loss。

--overwrite
如果输出目录已存在，则删除旧目录后重新训练。
```

### 输出文件

训练完成后，`--output-dir` 下会生成：

```text
baseline_report.json
metrics_history.csv
training_config.json
best_model.pt
test_predictions.csv
```

各文件含义如下：

```text
baseline_report.json
整体训练报告，包含模型配置、数据集信息、训练配置、train/val/test 指标和产物路径。

metrics_history.csv
每个 epoch 的训练记录，至少包含 epoch、train_loss、val_loss、val_accuracy、val_precision、val_recall、val_f1、val_auc、val_brier_score。

training_config.json
本次训练配置，便于复现实验。

best_model.pt
验证集表现最优的模型权重和模型配置。

test_predictions.csv
测试集预测结果，包含 sample_order、y_true、y_prob、y_pred。
```

### 输出目录是否会覆盖

如果 `output_dir` 已经存在，并且命令中使用：

```bash
--overwrite
```

训练脚本会删除旧目录后重新生成结果。

例如下面命令会覆盖旧的 baseline 结果：

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/window_w30_s1_h1 \
  --output-dir outputs/baseline_mlp_w30_s1_h1 \
  --model mlp \
  --epochs 10 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --overwrite
```

如果 `output_dir` 已存在，但不加 `--overwrite`，程序会直接报错，不会覆盖旧结果。

建议不同模型或不同实验使用不同输出目录，例如：

```text
outputs/baseline_mlp_w30_s1_h1
outputs/lstm_baseline_w30_s1_h1
outputs/bilstm_attention_w30_s1_h1
outputs/bilstm_attention_calibrated_w30_s1_h1
```

如果只是多次实验，也可以加 run 编号：

```text
outputs/baseline_mlp_w30_s1_h1_run01
outputs/baseline_mlp_w30_s1_h1_run02
outputs/bilstm_attention_w30_s1_h1_run01
```

### 结果如何判断

本任务不要求 MLP baseline 达到很高指标，它只是用于验证数据集是否具备基本可训练性。

真实数据集训练完成后，建议关注：

```text
1. train_loss 是否能下降。
2. val_loss 是否基本下降或稳定。
3. val_auc 是否明显高于 0.5。
4. val_f1 是否不是接近 0。
5. recall 是否能识别一部分正样本。
6. brier_score 是否处于合理范围。
7. train 指标和 val/test 指标差距是否过大。
```

如果 AUC 明显高于 0.5，F1 有有效值，loss 能正常下降，说明当前 X/y 数据集具备基本可训练性，可以继续进入后续任务，例如简单 LSTM baseline、工况划分、Bi-LSTM + Attention、概率校准和 MC-Dropout。

## 当前推荐执行顺序

完整流程建议按下面顺序执行：

### 1. 构建窗口数据集

```bash
python scripts/build_window_dataset.py \
  --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/代码/atp_segments" \
  --output-dir data/datasets/window_w30_s1_h1 \
  --window-size 30 \
  --stride 1 \
  --horizon 1 \
  --overwrite \
  --verbose
```

### 2. 检查窗口数据集

```bash
python scripts/inspect_dataset.py \
  --dataset-dir data/datasets/window_w30_s1_h1
```

### 3. 划分 train / val / test

```bash
python scripts/split_dataset.py \
  --dataset-dir data/datasets/window_w30_s1_h1 \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15 \
  --seed 42 \
  --overwrite
```

### 4. 训练 MLP baseline

```bash
python scripts/train_baseline.py \
  --dataset-dir data/datasets/window_w30_s1_h1 \
  --output-dir outputs/baseline_mlp_w30_s1_h1 \
  --model mlp \
  --epochs 10 \
  --batch-size 256 \
  --lr 0.001 \
  --seed 42 \
  --device auto \
  --hidden-dims 128,64 \
  --dropout 0.2 \
  --best-metric val_f1 \
  --overwrite
```

## 当前数据集目录结构

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

## 当前 baseline 输出目录结构

```text
outputs/baseline_mlp_w30_s1_h1/
├── baseline_report.json
├── metrics_history.csv
├── training_config.json
├── best_model.pt
└── test_predictions.csv
```

## Git 提交注意事项

真实数据文件和训练产物不应提交到 GitHub。

建议在 `.gitignore` 中忽略：

```gitignore
# Generated datasets and training outputs
railphm-ai/outputs/
railphm-ai/data/datasets/
```

如果 `.gitignore` 位于 `railphm-ai/` 目录下，则写成：

```gitignore
# Generated datasets and training outputs
outputs/
data/datasets/
```

原因如下：

```text
outputs/
保存训练报告、模型权重、预测结果等实验产物，文件可能较大，而且每次训练都会变化。

data/datasets/
保存 X.npy、y.npy、split indices 等真实数据集产物，文件较大，不适合提交到 GitHub。
```

代码本身、脚本、README、测试文件可以提交；真实数据和训练结果不提交。

## 注意事项

1. `build_window_dataset.py` 会生成窗口数据集，可能耗时并占用较多磁盘空间。
2. `inspect_dataset.py` 不会重新生成窗口，只负责检查已有数据集。
3. `split_dataset.py` 不会复制 X/y，只生成索引文件。
4. `train_baseline.py` 会训练 MLP baseline，并在输出目录生成训练报告和模型权重。
5. 不同参数的数据集建议使用不同输出目录，例如 `window_w30_s1_h1`、`window_w30_s3_h1`。
6. 不同模型或不同实验建议使用不同输出目录，例如 `baseline_mlp_w30_s1_h1`、`lstm_baseline_w30_s1_h1`。
7. 如果输出目录相同且使用 `--overwrite`，新结果会覆盖旧结果。
8. `.npy` 是 NumPy 数组文件格式，`X.npy` 保存滑动窗口输入，`y.npy` 保存标签，`*_indices.npy` 保存样本索引。
9. `best_model.pt` 是 PyTorch 模型权重文件，属于训练产物，不应提交到 GitHub。
10. 当前 MLP baseline 只用于验证数据集可训练性，不是论文最终模型。
11. 后续如果继续实现 LSTM、Bi-LSTM + Attention、概率校准和 MC-Dropout，应继续使用独立输出目录保存实验结果。
