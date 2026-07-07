# MCP 适配器

> 把 `ZzzBackendContext`（见 [architecture.md](architecture.md)）以 **MCP** 暴露给 MCP 客户端（AI 编码工具等）。MCP 是两个并行适配器之一，另一个是 HTTP（见 [http.md](http.md)）；两者共享同一 backend。

## 工具

14 个 `@mcp.tool`，各自委托一个 backend 方法：

| MCP tool | 委托 | 返回 |
|---|---|---|
| `check_game_window` | `backend.check_window()` | 状态文本（`str`） |
| `capture_game_screen` | `backend.capture()` | 截图绝对路径（落盘 `.debug/zzz_od_mcp/screenshot/`） |
| `analyze_screen(screenshot=None, save_image=False)` | `backend.analyze()` | `AnalyzeScreenResult`（结构化 JSON；实时 + `save_image=True` 多回传 `screenshot_path`） |
| `open_game(enter=True, block=True)` | `backend.start_run('mcp', op_factory)`（`enter=False`→`OpenGame`，`enter=True`→`OpenAndEnterGame`） | `block=True`：结果文本；`block=False`：已启动 JSON；并发拒绝时返错误 JSON |
| `click_game(x, y, press_time=0)` | `backend.click_game()` | `{success, x, y, in_window}`（坐标不在窗口内 → `in_window=False`） |
| `input_text(text, use_clipboard=None)` | `backend.input_text()` | `{success, method, masked_text}`（`use_clipboard=None` 跟 `game_config.type_input_way`） |
| `list_applications` | `backend.list_applications()` | 当前实例可运行应用、独立应用列表和当前选中项 |
| `run_one_dragon(block=False)` | `backend.run_one_dragon('mcp')` | 默认立刻返回启动状态；`block=True` 等待一条龙结束 |
| `run_standalone_app(app_id=None, block=False)` | `backend.run_standalone_app('mcp', app_id)` | `app_id=None` 时使用 GUI「应用运行」当前选中项 |
| `get_run_status` | `backend.query_status()` | `RunStatusResult`（运行中返当前节点/重试；终态返结果/失败定位） |
| `stop_run` | `backend.stop()` | `{"stopped": bool, ...}`（仅表信号已发出，过渡期 `get_run_status` 仍显示 running） |
| `close_game` | `backend.close_game()` | 文本（`str`，已发送关闭信号；controller 吞异常，用 `check_game_window` 验证） |
| `list_mcp_usage_guides` | `mcp/prompts.py` | 可用操作指南目录，相当于帮助索引 |
| `get_mcp_usage_guide(name, app_id=None)` | `mcp/prompts.py` | 指定操作指南正文，相当于任务级 `--help` |

要点：

- `app.py` 放 MCP server 创建、基础 game tool 和总注册入口；`service_app.py` 放应用运行 tool 工厂。
- backend 实例通过闭包注入 tool，不使用全局单例，也不让 FastMCP lifespan 管 backend 生命周期。
- `capture_game_screen` 落盘返回路径；`analyze_screen` 返回结构化 dataclass，由 FastMCP 序列化。
- `analyze_screen(save_image=True)`（实时模式）把已截的内存图顺手存盘 + 回传 `screenshot_path`，供调用方喂 vision double-check；默认 `false` 不落盘，离线模式忽略。
- 长耗时 operation（`open_game`）经 `RunSlot` 派发：`block=True` 用 `asyncio.wrap_future(future)` 阻塞 await 取结果，`block=False` 立刻返回已启动状态，后续用 `get_run_status` 查进度。
- `run_one_dragon` 和 `run_standalone_app` 经 `ApplicationRunSlot` 复用 `run_context.run_application`，避免复制 GUI 应用运行路径。
- 应用运行 tool 启动前会让 backend 刷新当前进程内的 YAML 配置缓存，尽量对齐 GUI 已保存设置。
- `get_run_status` / `stop_run` 是统一入口：无论最近一次运行来自进游戏 operation 还是应用运行，都通过同一组工具查询和停止。
- 单进程内已有运行时会返回并发拒绝，避免同一个 backend 内重复操作游戏资源。
- MCP tool 不返回运行日志正文；客户端需要用 `get_run_status` 轮询是否完成，GUI 服务页负责展示日志。
- `close_game` / `click_game` / `input_text` 是独立同步操作，不走运行槽；`click_game` 使用 1080p 游戏空间坐标。
- `list_mcp_usage_guides` / `get_mcp_usage_guide` 把 prompt 模板以普通 tool 暴露，方便不会主动消费 MCP prompts 的客户端发现。
- 理念：MCP 只做感知 / 操作，编码 / 调试交给 AI（[design-principles.md](design-principles.md)）。

## Prompts

| MCP prompt | 用途 |
|---|---|
| `zzz_check_status` | 引导 AI 查询运行状态、窗口状态与当前画面分析结果。 |
| `zzz_run_one_dragon` | 引导 AI 按当前配置启动一条龙，并轮询 `get_run_status`。 |
| `zzz_run_standalone_app(app_id=None)` | 引导 AI 列出应用、选择独立应用并启动运行。 |

要点：

- prompt 只描述调用顺序，不直接执行工具；实际执行仍由 MCP 客户端选择 tool。
- `zzz_run_standalone_app` 支持传入 `app_id`，为空时提示使用 GUI「应用运行」当前选中项。
- 运行类 prompt 默认使用 `block=False` 启动，再轮询 `get_run_status`，便于客户端在长耗时任务中持续反馈状态。
- 部分 MCP 客户端不会主动展示 prompts；这时可让 agent 先调用 `list_mcp_usage_guides`，再调用 `get_mcp_usage_guide` 读取同一份模板。

## 传输与端口

- 传输：streamable-http。
- MCP 端点：`/mcp`。
- 默认本机端口：`23001`。
- MCP URL：`http://127.0.0.1:23001/mcp`。
- 健康检查：`http://127.0.0.1:23001/health`。

## 接入 MCP 客户端

主 server 是标准 streamable-http,任何 MCP 客户端都可挂载。
先通过 GUI「开发工具 -> MCP 服务」或命令行启动本机 server，再在 Codex/Claude 里新增 MCP 服务器。

### Claude Code MCP 配置

```shell
claude mcp add --transport http zzz_od http://127.0.0.1:23001/mcp
```

### Codex GUI MCP 配置

| 字段 | 填写 |
|---|---|
| 名称 | `zzz_od` |
| 类型 | `Streamable HTTP` |
| Bearer 令牌环境变量 | 留空 |
| URL | `http://127.0.0.1:23001/mcp` |
| 标头 | 留空；如果界面要求 JSON，填 `{}` |
| 启动命令 | 留空 |
| 参数 | 留空 |

要点：

- 当前服务只实现 streamable HTTP，不是 STDIO server；Codex 中不要选 STDIO。
- 本机接口默认无鉴权，因此不需要 Bearer token 或额外 headers。
- Codex/Claude 只负责连接已启动的 HTTP MCP server；启动 / 停止 / 重启由 GUI「MCP 服务」页或命令行负责。
- 命令行启动可用 `uv run python -m zzz_od.backend.entry.server --host 127.0.0.1 --port 23001`；如果项目根目录存在 `.env`，也可使用 `uv run --env-file .env python -m zzz_od.backend.entry.server --host 127.0.0.1 --port 23001`。

## 路线图（尚未实现）

- 更多 game 感知 / 交互 tool：原 `identify_current_screen` 已由 `analyze_screen` 实现，`click_at_position` 已由 `click_game` 实现；后续按需补 `press_key`（单键，如 Esc/Enter）、`scroll` / `drag_to` 等。
- 更完整的 AI 操作范式，例如失败恢复、实例切换与多步巡检。

## 相关文档

- [architecture.md](architecture.md) - backend 方法定义
- [http.md](http.md) - 并行的 HTTP 适配器
- [design-principles.md](design-principles.md) - MCP tool 设计规范
- [entry.md](entry.md) - 服务入口
