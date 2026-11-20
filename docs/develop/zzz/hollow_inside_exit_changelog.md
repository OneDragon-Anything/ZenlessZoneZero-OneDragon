# 空洞局内退出：本次改动说明

> 本文件用于在本地改动被覆盖、分支切换或合并冲突后快速还原上下文。
> 正式实现说明在 [enter_game.md](enter_game.md)，本文只记「改了什么、为什么、怎么验证」。

## 要解决的问题

在空洞类玩法（贝果计划、零号空洞）局内直接退出游戏，再启动一条龙时，角色会停在局内画面。
登录流程只把大世界当作成功终点，遇到这种画面按「未知画面」一直重试，
直到 `EnterGame` 的 `MAX_LOADING_SECONDS`（180 秒）超时，后面的应用根本不会被加载。

相关 issue：OneDragon-Anything/ZenlessZoneZero-OneDragon#3050

## 为什么不能只做插件

登录发生在应用加载之前：`Application.execute()` 会把 `op_to_enter_game` 插到第一个应用的起始节点前，
只有它成功后才轮到应用执行。所以「放在一条龙第一个的应用」也无法处理这种状态，
必须在登录流程里解决。

## 改动文件

| 文件 | 作用 |
| --- | --- |
| `src/zzz_od/game_data/hollow_zero_inside_screen.py` | 新增。局内 HUD 判据：右上角金黄圆环计时 + 右下角普攻按钮，两条同时命中才算 |
| `src/zzz_od/operation/exit_hollow_inside.py` | 新增。退出链路：Esc 开菜单 → 退出战斗 → 确认专用提示 → 结算点继续 → 仓库返回研究站 → 回大世界 |
| `src/zzz_od/operation/enter_game/enter_game.py` | 在 `画面识别` 和 `登录成功` 两处接入：识别到局内就执行退出并返回 `已在玩法局内` |
| `assets/game_data/screen_info/hollow_zero_inside.yml` | 新增。画面区域定义（1080p 基准） |
| `assets/game_data/screen_info/_od_merged.yml` | 追加新画面条目，纯新增不做删除 |
| `docs/develop/zzz/enter_game.md` | 补「登录后直接落在玩法局内」与「退出链路」两节 |

## 关键实现细节（踩过的坑）

### 1. 识别必须两条同时命中

只用右上角计时图标会误判：结算画面、大地图也有类似元素。
只用普攻按钮也会误判：被面板遮住时判断不稳。
两条同时命中才代表「角色正处在可操作的局内」。

实测：61 张局内帧命中 21 张（其余是搜查面板态，时钟被面板遮住，重启场景不会出现），
80 张大世界帧与 59 张登录帧零误报。

### 2. 新成功状态必须补显式边

`画面识别` 节点的所有出边都带具体 status，新增 `已在玩法局内` 后必须显式加一条
`@node_from(from_name='画面识别', status=STATUS_ALREADY_INSIDE)` 指向 `登录成功`，
否则会走兜底边跳到错误节点。

### 3. `until_not_find_all` 会导致重复点击（实机踩到）

`round_by_find_and_click_area` 带 `until_not_find_all` 时，每轮都会重新点一次。
实机表现为：点了「继续」画面还没切走，下一轮又点一次，游戏吃掉重复点击，
永远等不到按钮消失，60 秒超时。

**改法**：点一次就置 `continue_clicked`，之后只等画面变化；隔 3 秒还没变化才补点，
最多补 2 次，仍无效明确失败，不再无声卡死。`确认退出` 同样处理。

### 4. 分辨率不需要额外适配

框架已经把截图统一缩放到 1920×1080（`pc_screenshot_controller.py:76-77`），
点击时按 `win_rect` 等比反算回实际窗口（`pc_game_window.py:196-205`）。
所以屏幕区域坐标一律按 1080p 写，2K 下自动换算。

### 5. `_od_merged.yml` 不能用 `save_screen` 批量写

用 `ScreenContext.save_screen()` 会重写全部画面，丢失 4586 行（YAML 序列化格式差异）。
正确做法是只 append 新条目后整体写回，保证 diff 是纯增量（+131 行，0 删除）。

## 验证方式

```shell
# 语法与风格（只检查改动的文件）
uv run --env-file .env ruff check src/zzz_od/operation/exit_hollow_inside.py \
  src/zzz_od/game_data/hollow_zero_inside_screen.py \
  src/zzz_od/operation/enter_game/enter_game.py
```

用归档截图离线验证的结论：

- 节点图：`EnterGame` 11 节点、`ExitHollowInside` 6 节点，构建无拓扑错误，所有状态都有出边。
- 识别：局内帧全命中（排除搜查面板态），大世界/登录帧零误报。
- 正常登录路径：非局内帧不进入新分支，原有加载/弹窗/大世界判定逻辑一行未动；
  判据单次耗时约 0.03ms，可忽略。
- 点击：「继续」只点一次，时间推进后补点 2 次仍无效则明确失败。

## 已知边界

- 退出会丢弃安全箱外的物资。这是游戏对主动退出的既定规则，与玩法自己退出一致。
- 只做「离开这局」，不做入仓、出售、重开——那些属于各玩法自己的业务。
- 判据只覆盖「从局内重启」这一种场景；搜查面板等子态不额外兜底。
- 本机未克隆测试仓 `zzz-od-test`，完整 FixtureController 流程测试待补。
