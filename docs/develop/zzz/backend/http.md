# HTTP 适配器

> 把 `ZzzBackendContext`（见 [architecture.md](architecture.md)）以 **HTTP** 暴露。它是 **web 前端 + skill 的共同目标**——任何能发 HTTP 的客户端（含 AI 经 Bash / curl）都能用；MCP 客户端另走 [mcp.md](mcp.md)。两个适配器并行、共享同一 backend。

## 端点

按作用对象分前缀：`/game/*` 直接作用于游戏（窗口 / 画面 / 启动 / 自定义 op 运行）、流程类（`/app/*`）、账号类（`/instances/*`）端点属路线图、`/health` 用于本机服务探测。

| 方法 | 端点 | 委托 | 返回 |
|---|---|---|---|
| GET | `/health` | backend 进程探测 | `{"ok": true, "server": "zzz_od", "ready": bool}` |
| GET | `/game/window` | `backend.check_window()` | `WindowStatus` JSON |
| GET | `/game/capture` | `backend.capture()` | PNG 字节（`image/png`，不落盘） |
| GET | `/game/analyze?save_image=` | `backend.analyze()` | `AnalyzeScreenResult` JSON（`save_image=true` 实时模式多带 `screenshot_path`） |
| POST | `/game/enter?block=` | `backend.start_run('http', op_factory)` | `block=true`（默认）：结果 JSON；`block=false`：已启动 JSON；并发拒绝返错误 JSON |
| GET | `/game/applications` | `backend.list_applications()` | 当前实例可运行应用、独立应用列表和当前选中项（只读，不刷新配置） |
| POST | `/game/run/one-dragon?block=` | `backend.run_one_dragon('http')` | 默认返回启动状态；`block=true` 等待一条龙结束 |
| POST | `/game/run/standalone?app_id=&block=` | `backend.run_standalone_app('http', app_id)` | `app_id` 为空时使用 GUI「应用运行」当前选中项 |
| GET | `/game/operations` | `operation_registry.scan_operations(ctx)` | 可运行自定义 op 列表（`op_id` + 参数 schema，纯反射不实例化） |
| GET | `/game/operations/describe?op_id=` | `operation_registry.describe_operation(ctx, op_id)` | 单个 op 参数 schema（每参数标 `json_serializable` + 整体 `debuggable`） |
| POST | `/game/run/operation?op_id=&block=` | `operation_registry` 校验 + `run_slot._start`（op 路径） | 默认返回启动状态；`block=true` 等结束；`args` 走 JSON body |
| GET | `/game/status` | `backend.query_status()` | `RunStatusResult` JSON |
| POST | `/game/stop` | `backend.stop()` | `{"stopped": bool, ...}` JSON |
| POST | `/game/close` | `backend.close_game()` | `{"result": 文本}` JSON；窗口未就绪返回 503 |

要点：

- `routes.py` 放基础 game handler 与总注册入口；`service_routes.py` 放应用运行、自定义 op 和 `/health` 这组服务端点。
- 处理器调 backend 走 `asyncio.to_thread`；`BackendNotReadyError` 统一返回 503 JSON。
- `/game/capture` 直接回传 PNG 字节（区别于 MCP 的落盘返路径，同一能力、不同序列化）。
- `/game/analyze?save_image=true`（实时模式）让 backend 顺手存盘 + 响应多带 `screenshot_path`；默认 `false` 不落盘，离线模式忽略。
- 所有运行端点（`/game/enter`、`/game/run/one-dragon`、`/game/run/standalone`、`/game/run/operation`）经**同一个 `RunSlot`** 异步派发：op 路径（`enter` / `operation`）槽自管生命周期，app 路径（`one-dragon` / `standalone`）委托 `run_application`。
- 自定义 op 端点：`op_id` 走 query 参数（`?op_id=...`），`args` 走 JSON body（整体 body 即 args 字典，空 body 时 `args={}`）；`block` 走 query。**业务失败一律 `200 + body 内 error/started 标志`**（`op_id` 不存在 / 非 Operation / 参数校验失败 / 并发拒绝），不引入 400/404/409；仅 `BackendNotReadyError` 返 503。
- 配置刷新：app 路径在 `run_application` 前（槽线程内、`_start` 已赢锁后）刷新当前进程的 YAML 配置缓存，对齐 GUI 已保存设置；拒绝路径不刷新。`/game/applications` 与 `/game/operations` 是只读路径，不刷新。
- `/game/status` 和 `/game/stop` 是统一运行态入口，覆盖 op 路径与 app 路径两类后台任务。
- GUI「开发工具 -> MCP 服务」页面用 `/health` 探测本机 server 是否已经启动，用 `/game/status` 展示当前运行状态。
- skill 教 AI 经 Bash / curl 打这些端点（通用，任何 AI 工具可用）。

## 与 MCP 的关系

| | HTTP | MCP |
|---|---|---|
| 消费者 | web 前端、脚本、skill / Bash | MCP 客户端 |
| 调用方式 | REST | tool-call |
| 共享对象 | 同一个 `ZzzBackendContext` | 同一个 `ZzzBackendContext` |

运行态三件套**对称暴露**：`/game/enter` ↔ `open_game`、`/game/status` ↔ `get_run_status`、`/game/stop` ↔ `stop_run`，两侧调同一 backend 方法（[design-principles.md](design-principles.md) P11），跨适配器状态共享同一 `RunSlot`（HTTP 触发的运行 MCP 也能查到）；应用运行端点对应 `run_one_dragon` / `run_standalone_app` / `list_applications`；自定义 op 运行入口对应 `list_operations` / `describe_operation` / `run_operation`（`/game/operations` ↔ `list_operations`、`/game/operations/describe` ↔ `describe_operation`、`/game/run/operation` ↔ `run_operation`）。

## 路线图（尚未实现）

- 事件推送（WebSocket / SSE）：订阅 `subscribe_events`，推日志 / 运行状态给 web 前端。
- `/app/*`（跑一条龙流程）、`/instances/*`（账号切换）端点。

## 相关文档

- [architecture.md](architecture.md) - backend 方法定义
- [mcp.md](mcp.md) - 并行的 MCP 适配器
- [entry.md](entry.md) - 服务入口
