# AI 入口文件维护规范:AGENTS.md / CLAUDE.md

> `AGENTS.md`(仓库根,跨工具统一源)和 `.claude/CLAUDE.md`(Claude Code 入口)是 **always-on** 文件——每次会话完整进 context。本文档记录这两个文件的维护规范;分层判据见 [context_layering.md](context_layering.md),各工具机制见 [ai_tool_rules.md](ai_tool_rules.md)。

## 1. 纯指令,不掺杂元信息

入口文件**只放给 AI 的 always-on 指令（= 每次会话总要看的，见 §2）**。不写维护者注释、TODO、试验状态、变更说明——即使 HTML 注释也别用(strip 是隐式行为、格式稍错就漏,且文件该保持纯净)。

元信息去向:

- 维护规范、试验流程 → 本文档。
- 具体改动原因 → commit message。
- 历史决策 → git history / spec。

## 2. 只留每次会话总要看的

逐条「删了会出错吗」自检（不会错就砍，见 [context_layering.md](context_layering.md) §1）。**不是每次总要看的**按性质转走（context_layering §2 四档）：特定任务 / 多步流程 → skill / path-rule；确定性必做动作 → hook。单文件 < 200 行。

## 3. 一处维护（单一信息源）

- `AGENTS.md` 是**源**(跨工具通用)。
- `.claude/CLAUDE.md` 用 `@../AGENTS.md` 引入(非试验期),**不复制**;Claude 专属细则写在 `@import` 下方。
- 其他工具入口同理(依托 AGENTS.md,不复制)。
- **暂不采用 path-scoped rules**(特定任务规范放单文件,不拆 `.claude/rules/`)——原因见 §5。

## 4. 改动流程（小改直接 / 大改先试验）

- **小改**(加 / 改一条约束):直接改。`AGENTS.md` 改动影响所有工具,先确认。
- **大改 / 重组 `AGENTS.md`**:风险大,先在 `.claude/CLAUDE.md`(只影响 Claude)试验:
  1. CLAUDE.md 暂不 `@import`,自建精选正文(按判据)。
  2. 验证(Claude Code 跑试验版,观察表现是否下降)。
  3. OK → 试验结构晋升回 `AGENTS.md` → CLAUDE.md 回归 `@import`。
  4. 失败 → CLAUDE.md 回退 `@import`。
- **共享文档先确认**:两文件都是提交的团队共享文档,改动先经用户确认,不静默重写。

## 5. path-scoped rules:暂不采用

评估过把「特定任务规范」(如 GUI)拆成 **path-scoped rules**(`.claude/rules/*.md` + `paths` frontmatter,Claude 读匹配文件时自动加载,省 always-on context),以及「跨工具单源」(一份源文件 + 各工具 rules 目录 **hardlink** + frontmatter 写多家字段)。

**结论:暂不采用。**

- 当前分文件类型 加载的规范**需求不足**(就 GUI 一条、内容少),拆 path-scoped 收益 < 维护成本。
- 跨工具单源(硬链接)成本:git 不保留 hardlink(需脚本重建)+ 各工具 frontmatter 字段不同(Claude `paths` / Cursor·Trae `globs`)+ Qoder 不用文件 frontmatter + Codex/Pi/OpenCode 无 path-scoped——覆盖不全、运维重。
- 补充:rules 文件**不支持 `@import`**(只 CLAUDE.md 支持);rules 唯一引用机制是 hardlink/symlink,跨工具复用受限。

**现状**:特定任务规范(如 GUI)就放**单文件**(AGENTS.md 为源 / CLAUDE.md 正文),不拆 path-scoped。这些规范本质是**非 always-on**(只关系部分代码库),理想落 path-scoped rule(②档);本项目不用 path-scoped,故需在 always-on(AGENTS.md)**提及其存在并指向 docs**,让智能体按需得知。提及形式按内容量:极少 → 直接进正文;较多 → 指针(一行 + 链接)。

**重启条件**:将来分文件类型 规范变多(测试 / 文档 / MCP 等)且 always-on context 紧张时,再评估。

> 依据:[context_layering.md](context_layering.md) §2/§5(path-scoped 是②档,仅 Claude Code + IDE 派,不跨工具)、[ai_tool_rules.md](ai_tool_rules.md)(frontmatter 跨工具不兼容)。
