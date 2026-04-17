# railphm-server

高铁列控设备故障预测与健康管理系统 (RailPHM) - 后端主服务

## 当前状态
- Task 1 - 最小 Flask 启动入口已完成。
- Task 2 - 最小配置管理能力已实现。

## 运行环境与配置

1. **安装依赖**
   建议在虚拟环境中执行：
   ```bash
   pip install -r requirements.txt
   ```

2. **环境变量配置**
   项目使用系统环境变量进行基础配置。您可以参考项目根目录下的 `.env.example` 文件了解所需的配置项。
   
   在 macOS 终端中，您可以通过 `export` 命令临时覆盖默认配置来启动服务，例如：
   ```bash
   export APP_PORT=8080
   python run.py
   ```

3. **启动服务**
   ```bash
   python run.py
   ```
   服务默认将在 `http://127.0.0.1:5000` 启动。当 `APP_ENV` 为 `development`（默认值）时，Flask 会自动开启 `debug` 模式。