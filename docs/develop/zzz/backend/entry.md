# 服务入口

> `ZzzBackendContext` 的进程入口：装配 backend + MCP / HTTP 适配器，uvicorn 运行。本地 headless 入口见下；远程 SSH daemon（管本入口启停）见 [remote-ssh.md](remote-ssh.md)。

## 命令行运行

```shell
uv run --env-file .env python -m zzz_od.backend.entry.server --host 127.0.0.1 --port 23001
```

如果项目根目录没有 `.env`，可省略 `--env-file .env`：

```shell
uv run python -m zzz_od.backend.entry.server --host 127.0.0.1 --port 23001
```

启动流程：

1. 创建 `ZContext()`。
2. 创建 `ZzzBackendContext(ctx)`。
3. `await backend.start()` 在线程池中执行同步初始化。
4. 注册 MCP `/mcp` 和 HTTP `/health`、`/game/*`。
5. `uvicorn.serve` 监听本机端口。
6. 关闭时调用 `backend.shutdown()`。

CLI 参数：

- `--host`：默认 `127.0.0.1`。
- `--port`：默认 `23001`。

## GUI 启动

GUI 的「开发工具 -> MCP 服务」页面提供本机 server 管理：

- 探测：请求 `http://127.0.0.1:<port>/health`。
- 启动：在项目根目录执行 `uv run python -m zzz_od.backend.entry.server --port <port>`；如果项目根目录存在 `.env`，会自动补上 `--env-file .env`。
- 停止 / 重启：查找并管理 `zzz_od.backend.entry.server` 进程。
- 日志：`.debug/zzz_od_mcp/main_server.log`，默认关闭 uvicorn access log，避免状态轮询刷屏。
- MCP 地址：`http://127.0.0.1:<port>/mcp`。
- 当前运行状态：请求 `http://127.0.0.1:<port>/game/status`。

页面会低频轮询 `/game/status`，并尾读 `.debug/zzz_od_mcp/main_server.log` 到消息框；这些日志只用于 GUI 展示，不通过 MCP tool 返回给 agent。GUI 会过滤自身轮询、`GET /mcp` 探测和 Windows 连接重置这类噪音，并限制消息框保留行数，避免长时间打开后卡顿。

这个 GUI 页面管理的是一个本机 server 子进程，不是把 MCP server 嵌进 GUI 主进程。当前不做 GUI 主进程与 server 子进程之间的跨进程运行互斥。

## `.env`

`uv run --env-file .env ...` 会要求项目根目录存在 `.env`。如果本地没有 `.env`，命令会在启动前报错。GUI 启动会先判断 `.env` 是否存在；命令行手动启动时，开发环境可以按项目需要创建 `.env`，或在不需要环境变量的场景下省略 `--env-file .env`。

## 进程模型

- server 进程独立持有一个 `ZContext`。
- 每个进程内通过运行槽保证同进程单跑道。
- 常驻 `ZContext` 可避免 OCR / YOLO 冷启动成本。

## 依赖（dev 组）

- `mcp`：FastMCP / streamable-http。
- `uvicorn`：ASGI server。

## 远程 SSH

远程 SSH 场景由 daemon 管 server 启停，详见 [remote-ssh.md](remote-ssh.md)。

## 相关文档

- [architecture.md](architecture.md) - backend 生命周期和进程模型
- [mcp.md](mcp.md) - MCP tool
- [http.md](http.md) - HTTP 端点
