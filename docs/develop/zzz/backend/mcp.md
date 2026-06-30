# MCP 适配器

> 把 `ZzzBackendContext`（见 [architecture.md](architecture.md)）以 **MCP** 暴露给 MCP 客户端（AI 编码工具等）。MCP 是两个并行适配器之一，另一个是 HTTP（见 [http.md](http.md)）；两者共享同一 backend。

## 工具

4 个 `@mcp.tool`，各自委托一个 backend 方法：

| MCP tool | 委托 | 返回 |
|---|---|---|
| `check_game_window` | `backend.check_window()` | 状态文本（`str`） |
| `capture_game_screen` | `backend.capture()` | 截图绝对路径（落盘 `.debug/zzz_od_mcp/screenshot/`） |
| `analyze_screen` | `backend.analyze()` | `AnalyzeScreenResult`（结构化 JSON；FastMCP 据返回注解自动生成 output schema） |
| `open_and_enter_game` | `backend.enter_game()` | 结果文本（`str`） |

要点：

- backend 实例**注入**（闭包捕获），不用全局单例，也不用 FastMCP lifespan 管 backend 生命周期（由入口管）。
- `capture_game_screen` 落盘返路径,客户端读取该图片;`analyze_screen` 返结构化 dataclass,FastMCP 序列化为带嵌套 `OcrText` 的 JSON。
- `open_and_enter_game` 是长阻塞，适配器用 `asyncio.to_thread` 调用，不阻塞事件循环。
- 理念：MCP 只做感知，编码 / 调试交给 AI。

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
- [entry.md](entry.md) — 服务入口
