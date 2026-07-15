---
name: zzz-od-dev-gameplay-onboarding
description: 当一个已有 app / 玩法(代码已写、跨多画面)需要写玩法流程 doc 时用。
---

# 玩法建档(读 app 代码 → 串多画面 → gameplay doc)

拿到**已有功能**(app 代码已写、跨多画面)时,把流程编排 / config 分支 / 子玩法沉淀成 `docs/game/gameplay/<name>.md`(参考型 = 写当前现状)。单画面细节引用 screen doc,不重复。

## 定位与边界
- **管**:跨 ≥2 画面的**已有 app** 流程知识(参考 doc,写现状)。
- **不管**:单画面细节(zzz-od-dev-screen-onboarding 管);新玩法从 0 设计 spec(待实践补);运行时识别。
- 判据:**跨多画面才建 gameplay doc**;单画面用 screen doc。

## 信息源(理解玩法,三层)
1. **app 代码(主,权威)**:`@operation_node` 链 = 编排 / 状态流转;`config` 开关 = 分支;子 op 委托 = 子玩法。**编排以代码为准,别靠截图猜流程**。
2. **screen doc**:每画面 id_mark / area / 细节(已建档的引用,没建的标缺口,不编)。
3. **实拍**:入口路径 / 互斥态 / 条件态(代码不体现,要实拍确认;复用 zzz-od-dev-screen-onboarding 的 interact `>`名字`<` 判据)。

## 流程
1. **理骨架**:读 app `@operation_node` 链 + config,理清编排(节点 / 顺序 / 分支 / status 流转),画成表或链。
2. **定入口出口**:玩法从哪进(Transport / interact)、到哪出(回大世界)。
3. **拆子玩法**:每个子 op → 一段(入口 / 操作 / 出口),细节引用 screen doc。
4. **双向引用**:`gameplay.involves_screens`(出现顺序,用 `screen_name`)+ 各 `screen.appears_in`(`gameplay_name`)。
5. **缺口**:无 screen_info 画面 / 子玩法待实拍 → 标记(不编)。

## gameplay doc 结构
- frontmatter:`gameplay_name` / `involves_screens`(出现顺序)。
- **概述**:玩法是什么、重 or 轻 app。
- **入口**:大世界 → 进玩法(Transport + interact)。
- **app 编排 + config 开关分支**(核心):`@operation_node` 链 + config 开关决定走哪条路(表 / 链)。
- **子玩法**:每子 op 一段,引用 screen doc 细节。
- **备注**:互斥 / 前置 / 未实拍。

## 判据(防坑)
- **编排以代码为准**(`@operation_node`),别靠截图猜流程;截图只补入口 / 条件态。
- **config 开关分支必记**(决定哪些子玩法条件跑 —— 测试 config 守卫也靠它,守住下游 `@node_from` status 契约)。
- **不重复 screen doc**:gameplay 写跨画面流程,screen 写单画面,互相引用。
- 入口 / 互斥态实拍确认(代码不体现)。
- **参考 doc 只写当前现状**(= 代码实际);设计 / 预期另存 spec(参考 doc 写现状、spec 写设计预期,二者分清)。

## 收尾判据
- gameplay doc 与 app 代码一致(`@operation_node` 链对齐);双向引用齐(`involves_screens` ↔ `appears_in`);缺口标记。
