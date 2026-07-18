---
name: zzz-od-dev-skill-guide
description: 当要创建 skill、编辑/修改 skill、写 SKILL.md、或问 skill 该放哪、带哪些文件、内容怎么写时用。英文:create/author/edit a skill、write SKILL.md、skill structure。仅创建/修改 skill 时用;使用已有 skill 不触发。
---

# 创建/修改项目 skill

本项目开发类 skill 用 `zzz-od-dev-` 前缀(使用类 `zzz-od-`)、放根 `skills/`、junction 到 `.claude/skills/`。创建或改 skill 时,下面 4 条硬规范必须满足。

## 硬规范

### 1. 必须有 design.md
每个 skill 目录下要有 `design.md`,记这个 skill 的**设计与决策**:为什么做、定位与边界、每条关键决策的理由、落点选择。
- 目的:后续修改时(人或智能体)知道当初为什么这么定,避免盲目改动破坏原意。
- 写「为什么这么决策」,不只是「是什么」。

### 2. 内容给智能体看(指令式)
SKILL.md 是**智能体要执行的指令与判据**,不是给人读的说明文档。
- 祈使句 + 判据(「先 X 再 Y」「若 Z 则 W」),不要叙述文档腔。
- frontmatter 的 `description` 只写**何时用**(触发条件),不写「做什么/怎么做」 —— 否则智能体照 description 行事、不读正文。

### 3. 自包含:分场景(独立发布 vs 项目内)
- **可引用其它 skill**(写**完整标识符含命名空间**,如「按 superpowers:receiving-code-review 的方法」):用完整标识符,避免裸名解析不到。
- **引用 skill 目录外的文件,分场景**:
  - **独立发布 skill**(跨项目用):**禁止**外引(发布不含,目标环境可能不存在)。知识内联进 SKILL.md 或 skill 目录内辅助文件。
  - **项目内 dev skill**(放项目 `skills/`,跟项目走、不独立发布):可引用项目 **runtime 资产路径** —— 即 skill 要去读/写的**操作对象**(screen_info / application 源码 / docs/game 等),本项目必有、稳定。但**具体代码文件 / 实现行 / 易变文档**(如某 devtools 模块 L640、「详见某 README」)**抽象化**,不点具体位置。
  - 判据:**「要去读/写操作的资产路径」可引**(runtime,稳定);**「只为佐证某约定的具体代码/文档位置」抽象化**(耦合,易变)。

### 4. 写方法论,不写具体例子(限 SKILL.md 与智能体读的辅助文件)
写**方法、原则、判据**(怎么判断、怎么选),不要写「某个具体场景/项目的做法」。**具体游戏事实(键位/坐标/具体流程/机制)归 doc 不归 skill**;skill 只记方法论(分工见 doc_organization)。
- **适用范围**:SKILL.md 正文 + skill 目录内会被智能体读取的辅助文件(这些注入智能体执行上下文)。
- **design.md 不在此列**:它是给后续维护者的设计记录,可以有具体例子/踩坑作为决策论据。
- 理由:具体例子会以偏概全 —— 智能体把例子的偶然细节当成必然规则,套到不匹配的新场景。
- 抽象成判据:「在 X 条件下选 A,在 Y 条件下选 B」,而非「项目 P 里我们用了 A」。
- 不得不具体的,**仅限纯语法/字段名**(如 frontmatter 的 `name`+`description`、命令必填参数),给最小可用形式;「为什么选 A」「项目里遇过 X」这类划到 design.md。

## 落点(项目约定)
- 目录:根 `skills/<dev-name>/`(跨工具源,提交共享)。
- 前缀:开发类 `zzz-od-dev-`(项目开发流程类);使用类 `zzz-od-`。`zzz-od-` 兼项目命名空间,防和插件/个人 skill 撞名。
- Claude Code 发现:junction `.claude/skills/<dev-name>` → 根 `skills/<dev-name>`,形如 `cmd /c mklink /J .claude\skills\<dev-name> skills\<dev-name>`(Windows junction 免管理员;symlink 需特权)。junction 不提交(`.claude/` 已 gitignore),每人本地建。
- 结构:`SKILL.md`(入口)+ `design.md`(设计决策)+ 按需辅助文件(必须在 skill 目录内)。

## 创建/修改流程
1. **定位**:这个 skill 管什么、不管什么。和已有 skill(`superpowers:*`、本项目 `zzz-od-dev-*`)重叠的,**引用而非重复**。
2. **写 SKILL.md**:frontmatter(name + description,description 只写触发)+ 指令式正文(方法论)。
3. **写 design.md**:为什么做、定位边界、关键决策理由、落点。
4. **自检 4 条硬规范**(逐条对照)+ 通读正文确认每条指令可执行。
5. **junction 到 `.claude/skills/`**,验证 skill 可被触发(按工具要求重载/重启)。
6. 提交 `skills/<dev-name>/`(junction 不提交)。

## 与 superpowers:writing-skills 的关系
通用 skill 结构、frontmatter 字段、description 触发优化(SDO)、token 效率、cross-reference 写法 —— **参考 superpowers:writing-skills**(它讲得全,引用即可,本 skill 不重复)。
本 skill 只叠加**项目特定**部分:上面 4 条硬规范 + 落点。

### 两类 skill:RED 必要性不同,GREEN 始终必做
writing-skills 把 skill 创建当严格 TDD(必须先 baseline pressure-test 再写)。本项目按 skill 的**内容依据**分两类:
- **纠正型**:改变智能体默认会做错的行为,内容依据是"baseline 暴露的 failure" → RED(baseline)必做,再写最小纠正。
- **方法论覆盖型**:整合业界已验证的方法论成系统流程,内容依据是方法论本身 → RED 可省(团队工具/模型异构,单一 baseline 外部效度不足);但写完必须 GREEN 验证(跑 application 场景,确认用了 skill 的智能体决策/产出更系统)。

无论哪类,**GREEN 验证不可省**(writing-skills 的"写完要验证"对两类都成立);差异只在 RED 是否必须。
判断属于哪类:问"这条规范的依据,是'智能体默认会做错所以纠正',还是'业界方法论本来就该这么做'?"。前者纠正型,后者方法论型。`zzz-od-dev-deciding-a-fix` 是方法论型(锚定 RCA / Impact Analysis 等)。
