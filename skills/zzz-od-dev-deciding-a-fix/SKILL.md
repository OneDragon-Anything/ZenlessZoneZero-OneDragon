---
name: zzz-od-dev-deciding-a-fix
description: Use when a bug or issue is reported and the failure mechanism is known, and you must decide how to fix it—where to intervene, how deep to dig the root cause, temporary workaround vs permanent fix, or choosing among candidate fixes. 当 bug/issue 已报告且故障机制已知，需要决定怎么修（修哪里 / 根因挖多深 / 临时还是永久 / 多方案选哪个）时用。还没定位故障机制时先用 systematic-debugging。
---

# Deciding a Fix

## 核心原则
修复的难点不是"找到 bug"，而是"在因果链的哪一环介入"。**根因是一条链，不是点；选在哪一环介入 = 选方案。** 本 skill 把"决定怎么修"拆成 5 步，每步锚定一个业界方法论，产出一份可被 review 的修复决策。

## When to use / 不适用
- 用：bug 已定位失败机制，要在多个修法里选
- 不用：还没定位失败机制 → `systematic-debugging`；新功能设计 → `brainstorming`

## 流程

**0. 确认故障机制（入口）** — 能复述"失败怎么发生"？不能 → systematic-debugging 先定位。

**1. 画因果链** *(RCA / 5 Whys / Fault Tree)* — 症状→直接原因→机制→包级→系统级→上游代码→流程→修复状态。每节点 = 候选介入点。**挖到 actionable 层（你有权且能修的那层），不更深。**

**2. 影响面 + 可行动性** *(Impact Analysis / Blast Radius)* — 在链上标"我能修"的节点。影响面决定方案形态：全量用户 / 主依赖链 → 必须零用户操作；个别环境 → 文档可接受。

**3. 候选方案** — 在 actionable 节点生成：补系统依赖 / 锁版本或换实现 / 改代码移除问题调用 / 文档绕过 / 提上游 PR。

**4. 前提验证 + 权衡** *(Trade-off Matrix / Pugh)* — 每个候选必填：
- **前提验证**：前提是事实还是假设？最小成本证伪（下 artifact 看、跑解析、grep 全库）。
- **权衡**：[代价 / 风险 / 可逆性 / 临时-永久] 横评。
- **必填：根因链的"上游修复状态"**（已修？待发版？有意设计？）→ 决定方案是"有终点的临时止损"还是"永久拖延"。

**5. 假设驱动验证** *(Hypothesis-driven Verify)* — 精确化"失败的可观察判据"，确认介入后该判据不再成立。不是"能跑就行"——开发机有系统资源时成功可能是假绿，把判据收紧到具体路径 / 行为。

## Quick Reference
| 步 | 方法论 | 核心提问 |
|---|---|---|
| 0 | — | 能复述失败机制吗？ |
| 1 | RCA / 5 Whys | 链上有哪些介入点？哪个 actionable？ |
| 2 | Impact Analysis | 影响谁？谁有权修？ |
| 3 | Intervention Selection | 每个 actionable 节点对应什么方案？ |
| 4 | Trade-off Matrix | 前提验证了吗？上游修了吗？ |
| 5 | Hypothesis-driven Verify | 失败的判据是什么？还成立吗？ |

## Common Mistakes
- 直接采纳 issue 里用户的方案，不验证前提
- 根因停在"缺某文件"，不查"上游是否已修" → 误判方案临时 / 永久
- 验证停在"能跑"，不收紧到失败机制
- 介入点前提（如"只有这一处用"）不验证就下结论
