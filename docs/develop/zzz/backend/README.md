# 后端服务层（Backend Context）

> `docs/develop/zzz/backend/` 的入口。绝区零一条龙的运行层（`ZContext`）之上的**传输无关**后端，把游戏感知 / 操作能力经 MCP 与 HTTP 对外暴露。本文为「总」，各「分」文档见下方索引。

## 是什么

一个 **headless 服务进程**：自己持有 `ZContext`，通过 `ZzzBackendContext` 收敛成传输无关方法，再由 MCP、HTTP 两个适配器并行对外暴露。GUI 是另一个独立入口，不经过本层。

三层：

| 层 | 内容 |
|---|---|
| Layer 0 | `ZContext`（截图 / OCR / YOLO / 控制器 / 执行引擎），不改动 |
| 收敛层 | `ZzzBackendContext`：持有 ctx、管生命周期、感知 / 操作方法 |
| 适配器 | MCP（`@mcp.tool`）+ HTTP（`/game/*`），并行、共享 backend |

当前已实现：**4 个感知 / 操作方法**（窗口状态 / 截图 / OCR / 进游戏）+ MCP / HTTP 适配器 + 服务入口 + 远程 SSH daemon。其余（run-as-service、事件桥、多实例、GUI 收敛）见各文档的「路线图」。

## 怎么跑

```shell
uv run --env-file .env python -m zzz_od.backend.entry.server --port 23001
```

启动后同时服务 `http://127.0.0.1:23001/mcp`（MCP）与 `/game/*`（HTTP）。详见 [entry.md](entry.md)。

## 文档索引（总—分）

| 文档 | 内容 |
|---|---|
| [design-principles.md](design-principles.md) | **设计纲领**：MCP tool 的能力边界与设计原则（agent 能力视角） |
| [architecture.md](architecture.md) | `ZzzBackendContext` 架构、生命周期、方法、资源约束、进程模型 |
| [mcp.md](mcp.md) | MCP 适配器（tool、传输、注册） |
| [http.md](http.md) | HTTP `/game/*` 适配器 |
| [entry.md](entry.md) | 服务入口、运行方式 |
| [remote-ssh.md](remote-ssh.md) | 远程 SSH daemon（Session 1 常驻，管主 server 启停） |

> 各文档末尾有「路线图（尚未实现）」段落，列 run-as-service / 事件桥 / 多实例 / GUI 收敛等待办。

## 相关文档

- [一条龙整体架构](../../one_dragon/one_dragon_architecture.md) — Layer 0 运行层
- [AI 编码助手接入](../../setup/ai_coding.md) — MCP / skill 接入
- [AI Coding Harness 工程](../../harness/README.md) — 方向 B 路线图
