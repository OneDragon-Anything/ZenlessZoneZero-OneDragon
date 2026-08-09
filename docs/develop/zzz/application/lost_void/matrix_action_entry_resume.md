# 迷失之地-矩阵行动入口续传确认

矩阵行动入口流程在点「下一步」后存在**中途加入（续传）**分支的处理说明。

## 背景

矩阵行动点「下一步」后有两种去向：

1. **常规流程**：直接进入 `迷失之地-矩阵行动-编队选择`，走 `matrix_*` 节点选主战/协战。
2. **中途加入（续传）**：游戏检测到进行中的挑战，弹出确认弹窗（画面 `迷失之地-矩阵行动` 的 `按钮-确认`）。点确认后**直接进入挚交会谈（大世界）**，跳过编队选择，走层间移动续传。

确认弹窗只在续传场景出现，属少数情况；常规流程占绝大多数。

## 实现位置

- 节点：`矩阵行动-前往入口`（`matrix_goto_entry`，`src/zzz_od/application/hollow_zero/lost_void/lost_void_app.py`）
- 画面：`迷失之地-矩阵行动`（`assets/game_data/screen_info/lost_void_entry_matrix_action.yml`，新增 `按钮-确认`，rect [963,573,1274,685]，text=确认）

## 逻辑

`matrix_goto_entry` 正常走 `round_by_goto_screen` 前往 `迷失之地-矩阵行动-编队选择`：

- `round_by_goto_screen` 返回 `Operation.STATUS_SCREEN_UNKNOWN`（未能识别当前画面，即点完「下一步」后等不到编队画面）时，**降级检测一次**确认按钮：
  - 找到 `按钮-确认` → 点确认：
    - 成功 → `next_region_type` 置 `LostVoidRegionType.FRIENDLY_TALK`，返回 `已进入挚交会谈`，经 `加载自动战斗配置` 直接进层间移动续传。
    - 失败 → 返回 `点击确认失败` 重试。
  - 没找到确认按钮 → 透传原 goto 结果，继续等编队画面。
- 其它 status（成功 / 其它重试状态）→ 直接透传，不额外处理。

要点：确认检测只挂在「等不到编队画面」的降级路径上，不影响常规流程（正常进编队选择时不会多一次确认查找）。

## 测试

`zzz-od-test/test/zzz_od/application/hollow_zero/lost_void/test_matrix_goto_entry.py`，纯逻辑 mock 测试，覆盖：

- `STATUS_SCREEN_UNKNOWN` + 确认存在 + 点击成功 → `已进入挚交会谈` + `FRIENDLY_TALK`
- `STATUS_SCREEN_UNKNOWN` + 确认存在 + 点击失败 → 重试
- `STATUS_SCREEN_UNKNOWN` + 无确认 → 透传
- goto 成功 → 透传且不查确认
- goto 其它重试 → 透传

画面识别部分依赖实时截图（确认弹窗截图未归档，见 `docs/game/screens/迷失之地.md` 的「确认弹窗子态」），属现场快照待补项。
