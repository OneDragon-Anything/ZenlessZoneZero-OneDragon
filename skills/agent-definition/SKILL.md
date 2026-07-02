---
name: agent-definition
description: 角色模板配置指南 - 在一条龙中新增可自动战斗角色所需的三部分配置
version: 1.0.0
author: OneDragon-Anything
tags: [zzz, agent, config, template, automation]
---

# 角色模板配置指南

在一条龙中新增一个可自动战斗的角色，需要完成以下三部分配置。

---

## 一、Agent 定义（agent.py）

文件位置：`src/zzz_od/game_data/agent.py`

### 基础字段

```python
AGENT_ID = Agent(
    'agent_id',           # 英文标识，全局唯一
    '中文名',              # 游戏中文化名
    RareTypeEnum.S,       # 稀有度：S / A
    AgentTypeEnum.ATTACK, # 职业：ATTACK / ANOMALY / DEFENSE / STUN / SUPPORT
    DmgTypeEnum.PHYSICAL, # 伤害类型：PHYSICAL / FIRE / ICE / ELECTRIC / ETHER / WIND
    ['agent_id'],         # template_id_list：角色头像模板 ID 列表（含皮肤变体）
)
```

### 特殊能量条状态（state_list）

```python
state_list=[AgentStateDef(
    '中文名-状态名',
    AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
    template_id='agent_id',
    hsv_color=(H, S, V),
    hsv_color_diff=(dH, dS, dV),
    max_length=120
)]
```

#### 常用检测方式枚举

| 常量 | 说明 |
|---|---|
| `FOREGROUND_COLOR_RANGE_LENGTH` | 彩色前景条，用 HSV 匹配 |
| `FOREGROUND_GRAY_RANGE_LENGTH` | 白色/灰色前景条，用灰度匹配 |
| `BACKGROUND_GRAY_RANGE_LENGTH` | 空心/背景条检测 |

---

## 二、头像模板（assets）

### 战斗头像

路径：`assets/template/battle/`

目录命名：`avatar_{布局}_{agent_id}`

| 目录 | 说明 |
|---|---|
| `avatar_1_{agent_id}/` | 单人/主位头像 |
| `avatar_2_{agent_id}/` | 副位头像 |
| `avatar_chain_{agent_id}/` | 连携技头像 |
| `avatar_quick_{agent_id}/` | 快速支援头像 |

每个目录包含：`mask.png`（遮罩）、`raw.png`（原图参考）

### 其他界面头像

| 路径 | 说明 |
|---|---|
| `assets/template/hollow/avatar_{agent_id}/` | 空洞界面头像 |
| `assets/template/predefined_team/avatar_{agent_id}/` | 预设队伍头像 |

---

## 三、能量条状态模板（agent_state）

路径：`assets/template/agent_state/`

### 目录命名

`{agent_id}_3_1/`（agent_id + 总人数 + 位置编号）

### config.yml 结构

```yaml
sub_dir: agent_state
template_id: {agent_id}_3_1
template_name: 角色状态-{中文名}-31
template_shape: rectangle
auto_mask: true
point_list:
- {x1}, {y1}
- {x2}, {y2}
```

---

## 四、校验清单

- [ ] agent.py 中的 `template_id` 与能量条模板目录的基础名一致
- [ ] 头像模板目录下的 `mask.png` + `raw.png` 齐全
- [ ] 能量条 `config.yml` 的 `point_list` 坐标对应正确的检测区域
- [ ] `hsv_color` 与 `hsv_color_diff` 能在实际画面中正确匹配能量条颜色
- [ ] `max_length` 与能量条满条时的像素长度一致
- [ ] `template_id_list` 包含所有可能出现的皮肤头像模板 ID