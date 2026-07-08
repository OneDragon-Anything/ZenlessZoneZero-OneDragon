# 快速开始（Quickstart）

> 面向第一次接触本项目的人（或 AI agent）：从零把项目在本机跑起来。
> 也可把本文档链接发给 AI agent，说「按 quickstart 帮我初始化项目」。
>
> 分三阶段，每阶段做完都会问「是否继续」——只想先把 GUI 跑起来，做完 **①** 即可。

## 前提

- **Windows**：项目仅支持 `win32`（见 `pyproject.toml` 的 `environments`）。
- **终端**：PowerShell（下文命令均为 PowerShell 语法）。
- **Git**：已安装。

## ① 跑起来（核心）

### 1. 获取代码

- **组织/项目成员**（有主仓 push 权）：直接 clone

  ```powershell
  git clone https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon.git
  cd ZenlessZoneZero-OneDragon
  ```

- **外部贡献者**（无 push 权）：先 Fork 再 clone 自己的 fork，提 PR 回主仓

  1. 在 [仓库页面](https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon) 右上角点 **Fork**，fork 到自己账号下。
  2. clone **你 fork 的仓库**（`<你的账号>` 换成 GitHub 用户名）：

     ```powershell
     git clone https://github.com/<你的账号>/ZenlessZoneZero-OneDragon.git
     cd ZenlessZoneZero-OneDragon
     ```
  3. （可选）配 upstream remote，方便后续同步主仓更新（clone 只会设 `origin`，upstream 需手动加）：

     ```powershell
     git remote add upstream https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon.git
     ```

> 其余相关仓库（测试仓 / yolo 训练仓 / 数据集 / 官网 blog）见 [相关仓库](repositories.md)。

### 2. 安装 uv

本项目用 [uv](https://github.com/astral-sh/uv) 管理依赖与 Python 版本。

```powershell
winget install --id=astral-sh.uv -e
# 或：irm https://astral.sh/uv/install.ps1 | iex
```

装完**重开终端**，`uv --version` 能输出版本即成功。

### 3. 初始化 Python 环境 + 装依赖

```powershell
uv sync --group dev
```

- uv 会按 `requires-python = ">=3.11.9,<3.12"` **自动准备 Python 3.11.x**，无需手动装 Python。
- `--group dev` 必须带：本项目 `default-groups = []`，不带只会装运行依赖、漏掉 dev 组（`ruff` / `pytest` / `mcp` / `uvicorn` 等）。
- 成功判据：生成 `.venv/`、命令无报错退出。

### 4. 让 `src/` 进入模块搜索路径（src-layout 前提）

项目是 `src-layout` + `package = false`，源码在 `src/` 下，但**不会自动进 `sys.path`**。二选一（一次设置，跑 app / 测试 / 构建都生效）：

- **IDE（推荐）**：把 `src/` 设为 `Sources Root`（PyCharm），或 VS Code 里设 `PYTHONPATH=src`。
- **命令行**：每个新 PowerShell 会话先 `$env:PYTHONPATH = "src"`（会话级）；或 `setx PYTHONPATH "src"`（永久，需重开终端）。

> 这是 **src-layout 的结构前提**，不是测试相关的 `.env`（那摊见 ②）。本阶段不需要任何 `.env` 文件。

### 5. 跑起来验证

```powershell
# 已在 IDE 设 Sources Root：
uv run src/zzz_od/gui/app.py
# 纯命令行（本会话临时设 PYTHONPATH）：
$env:PYTHONPATH = "src"; uv run src/zzz_od/gui/app.py
```

**主窗口（绝区零一条龙 GUI）弹出 = ① 完成。** app 本身不读任何环境变量。

> ① 完成即可开发、可跑 GUI。下面两阶段按需继续。

## ② 跑测试（可选）

测试代码在独立仓 `zzz-od-test`，clone 到**本项目根目录**下：

```powershell
# 组织/项目成员
git clone https://github.com/OneDragon-Anything/zzz-od-test.git zzz-od-test
# 外部贡献者：先在 GitHub fork，再 clone 你的 fork（<你的账号> 替换为 GitHub 用户名）
git clone https://github.com/<你的账号>/zzz-od-test.git zzz-od-test
```

IDE 里把 `zzz-od-test/` 设为 `Test Sources Root`；运行方式（含所需环境变量）见 [开发指南 §1.3](../README.md)。测试改动随主仓 PR 同分支名一起提（CI 按分支名匹配 clone 测试仓），详见 [相关仓库](repositories.md)。

## ③ 配 AI 工具（可选）

### MCP（项目自有，已实现）

项目把游戏感知 / 操作（窗口状态 / 截图 / OCR / 进游戏）经 MCP 暴露给 agent，辅助开发与调试。两步（需 ① 的 `uv sync --group dev` 已装好 `mcp`）：

```powershell
# 1) 起后端 server（:23001；项目根目录，另起一个常驻终端）
uv run python -m zzz_od.backend.entry.server
# 2) 注册到 Claude Code（再另开终端）
claude mcp add --transport http zzz_od http://127.0.0.1:23001/mcp
```

- **工具清单见 [zzz/backend/mcp.md](../zzz/backend/mcp.md)**（不在此列举，避免随实现演进过时）。
- **远程 SSH**（在别的机器 SSH 到游戏本机操作）场景下，游戏在 Session 1、SSH 在 Session 0，需用常驻 daemon 跨会话拉起 server —— 详见 [AI 编码助手接入 §MCP](ai_coding.md#mcp) 与 [zzz/backend/](../zzz/backend/)。

### LSP（代码导航，pyright）
项目用 uv 方式 pyright 做 LSP（定义 / 引用 / 符号）；Claude Code 的插件安装见 [claude-code/pyright-lsp.md](claude-code/pyright-lsp.md)。

### Skills

项目有开发类 skill（`zzz-od-dev-*`），Claude Code 经 `.claude/skills/` junction 自动加载；叠加在团队采用的 [superpowers](https://github.com/anthropics/superpowers) 开发流程方法论之上（brainstorming → 计划 → TDD → review → 合并）。建议一并安装：`/plugin install superpowers`。

- **现有 skill 见 [`skills/` 目录](../../../skills/)**（每个 SKILL.md 的 frontmatter 有触发描述）；分类与命名规范见 [AI 编码助手接入 §Skills](ai_coding.md#skills)。

### Plugin

后续补充。

## 下一步

- 架构与开发规范：[AGENTS.md](../../../AGENTS.md) · [agent_guidelines.md](../spec/agent_guidelines.md)
- AI 工具接入全貌：[ai_coding.md](ai_coding.md)
- 开发指南索引：[README.md](../README.md)
