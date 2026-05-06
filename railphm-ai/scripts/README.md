# scripts

本目录用于存放 `railphm-ai` 的离线任务脚本。当前脚本主要围绕 ATP segment 数据集构建、数据集质量检查和 train / val / test 划分展开。

注意：`scripts/` 目录下的脚本属于离线开发和实验工具，不会在 `python run.py` 启动 AI 服务时自动执行。`python run.py` 只负责启动 Flask AI 服务；数据集构建、检查和划分需要通过本目录脚本手动执行。

## 当前脚本列表

```text
scripts/
├── build_window_dataset.py
├── inspect_dataset.py
├── split_dataset.py
└── README.md
```

脚本作用概览：

```text
build_window_dataset.py
从已切分的 ATP segment CSV 文件构造滑动窗口数据集。

inspect_dataset.py
检查已经构建好的窗口数据集是否可用。

split_dataset.py
按 segment_id 划分 train / val / test，避免滑动窗口数据泄露。
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

如果直接执行脚本时报 `ModuleNotFoundError: No module named 'app'`，说明脚本没有正确识别项目根目录。当前脚本已在顶部加入 `PROJECT_ROOT` 路径处理，正常情况下在 `railphm-ai` 目录下执行即可。

## build_window_dataset.py

### 作用

`build_window_dataset.py` 用于从已经切分好的 ATP segment CSV 文件构造滑动窗口数据集。

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

当前默认任务定义：

```text
使用同一 segment 内连续 30 个采样点，预测下一时刻第一列“报警部位”是否非空。
```

默认参数：

```text
window_size = 30
stride = 1
prediction_horizon = 1
```

### 默认启动命令

```bash
python scripts/build_window_dataset.py   --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/代码/atp_segments"   --output-dir data/datasets/window_w30_s1_h1   --window-size 30   --stride 1   --horizon 1   --overwrite   --verbose
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

### 修改窗口参数示例

如果将步长改为 3：

```bash
python scripts/build_window_dataset.py   --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/代码/atp_segments"   --output-dir data/datasets/window_w30_s3_h1   --window-size 30   --stride 3   --horizon 1   --overwrite   --verbose
```

建议输出目录名称体现参数：

```text
window_w30_s1_h1
window_w30_s3_h1
window_w60_s1_h1
```

含义：

```text
w30 表示 window_size = 30
s1  表示 stride = 1
h1  表示 prediction_horizon = 1
```

### 当前真实构建结果

当前已基于 1980 个真实 segment 文件完成构建：

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

### 启动命令

```bash
python scripts/inspect_dataset.py   --dataset-dir data/datasets/window_w30_s1_h1
```

默认输出文件为：

```text
data/datasets/window_w30_s1_h1/inspection_summary.json
```

如需指定输出路径：

```bash
python scripts/inspect_dataset.py   --dataset-dir data/datasets/window_w30_s1_h1   --output-file data/datasets/window_w30_s1_h1/inspection_summary.json
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

### 当前真实检查结果

当前真实数据集检查结果：

```text
is_valid             : True
errors               : []
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
```

当前存在一个 warning：

```text
不同 segment 的窗口样本数差异较大: min_samples_per_segment=7, max_samples_per_segment=252
```

该 warning 来源于不同 segment 原始长度不同，属于正常现象，不影响继续使用。

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

### 默认启动命令

```bash
python scripts/split_dataset.py   --dataset-dir data/datasets/window_w30_s1_h1   --train-ratio 0.7   --val-ratio 0.15   --test-ratio 0.15   --seed 42   --overwrite
```

默认输出目录为：

```text
data/datasets/window_w30_s1_h1/splits/
```

输出文件：

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

### seed 是什么

`seed` 是随机种子，用于保证随机划分结果可复现。

例如：

```bash
--seed 42
```

表示虽然脚本会随机打乱 1980 个 `segment_id`，但只要 seed 不变，每次划分结果都一样。

建议毕业设计阶段固定使用：

```text
seed = 42
```

这样后续训练、评估和论文记录更稳定。

### 当前真实划分结果

当前按 `segment_id` 完成 70% / 15% / 15% 划分，结果如下：

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
```

泄露检查结果：

```text
train_val_overlap_count  : 0
train_test_overlap_count : 0
val_test_overlap_count   : 0
has_segment_leakage      : False
```

说明训练集、验证集、测试集之间没有共享 `segment_id`，划分合格。

## 常用命令汇总

### 构建窗口数据集

```bash
python scripts/build_window_dataset.py   --segments-dir "/Users/hannn/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_4wgkj7va6emi12_5d45/msg/file/2026-03/数据/代码/atp_segments"   --output-dir data/datasets/window_w30_s1_h1   --window-size 30   --stride 1   --horizon 1   --overwrite   --verbose
```

### 检查窗口数据集

```bash
python scripts/inspect_dataset.py   --dataset-dir data/datasets/window_w30_s1_h1
```

### 划分 train / val / test

```bash
python scripts/split_dataset.py   --dataset-dir data/datasets/window_w30_s1_h1   --train-ratio 0.7   --val-ratio 0.15   --test-ratio 0.15   --seed 42   --overwrite
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

## 注意事项

1. `build_window_dataset.py` 会生成窗口数据集，可能耗时并占用较多内存。
2. `inspect_dataset.py` 不会重新生成窗口，只负责检查已有数据集。
3. `split_dataset.py` 不会复制 X/y，只生成索引文件。
4. 不同参数的数据集建议使用不同输出目录，例如 `window_w30_s1_h1`、`window_w30_s3_h1`。
5. 如果输出目录相同且使用 `--overwrite`，新结果会覆盖旧结果。
6. `.npy` 是 NumPy 数组文件格式，`X.npy` 保存滑动窗口输入，`y.npy` 保存标签，`*_indices.npy` 保存样本索引。
7. 真实数据文件和构建出的数据集文件不应提交到 GitHub。
