from app import create_app

# 创建 Flask 应用实例
app = create_app()

if __name__ == "__main__":
    # 从 app.config 中安全提取配置项
    host = app.config.get("APP_HOST", "127.0.0.1")
    port = app.config.get("APP_PORT", 5000)
    env = app.config.get("APP_ENV", "development")
    
    # 根据环境推断是否开启调试模式
    debug_mode = True if env == "development" else False

    app.run(
        host=host,
        port=port,
        debug=debug_mode
    )