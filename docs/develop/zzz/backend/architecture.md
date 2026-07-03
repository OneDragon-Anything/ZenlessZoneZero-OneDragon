# 后端服务层架构

> `ZzzBackendContext` —— 绝区零一条龙的运行层（`ZContext`）之上的一层**传输无关**后端，把游戏感知 / 操作能力对外暴露给 MCP 与 HTTP 适配器。本文描述**当前已实现**的能力（3 个感知方法 + 运行态三件套 + `close_game`）；未实现的扩展见 [§路线图](#路线图尚未实现)。MCP / HTTP 适配器见 [mcp.md](mcp.md) / [http.md](http.md)，进程入口见 [entry.md](entry.md)，MCP tool 设计规范见 [design-principles.md](design-principles.md)。

## 概述

后端服务层是一个 **headless 服务进程**：自己持有 `ZContext`（截图 / OCR / YOLO / 控制器 / 执行引擎），通过 `ZzzBackendContext` 收敛成一组**传输无关**方法，再由 MCP、HTTP 两个适配器并行对外暴露。GUI 是另一个独立入口，不经过本层。

三层：

- **Layer 0** —— `ZContext`（成熟运行核心，不改动）。
- **收敛层** —— `ZzzBackendContext`：持有 `ZContext`，管生命周期，暴露感知 / 操作方法。
- **适配器** —— MCP（`@mcp.tool`，原生 tool-call）+ HTTP（`/game/*`，通用 REST）；两者共享同一 backend，各自序列化。

## 模块布局

```
src/zzz_od/backend/
  __init__.py
  schemas.py             # 传输无关返回结构：WindowStatus / OcrText / AnalyzeScreenResult / RunStatusResult
  backend_context.py     # ZzzBackendContext + BackendNotReadyError + RunState + RunSlot
  mcp/
    __init__.py
    app.py               # create_mcp_server + 7 个 @mcp.tool + _save_screenshot
  http/
    __init__.py
    routes.py            # register_http_routes + 7 个 /game/* 处理器
  entry/
    __init__.py
    server.py            # create_app + _serve + main（uvicorn，默认 23001）
```

## ZzzBackendContext

`ZzzBackendContext` 在构造时持有（不继承）一个 `ZContext`，由服务入口注入（不用全局单例）。

### 生命周期

服务启动 / 关闭在线程池执行（`asyncio.to_thread`），不阻塞事件循环。

> `ctx.init_async()` 返回 `None`（fire-and-forget），**不可 await**；要等初始化完成须 `asyncio.to_thread(ctx.init)`。

所有方法前置校验 `ctx.ready_for_application`，未就绪抛 `BackendNotReadyError`。

### 感知 / 操作方法

| 方法 | 作用 | Layer 0 调用 | 返回 |
|---|---|---|---|
| `check_window()` | 游戏窗口状态 | `ctx.controller.game_win`（title / valid / active / scale / rect） | `WindowStatus` |
| `capture()` | 截图 | `controller.is_game_window_ready` + `get_screenshot(independent=False)` | RGB `MatLike` |
| `analyze()` | 截图 + OCR | `get_screenshot` + `ctx.ocr_service.get_ocr_result_list(image=)` | `AnalyzeScreenResult` |
| `start_run(source, op_factory)` | 派发长耗时 operation 到共享 `RunSlot` | 委托 `run_slot._start_run`：后台线程内 `run_context.start_running()` → `op_factory(ctx).execute()` → `finally stop_running()` 并固化终态 | `(ok, future)`：`ok=False` 表已有运行；`ok=True` 表已启动 |
| `query_status()` | 查询当前/最近一次运行状态 | 委托 `run_slot._query_status` | `RunStatusResult` |
| `stop()` | 发出停止信号 | 委托 `run_slot._stop` | `dict`（`{"stopped": bool, ...}`） |
| `close_game()` | 关闭游戏（秒级，**不走 RunSlot**） | `controller.close_game()`（`win.close`，吞异常不返） | `str`（已发送关闭信号；用 `check_window` 验证） |

- backend 返回**原始数据**（图像 / 结构），持久化与协议格式交给适配器（MCP 落盘返路径、HTTP 直传字节）。
- 长耗时 operation 经 `start_run` 异步派发：适配器 `block=True` 时 `await asyncio.wrap_future(future)` 取结果，`block=False` 立刻返回、用 `query_status` 查进度。MCP / HTTP 对称暴露（[design-principles.md](design-principles.md) P11）。

### RunSlot（单跑道运行槽）

`RunSlot`（`backend_context.py`）是跨 MCP / HTTP 共享的运行态载体，由 `ZzzBackendContext` 持有一个实例（`backend.run_slot`）。设计要点：

- **单跑道**：单线程 `ThreadPoolExecutor(max_workers=1)`，`_start_run` 在锁内检查 `future` 未完成才派发，否则返回 `ok=False`（并发拒绝），保证独占资源不冲突。
- **固化终态**：状态判据用固化字段 `terminal_state`（`RunState` 枚举：`IDLE` / `RUNNING` / `SUCCESS` / `FAILED` / `STOPPED`），不读 `run_context` 推中间态；`_run` 在 `finally` 锁内固化 `terminal_state` / `last_status` / `failed_node` / `finished_at`，清空 `current_op`。
- **运行中读 operation**：运行期间 `_run` 在锁内把 `current_op` 暴露给 `_query_status`，可读当前节点 / 重试次数（终态后 `current_op` 销毁，仅留固化字段）。
- **跨适配器共享**：MCP（`source='mcp'`）与 HTTP（`source='http'`）调同一 `RunSlot`，HTTP 触发的运行 MCP 也能 `query_status` 查到。
- **停止语义**：`_stop` 只发停止信号，operation 在当前节点完成后退出（`OperationResult.status == '人工结束'` → `RunState.STOPPED`），非强杀；过渡期 `query_status` 仍报 `RUNNING`。

### 返回结构（`schemas.py`）

三个 dataclass（具体定义见源码）：

- **`WindowStatus`**：`win_title` / `is_win_valid` / `is_win_active` / `is_win_scale`，可选 `x` / `y` / `width` / `height`。
- **`OcrText`**：`text` / `x` / `y` / `width` / `height`。
- **`AnalyzeScreenResult`**：`success` / `ocr_texts: list[OcrText]` / `error: str | None`。

## 有状态资源约束

backend 独占持有 `ZContext`，适配器 / 前端不可并发直调其内部：

| 资源 | 约束 |
|---|---|
| `gpu_executor` | 单线程，强制串行 DirectML onnx session（YOLO 等） |
| 游戏窗口句柄 | `ZPcController → PcGameWindow`，win32 句柄，1080p，独占 |
| 输入注入 | `pyautogui` / `pydirectinput` 需管理员权限 + 交互式桌面会话 |
| OCR / YOLO session | onnxruntime InferenceSession，重资源 |

## 进程模型

- 后端是**独立的 headless 服务入口**（`entry/server.py`），自己 `ZContext()` 再包 `ZzzBackendContext`；GUI 是另一个入口，二者择一运行（同 onedragon headless 模式）。
- 每进程独占一个 `ZContext` → `gpu_executor` / 窗口句柄天然不冲突。
- 服务进程常驻 `ZContext`，规避冷启动（OCR / YOLO 装载数秒）。

## 路线图（尚未实现）

当前已实现：上述 3 个感知方法 + 运行态三件套（`start_run` / `query_status` / `stop`，经共享 `RunSlot`）+ `close_game`（独立同步关游戏）+ MCP / HTTP 适配器 + 入口 + 远程 SSH daemon（见 [remote-ssh.md](remote-ssh.md)）。后续扩展：

- **run-as-service**：`run_application` / `pause` —— 把一条龙 Application 当可控服务跑。`status` / `stop` 已实现（本次，经 `RunSlot` 暴露的运行态三件套）。
- **事件桥**：`subscribe_events` —— 把日志 / 运行状态 / overlay-debug 事件桥成可订阅流（WS 推 web、MCP notifications 推 AI）。
- **多实例**：`list_instances` / `switch_instance` —— 账号实例切换。
- **更多 game 能力**：`identify_current_screen`（屏幕识别）、`click_at_position`（按坐标点击）。
- **GUI 收敛**：将来 GUI 入口改走 backend（接口形状已对齐：`run_application` / `pause` / `subscribe_events`）。

## 相关文档

- [README.md](README.md) — 总览
- [mcp.md](mcp.md) — MCP 适配器
- [http.md](http.md) — HTTP 适配器
- [design-principles.md](design-principles.md) — MCP tool 设计规范（P1–P12）
- [entry.md](entry.md) — 服务入口
- [一条龙整体架构](../../one_dragon/one_dragon_architecture.md) — Layer 0 运行层
