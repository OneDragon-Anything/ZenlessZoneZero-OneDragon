# 后台模式设计文档

## 概述

后台模式允许在游戏窗口不在前台时进行自动化操作。根据验证测试，确定了以下可行方案：

| 场景 | 输入方式 | 技术方案 | 验证结果 |
|------|---------|---------|---------|
| UI/菜单 (非锁鼠标) | 鼠标点击 | `WM_ACTIVATE` + `PostMessage` | ✅ 后台可用 |
| gamepad_key 场景 | 手柄按键替代 | `vgamepad` 手柄按键映射 | ✅ 后台可用 |
| 大世界/战斗 (锁视角) | 手柄按键 | `vgamepad` (ViGEm 虚拟手柄) | ✅ 后台可用 |
| 键盘输入 | — | 标准 API 均不可行 | ❌ |

## 技术原理

### 1. 后台鼠标点击 — WM_ACTIVATE + PostMessage

游戏在失去焦点后会忽略 `WM_LBUTTONDOWN`/`WM_LBUTTONUP` 消息。但通过先发送
`WM_ACTIVATE(WA_ACTIVE)` 欺骗游戏认为自己处于激活状态，后续的点击消息即可被处理。

**消息序列：**

```
1. SendMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)   -- 假装激活
2. sleep(10ms)
3. PostMessage(hwnd, WM_MOUSEMOVE, 0, MAKELPARAM(x, y))  -- 先移动
4. sleep(10ms)
5. PostMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(x, y))
6. sleep(20ms)
7. PostMessage(hwnd, WM_LBUTTONUP, 0, MAKELPARAM(x, y))
```

**适用范围：**
- ✅ 所有 UI 界面、菜单、对话框
- ✅ 非锁鼠标的交互
- ❌ 战斗中的视角控制

### 1.1 gamepad_key 场景 — 手柄按键替代

在大世界、战斗画面等锁鼠标场景，前台模式需要 ALT 键解锁光标才能点击 UI。
后台模式下 ALT 无法可靠传递（`keybd_event` 方案已验证失败），改用手柄按键替代：

**方案：** 为 `ScreenArea` 添加可选 `gamepad_key` 字段，存储 `GamepadActionEnum` 动作名。
当后台模式 `click()` 检测到 `gamepad_key` 不为空时，
通过 `gamepad_action_keys` 字典解析为实际按键列表，调用 `tap()` 或 `tap_combo()` 替代鼠标点击。

**数据模型：**
```python
class ScreenArea:
    gamepad_key: str | None = None  # GamepadActionEnum 动作名
    # 示例: 'menu'、'compendium'、'map'
```

**动作名解析：**
```python
# GamepadActionEnum 定义的动作:
# menu, map, minimap, compendium, function_menu
#
# 用户在设置界面配置每个动作对应的实际手柄按键 (list[str])：
# 'compendium' → ['xbox_lb', 'xbox_a']   (LB+A)
# 'menu'       → ['xbox_start']          (Start)
```

**调用链：**
```
find_and_click_area / round_by_click_area
  └─ click(pos, gamepad_key=area.gamepad_key)
       ├─ 后台 + gamepad_key → _gamepad_click(gamepad_key)
       │     ├─ gamepad_action_keys['menu'] → ['xbox_start']
       │     ├─ 单键 → btn_controller.tap()
       │     └─ 组合 → btn_controller.tap_combo()
       ├─ 后台 → _background_click(pos, press_time)
       └─ 前台 → pyautogui + ALT
```

**YAML 格式 (screen_info，可选字段)：**
```yaml
- area_name: 菜单
  gamepad_key: menu         # GamepadActionEnum 动作名
  pc_alt: true
  pc_rect: [...]

- area_name: 快捷手册
  gamepad_key: compendium   # 实际按键由配置决定
  pc_alt: true
  pc_rect: [...]
```

**涉及的 screen_info：**
- `battle.yml` — 战斗画面（结算界面 menu）
- `normal_world.yml` — 大世界（menu / map / compendium / minimap / function_menu）
- `normal_world_basic.yml` / `normal_world_investigation.yml` — 大世界变体
- `lost_void_normal_world.yml` / `lost_void_choose_common.yml` — 迷失之地

### 2. 后台手柄输入 — vgamepad (ViGEm)

ViGEm (Virtual Gamepad Emulation Bus) 在内核驱动层创建虚拟 Xbox 360 控制器。
游戏通过 XInput API 轮询手柄状态，该 API 直接从驱动读取，不依赖窗口焦点。

**工作原理：**
```
vgamepad (Python) → ViGEmBus 驱动 → 虚拟 Xbox 控制器 → XInput API → 游戏读取
```

**适用范围：**
- ✅ 战斗操作（普攻、闪避、切人、大招）
- ✅ 大世界移动
- ✅ 所有手柄支持的交互
- ❌ 需要精确像素点击的 UI 操作

**依赖：** `vgamepad` Python 包 + ViGEmBus 驱动

**组合键支持：**
`PcButtonController.tap_combo(keys)` 在基类实现，逐个 `press(key, None)` 按住 → sleep → 逐个 `release(key)`。

### 3. 键盘输入 — 无后台方案

| 方案 | 结果 | 原因 |
|------|------|------|
| PostMessage WM_KEYDOWN/UP | ❌ | 游戏不从消息队列读键盘 |
| SendMessage WM_KEYDOWN/UP | ❌ | 同上 |
| WM_CHAR | ❌ | 同上 |
| SetKeyboardState | ❌ | 仅影响线程局部状态 |
| keybd_event / SendInput | 前台✅ 后台❌ | 硬件合成只投递到前台窗口 |
| WM_ACTIVATE + keybd_event | ❌ | keybd_event 无视消息级激活 |

游戏键盘走 `GetAsyncKeyState` / `Raw Input`，读取硬件状态，无法通过标准 API 后台伪造。

## 配置架构

### 按键属性动态生成

`GameConfig` 通过 `_with_key_properties` 装饰器自动生成所有按键属性，避免手写数百行 property。

**两类默认值字典：**
```python
# 1. 战斗按键（存储为 str）
_KEY_DEFAULTS: dict[str, dict[str, str]] = {
    'key':      {'interact': 'f', 'dodge': 'shift', ...},      # 键盘 (15 个)
    'xbox_key': {'interact': 'xbox_a', 'dodge': 'xbox_a', ...}, # Xbox
    'ds4_key':  {'interact': 'ds4_cross', ...},                  # DS4
}

# 2. 后台模式动作键（存储为 list[str]）
_ACTION_KEY_DEFAULTS: dict[str, dict[str, list[str]]] = {
    'xbox_action': {'menu': ['xbox_start'], 'compendium': ['xbox_lb', 'xbox_a'], ...},
    'ds4_action':  {'menu': ['ds4_options'], 'compendium': ['ds4_l1', 'ds4_cross'], ...},
}
```

**装饰器逻辑：** 遍历两个字典 × 对应枚举，为每个组合创建 `property(getter, setter)`：
```python
# 生成 key_interact, key_dodge, ..., xbox_key_interact, ..., ds4_key_interact, ...
for prefix, defaults in _KEY_DEFAULTS.items():
    for action in GameKeyAction:          # 15 个动作
        setattr(cls, f'{prefix}_{action.value.value}', property(...))

# 生成 xbox_action_menu, xbox_action_compendium, ..., ds4_action_menu, ...
for prefix, defaults in _ACTION_KEY_DEFAULTS.items():
    for action in GamepadActionEnum:      # 5 个动作
        setattr(cls, f'{prefix}_{action.value.value}', property(...))
```

### 旧版配置迁移

`_LEGACY_GAMEPAD_KEYS` 映射旧数字索引格式（如 `xbox_0`→`xbox_a`、`ds4_6`→`ds4_l1`）。
`__init__` 中调用 `_migrate_legacy_gamepad_keys()` 一次性迁移 `xbox_key_*` / `ds4_key_*`。

### UI — GamepadActionKeyCard

`GamepadActionKeyCard` 继承 `MultiPushSettingCard`，包含两个 `ComboBox`（修饰键 + 按钮键），
以 `list[str]` 形式读写配置。用于设置界面中后台模式动作键的配置。

## 架构设计

### 双模式控制器

```
PcControllerBase
├── background_mode: bool        → 全局后台模式开关
├── click(gamepad_key=...)       → 分发到下列私有方法
│   ├── _gamepad_click()         → 后台 + gamepad_key 时手柄按键替代
│   ├── _background_click()      → 后台 SetCursorPos + PostMessage 点击
│   └── _foreground_click()      → 前台 pyautogui + ALT 点击
├── drag_to()                    → 分发到下列私有方法
│   ├── _background_drag()       → 后台 SetCursorPos + PostMessage 拖拽
│   └── _foreground_drag()       → 前台 pyautogui 拖拽
├── btn_controller               → keyboard_controller / xbox_controller
├── btn_tap / btn_press          → 按键前 _ensure_gamepad_mode()
├── btn_release                  → 释放前 _ensure_gamepad_mode()（防御性）
├── _send_activate()             → 发送 WM_ACTIVATE 激活消息
└── 模式切换
    ├── enable_background_mode()   → PostMessage 点击 + Xbox 手柄
    └── enable_foreground_mode()   → pyautogui 点击 + 键盘
```
### ZPcController.init_before_context_run — 配置刷新

每次 `start_running()` 时自动刷新所有快照配置，保证设置界面的修改在下次运行生效：
```python
def init_before_context_run(self) -> bool:
    # 根据配置启用后台/前台模式，内部调用 enable_*() 刷新 action_keys
    enable_background_mode() / enable_foreground_mode()
    # 刷新其他快照值
    self.turn_dx = game_config.turn_dx
    self.gamepad_turn_speed = game_config.gamepad_turn_speed
    self.mouse_flash_duration = game_config.mouse_flash_duration
```
### ZPcController — 按键映射与动作方法

**按键映射：** `ZPcController` 使用 `action_keys: dict[str, str]` 存储当前控制方式的
所有按键映射（如 `{'dodge': 'shift', 'interact': 'f', ...}`），由 `GameConfig.get_action_keys()`
根据控制方式返回。初始化时始终加载键盘键名，`enable_xbox()`/`enable_ds4()` 切换时同步更新。

**动作方法：** 15 个动作方法（`dodge()`、`normal_attack()` 等）均为一行委托：
```python
def dodge(self, press=False, press_time=None, release=False):
    self._action_btn(self.action_keys['dodge'], press, press_time, release)
```

**`_action_btn(key, press, press_time, release)`：** 通用按键动作分发——按下/释放/点按。

### 转向 — _gamepad_turn

`turn_by_distance()` 和 `turn_vertical_by_distance()` 统一委托给 `move_mouse_relative()`：
```
move_mouse_relative(dx, dy)
├── 后台 → _gamepad_turn(dx, dy)
│     ├── gamepad_turn_speed <= 0 时跳过（速度下限保护）
│     ├── _ensure_gamepad_mode()（自包含，不依赖调用方）
│     └── 右摇杆满偏转 duration = max_d / gamepad_turn_speed
└── 前台 → _ensure_mouse_mode() + mouse_event
```

### _ensure_mouse_mode — 闪切键鼠模式

后台模式下，前台转向需要短暂切换到键鼠模式，流程：
1. `SetForegroundWindow(hwnd)` 切到前台（失败时用 ALT 技巧重试）
2. `sleep(mouse_flash_duration)` — 可配置，默认 0.05s
3. `mouse_event(MOVE)` 触发 Raw Input 切换键鼠
4. `sleep(mouse_flash_duration)`
5. `SetForegroundWindow(prev_hwnd)` 切回原窗口

`mouse_flash_duration` 在设置界面可调整（后台模式风琴组内），过小可能导致切换失败。

### 场景切换策略

| 操作类型 | 后台模式 | 前台模式 |
|---------|---------|---------|
| 菜单点击 | WM_ACTIVATE + PostMessage | pyautogui |
| 锁鼠标场景 (pc_alt) | vgamepad 手柄按键 | pynput ALT + pyautogui |
| 战斗按键 | vgamepad Xbox 手柄 | keyboard (pynput) |
| 移动控制 | vgamepad 左摇杆 | keyboard WASD |
| 文本输入 | 不支持 | keyboard.type() |
| 截图 | 不受影响（已有后台截图） | 同 |

### API

**`PcControllerBase` 核心方法：**
- `background_mode: bool` — 全局后台模式标志
- `click(pos, press_time, pc_alt, gamepad_key)` — 统一入口，根据模式分发
- `drag_to(start, end, duration)` — 统一拖拽入口，根据模式分发
- `_foreground_click(pos, press_time, pc_alt)` — 前台 pyautogui 点击，可选 ALT 解锁光标
- `_foreground_drag(start, end, duration)` — 前台 pyautogui 拖拽
- `_gamepad_click(gamepad_key)` — 后台 + gamepad_key 手柄替代，通过 `gamepad_action_keys` 解析动作名为实际按键
- `_background_click(pos, press_time)` — 后台 SetCursorPos + PostMessage 点击
- `_background_drag(start, end, duration)` — 后台 SetCursorPos + PostMessage 拖拽
- `_send_activate()` — 发送 `WM_ACTIVATE(WA_ACTIVE)` 到游戏窗口
- `enable_background_mode()` — 开启后台模式（PostMessage + Xbox）
- `enable_foreground_mode()` — 开启前台模式（pyautogui + 键盘）

**`PcButtonController` 基类：**
- `tap(key)` — 单键按下释放
- `tap_combo(keys: list[str])` — 组合键：逐个 press → sleep → 逐个 release
- `press(key, press_time)` — 按下（press_time=None 不松开）
- `release(key)` — 释放

**`ScreenArea` 数据模型：**
- `gamepad_key: str | None` — `GamepadActionEnum` 动作名（如 `'menu'`、`'compendium'`），默认不写入 YAML

**`GameConfig` 核心方法：**
- `get_action_keys(control_method) -> dict[str, str]` — 返回 `{action_name: key_value}`
  - `control_method`: `'keyboard'` / `'xbox'` / `'ds4'`（默认读 `config.control_method`）
  - 前缀推导：`'key' if control_method == 'keyboard' else f'{control_method}_key'`
  - 例如 `get_action_keys('keyboard')` → `{'dodge': 'shift', 'interact': 'f', ...}`
- `get_gamepad_action_keys(gamepad_type) -> dict[str, list[str]]` — 返回 `{action_name: [key, ...]}`
  - `gamepad_type`: `'xbox'` / `'ds4'`（默认读 `config.background_gamepad_type`）
  - 例如 `get_gamepad_action_keys('xbox')` → `{'menu': ['xbox_start'], 'compendium': ['xbox_lb', 'xbox_a'], ...}`

## 前置条件

1. **ViGEmBus 驱动**：需要安装（安装器可集成）
2. **vgamepad Python 包**：`uv pip install vgamepad`
