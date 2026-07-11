---
name: agent-definition
description: 角色模板配置指南 - 在一条龙中新增可自动战斗角色所需的 Agent 定义、头像模板、状态模板与自动战斗配置
version: 1.1.0
author: OneDragon-Anything
tags: [zzz, agent, character, auto-battle, development]
---

# 新增角色配置指南

新增一个可被自动战斗识别和使用的角色，通常包含四层：

1. `AgentEnum` 角色定义
2. 头像模板
3. 角色状态模板
4. 自动战斗 YAML

如果只是让程序“认识这个角色”，做到第 1、2 层即可；如果要写完整自动战斗模板，还要补第 3、4 层。

## 1. Agent 定义

文件：`src/zzz_od/game_data/agent.py`

### 1.1 基础枚举

当前可用职业：

```python
AgentTypeEnum.ATTACK   # 强攻
AgentTypeEnum.STUN     # 击破
AgentTypeEnum.SUPPORT  # 支援
AgentTypeEnum.DEFENSE  # 防护
AgentTypeEnum.ANOMALY  # 异常
AgentTypeEnum.RUPTURE  # 命破
```

当前可用属性：

```python
DmgTypeEnum.ELECTRIC
DmgTypeEnum.ETHER
DmgTypeEnum.PHYSICAL
DmgTypeEnum.FIRE
DmgTypeEnum.ICE
DmgTypeEnum.WIND
```

稀有度：

```python
RareTypeEnum.S
RareTypeEnum.A
```

### 1.2 在 `AgentEnum` 注册角色

```python
class AgentEnum(Enum):
    MY_AGENT = Agent(
        'my_agent',                  # agent_id，全局唯一，使用 snake_case
        '中文名',                     # 游戏内中文名
        RareTypeEnum.S,
        AgentTypeEnum.ATTACK,
        DmgTypeEnum.FIRE,
        ['my_agent'],                # template_id_list，头像模板 ID 列表
    )
```

如果角色有皮肤头像或不同 UI 头像，把所有模板 ID 放进 `template_id_list`：

```python
['my_agent', 'my_agent_skin_name']
```

`Agent.template_id` 运行时会根据皮肤配置切换；不要只在代码里写死一个新皮肤模板。

## 2. 头像模板

头像模板用于识别当前队伍、连携技、快速支援和部分界面。

### 2.1 战斗头像

路径：`assets/template/battle/`

常用目录：

| 目录 | 用途 |
|---|---|
| `avatar_1_<template_id>/` | 前台头像 |
| `avatar_2_<template_id>/` | 后台头像 |
| `avatar_chain_<template_id>/` | 连携技头像 |
| `avatar_quick_<template_id>/` | 快速支援头像 |

每个模板目录通常包含：

```text
mask.png
raw.png
```

以现有角色模板为准复制结构。模板 ID 要与 `Agent.template_id_list` 中的值一致。

### 2.2 其他界面头像

| 路径 | 用途 |
|---|---|
| `assets/template/hollow/avatar_<template_id>/` | 空洞界面头像 |
| `assets/template/predefined_team/avatar_<template_id>/` | 预设队伍头像 |

不是所有角色都必须立刻补齐所有界面头像；缺哪类模板，就会在哪类场景识别不到。

## 3. 角色状态定义

角色独有资源条、层数、特殊状态写在 `Agent.state_list`。

```python
MY_AGENT = Agent(
    'my_agent',
    '中文名',
    RareTypeEnum.S,
    AgentTypeEnum.ATTACK,
    DmgTypeEnum.FIRE,
    ['my_agent'],
    state_list=[
        AgentStateDef(
            '中文名-资源名',
            AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH,
            template_id='my_agent',
            hsv_color=(0, 255, 255),
            hsv_color_diff=(30, 80, 80),
            max_length=120,
        ),
    ],
)
```

### 3.1 `AgentStateDef` 常用参数

| 参数 | 说明 |
|---|---|
| `state_name` | 状态名，会进入自动战斗状态系统 |
| `check_way` | 检测方式 |
| `template_id` | 对应 `assets/template/agent_state/<template_id>/` |
| `lower_color` / `upper_color` | RGB 范围 |
| `hsv_color` / `hsv_color_diff` | HSV 中心值与容差 |
| `connect_cnt` | 连通块或像素数量阈值 |
| `split_color_range` | 条形资源中间有空隙时，用于切分 |
| `max_length` | 资源条满值对应长度或最大值 |
| `min_value_trigger_state` | 最小触发值；为 0 时可用于清除/记录 0 值 |
| `template_threshold` | 模板匹配阈值 |
| `clear_on_zero` | 检测值为 0 时是否清除状态 |

### 3.2 常用检测方式

| `AgentStateCheckWay` | 用途 |
|---|---|
| `COLOR_RANGE_CONNECT` | RGB/HSV 范围内找连通块数量 |
| `COLOR_RANGE_EXIST` | 指定颜色范围是否出现 |
| `FOREGROUND_COLOR_RANGE_LENGTH` | 彩色前景条长度 |
| `FOREGROUND_GRAY_RANGE_LENGTH` | 灰白前景条长度 |
| `BACKGROUND_GRAY_RANGE_LENGTH` | 通过背景灰度反推条长度 |
| `TEMPLATE_FOUND` | 模板存在 |
| `TEMPLATE_NOT_FOUND` | 模板不存在 |
| `COLOR_CHANNEL_MAX_RANGE_EXIST` | 某颜色通道最大值范围是否出现 |
| `COLOR_CHANNEL_EQUAL_RANGE_CONNECT` | 三通道相等像素连通块数量 |

## 4. 角色状态模板

路径：`assets/template/agent_state/`

目录名由 `AgentStateDef.template_id` 和识别位置共同决定：

- 未传入队伍位置时，直接使用 `template_id`。
- 角色独有状态会传入 `total` 和 `pos`，实际读取 `template_id_3_<pos>`；双人队伍的 2 号位读取 `template_id_2_2`。

因此一个角色独有状态通常需要准备这些目录：

```text
assets/template/agent_state/my_agent_3_1/
assets/template/agent_state/my_agent_3_2/
assets/template/agent_state/my_agent_3_3/
assets/template/agent_state/my_agent_2_2/   # 双人 2 号位需要时
```

每个目录内包含：

```yaml
sub_dir: agent_state
template_id: my_agent
template_name: 角色状态-中文名-资源名
template_shape: rectangle
auto_mask: true
point_list:
  - 100, 100
  - 220, 120
```

坐标基准是项目默认 1080p。不要为新增角色额外设计分辨率适配。

## 5. 自动战斗 YAML

如果要让角色可被通用自动战斗使用，继续补：

```text
config/
├── auto_battle_operation/       # 底层连招动作
├── auto_battle_state_handler/   # 中层状态决策
└── auto_battle/                 # 顶层战斗模板
```

常见接入点：

1. 新增角色操作模板：`config/auto_battle_operation/<角色名>-*.yml`
2. 新增角色状态模板：`config/auto_battle_state_handler/<角色名>.yml`
3. 注册到角色分派器：`config/auto_battle_state_handler/速切模板-全角色.yml`
4. 纳入轮换逻辑：`轮换-合轴-全角色.yml`、`轮换-紧急-全角色.yml`

自动战斗 YAML 语法见 `skills/agent-auto-battle-config/SKILL.md`。

## 6. 推荐顺序

1. 在 `AgentEnum` 新增角色定义。
2. 添加基础战斗头像模板，让战斗中能识别队伍成员。
3. 运行识别或进入战斗观察角色识别是否稳定。
4. 如有专属资源条，添加 `AgentStateDef` 和 `agent_state` 模板。
5. 用图像分析/模板工具调色值、区域和阈值。
6. 编写角色操作模板和状态模板。
7. 接入全角色分派器与轮换模板。
8. 运行自动战斗验证。

## 7. 常见问题定位

### 7.1 识别不到角色

检查：

- `Agent.template_id_list` 是否包含对应模板 ID。
- `assets/template/battle/avatar_*_<template_id>/` 是否存在。
- `mask.png` 是否遮掉了干扰背景。
- 连携技、快速支援是否分别补了 `avatar_chain_`、`avatar_quick_`。
- 皮肤头像是否使用了另一个 template id。

### 7.2 状态数值不准

检查：

- `template_id` 是否指向正确的 `agent_state` 模板目录。
- `point_list` 是否框住资源条有效区域。
- RGB/HSV 颜色空间是否混用。
- `max_length` 是否等于满条实际长度或最大值。
- `connect_cnt` 是否过高导致小图标识别不到。
- `min_value_trigger_state` 是否需要设为 0 来清除旧状态。

### 7.3 自动战斗不使用新角色逻辑

检查：

- 角色状态模板是否被 `速切模板-全角色.yml` 引用。
- 角色名状态是否与代码生成的 `切换角色-<agent_name>` 一致。
- 操作模板名是否与 `operation_template` 引用一致。
- `states` 条件是否过严，导致分支永远不命中。
- 高优先级 scene 是否抢占了角色分支。

## 8. 校验清单

- [ ] `src/zzz_od/game_data/agent.py` 的 `AgentEnum` 已新增角色。
- [ ] `agent_id` 使用 snake_case，且全局唯一。
- [ ] `AgentTypeEnum`、`DmgTypeEnum`、`RareTypeEnum` 选择正确。
- [ ] `template_id_list` 包含所有头像模板 ID，包括皮肤。
- [ ] 战斗头像模板至少覆盖实际会出现的队伍头像。
- [ ] 连携技/快速支援需要识别时，已补对应模板。
- [ ] 独有状态的 `state_name` 能被自动战斗 YAML 引用。
- [ ] `AgentStateDef.template_id` 与 `assets/template/agent_state/` 目录一致。
- [ ] 自动战斗 YAML 已接入全角色分派器和轮换模板。
- [ ] 修改代码后只对改动文件运行 `uv run --env-file .env ruff check <file>`。