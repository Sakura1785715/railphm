# railphm-web

高铁列控设备故障预测与健康管理系统（RailPHM）- 前端子项目

## 当前阶段目标

当前已完成前端基础启动与路由框架建设，具备以下最小可运行能力：

- 基于 Vue 3 + Vite 的前端启动能力
- 基于 Vue Router 的基础页面路由
- 基础 Layout 与导航结构
- Axios 请求层封装
- `/health` 前后端联通测试页

## 启动方式

1. 安装依赖

```bash
npm install
```

2. 启动开发服务

```bash
npm run dev
```

默认开发地址为：`http://127.0.0.1:5173`

## 接口联调说明

- 前端请求基础路径由 `VITE_API_BASE_URL` 控制
- 开发代理目标由 `VITE_API_PROXY_TARGET` 控制
- 当前默认配置：
  - `VITE_API_BASE_URL=/api`
  - `VITE_API_PROXY_TARGET=http://127.0.0.1:5000`

如后端端口调整，可在 `.env.development` 中修改代理目标。

## 页面说明

- `/`：首页
- `/health`：系统联通测试页
- 其他路径：404 页面
