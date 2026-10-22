# 代理人模板生成(AgentTemplateGenerator)

## 概述

开发工具中的「代理人模板生成」页面,用于给新代理人或新皮肤生成 6 个头像模板。每个模板对应游戏里的一个画面,按步骤分别截图,截图只属于当前步骤,6 张都完成后再保存。

| 步骤 | 截图画面 | 保存位置 |
| --- | --- | --- |
| 1 号位 | 自由训练,三人编队,目标角色在 1 号位 | `assets/template/battle/avatar_1_{id}` |
| 2 号位 | 自由训练,三人编队,目标角色在 2 号位 | `assets/template/battle/avatar_2_{id}` |
| 连携 | 自由训练中触发目标角色的连携技 | `assets/template/battle/avatar_chain_{id}` |
| 快速支援 | 自由训练中触发目标角色的快速支援 | `assets/template/battle/avatar_quick_{id}` |
| 零号空洞 | 零号空洞-枯萎之都(走格子)任意关卡,目标角色在编队 1 号位 | `assets/template/hollow/avatar_{id}` |
| 预备编队 | 菜单 > 更多 > 预备编队,目标角色在 1 号队伍 1 号位 | `assets/template/predefined_team/avatar_{id}` |

每个目录下是 `raw.png` 和 `mask.png`。裁剪区域和掩码形状来自 `assets/template/template/` 下对应的参考模板。

## 流程

1. **列表**:只显示当前提交(HEAD)中还没有的代理人,即本地新增、尚未提交的模板,按修改时间倒序。可以打开继续编辑,或删除它的 6 个模板目录。没有未提交的代理人时直接进入新建。
2. **编辑**:新建时填写代理人英文名(小写字母、数字、下划线);打开已有代理人时名称不可修改,已保存的模板会显示在步骤条中,只需重拍需要修改的步骤。
3. **截图**:截取游戏画面,或从文件选择 1080p 截图。游戏截图的整屏原图会保存到 `.debug/agent_template/{步骤}.png`。连携步骤可选择目标角色头像在左侧还是右侧。
4. **保存**:最后一步点击保存,只写入本次重新截图的步骤,保存后回到列表。

## 关键点

- **快捷键**:截图、下一步、上一步、回到主界面均可设置组合键,使用全局键盘监听,只在该页面或悬浮窗打开时生效。截图和下一步设为同一个键时,当前步骤还没有截图时截图,已有截图或已保存的模板时进入下一步。
- **悬浮窗**:置顶且不抢占游戏焦点,只能截图和推进步骤;最后一步的按钮改为回到主界面,保存只在主界面进行。
- **配置**:快捷键和悬浮窗位置保存在 `config/agent_template_generator.yml`。
- **生效**:模板生成后,需要在 `src/zzz_od/game_data/agent.py` 中把模板 id 加入对应代理人的 `template_id_list`,自动战斗才会使用。

## 相关

- 代码:`src/zzz_od/gui/view/devtools/agent_template_generator_interface.py` 及同目录 `agent_template_*.py`。
- 识别:连携头像同时匹配 `战斗画面` 的 `连携技-1` / `连携技-2` 两个区域,见 `src/zzz_od/auto_battle/auto_battle_context.py`。
