# AI 编码助手接入

本仓库支持多种 AI 编码助手（如 Claude Code、GitHub Copilot 等）协作开发。本文档说明如何把它们接入本项目，以及**新增的 AI 协作约定应该放到哪一级**。

## 核心原则：三级晋升

新增任何"给 AI 看的约定"时，按下面的阶梯**从低到高**放——能放低就不放高：

| 级别 | 位置 | 是否提交 | 适用 |
|---|---|:---:|---|
| **① 个人级** | `CLAUDE.local.md`（及各工具的本地文件） | ❌ gitignore | 只对自己有用的偏好、实验性约定。**先在这里试。** |
| **② 项目级** | 工具的项目文件（如 `.claude/CLAUDE.md`、`.github/copilot-instructions.md`）或 `docs/develop/` 文档 | ✅ 提交 | 团队共享、但**某个工具特有**的内容。 |
| **③ 统一源** | 根目录 `AGENTS.md` | ✅ 提交 | **跨工具通用**的项目知识（架构、硬约束、流程）。 |

**晋升路径**：① 个人级 →（证明对团队有用）→ ② 项目级 →（证明跨工具通用）→ ③ `AGENTS.md`。

- **工具特有**的内容（如 Claude 专属的 uv / context7 规则）**不进 `AGENTS.md`**，留在该工具的项目级文件里。
- 只有"所有工具都该知道"的内容，才晋升到 `AGENTS.md`。

## AGENTS.md：统一源

根目录 [AGENTS.md](../../../AGENTS.md) 是跨工具的单一信息源（项目架构、开发硬约束、提交流程）；详细编码规范见 [spec/agent_guidelines.md](../spec/agent_guidelines.md)。

> 修改这两份即等同于更新所有已接入工具的行为——前提是内容确实**跨工具通用**。否则按上面的阶梯放低一级。

## 各工具接入

> **原则**：入口文件优先放该工具自己的**配置目录**（如 `.claude/`、`.github/`），而不是项目根目录，避免根目录堆积。最理想的是工具能直接读 `AGENTS.md`——这样根本不需要入口文件。

### Claude Code（用 `@` 引用，不用硬链接）

- 仓库已提交 `.claude/CLAUDE.md`，内部用 `@../AGENTS.md` **引入** `AGENTS.md`。Claude Code 启动时自动加载，无需配置。
- **Claude 特有**的项目级规则写在 `.claude/CLAUDE.md` 里 `@` 引入的**下方**（提交、团队共享）。例如强制 `uv`、用 context7、Bash 后台等。
- **个人**偏好写在仓库根 `CLAUDE.local.md`（gitignore），加载顺序在 `CLAUDE.md` 之后。

### GitHub Copilot

- 仓库已提交 `.github/copilot-instructions.md`（frontmatter `applyTo: '**'`，对所有文件生效）；每次会话自动注入，并 defer 到 `AGENTS.md` 取完整上下文。

### 其他工具（无原生引入机制时）

若某工具既读不了 `AGENTS.md`、又没有 `@` 之类的引入语法，只能读它自己固定的入口文件，就用**硬链接**让该文件镜像 `AGENTS.md`。入口文件位置同样遵循上面的原则——优先配置目录，其次根目录。

示例（文件名依工具而定，此处以 `CLAUDE.md` 作占位演示命令形式）：

```powershell
New-Item -ItemType HardLink -Path "CLAUDE.md" -Target "AGENTS.md"
```

- 该入口文件应被 `.gitignore` 忽略，仅本地生效（个人级）。
- 工具特有的项目级内容，另起一个**提交**的文件维护，不要塞进 `AGENTS.md`。
- 将来某工具支持引入语法时，优先用引入、弃用硬链接。（Unix：`ln AGENTS.md CLAUDE.md`。）

## 内容该放哪（速查）

| 内容 | 放哪 |
|---|---|
| 只对自己有用的偏好 / 实验 | ① 个人级：`CLAUDE.local.md` |
| 团队共享、但某工具特有 | ② 项目级：该工具文件（如 `.claude/CLAUDE.md`） |
| 跨所有工具通用 | ③ `AGENTS.md` |

## MCP

- **推荐**：[context7](https://github.com/upstash/context7) — 查询库文档；已在本项目 `.claude/settings.json` 启用（Claude Code 场景）。
- **项目自有 MCP（规划中）**：后续将把游戏操作（截图 / OCR / 进游戏等）暴露给 agent，用于辅助开发与调试。运行层后端化与 MCP 适配的整体设计见 [zzz/backend/](../zzz/backend/)，路线图见 [harness/README.md](../harness/README.md)。

## Skills

Skill 是 Claude Code（及 Codex 等少数工具）的可调用能力。要点：**每个工具只读自己目录下的 skill**——Claude Code 读 `.claude/skills/`，**不读根目录 `skills/`**；且 skill 没有 `@import` 之类的引入逃逸口。

### Skill 分类与命名

Skill 分两类，统一用 `zzz-od-` 项目前缀，开发类再加 `dev-`：

| 类别 | 前缀 | 用途 | 现有 skill（迁移时按此重命名） |
|---|---|---|---|
| **开发** | `zzz-od-dev-` | 指引 AI 在本项目开发/配置/构建 | agent-auto-battle-config、agent-definition、new-config |
| **使用** | `zzz-od-` | 指引使用本项目做游戏自动化 | zzz-one-dragon-player |

> `zzz-od-` 兼作**项目命名空间**——避免和插件/个人 skill 撞名，`/` 列表里本项目 skill 聚一起。命名示例：`zzz-od-dev-character`（新增角色）、`zzz-od-dev-build`（构建配置）、`zzz-od-player`（安装使用）。将来若出现第 3 类（如调试），加对应中缀（`zzz-od-debug-*`）即可。

### Skill 开发：三级晋升

跟整体"三级晋升"一致，新增 skill 从低到高放：

| 级别 | 位置 | 是否提交 | 说明 |
|---|---|:---:|---|
| **① 个人级** | `.claude/skills/<name>/`（`.claude/*` 已 gitignore，天然不提交）或 `~/.claude/skills/` | ❌ | 先在这里试做、验证有用再升级。 |
| **② 工具项目级** | `.claude/skills/<name>/`（**提交**：`.gitignore` 放行 `.claude/skills/`） | ✅ | 团队共享、Claude Code 特有。 |
| **③ 项目级（跨工具源）** | 根目录 `skills/<name>/`（**提交**） | ✅ | 多个"skills 感知"工具都要用时，作单一源。 |

**晋升路径**：① 个人试做 →（验证有用）→ ② 提交到 `.claude/skills/` →（多工具都要）→ ③ 根 `skills/` 作跨工具源。

> ⚠️ 根 `skills/` 不会被工具自动发现，只是③的单一源；要**符号链接**（symlink，目录级；非硬链接）进各工具目录（如 `.claude/skills/`）。Windows 符号链接需管理员或开发者模式。只有 Claude Code 一个消费者时，停在②即可，不必上③。

### 现状

仓库根 `skills/` 现有 4 个 skill（`agent-auto-battle-config`、`agent-definition`、`new-config`、`zzz-one-dragon-player`），放在根目录、**暂未被 Claude Code 自动加载**；是否迁移到 `.claude/skills/` 待定（价值还在评估）。

## 相关文档

- [AGENTS.md](../../../AGENTS.md) — 统一 AI 编码协作入口
- [spec/agent_guidelines.md](../spec/agent_guidelines.md) — 详细编码规范
- [开发指南](../README.md)
- [AI Coding Harness 工程](../harness/README.md)
