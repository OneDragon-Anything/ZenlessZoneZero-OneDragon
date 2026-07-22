# AI 编码工具的 rules 机制对比

> 本文档回答一个具体问题:**当规范变多、想把指令(rules)拆成多个文件互相引用时,各 AI 编码工具支不支持?** 结论直接影响本 harness「AGENTS.md 单源 + `@import`」架构能扩展到什么程度。
>
> 调研日期:2026-06-30。覆盖:Cursor、OpenAI Codex CLI、OpenCode、Trae、Qoder、CodeBuddy、Pi,以 Claude Code 作对照。
>
> 本文讲各工具 **rules 文件机制**(怎么放、能不能拆、能不能互引)。各工具**分层能力**(always-on / 条件触发 / hooks / permissions)能否复刻 Claude Code,见 [context_layering.md](context_layering.md)。

## 一句话结论

**真正支持「指令文件之间互相 import/展开」的,只有 Claude Code(`@`)。** 其余 6 个都没有——它们的 `@`(若有)都是**对话侧运行时引用**(用户在 chat 里 `@文件` 注入上下文),不是指令文件的静态包含。

⇒ 对多工具而言,「拆 AGENTS.md 成多文件再 `@` 互引」**只对 Claude Code 生效**,别家会把 `@xxx` 当纯文本。跨工具拆分只能靠「精简 rules + 自然语言指路到 docs」(本仓库现有做法)或「目录自动加载 / 配置引入列表」等近似机制。

## 对比表

| 工具 | rules 约定 | 多文件怎么拆 | 文件间 import/include | 读 AGENTS.md |
|---|---|---|---|---|
| **Claude Code**(对照) | `.claude/CLAUDE.md` + `CLAUDE.local.md` | `@path` 引入 | ✅ **唯一有真 import** | ✅(via `@`) |
| **Cursor** | `.cursor/rules/*.mdc`(frontmatter: `description`/`globs`/`alwaysApply`) | 多个 `.mdc`,靠 always/glob/auto 触发模式自动组合 | ❌ 无(长期 feature request) | ✅ 原生(纯 md 作 `.mdc` 轻量替代) |
| **Codex CLI** | `AGENTS.md`(全局 `~/.codex/` + 项目) | 目录嵌套(每层最多 1 个)+ `project_doc_fallback_filenames` 清单 | ❌ 无,逐层**拼接** | ✅ 原生(它的标准) |
| **OpenCode** | `AGENTS.md`(全局 `~/.config/opencode/` + 项目) | `opencode.json` 的 `instructions`(**glob + 远程 URL**,最灵活) | ❌ 不解析 `@`;但 `instructions` 可 glob 引多文件(最接近) | ✅(回退 `CLAUDE.md`) |
| **Trae** | `.trae/rules/*.md`(frontmatter: `description`/`globs`/`alwaysApply`/`scene`) | 多文件,递归读(≤3 层) | ❌ 无 | ⚠️ 需**手动开关**(Include AGENTS.md) |
| **Qoder** | `.qoder/rules/*.md`(IDE 面板配 type) | 多文件,每文件 1 rule,4 种 type | ❌ 无(`@` 仅对话侧) | ✅ 原生(rules 优先于 AGENTS.md) |
| **CodeBuddy** | `.codebuddy/rules/*.md` + `CODEBUDDY.md`(纯 md) | 多文件,**全部自动加载**(同优先级) | ❌ 无(社区靠自然语言 delegate) | ⚠️ **互斥**:有 `CODEBUDDY.md` 就不读 AGENTS.md |
| **Pi** | 读 `AGENTS.md` / `CLAUDE.md` | 全局 + 父目录链 + 当前目录**全部拼接** | ❌ 无(纯文本拼接,不展开 `@`) | ✅(也读 `CLAUDE.md`) |

> CodeBuddy 的「条件加载」未完全确认(官方页面为 SPA,正文难抓);据现有文档,`.codebuddy/rules/*.md` 是全部自动加载、与 `CODEBUDDY.md` 同优先级,未见表 frontmatter 触发模式。

## 没有真 import 时,「拆」的三种近似机制

| 机制 | 代表工具 | 适合 | 不适合 |
|---|---|---|---|
| **frontmatter 触发模式**(always / glob / auto / manual) | Cursor、Trae、Qoder | 按场景 / 按文件类型分块,各自触发自动组合 | 「主文件引子文件」 |
| **目录嵌套 / 全量拼接**(每层一个,或目录下全 `.md` 自动加载) | Codex、Pi、CodeBuddy | 按目录组织 | 跨目录互相引用 |
| **配置式引入列表**(配置文件里列要包含的文件,glob/URL) | OpenCode(`instructions`) | 最接近「引用」,能跨目录 | 仍是「我列你要读哪些」,非文件内部 `@` |

## 三个坑(对本架构特别相关)

1. **`@` 在别家是运行时引用**:AGENTS.md 里写 `@docs/xxx.md`,Cursor/Trae/Qoder/Pi 当**纯文本**塞进上下文,**不会**去读那个文件。只有 Claude Code 展开。
2. **CodeBuddy 互斥**:有 `CODEBUDDY.md` 就**不**读 AGENTS.md。在 CodeBuddy 下别指望「根 AGENTS.md + 工具入口」自动生效。
3. **Trae 默认未必开**:AGENTS.md 注入是 Settings→Rules 里的开关。

## 对本 harness 架构的含义

「拆 rules 文件」≠「拆文档」:

- **rules**(被自动注入上下文,**贵**)→ 尽量精简,只放硬约束 + 流程 + 索引;
- **详细规范**(按需 Read,**便宜**)→ 放 `docs/develop/`,rules 里用自然语言指路。

而 **Read 文件是所有 agent 都有的能力,不依赖任何 import 语法**——所以「精简 AGENTS.md + 指路到 docs/」是**唯一不依赖工具特性**的跨工具结构,正是本仓库现状。

- **首选**:规范变多时,把详细内容外移到 `docs/develop/`,AGENTS.md 当索引 + 硬约束。
- **Claude Code 锦上添花**:用 `@` 把 Claude 专属细则引入 `.claude/CLAUDE.md`,享受拆分(Claude 独享)。
- **不建议**:指望「拆 AGENTS.md 成多文件再 `@` 互引」对多工具生效。

> 这也细化了 [README](README.md)「架构原则 1」里的 `@import`:**`@import` 只对 Claude Code 成立**;对多工具,「单一信息源」靠 AGENTS.md 本体 + docs 指路,而非 `@`。

## 来源

- [Cursor Rules 官方](https://cursor.com/docs/rules) · [论坛:能否在 rules 引用 docs/files](https://forum.cursor.com/t/can-we-reference-docs-files-in-the-rules/23300)
- [Codex CLI – AGENTS.md](https://developers.openai.com/codex/guides/agents-md) · [Codex config 参考](https://developers.openai.com/codex/config-reference)
- [OpenCode Rules](https://opencode.ai/docs/rules/)
- [Trae Rules 官方](https://docs.trae.ai/ide/rules)
- [Qoder Rules](https://docs.qoder.com/user-guide/rules) · [Qoder @Mention](https://docs.qoder.com/user-guide/chat/context)
- [CodeBuddy Rules](https://www.codebuddy.ai/docs/ide/Rules) · [腾讯云规则文档](https://www.tencentcloud.com/zh/document/product/1256/77282)
- [Pi (github.com/earendil-works/pi)](https://github.com/earendil-works/pi) · [pi.dev](https://pi.dev/)
- [AGENTS.md 开放标准](https://agents.md/)
