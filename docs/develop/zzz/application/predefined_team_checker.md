# 预备编队角色识别(PredefinedTeamChecker)

## 概述

`PredefinedTeamChecker` 是一个**校准工具**(**开发工具应用 / devtools app** —— 不参与玩法流程,只用于校准并回写配置,非自动化玩法),识别游戏内预备编队的**实际角色**并写回 `team_config`。用途:玩家在游戏里改了预备编队后,跑此 app 核对 / 同步配置(切队前校准),避免 `team_config` 与游戏实际不一致导致后续选队错位。

⚠️ 它进入的是预备编队的**编辑 / 管理画面**(菜单-更多功能 → 预备编队),只能查看 / 编辑,**不能选队出战** —— 与战斗前的「选择(准备出战)」子态不同(后者有 `SELECT` / `预备出战`)。详见 [预备编队](../../../game/screens/预备编队.md)。

## 流程

1. **前往菜单**(GotoMenu)→ **菜单-更多功能** → 点「按钮-预备编队」→ 进入预备编队管理画面(编辑子态)。
2. **识别编队角色**(`update_team_members`):
   - OCR 全图队名 → 用 `difflib` 模糊匹配 `team_config` 的队伍名(找对应配置队)。
   - 在匹配队名左侧 -10 起、宽 800 高 250 的区域(`avatar_rect = Rect(x-10, y, x+800, y+250)`),`match_team_agent_template` 模板匹配代理人头像 → 按横坐标排序 + 重叠过滤(issue #1487,同位置多识别取高置信)。
   - `team_config.update_team_members(队名, [代理人])` 写回配置(按队名匹配,非 idx)。
3. **翻页**:中屏 drag 上滑(`-500px`),最多翻 4 次,每页重复识别。
4. **返回**:`BackToNormalWorld` 回大世界。

## 关键点

- **画面**:编辑 / 管理子态(无 `SELECT` / `预备出战`);主体布局同选择子态(2×3 卡片 + 1P/2P/3P + 核心技 X/3)。详见 [预备编队画面](../../../game/screens/预备编队.md)。
- **识别依据**:OCR 队名(模糊匹配 config)+ **代理人头像模板**(不是 1P/2P/3P 文字标记)。
- **写回**:`update_team_members`(按队名匹配),保留该队已有的自动战斗配置。

## 相关

- 画面:[预备编队](../../../game/screens/预备编队.md)(通用画面,选择 / 编辑两子态)。
- 代码:`src/zzz_od/application/game_config_checker/predefined_team_checker/`。
- 同类:`game_config_checker` 下其他 checker(均为校准工具,非玩法)。
