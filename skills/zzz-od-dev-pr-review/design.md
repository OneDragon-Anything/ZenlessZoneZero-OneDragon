# design.md — zzz-od-dev-pr-review

## 为什么做这个 skill

项目痛点:PR 提交后**无人验证功能**(作者自测,review 多停留在代码层,功能没跑)。需要一个系统化的"审查 + 验证"方法论,让审查者不只看 diff,还核实背景、跑逻辑、验画面、给可合并结论。本 skill 沉淀这套方法论(从 30 个 open PR 的实操中提炼)。

## 定位与边界

- **管**:一个 PR 从"拿到分支"到"给可合并结论"的全流程(分诊 → 静态审查 → 背景核实 → 离线/ live 验证 → 冲突解决 → 结论)。
- **不管**:PR 收尾(处理 review comment / 推可合并 / checks)→ `zzz-od-dev-pr-finishing`;单条 review comment 处理 → `superpowers:receiving-code-review`;画面建模细节 → `zzz-od-dev-screen-onboarding`。
- 引用上述 skill 而非重复。

## 关键决策与理由

### 1. "先 merge main 再审"是原则,不是可选步骤
- **决策**:每个 PR 必须先 `git merge origin/main`,在集成结果上审。
- **理由**:PR 基于旧 main,在旧 base 上审 = 审一个不存在的世界——漏 API 不兼容、被 main 改过的同文件、依赖 main 新加文件等问题。只有集成后的代码才是"这个 PR 合了实际长什么样"。
- **踩坑论据**:老 PR(#2300 等)缺 main 后加的 `server.py`,不 merge 直接在分支跑 server → `No module named` 崩;merge 后才正常。曾因没先 merge 就改代码被用户纠正——顺序必须 merge → 审 → 改,不能跳。

### 2. L0~L4 验证分级
- **决策**:分诊(L0)→ 静态(L1)→ 背景(L2)→ 离线(L3)→ live(L4),逐级有则记无则跳。
- **理由**:不同 PR 需要不同深度(纯框架代码 L1 够;画面识别要 L3;游戏流程要 L4)。分级避免一刀切(全做 L4 太重,只做 L1 不够)。
- **L1 总做**:代码层问题(逻辑错/回归/泄漏)任何 PR 都要查。
- **L4 对游戏流程类 PR 是硬性要求**:功能没在游戏里跑过 = 没验。但优先可逆低消耗路径(导航,不消耗周限/体力)。

### 3. 框架语义必查项
- **决策**:L1 里固定查 5 项框架语义(after_operation_done/op_callback 触发时机、round_wait vs round_retry 重试预算、@operation_node 装饰器行为、execute 重置、node_from 路由)。
- **理由**:这些是"代码看起来对但运行时崩"的高发点——错了不是 style 问题,是真崩/死循环/泄漏。逐条对照源码确认,别照 PR description 行事。
- **踩坑论据**:
  - #2459 的 CodeRabbit comment 抓到了 `after_operation_done` 里 stop_auto_battle 抛异常会跳过基类清理 → 应 try/finally。我初轮 review 漏了这条(只做了 L1 表面审),说明框架语义要显式列出来查,不能靠"扫一眼"。
  - #2503 删大 `node_max_retry_times=300` 看似回归,查源码发现主路径走 round_wait(无界)→ 安全。
  - #2388 把"抛异常"改"返回 None",逐个消费方确认 None-safe(AppRunCard 本就 None-safe)→ 否则只是位移崩溃。

### 4. 冲突→建档→解
- **决策**:解 merge 冲突时,游戏流程类(同文件两侧改核心逻辑)要先 live 建档该玩法,理解当前真实结构再融合;框架/纯代码类直接解。
- **理由**:盲合游戏流程冲突会错配(不知道当前游戏画面/流程长什么样)。先建档(搞清现实)才能判断哪边对、怎么融。
- **踩坑论据**:#2300(charge_plan 三 PR 纠缠)——正是先 live 建档了 charge_plan 玩法(资源栏+道具处理),才正确融合了 #2300 的兑换以太电池与 main 的每日重置/双倍活动,没靠盲合。反例:曾预设"游戏流程冲突必复杂",实际看了发现很多是机械可解(注释/import/不同区域 additive)——别预设,看实际冲突。

### 5. live = 验证 + 熟悉游戏 + 顺路建档(三位一体)
- **决策**:live 进游戏不只是验 PR,沿途画面若未建档顺便补 screen_info。
- **理由**:live 过程天然接触真实画面,顺手建档成本最低、价值叠加。screen_info(.yml 机器模型)就是"建档"(本仓 docs/game/ 尚未建立人读约定)。

### 6. 解冲突后必做 import 冒烟
- **决策**:解完冲突除 py_compile + ruff,还要 `import` 冒烟(实际导入模块)。
- **理由**:py_compile 只查语法,import 抓运行时导入/符号缺失(合并后某侧删了符号另一侧还引用)。三连验证才稳。

### 7. 游戏流程 PR:L1 前先建玩法理解
- **决策**:L0 判定"继续"的游戏流程类 PR,L1 静态审查前先查 `docs/game/gameplay/` + `docs/game/screens/` 建立玩法初步理解(玩法是什么 / 目标 / 资源 / 循环 / 走哪些画面);无建档则先查玩法(网络攻略 / wiki / 实玩)。
- **理由**:直接读 diff 容易"见树不见林"——不懂玩法目标与画面流转,难判断改动合理性、识别流程缺失 / 画面未建模。先建玩法理解再看代码,审查更准更快;它也是 L2 背景核实的前置(L2 核实 PR 描述的 bug / 行为是否属实,需先懂玩法)。
- **踩坑论据**:#2300 review 时中途用户提醒"先了解玩法"才去查以太电池机制(60 电量 / 储值电卡合成);若 skill 有这条,开审就查,不必中途补。

## 落点

- 目录:根 `skills/zzz-od-dev-pr-review/`(跨工具源,提交共享)。
- 前缀:`zzz-od-dev-`(开发流程类)。
- junction:`.claude/skills/zzz-od-dev-pr-review` → 根 skills/(本地,不提交)。
- 结构:`SKILL.md`(方法论入口)+ `design.md`(本文件)。

## 与现有 skill 的关系

- `zzz-od-dev-pr-finishing`:PR 收尾(已开 PR 推可合并)。本 skill 是**收尾前的审查验证**;审完给结论,收尾走 pr-finishing。
- `zzz-od-dev-screen-onboarding`:画面建档。本 skill L4 live 时"顺路建档"引用它。
- `superpowers:writing-skills`:通用 skill 结构/frontmatter。本 skill 的项目特定部分(4 硬规范 + 落点)由 `zzz-od-dev-skill-guide` 管。
