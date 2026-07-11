# 画面描述索引

按 `screen_name` 组织,每篇 ↔ 一个 `assets/game_data/screen_info/<name>.yml`。

| screen_name | 文件 | 简介 |
|---|---|---|
| 菜单 | [menu.md](menu.md) | 游戏主菜单 |
| 米哈游启动页 | [米哈游启动页.md](米哈游启动页.md) | 打开游戏首个画面(品牌/合规);screen_info 缺口 |
| 警告:游戏前详阅 | [警告_游戏前详阅.md](警告_游戏前详阅.md) | 登录前的光敏性癫痫警告页;screen_info 缺口 |
| 绝区零标题页 | [绝区零标题页.md](绝区零标题页.md) | 游戏 logo 展示页;screen_info 缺口 |
| 打开游戏 | [打开游戏.md](打开游戏.md) | 登录页(自动/手动登录多子态:验证码/账号密码/扫码/选区服);已建模 |
| 加载画面 | [加载画面.md](加载画面.md) | 通用加载画面(lore 轮换);screen_info 缺口 |
| 大世界 | [大世界.md](大世界.md) | Overworld 主画面(活动入口/任务/快捷键);已建模(is_precise) |
| 邮件 | [邮件.md](邮件.md) | 每日领取邮件附件(菜单→邮件);列表态 + 确认弹窗子态已建档 |
| 菜单-更多功能 | [菜单-更多功能.md](菜单-更多功能.md) | 菜单点「更多」;功能入口枢纽(预备编队/兑换码/登出);已建模 |
| 兑换码输入 | [兑换码输入.md](兑换码输入.md) | 兑换码输入框(菜单-更多功能→兑换码);screen_info 缺口;结果弹窗待补 |
| 仓库-驱动仓库 | [仓库-驱动仓库.md](仓库-驱动仓库.md) | 仓库音擎 TAB-驱动盘;驱动盘管理;已建模,识别模糊 |
| 仓库-驱动仓库-驱动盘拆解 | [驱动盘拆解.md](驱动盘拆解.md) | 驱动盘拆解(快速选择/拆解);默认态误匹配快捷手册;拆解确认待补 |
| 快捷手册-日常 | [快捷手册-日常.md](快捷手册-日常.md) | 手册日常 tab(今日活跃度奖励);已建模;领取弹窗待补(活跃度已满) |
| 丽都城募 | [丽都城募.md](丽都城募.md) | 大月卡(菜单→丽都城募);5 tab,成长任务/等级回馈领奖;已建模 |

## 非战斗 app 建档进度

**已建档(纯 UI,MCP 可复现)**:`email`(邮件)/ `redemption_code`(兑换码)/ `drive_disc_dismantle`(驱动盘拆解)/ `engagement_reward`(活跃奖励)/ `city_fund`(丽都城募)。

**⚠️ 跳过(MCP 无法完整复现 —— 涉及传送/角色移动/拖拽,`click_game`+`input_text` 不足以驱动)**:
- `scratch_card`(刮刮卡:Transport + move_w + interact + drag_to 刮)
- `hou_hou_bakery`(吼吼饼铺:Transport + interact)
- `random_play`(随机播放:Transport + move_w + interact + drag_to)
- `trigrams_collection`(八卦收集:Transport + interact + drag_to)
- `suibian_temple`(随便观:Transport + drag_to)
- `commission_assistant`(委托助手:interact)/ `life_on_line`(危局:Transport + interact)

**不建档(无游戏画面)**:`notify`(只发推送通知,汇总 run_record,不截图/不点 UI)。

> 跳过的 app 待 MCP 补足 `transport`/`move`/`drag`/键盘注入能力后,或用框架 `run_standalone_app` 跑通后沿途截图补。

(后续自由补充)
