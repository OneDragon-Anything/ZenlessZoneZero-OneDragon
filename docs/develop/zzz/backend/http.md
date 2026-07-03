# HTTP 适配器

> 把 `ZzzBackendContext`（见 [architecture.md](architecture.md)）以 **HTTP** 暴露。它是 **web 前端 + skill 的共同目标**——任何能发 HTTP 的客户端（含 AI 经 Bash / curl）都能用；MCP 客户端另走 [mcp.md](mcp.md)。两个适配器并行、共享同一 backend。

## 端点

按作用对象分前缀：`/game/*` 直接作用于游戏（窗口 / 画面 / 启动）。流程类（`/app/*`）、账号类（`/instances/*`）端点属路线图。

| 方法 | 端点 | 委托 | 返回 |
|---|---|---|---|
| GET | `/game/window` | `backend.check_window()` | `WindowStatus` JSON |
| GET | `/game/capture` | `backend.capture()` | PNG 字节（`image/png`，不落盘） |
| GET | `/game/analyze` | `backend.analyze()` | `AnalyzeScreenResult` JSON |
| POST | `/game/enter?block=` | `backend.start_run('http', op_factory)` | `block=true`（默认）：结果 JSON；`block=false`：已启动 JSON；并发拒绝返错误 JSON |
| GET | `/game/status` | `backend.query_status()` | `RunStatusResult` JSON |
| POST | `/game/stop` | `backend.stop()` | `{"stopped": bool, ...}` JSON |

要点：

- 处理器调 backend 走 `asyncio.to_thread`；`BackendNotReadyError` → 503 JSON。
- `/game/capture` 直接回传 PNG 字节（区别于 MCP 的落盘返路径——同一能力、不同序列化）。
- `/game/enter` 经 `backend.start_run` 异步派发到共享 `RunSlot`：`block=true`（默认）用 `asyncio.wrap_future(future)` 阻塞到运行结束返结果文本；`block=false` 立刻返回已启动状态，后续用 `/game/status` 查进度与结果。单跑道，已有运行时返回并发拒绝 JSON（含 `source` + 提示）。
- skill 教 AI 经 Bash / curl 打这些端点（通用，任何 AI 工具可用）。

## 与 MCP 的关系

| | HTTP（本适配器） | MCP（[mcp.md](mcp.md)） |
|---|---|---|
| 消费者 | web 前端 + skill / Bash 的 AI | MCP 客户端（AI 编码工具等） |
| 调用方式 | REST | tool-call（类型化 schema） |
| 共享 | 同一 `ZzzBackendContext` | 同一 `ZzzBackendContext` |

运行态三件套**对称暴露**：`/game/enter` ↔ `open_and_enter_game`、`/game/status` ↔ `get_run_status`、`/game/stop` ↔ `stop_run`，两侧调同一 backend 方法（[design-principles.md](design-principles.md) P11），跨适配器状态共享同一 `RunSlot`（HTTP 触发的运行 MCP 也能查到）。

## 路线图（尚未实现）

- 事件推送（WebSocket / SSE）：订阅 `subscribe_events`，推日志 / 运行状态给 web 前端。
- `/app/*`（跑一条龙流程）、`/instances/*`（账号切换）端点。

## 相关文档

- [architecture.md](architecture.md) — backend 方法定义
- [mcp.md](mcp.md) — 并行的 MCP 适配器
- [entry.md](entry.md) — 服务入口
