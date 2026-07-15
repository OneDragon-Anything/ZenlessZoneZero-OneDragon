# design: zzz-od-dev-gameplay-onboarding

## 为什么做
跨多画面的重 app(如随便观:9 画面、7+ 子 op、config 开关编排)缺整体流程 doc —— 只有 screen doc(单画面)和 app 代码(实现),没有「串起来」的玩法视图。gameplay doc 串多画面,给智能体理解玩法编排 / 分支 / 入口出口。从随便观实战沉淀。

## 定位与边界
- **管**:已有 app(代码已写)的跨画面流程知识 → 参考 doc(写现状)。
- **不管**:单画面(zzz-od-dev-screen-onboarding);新玩法从 0 设计 spec(待实践补);运行时识别。

## 关键决策
1. **编排权威是代码(`@operation_node`)**:已有功能,代码是流程真相,doc 描述现状;截图只补入口 / 条件态(代码不体现的)。别靠截图反推流程(易错)。
2. **参考 vs spec**:已有功能 = 参考 doc(现状,`docs/game/gameplay/`);新玩法 = 设计 spec(预期,`superpowers/specs/`,待实践)。本 skill 只管前者(参考)。区分:参考 doc 写当前现状,spec 写设计预期。
3. **不重复 screen doc**:gameplay 写跨画面编排 / 分支 / 入口出口,screen 写单画面细节;互相引用(involves_screens / appears_in)。
4. **config 开关必记**:决定哪些子玩法条件跑(随便观 `auto_manage_enabled` / `yum_cha_sin` / `good_goods_purchase_enabled` / `boo_box_purchase_enabled`);测试 config 守卫也靠它(monkeypatch config 关分支 → 守住下游 `@node_from` status 匹配词契约)。

## 落点
- `skills/zzz-od-dev-gameplay-onboarding/`(`SKILL.md` + `design.md`),junction 到 `.claude/skills/`(同 zzz-od-dev-screen-onboarding,每人本地建)。
- 开发类前缀 `zzz-od-dev-`。

## skill 类型与验证(参考 zzz-od-dev-skill-guide 两类划分)
- **方法论覆盖型**:整合「读 app 代码 → 建流程 doc」的方法论,内容依据是方法论本身(非纠正某 baseline 错误)→ RED(baseline)可省。
- **GREEN 必做**:写完用 skill 跑一个 app 建 gameplay doc,确认产出系统(编排 / config 分支 / 子玩法 / 双向引用齐全)。随便观.md 即首个 GREEN 样本(本 skill 从其经验提炼,需后续再跑一个 app 复核)。
- 通用 skill 结构 / frontmatter / description 触发优化,参考 superpowers:writing-skills。

## 后续(实战完善)
- ⬜ **新玩法从 0 场景**(待实践):没代码时,从游戏实玩 / 实拍调研 → 设计 spec → 指导实现 → 实现后转参考。信息源 / 落点 / 流程待实战补。
- 编排表达:表格 vs mermaid 流程图(多几个 doc 后定)。
- 与 testing 方法论联动:gameplay doc 的 config 开关 / 节点,直接指导测试的 config 守卫 + 节点覆盖。
