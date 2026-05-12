# configs

本目录用于存放 railphm-ai 实验配置。

`experiment_pipeline.json` 是统一实验入口的默认配置文件，用于管理 `window_size`、`stride`、`prediction_horizon`、`feature_profile`、`model`、`training`、阈值搜索和诊断等参数。

运行入口：

```bash
python scripts/run_experiment_pipeline.py --config configs/experiment_pipeline.json
```

配置文件使用 JSON，不引入 YAML 依赖。
