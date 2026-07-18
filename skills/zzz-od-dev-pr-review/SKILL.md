---
name: zzz-od-dev-pr-review
description: 当要审查/验证一个 open PR 是否可合并时用。英文 review/verify a PR、check if mergeable、validate PR functionality、PR code review。
---

# PR 审查验证

审查一个 PR 时,按 L0→L4 逐级验证,每级有则记无则跳,最终给"可合并 / 可合并但有建议 / 需返工 / 无法验证(写明缺什么)"结论。
**先做 L1/L2(总做、不依赖环境),再按 PR 类型决定是否 L3/L4。** 游戏流程类 PR,L4 live 是硬性要求(不是可选项)。

## 0. 准备:分支与基线(每个 PR 必做)

**原则:在"PR + 当前 main"的集成结果上审查,不在旧 base 上审。** PR 基于旧 main,旧 base 上审会漏集成问题(API 不兼容、被 main 改过的同文件、依赖 main 新加的文件等)。

- 用提交者分支(`gh pr checkout <n>`,拉的是 PR 当前 HEAD;不要用可能被本地 merge 污染的旧本地分支)。
- **先 `git merge origin/main`**:确保改动在当前代码上成立。老 PR 不 merge 可能缺文件 / 跑崩;merge 后才有"这个 PR 真能合、合了不崩"的判断基线。
- merge 冲突 → 见 §6(先解冲突再审,解的过程本身也暴露集成影响)。
- **审完再决定改不改**:看到 review comment(CodeRabbit / 人)不要先改代码——先在 merged 代码上审(理解改动 + 框架语义),再决定 comment 采纳(改)还是驳回(说明理由)。顺序:merge → 审 → 评 comment → 改。
- 每个 PR 开一个 notes,记:背景核实 / 改动合理性 / 每级验证结果 / 结论 / 给 reviewer 的要点。

## 1. L0 分诊

前端 / CI / 纯 git 启动逻辑 → 一般 skip(记原因)。业务逻辑 / 画面识别 / 操作流程 → 继续。

## 2. L1 静态审查(总是做)

读 diff + 相关代码。查:逻辑错误、回归、死循环、资源泄漏、是否复用现有模式(Application / Operation / config / setting card)、类型注解、1080p 硬编码合理性。

**框架语义必查项**(任一错就运行时崩,逐条对照源码确认):
- **生命周期钩子 `after_operation_done` / `op_callback`**:在 success 和 fail 都会触发(在结果判断之外)。**必查**:若 PR 在此做了自定义清理(如 stop_xxx),该清理有**几个子步骤**?任一步骤抛异常的概率?若有异常风险 → **基类调用必须在 `finally` 里**(try 包自定义清理,finally 包基类清理),否则 run_record/notify/`APPLICATION_STOP` 等基类清理被跳过。这是"代码看着对但异常路径漏"的高发点,不要只看 happy path。
- **节点重试预算**:`round_wait` 重置 `node_retry_times`(无界),只有 `round_retry` 消耗、超 `node_max_retry_times`(默认 3)才 FAIL。审"删除大 `node_max_retry_times`"的重构时,确认主路径走 `round_wait`(否则默认 3 不够)。
- **`@operation_node` 装饰器**:只挂元数据、原样返回 func → 可直接调用被装饰方法;节点调度读元数据。删/改节点不影响直接调用。
- **`execute()` 重复调用安全**:每次开头全重置(节点图 + 重试计数 + `handle_init`)。retry 包 `execute` 的模式安全。
- **节点路由 `node_from(status=...)`**:契约从"抛异常"改"返回 None/默认值"时,**逐个消费方确认 None-safe**(否则只是把崩溃换地方)。`ignore_status` + `status` 组合决定路由,有疑义查匹配源码。

## 3. L2 背景核实

PR 描述 / 关联 issue 提到的游戏行为 / bug 是否属实?对 `assets/game_data/screen_info/`(画面模型)、`docs/game/`(玩法)、相关代码路径交叉验证。issue 标题/日志往往透露真实复现路径(如"某 app 复用同一 operation"会扩大影响范围)。

## 4. L3 离线运行(不改游戏状态)

- 用测试仓留档截图喂 `analyze_screen`,验画面识别 / OCR 是否如改动静称。
- **自定义 OCR / 识别管线**(颜色 mask + ROI 切分等):写脚本用项目 ctx 在截图上复刻该管线再断言(比整图默认 OCR 强,能抓串扰)。
- PR 自带测试:直接 `pytest` 跑。

## 5. L4 live 运行(游戏流程类 PR 硬性要求)

**想办法在游戏里验证**,优先可逆、低消耗路径:
- 导航到目标画面(`click_game` / 通用 op 如 GotoMenu)→ `capture_game_screen` / `analyze_screen` 在**实时截图**上验识别/行为。
- 避开消耗周限/体力/日限的动作与"停止托管"等不可逆按钮;导航类(菜单/仓库/快捷手册)对后台托管无害。
- **server 跑当前检出分支的代码**:要验某 PR 流程 → checkout(先 merge main)→ 经 daemon 重启 server → server 即该分支逻辑 → `run_operation` / `run_standalone_app` 驱动 + `get_run_status` 观察。
- 大世界等需解锁光标的画面,`click_game` 传 `pc_alt=true`;子画面/菜单 `false`。
- **沿途画面若 screen_info 未建模 → 顺便建档**(补 area/screen_info;走 `zzz-od-dev-screen-onboarding`)。
- 真无法 live(纯消耗且无低消耗切入 / 需特定账号或地区 / 需外部凭据)→ 明确标"无法 live 验证"并写明缺什么,**不要假装验过**。

## 6. 冲突解决(merge origin/main 时)

- **看实际冲突再判断,别预设复杂**:很多"看似游戏流程"的冲突其实机械可解(注释 / import / 不同区域 additive)。
- 逻辑纠缠(同文件两侧都改核心)→ **先 live 建档该玩法**(搞清当前真实结构),再据此融合,不盲合。
- 解完必验证三连:`py_compile` + `ruff` + **`import` 冒烟**(import 比 compile 强,抓运行时导入/符号缺失)。

## 7. 结论与产出

每 PR 给明确结论 + reviewer 要点。性能 / 过程建议即便非阻塞也记(给 maintainer 决策)。
PR 收尾(处理 review comment、推到可合并)走 `zzz-od-dev-pr-finishing`;单条 review comment 处理走 `superpowers:receiving-code-review`。

## 通用原则

- **追源码确认,别照 description 行事**:框架语义(op_callback 触发时机、round_wait/retry 预算、路由匹配)以源码为准,PR description 可能省略。
- **删配置项/重构类**:grep 全量残留引用 + 确认迁移完备 + 测试仓同步检查。
- **巨型 PR**:抽查高风险模块(有测试的优先 L3 实跑),诚实标注未深审范围,建议拆分而非整体背书。
- **性能**:涉及热路径(战斗循环/OCR 推理)的改动,看锁粒度与阻塞——`Future.result()` 同步等、推理期持锁串行化,默认配置下影响所有用户时尤其要标。
