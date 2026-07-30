# 上下文分层与维护判据

> 维护 `AGENTS.md` / `.claude/CLAUDE.md` 等 AI 指令文件的**方法论**:一条规范该放哪一层、怎么判、怎么维护。
> 依据:Anthropic 官方([context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Claude Code 最佳实践](https://www.anthropic.com/engineering/claude-code-best-practices)、[memory 机制](https://code.claude.com/docs/en/memory))+ 本仓库 [ai_tool_rules.md](ai_tool_rules.md) 的跨工具调研。

**一句话**:上下文是**有限且递减收益**的资源——塞得越满,模型越容易忽略你的指令(Anthropic 称 *context rot*)。所以「分层」不是整洁癖,是让 agent 真的做对事。

## 1. 核心判据:删了会出错吗

> "For each line, ask: **'Would removing this cause Claude to make mistakes?'** If not, cut it." —— Anthropic

**否决式自检**:默认砍,只有「删了会犯错」才留进 always-on。

| ✅ 该进 always-on | ❌ 该搬走 / 删 |
|---|---|
| Claude 猜不到的命令(uv / ruff 的特殊用法) | 读代码就能搞清楚的 |
| **与默认不同**的代码风格(`list[str]`、绝对导入、中文注释、禁 `**kwargs`) | 语言标准约定(Claude 本来就会) |
| 测试指令与首选 runner | 详细 API 文档(改成链接) |
| 仓库礼仪(分支/PR 约定、不主动 commit) | 频繁变动的信息 |
| 项目特有的架构决策 | 冗长解释 / 教程 |
| 环境怪癖(必需的 `.env`) | 逐文件描述代码库 |
| 常见 gotcha / 非显然行为 | 「写干净代码」这种废话 |

> 配套判据:"Keep it to facts Claude should hold in **every session**… If an entry is a **multi-step procedure or only matters for one part of the codebase**, move it to a **skill or path-scoped rule**."

## 2. 四档分层

按「往 context 注入什么、以什么可靠性」分四档,可靠性从上到下递增:

| 档 | 载体 | 何时加载 | 可靠性 | 放什么 |
|---|---|---|---|---|
| ① always-on | `CLAUDE.md` / `AGENTS.md` | 每次会话全量 | advisory(非强制) | §1 表里 ✅ 的:全局硬约束、命令、架构、gotcha |
| ② on-demand 机制触发 | **path-scoped rules**(`.claude/rules/*.md` + `paths` frontmatter) | Claude 读匹配文件时**自动**加载 | 机制级,不靠自觉 | 只关系某类文件的规范(测试规范、API 约定) |
| ③ on-demand 流程 | **skills**(`.claude/skills/`) | 模型判断相关时 / `/skill` 调用 | advisory | 多步可复用流程(发版、修 issue) |
| ④ 确定性强制 | **hooks**(生命周期跑脚本)+ **permissions**(allow/deny) | 生命周期事件,**不经模型** | 最高,保证发生 | 必须每次发生的(lint、commit trailer、禁改某目录) |

## 3. advisory vs hook vs permissions

三档按「漏了会怎样」区分——这是选档的实操判据:

| 想要的效果 | 漏了的代价 | 用 |
|---|---|---|
| 引导它尽量这么做 | 偶尔漏也能接受 | ①②③(advisory:CLAUDE.md / path-rule / skill) |
| 每次必须发生某动作 | 漏一次就出错 / 出事 | **hook**(确定性脚本) |
| 根本不许做某事 / 免确认 | 不能给它机会 | **permissions**(客户端硬拦 / 放行) |

> 官方原话:"Unlike CLAUDE.md instructions which are **advisory**, hooks are **deterministic** and guarantee the action happens." / "already does something correctly without the instruction → **delete it or convert it to a hook**."

## 4. 反模式与澄清

- **`@import` 不省 context**:"Splitting into `@path` imports helps organization but **does not reduce context**, since imported files load at launch." → `@` 只用于**组织 / 单一源**,减负靠**精简本体 + path-scoped rules**。
- **单文件 < 200 行**;超长 → "Bloated CLAUDE.md files cause Claude to **ignore your actual instructions**."
- **over-specified CLAUDE.md**:模型已做对的,删或转 hook;同一问题纠错 >2 次,`/clear` 重来。
- **CLAUDE.md 是 advisory**:以 user message 注入,非 system prompt,**不保证**严格遵守——要硬拦只能 hook。

## 5. 跨工具边界:四档在别家能否复刻

这套四档(尤其 ②③④)是 **Claude Code 的红利**。跨工具能复刻到哪?详见 [ai_tool_rules.md](ai_tool_rules.md);浓缩矩阵:

| 工具 | ① always-on | ② 条件触发 | ③ skill/流程 | ④a hooks | ④b permissions |
|---|:-:|:-:|:-:|:-:|:-:|
| **Claude Code**(标杆) | ✅ | ✅ `paths` glob | ✅ | ✅ | ✅ |
| **Cursor** | ✅ | ✅ `globs` | ✅(2.x) | ✅ 完整 | 🟡 仅命令级 |
| **Trae** | ✅ | ✅ `globs` | ✅ | ✅(**原生兼容 CC 配置**) | 🟡 靠 hooks |
| **Qoder** | ✅ | ✅ glob | ✅ | ✅ | 🟡 靠 hooks |
| **CodeBuddy**(Code) | ✅ | 🟡 | ✅ | ✅ | ✅ |
| **OpenCode** | ✅ | 🟡 全量 | ✅ | 🟡 写 plugin | 🟡 有 glob 名单无沙箱 |
| **Codex CLI** | ✅ | ❌ | 🟡 | 🟡 实验性 | 🟡 有沙箱无名单 |
| **Pi** | ✅ | ❌ 原生无 | ✅ | ✅ 编程式 | ❌ 无内置 |

**分档结论**:

- **① always-on 是全员公分母** ⇒ 跨工具基线只能建立在 AGENTS.md(精简)。
- **② 条件触发**只 IDE 派(Cursor / Trae / Qoder)+ CC 有;Codex / Pi 没有 ⇒ 不能当跨工具基线。
- **③ skill 正向 [Agent Skills 开放标准](https://agentskills.io)(`SKILL.md`)收敛**(Cursor / Trae / Pi / CodeBuddy 兼容)⇒ **skill 是最该跨工具复用的档**。
- **④ hooks / permissions 分化大**:Trae 最省事(原生读 `.claude/settings.json`);Codex 实验性;Pi / OpenCode 要写 extension / plugin 代码。

## 6. 维护纪律

**何时加进 CLAUDE.md / AGENTS.md**:Claude 同样错误犯第二次 / code review 抓到本该知道的 / 同一句纠正打了第二遍 / 新同事也需要。
**何时砍**:逐行「删了会出错吗」自检,不会错就砍;模型已做对的 → 删或转 hook。
**节奏**:把 CLAUDE.md 当代码——定期 review、prune,出问题时先查它。

## 来源

- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Best practices for Claude Code](https://www.anthropic.com/engineering/claude-code-best-practices)
- [How Claude remembers your project](https://code.claude.com/docs/en/memory)
- [Building Effective AI Agents](https://www.anthropic.com/research/building-effective-agents)
- [Agent Skills 开放标准](https://agentskills.io)
- 跨工具四档审计的一手来源见 [ai_tool_rules.md](ai_tool_rules.md)
