# Nightly 尝鲜版

本分支是绝区零一条龙的 Nightly 尝鲜版：**官方 main + 社区提交补丁队列，每月发一班车**。代码更新机制与官方版一致，通过配套切换插件一键使用。

## 交付物

- **本分支（nightly）**：基座每月更新一班车（发车前过全链回归），插件随时更新；不承诺稳定
- **[Nightly 尝鲜版切换插件](https://github.com/idk500/zzzod-plugin-nightly)**：一键把代码源切到本分支，随时可切回官方版
- **配套功能插件**（idk500 账号维护，均可在插件商店 / 各仓 Release 安装）：
  - [inventory_scan](https://github.com/idk500/zzzod-plugin-inventory-scan) 仓库扫描（代理人 / 驱动盘 / 音擎）
  - [disc_cleanup](https://github.com/idk500/zzzod-plugin-disc-cleanup) 驱动盘拆解
  - [battery_exchange](https://github.com/idk500/zzzod-plugin-battery-exchange) 储值电卡兑换
  - [bangboo_companion](https://github.com/idk500/zzzod-plugin-bangboo-companion) 邦布互动
  - [agent_train](https://github.com/idk500/zzzod-plugin-agent-train) 代理人培养
  - [mys_checkin](https://github.com/idk500/zzzod-plugin-mys-checkin) 米游社签到
  - [graphics_low](https://github.com/idk500/zzzod-plugin-graphics-low) 画质切换

## 使用

1. 主程序「资源管理 → 插件管理」导入切换插件 Release 的 zip，重启
2. 运行工具列表中的「Nightly 尝鲜版」，按提示再次重启，之后自动从本分支更新
3. 回官方版：「资源管理」切回官方源（GitHub / Gitee / CNB）+ `main`，同步一次即可

## 吸纳策略

- 官方 main 每月并一班车（发车前过全链回归）；期间基座级紧急问题出报告拍板，插件层能兜的走插件热修
- 社区 PR 与修复评估后收进补丁队列随车并入，不以"还不够完美"为由卡住
- 三类先评估再合：**破坏性变更**（删配置项、改数据结构、动插件接口，需迁移方案）、**涉及游戏安全与账号风险**（点击范围、请求频率、凭据处理）、**无法本地复现或验证**（挂起等作者补证据）

被拒的提交会在对应 PR 里说明原因。
