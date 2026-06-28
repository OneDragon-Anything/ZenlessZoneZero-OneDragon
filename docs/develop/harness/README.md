# AI Coding Harness 工程

本目录是「绝区零一条龙」**AI 编码 harness 工程**的专题文档区。它记录"如何让 AI 编码工具（Claude Code 等）在本项目高效、可靠地工作"这件事本身的工程化沉淀。

## 什么是 harness 工程

Harness 指把 LLM 变成能干活的编码 Agent 的那一层"外壳"——上下文（CLAUDE.md / AGENTS.md）、工具（MCP / skills / commands）、记忆、权限，以及把本项目特有的能力（游戏操作、CV 调试）暴露给 Agent 的接入层。模型本身只会 next-token，harness 决定它能不能在这个 repo 里**做对事**。

## 两条方向

- **方向 A｜武装 harness（当前重心）**：把项目知识、规范、工具固化进 harness，让 AI（和贡献者）开箱即用、少踩坑。已落地：`AGENTS.md` 单源、`.claude/CLAUDE.md`、`skills/`、`setup/ai_coding.md`。
- **方向 B｜MCP 驱动的游戏自动化（远期）**：把游戏操作（截图 / OCR / 进游戏 / 跑流程）通过常驻 MCP 暴露给 Agent，用于辅助开发调试，乃至让 Agent 直接驱动游戏。

## 当前状态（方向 A）

| 组件 | 位置 | 作用 |
|---|---|---|
| `AGENTS.md` | 仓库根 | 统一 AI 编码入口（架构 / 硬约束 / 流程），所有工具的信息源 |
| `.claude/CLAUDE.md` | 仓库根 | Claude Code 入口，`@../AGENTS.md` 引入 |
| `.github/copilot-instructions.md` | 仓库根 | Copilot 入口 |
| [`skills/`](../../../skills/) | 仓库根 | 4 个 Claude Code skill（`agent-auto-battle-config` / `agent-definition` / `new-config` / `zzz-one-dragon-player`） |
| [../setup/ai_coding.md](../setup/ai_coding.md) | docs/develop/setup | 各 AI 工具的接入指引（用户向："怎么用"） |

> "怎么用"见 `setup/ai_coding.md`；本目录（harness/）记录"怎么建、为什么这么建"。

## 架构原则

1. **单一信息源**：项目知识集中在 `AGENTS.md` + `docs/`，工具入口用 `@import` 引入而非复制。
2. **贵重 infra 常驻**：MCP 的价值是让 `ZContext`（OCR / YOLO / 控制器）常驻内存，规避每次冷启动数秒成本。
3. **共享 Layer 0、单服务器生长**：A→B1 工具在同一 MCP 服务器内按命名空间增长；B2（模型实时当玩家）另起独立 loop，复用 Layer 0，MCP 退为控制面。

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| A-1 | AGENTS.md 单源 + CLAUDE.md/@import + ai-tooling 文档 | ✅ |
| A-2 | skills/ 整理与约定 | ⏳ 待实施 |
| A-3 | devtools 调试指南、术语表、游戏领域文档 | ⏳ 规划 |
| B-1 | MCP：dev/inspection 工具（截图 / OCR / 跑流程） | ⏳ 规划 |
| B-2 | MCP：原子操作工具 + 跑现成 Application/Operation | ⏳ 规划 |
| B-3 | 模型实时当玩家（独立 loop，MCP 作控制面） | 🔭 远期 |

> 各方向的详细设计（决策记录 / skill 清单 / MCP 实现）在真正实施后再补对应子文档。
