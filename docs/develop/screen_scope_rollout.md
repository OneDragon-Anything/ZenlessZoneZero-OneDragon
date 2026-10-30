# Screen Scope 分层迁移清单

本文档记录主工程 `assets/game_data/screen_info/` 的 screen local 化落地范围。

`app_id` 为空的 screen 保持全局，所有应用都能参与自动识别；`app_id` 非空的 screen 只在对应 `Application.app_id` scope 内参与自动识别。直接通过 `get_area`、`round_by_find_area`、`round_by_click_area` 指定 screen 名称的调用不受 scope 过滤影响。

## 保持全局

以下 screen 是基础导航、共享路由或跨应用复用入口，暂不 local 化：

| screen | 原因 |
| --- | --- |
| `打开游戏` | 启动流程基础 screen |
| `菜单` | 多应用打开入口和返回链路 |
| `菜单-更多功能` | 仍属于菜单功能集合，不绑定单个配置检查 app |
| `画面-通用` | 通用弹窗和确认区域 |
| `通用-出战` | 多个战斗/副本入口共用 |
| `大世界`, `大世界-普通`, `大世界-勘域` | 传送、返回、等待大世界等基础流程共用 |
| `地图` | 传送和地图操作共用 |
| `HDD` | 录像店副本入口，保留给后续更多 HDD 业务复用 |
| `战斗画面`, `战斗-菜单`, `战斗-挑战结果-失败` | 自动战斗和多个应用共享 |
| `快捷手册`, `快捷手册-日常`, `快捷手册-作战`, `快捷手册-目标`, `快捷手册-训练`, `快捷手册-战术` | `TransportByCompendium` 共享导航链路 |
| `区域巡防`, `实战模拟室`, `专业挑战室`, `恶名狩猎`, `恢复电量` | 体力计划、情报板、咖啡、周常等多业务复用 |
| `电玩店`, `拉面店`, `家政券` | 当前更像通用 operation 或尚无明确独立 app owner |

## 第一层：独立日常类

这层 screen 业务边界最清晰，只被对应 app 自动识别或操作。

| app_id | screen |
| --- | --- |
| `city_fund` | `丽都城募` |
| `email` | `邮件` |
| `intel_board` | `情报板` |
| `random_play` | `影像店营业` |
| `ridu_weekly` | `丽都周纪` |
| `scratch_card` | `报刊亭` |
| `trigrams_collection` | `卦象集录` |

## 第二层：路线链路/业务组

这层需要保持一组 screen 同时 local 化，避免路由过程中只识别到局部链路的一部分。

| app_id | screen |
| --- | --- |
| `world_patrol` | `3D地图`, `绳网` |
| `coffee` | `咖啡店` |
| `commission_assistant` | `委托助手`, `钓鱼` |
| `drive_disc_dismantle` | `仓库-音擎仓库`, `仓库-驱动仓库`, `仓库-驱动仓库-驱动盘拆解` |
| `life_on_line` | `真拿命验收` |
| `suibian_temple` | `随便观-入口`, `随便观-游历`, `随便观-邦巢`, `随便观-制造坊`, `随便观-德丰大押`, `随便观-售卖铺`, `随便观-饮茶仙` |

## 第三层：空洞/战斗域

这层 screen 数量多、链路深，需要整组迁移并重点回归入口识别、战斗后结算、事件交互。

| app_id | screen |
| --- | --- |
| `lost_void` | `迷失之地-入口`, `迷失之地-特遣调查`, `迷失之地-战线肃清`, `迷失之地-矩阵行动`, `迷失之地-大世界`, `迷失之地-武备选择`, `迷失之地-通用选择`, `迷失之地-邦布商店`, `迷失之地-抽奖机`, `迷失之地-路径迭换`, `迷失之地-挑战结果`, `迷失之地-战斗失败`, `迷失之地-藏品面板`, `迷失之地-调查战略选择` |
| `withered_domain` | `零号空洞-入口`, `零号空洞-事件`, `零号空洞-战斗`, `零号空洞-商店` |
| `shiyu_defense` | `式舆防卫战`, `新式舆防卫战` |

## 回归重点

- 加载默认 `_od_merged.yml` 与分文件加载 `from_separated_files=True` 时，`app_id` 数量应一致。
- `HDD` 与 `菜单-更多功能` 必须仍保持全局。
- 逐层验证 `enter_scope(app_id)` 后的活跃范围为 `全局 screen + 当前 app 局部 screen`。
- 优先 smoke test：`email`, `drive_disc_dismantle`, `lost_void`, `withered_domain`, `suibian_temple`, `shiyu_defense`。
