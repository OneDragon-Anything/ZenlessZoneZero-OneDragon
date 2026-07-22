# FixtureController:多帧流程测试

> 用固定截图跑 op 的完整 `execute()`(多帧、轮询、重试、恢复性 click),验 op 的**流程逻辑**。单节点测试(见 [README](README.md))只覆盖单帧单节点;流程测试补的是**节点图边 + 轮询/重试 + 恢复分支**。

## 是什么
`FixtureController`(`MockController` 子类,在 `zzz-od-test/test/harness/fixture_controller.py`)= 一个"会反应的假游戏":
- `screenshot()` 返当前 phase 的固定截图;
- `click/input/press_key` 记录动作 + 按剧本推进到下一 phase;
- 配真 ctx(真 OCR + screen_info),op 的识别/流转/决策在固定帧上跑。

## 何时用
验 op 的流程逻辑:节点间流转、轮询等待、登录异常/数据更新等分支恢复。例:EnterGame 自动登录流程(ready → 点进入游戏 → 登录服务器中 → ... → 大世界)。

## 剧本(phase)
有序 phase 列表,每 phase = 一帧 + 退出条件:
- **`on_click_in(region)`**:click 落在 region(查 screen_info 的 area `pc_rect`,或剧本给坐标 rect)才推进。**对有恢复性 click 的节点强制用这个**(避免恢复 click 误推进)。
- **`on_action`**:任何 click/input 推进。**只用于"该 phase 唯一流程 click、无恢复 click"**。
- **`on_polls(n)`**:screenshot() 调 n 次后自动推进(模拟游戏自动流转,如登录服务器中 → 大世界,无用户动作)。**最脆弱**(见坑 §看门狗),优先少用。
末 phase 默认粘住(多余 sense 一律返末帧,抗轮询次数漂移)。

## 关键坑(必读)

1. **运行态前置**:op 的 `execute()` 首轮查 `is_context_stop`(`_run_state==STOP` 默认)→ 直接退出。`is_context_stop` 是**只读属性**(无 setter)。测试 `execute()` 前直接置 `ctx.run_context._run_state = RUNNING`;**`finally` 复位**(`STOP` + `ctx.run_context.event_bus.unlisten_all_event(op)`——session `test_context` 复用,不复位会污染后续测试)。用 harness 的 `enter_running_state(ctx, op)` / `reset_running_state(ctx, op)`。

2. **看门狗(必须)**:op 框架的 round 上限**只管 RETRY,WAIT 无上限**——剧本对不齐会在 WAIT 段死循环。用 `WatchdogOperationMixin`(覆盖 `_execute_one_round`,**不是 `execute()`**),轮次上限 → 置 `_run_state=STOP`,loop 下轮退出。

3. **恢复性 click + on_click_in**:op 有些节点在 retry/recovery 时也 click(如 EnterGame `check_screen` 卡登录时点 `国服-返回按钮` 恢复)。这些 click **不能推进 phase**——该 phase 用 `on_click_in(期望的流程 area)`,只认流程 click,忽略恢复 click。

4. **OpenGame 排除**:`OpenGame`/`OpenAndEnterGame` 会写 Windows 注册表(HDR)+ `subprocess.Popen` 拉 exe,FixtureController 拦不住。**只测画面驱动的 op(如 EnterGame)**;`is_game_window_ready=True` 绕过框架注入的 check-window 链(否则会被路由到"打开并进入游戏"调 OpenGame)。

5. **剪贴板规避**:op 输账号密码可能走 `PcClipboard.copy_and_paste`(不走 controller,会写真实 OS 剪贴板)。测试 pin `ctx.game_config.type_input_way = INPUT`(走 `keyboard.type` 分支,FixtureController 能 mock)。fixture 用 `monkeypatch` 改 controller + type_input_way(避免污染 session `test_context`)。

## 参考实现
- `zzz-od-test/test/harness/fixture_controller.py`(FixtureController + WatchdogOperationMixin + 运行态 helper)。
- `zzz-od-test/test/zzz_od/operation/enter_game/test_enter_game_flow.py`(EnterGame 自动登录流程测试 + on_click_in 门控单测)。
