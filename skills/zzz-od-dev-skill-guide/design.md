# zzz-od-dev-skill-guide 设计说明

## 为什么做
项目 skill 部署到不确定的智能体环境(不像 superpowers 自带 plugin、运行时文件环境确定),需要项目特定的自包含 / 落点 / 风格规范。superpowers:writing-skills 是通用且偏 TDD 流程,不含本项目约束,且其 cross-reference(引其它 skill + heavy reference 文件)倾向与本项目「不引 skill 目录外文件」相反。不固化则每次写 skill 易踩红线。

**为什么是 skill 而非 docs**:skill 触发时自动注入执行上下文(主动),docs 要记得翻(被动);写 skill 的规范本身也该在「要写 skill 时」被主动注入,故做成 skill。

## 4 条硬规范的决策理由
1. **design.md 必需**:防后续修改者不懂当初决策、盲目改动。决策记「为什么」才有指导意义。
2. **给智能体看(指令式)**:skill 正文注入智能体上下文执行,指令式有效、文档式无效。description 只写触发(不写流程),否则智能体照 description 走、不读正文(writing-skills 的 SDO 实测结论)。
3. **自包含(分场景:独立发布 vs 项目内)**:skill 独立发布时,被引 skill 使用者同时具备即可;docs/代码等文件发布不含、目标环境可能没有 → 禁。但**项目内 dev skill**(放项目 `skills/`,跟项目走、不独立发布)可引用项目 **runtime 资产路径**(skill 要读/写的操作对象:screen_info / application 源码 / docs/game,本项目必有、稳定);具体代码文件 / 实现行 / 易变文档(如 `devtools_xxx` L640、「详见某 README」)仍抽象化。判据:**操作资产路径可引(稳定),佐证性代码/文档位置抽象(易变)**。引用 skill 用完整标识符含命名空间。
4. **方法论非例子(限 SKILL.md 与智能体读的辅助文件)**:具体例子以偏概全 —— 智能体会把例子偶然细节当必然规则;抽象成判据才跨场景适用。范围限定 SKILL.md + 注入执行上下文的辅助文件;design.md 是维护者的设计记录,允许具体例子作论据。

## 落点决策
- 根 `skills/`(跨工具源)而非 `.claude/skills/`(工具特定):项目 skill 面向多个 skills 感知工具。
- `zzz-od-dev-` 前缀:项目开发流程类,与工具自带 skill 区分。
- junction 而非 symlink:Windows symlink 需特权,junction 免管理员;junction 不提交(`.claude/` gitignore),每人本地建。
- 引用 `superpowers:writing-skills`:本项目**默认 superpowers 常驻**(团队已统一采用),故引用安全;使用者同时具备即可。

## 与 writing-skills 的边界
- 引用它:通用 skill 写作(结构/frontmatter/SDO/token/cross-ref)。
- 本 skill 叠加:项目 4 条硬规范 + 落点。
- 两类 skill(取代早先"简化 pressure-test"的说法):纠正型(改变智能体默认错误)RED 必做;方法论覆盖型(整合业界方法论)RED 可省、GREEN 必做。两类都保留「正文必须可执行 + 写完验证」的自检。详见 SKILL.md「两类 skill」段。`zzz-od-dev-deciding-a-fix` 是方法论型范例(锚定业界 RCA / Impact Analysis / Trade-off Matrix 等,内容依据是方法论本身,故未据 baseline 写、但 GREEN 仍要验)。

## 自身一致性
本 skill 遵守自己的 4 条:有 design.md;SKILL.md 指令式;只引 superpowers:writing-skills(skill)、不引 docs 文件;正文是规范/判据/流程,无具体项目叙事例子。

## 当前状态
团队已统一采用 superpowers,本 skill 已 unignore 并提交(目录名 `zzz-od-dev-skill-guide`)。
