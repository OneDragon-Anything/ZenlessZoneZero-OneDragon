# zzz-od-dev-deciding-a-fix 设计说明

## 为什么做
已报告的 bug，"定位根因"有 `superpowers:systematic-debugging`，"决定怎么修"却缺一个系统决策框架。常见失败：直接采纳 issue 里用户给的方案、根因挖得不够深（误判方案临时/永久）、介入点前提没验证。本 skill 把"决定怎么修"锚定到业界方法论（RCA / Impact Analysis / Trade-off Matrix / Hypothesis-driven Verify），给一个可 review 的决策流程。

## 定位与边界
- 管：从"故障机制已知"到"选定并验证修复方案"的决策。
- 不管：定位故障机制（→ `superpowers:systematic-debugging`）；新功能设计（→ `superpowers:brainstorming`）。

## 关键决策

### 为什么是"方法论覆盖型"而非"纠正型"（不据 baseline 写最小 skill）
按 `zzz-od-dev-skill-guide` 的"两类 skill"区分（纠正型 / 方法论覆盖型，见其更新）。本 skill 内容依据是**业界已验证的方法论**，不是从 baseline failure 推导的最小纠正。理由：团队各人工具/模型异构，单一 baseline 外部效度不足；用业界方法论作依据更普适。**但 GREEN 后验证仍必做**（写完跑 application 场景，确认用了 skill 的决策更系统）。

baseline 仍跑了（pywin32 #2428 场景），价值沉淀在下面两个必填槽位的论证里，不进 SKILL.md 正文（正文只放方法论/判据）。

### 两个必填槽位的依据（来自 baseline 观察）
baseline（无 skill 处理匿名 #2428）暴露两个过程纪律缺口：
1. **前提验证槽**：baseline 否决"锁 pywin32 311"，理由"锁不住"——未验证的假设（实际显式声明 `pywin32<312` 即锁得住，下 wheel 验证 311 自带 `pythonwin/mfc140u.dll`）。→ SKILL.md 步骤 4 强制"前提验证"。
2. **上游修复状态槽**：baseline 没挖到"312 是 regression、上游已修待 build 313"，误判锁版本是"永久拖延"而非"有终点的临时止损"。→ SKILL.md 步骤 1 因果链含"修复状态"层、步骤 4 强制填"上游修复状态"。

### 五步顺序
因果链（步 1）必须前置：根因的"修复状态"决定方案"临时/永久"，是步 4 权衡的核心维度，不能在权衡之后才挖。影响面（步 2）紧随，因为它筛掉不可行动的介入点。前提验证并入步 4（针对具体候选方案），不单列早期步骤。

### actionable 层原则
因果链可深可浅；停在你**有权且有能力修**的那层——再深是过度（如给上游 pywin32 提 PR 修其 setup.py，对本项目不可行动；上游也已修）。

## 落点（项目约定）
- 根 `skills/zzz-od-dev-deciding-a-fix/`（源，提交共享）。
- junction `.claude/skills/zzz-od-dev-deciding-a-fix` → 根目录（`cmd /c mklink /J`，免管理员，不提交）。
- 结构：SKILL.md（入口，方法论/判据）+ design.md（本文件，含案例作论据）。

## 自身一致性
遵守 zzz-od-dev-skill-guide 4 条硬规范：有 design.md；SKILL.md 指令式；只引 superpowers skill（systematic-debugging / brainstorming），不引目录外文件；SKILL.md 只写方法论/判据，具体案例（pywin32 #2428）放本 design.md。

## 案例论据（pywin32 #2428，仅 design.md）
因果链：症状(闪退) → import win32ui ImportError → win32ui.pyd 找不到 mfc140u.dll → pywin32 312 wheel 不含 mfc140u.dll → 上游 setup.py 条件写反(PR #2755) → 已修(commit 3cc74e0)待 build 313。
- 介入点：锁 `pywin32<312`（包级，311 自带 mfc140u.dll）；备选"移除 win32ui import"（代码级，grep 验证全库仅 pc_game_window.py 用）。
- 前提验证：下 311/312 wheel 对比，确认 311 含 `pythonwin/mfc140u.dll`、312 不含。
- 上游修复状态：regression + 待 build 313 → 锁版本是"有终点的临时止损"。
- baseline 对照：无 skill 的 agent 否决"锁 311"（误以为锁不住）、未挖到上游已修（误判永久拖延）——正是两个必填槽位要防的。
