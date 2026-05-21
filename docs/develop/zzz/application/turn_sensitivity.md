# 转向与灵敏度配置

本文说明 ZZZ 仓库中的转向相关配置、底层调用链，以及锄大地、录像店营业、迷失之地、式舆防卫战等模块分别依赖哪套转向逻辑。

## 1. 配置项

- `turn_dx`
  - 含义：前台键鼠模式下，“角度差 -> 鼠标水平位移”的换算系数。
  - 可近似理解为“每 1 度需要移动多少鼠标像素”。
  - 配置位置：当前实例的 `config/<实例号>/game.yml`。
- `gamepad_turn_speed`
  - 含义：后台手柄模式下，右摇杆满偏转时“每秒等效多少鼠标像素距离”。
  - 配置位置：当前实例的 `config/<实例号>/game.yml`。

默认值只在配置文件里缺少对应字段时生效。只要实例 `game.yml` 中已经写入了 `turn_dx` 或 `gamepad_turn_speed`，运行时就会优先使用配置值。

## 2. 底层调用链

### 2.1. 角度型转向

业务层调用：

```python
controller.turn_by_angle_diff(angle_diff)
```

控制器内部会换算为：

```python
turn_by_distance(turn_dx * angle_diff)
```

这条链路的特点：

- 前台键鼠模式下，直接依赖 `turn_dx`。
- 后台手柄模式下，最终仍会进入 `move_mouse_relative()`，再由 `_gamepad_turn()` 使用 `gamepad_turn_speed` 完成转向。

### 2.2. 像素型转向

业务层直接调用：

```python
controller.turn_by_distance(d)
```

或：

```python
controller.move_mouse_relative(dx, dy)
```

这条链路的特点：

- 前台键鼠模式下，不经过 `turn_dx`。
- 后台手柄模式下，最终仍依赖 `gamepad_turn_speed`。

### 2.3. 方向约定

- `turn_by_distance(d)`：`d > 0` 向右转，`d < 0` 向左转。
- `MiniMapWrapper.view_angle`：正右为 `0`，逆时针为正。

因此在当前 ZZZ 仓库实现里，`turn_dx` 的实测值通常会落在负数区间。不要直接搬用其他游戏仓库里的正值经验默认值。

## 3. 校准如何更新配置

当前仓库中，自动更新转向配置的现成入口只有“灵敏度校准”：

- 鼠标灵敏度校准
  - 固定执行多次向右转。
  - 读取小地图角度变化。
  - 反推出 `turn_dx`。
  - 写回当前实例 `game.yml`。
- 手柄灵敏度校准
  - 基于已有 `turn_dx`。
  - 推算 `gamepad_turn_speed`。
  - 写回当前实例 `game.yml`。

除手动编辑配置文件外，当前仓库没有第二个常规业务入口会自动改写 `turn_dx`。

## 4. 各业务模块的使用情况

先区分两种口径：

- 严格口径：只看前台键鼠模式下是否直接依赖 `turn_dx`
- 广义口径：只要最终会进入后台手柄转向链路，就视为依赖 `gamepad_turn_speed`

| 模块 | 主要转向方式 | 前台键鼠依赖 | 后台手柄依赖 | 说明 |
|------|------|------|------|------|
| 锄大地 `world_patrol_run_route` | 角度型 `turn_by_angle_diff` | `turn_dx` + 运行时 `AngleTurnCompensator.scale` | `gamepad_turn_speed` | `scale` 只在本次运行中生效，不写配置 |
| 录像店营业 `random_play_app` | 角度型 `turn_by_angle_diff` | `turn_dx` + 运行时 `AngleTurnCompensator.scale` | `gamepad_turn_speed` | 与锄大地共用补偿器实现，但会话独立 |
| 咖啡店 `coffee_app` | 角度型 `turn_by_angle_diff` | `turn_dx` + 运行时 `AngleTurnCompensator.scale` | `gamepad_turn_speed` | 传送落地大世界后先转正西，会话独立 |
| 迷失之地移动 `lost_void_move_by_det` | 像素型 `move_mouse_relative` | `estimated_turn_ratio` | `gamepad_turn_speed` | 主移动逻辑前台不走 `turn_dx` |
| 式舆防卫战 `shiyu_defense_battle` | 像素型 `turn_by_distance` | 固定像素 `±50` / `±200` | `gamepad_turn_speed` | 前台主要不走 `turn_dx` |
| 恶名狩猎靠近移动 `notorious_hunt_move` | 像素型 `turn_by_distance` | 固定像素 `±25/50/100` | `gamepad_turn_speed` | 前台不走 `turn_dx`，后台会吃手柄转速 |
| 空洞类靠近战斗 `hollow_battle` | 像素型 `turn_by_distance` | 固定像素 `±50` | `gamepad_turn_speed` | 前台不走 `turn_dx` |
| 自动战斗原子操作 `AtomicTurn` | 像素型 `turn_by_distance` | 模板内给定像素值 | `gamepad_turn_speed` | 只要模板用了该原子操作，就会走这条链路 |

## 5. 重点说明

### 5.1. 锄大地

锄大地不是“只看 `turn_dx`”。

它会先根据当前位置和目标点算出 `angle_diff`，然后通过 `operation/turning/turn_compensation.py` 里的 `AngleTurnCompensator` 引入运行时自适应比例，再交给控制器做角度转向。

因此锄大地的前台转向效果由两部分共同决定：

- 配置里的 `turn_dx`
- 当前路线运行过程中逐步微调的 `AngleTurnCompensator.scale`

`AngleTurnCompensator.scale` 使用反向观测增益更新：如果一轮命令角度实际转少了，后续会放大；如果实际转多了，后续会缩小。这个比例只在当前运行期内生效，不会写回 `game.yml`。

### 5.2. 录像店营业与咖啡店

录像店营业的“转向正东”和咖啡店落地大世界后的“转向正西”都是固定方向的角度型转向。

它也使用独立的 `AngleTurnCompensator` 会话；初始 `scale` 为 `1.0`，首次转向效果等价于直接调用 `turn_by_angle_diff(angle_diff)`，后续节点重试时会用新截图里的朝向观测微调。因此：

- 未运行过灵敏度校准时，最容易暴露 `turn_dx` 问题。
- 若连续多次日志都停在“转向正东”，优先排查 `turn_dx` 是否缺失、为零、方向反了或量级明显不对。
- 若一转就过头并在正反方向来回摆动，补偿器会把跨过 180 度后的最短角度按指令方向展开后学习，避免误判成反向转动。

### 5.3. 迷失之地

迷失之地主移动不是“按角度转”，而是“按检测框偏差直接转像素”。

它会根据目标在屏幕中的偏移量计算 `turn_distance_x`，再直接调用 `move_mouse_relative()`。因此在前台键鼠模式下，核心依赖是它自己的 `estimated_turn_ratio`，不是 `turn_dx`。

### 5.4. 式舆防卫战

式舆防卫战的大部分微调逻辑是固定像素盲转，例如 `±50` 或 `±200`。这类前台逻辑不经过 `turn_dx`。

### 5.5. 恶名狩猎与部分战斗逻辑

恶名狩猎靠近目标时，会根据目标在屏幕中的位置直接给固定像素的水平转向指令，例如 `±25`、`±50`、`±100`。这类逻辑在前台模式下不依赖 `turn_dx`。

类似地，`hollow_battle` 和自动战斗中的 `AtomicTurn` 也属于固定像素转向。它们是否“依赖转向配置”，取决于你看的口径：

- 前台键鼠口径：不直接依赖 `turn_dx`
- 后台手柄口径：会依赖 `gamepad_turn_speed`
