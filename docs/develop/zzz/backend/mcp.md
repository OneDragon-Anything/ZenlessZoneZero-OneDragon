# MCP 适配器

> 把 `ZzzBackendContext`（见 [architecture.md](architecture.md)）以 **MCP** 暴露给 MCP 客户端（AI 编码工具等）。MCP 是两个并行适配器之一，另一个是 HTTP（见 [http.md](http.md)）；两者共享同一 backend。

## 工具

7 个 `@mcp.tool`，各自委托一个 backend 方法：

| MCP tool | 委托 | 返回 |
|---|---|---|
| `check_game_window` | `backend.check_window()` | 状态文本（`str`） |
| `capture_game_screen` | `backend.capture()` | 截图绝对路径（落盘 `.debug/zzz_od_mcp/screenshot/`） |
| `analyze_screen(screenshot=None)` | `backend.analyze(screenshot)` | `AnalyzeScreenResult`（结构化 JSON；FastMCP 据返回注解自动生成 output schema） |
| `open_and_enter_game(block=True)` | `backend.start_run('mcp', op_factory)` | `block=True`：结果文本（`str`）；`block=False`：已启动 JSON；并发拒绝时返错误 JSON |
| `get_run_status` | `backend.query_status()` | `RunStatusResult`（运行中返当前节点/重试；终态返结果/失败定位） |
| `stop_run` | `backend.stop()` | `{"stopped": bool, ...}`（仅表信号已发出，过渡期 `get_run_status` 仍显示 running） |
| `close_game` | `backend.close_game()` | 文本（`str`，已发送关闭信号；controller 吞异常，用 `check_game_window` 验证） |

要点：

- backend 实例**注入**（闭包捕获），不用全局单例，也不用 FastMCP lifespan 管 backend 生命周期（由入口管）。
- `capture_game_screen` 落盘返路径,客户端读取该图片;`analyze_screen` 返结构化 dataclass,FastMCP 序列化为带嵌套 `OcrText` 的 JSON。
- `analyze_screen(screenshot=...)`:省略 `screenshot` 走实时(截活窗口,精准命中回写 `current_screen_name`);传入则解析**本地截图**——绝对路径按路径读,纯名字补 `.debug/images/<名>.png`(复用 `debug_utils.get_debug_image_path`)。文件支**无需游戏在线**、**不回写**识别状态,用于离线校验/反哺 `screen_info`(`write_back = screenshot is None`)。
- 长耗时 operation（`open_and_enter_game`）经 backend 共享 `RunSlot` 派发：`block=True` 用 `asyncio.wrap_future(future)` 阻塞 await 取结果，`block=False` 立刻返回已启动状态，后续用 `get_run_status` 查进度。MCP 与 HTTP（见 [http.md](http.md)）**对称暴露**这套运行态三件套（[design-principles.md](design-principles.md) P11）。
- **中断安全**：`block=True` 时若调用方取消 await，中断的只是本次 await，底层 `RunSlot._run` 继续执行、结果入槽，可用 `get_run_status` 查到终态。
- 单跑道：已有运行在进行时 `open_and_enter_game` 返回并发拒绝（含 `source` + 提示），保证同进程独占资源不冲突。
- `close_game` **独立同步**（不走 RunSlot）：秒级关游戏窗口，镜像 `check_window` 同步模式；与 `open_and_enter_game`（走 RunSlot）非对称（耗时量级不同）。反复 open→close 测试用。
- 理念：MCP 只做感知 / 操作，编码 / 调试交给 AI（[design-principles.md](design-principles.md)）。

## 传输与端口

- 传输 streamable-http，端点 `/mcp`，与 HTTP `/game/*` 同进程共存。
- 默认端口 **23001**。

## 接入 MCP 客户端

主 server 是标准 streamable-http,任何 MCP 客户端都可挂载。以 Claude Code 为例:

```shell
claude mcp add --transport http zzz_od http://127.0.0.1:23001/mcp
```

注册后重启客户端生效。

## 路线图（尚未实现）

- `identify_current_screen`（屏幕识别 / 模板匹配）、`click_at_position`（按坐标点击）—— 更多 game 感知 / 交互 tool。

## 相关文档

- [architecture.md](architecture.md) — backend 方法定义
- [http.md](http.md) — 并行的 HTTP 适配器
- [design-principles.md](design-principles.md) — MCP tool 设计规范（P1–P12）
- [entry.md](entry.md) — 服务入口
