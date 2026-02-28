# 纯后台模式设计文档

## 概述

纯后台模式允许在游戏窗口不在前台时进行自动化操作。根据验证测试，确定了以下可行方案：

| 场景 | 输入方式 | 技术方案 | 验证结果 |
|------|---------|---------|---------|
| UI/菜单 (非锁鼠标) | 鼠标点击 | `WM_ACTIVATE` + `PostMessage` | ✅ 后台可用 |
| 锁鼠标场景 (pc_alt=true) | 手柄按键替代 | `vgamepad` 手柄按键映射 | ✅ 后台可用 |
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

### 1.1 锁鼠标场景 (pc_alt=true) — 手柄按键替代

在大世界、战斗画面、咖啡店等锁鼠标场景，前台模式需要 ALT 键解锁光标才能点击 UI。
后台模式下 ALT 无法可靠传递（`keybd_event` 方案已验证失败），改用手柄按键替代：

**方案：** 为 `ScreenArea` 添加可选 `gamepad_key` 字段（列表类型），存储手柄按键标识。
当后台模式 `gamepad_click()` 遇到 `pc_alt=True` 且 `gamepad_key` 不为空时，调用
`btn_controller.tap()` 或 `tap_combo()` 替代鼠标点击。

**数据模型：**
```python
class ScreenArea:
    gamepad_key: list[str] | None = None  # 后台模式下手柄按键替代
    # 单键: ['xbox_0']  (A)
    # 组合键: ['xbox_6', 'xbox_0']  (LB+A)
```

**调用链：**
```
find_and_click_area / round_by_click_area
  ├─ area.pc_alt? → gamepad_click(area.gamepad_key)
  │     ├─ 单键 ['xbox_0'] → btn_controller.tap()
  │     └─ 组合 ['xbox_6', 'xbox_0'] → btn_controller.tap_combo()
  └─ else → click(pos, pc_alt=...)
```

**YAML 格式 (可选字段，默认不写入)：**
```yaml
- area_name: 战斗结果-完成
  gamepad_key: [xbox_0]  # A 键
  pc_rect: [...]

- area_name: 连携技-左
  gamepad_key: [xbox_6, xbox_0]  # LB+A 组合键
  pc_rect: [...]
```

**涉及的 screen_info (pc_alt: true)：**
- `battle.yml` — 战斗画面（技能按钮、结算界面）
- `normal_world.yml` / `normal_world_basic.yml` / `normal_world_investigation.yml` — 大世界
- `coffee_shop.yml` — 咖啡店
- `lost_void_normal_world.yml` — 迷失之地大世界

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

## 架构设计

### 双模式控制器

```
PcControllerBase
├── background_mode: bool        → 全局后台模式开关
├── click()                      → 后台: background_click() / 前台: pyautogui
├── gamepad_click(gamepad_key)   → 后台 + pc_alt 时手柄按键替代 (高层调用)
├── btn_controller               → keyboard_controller / xbox_controller
├── send_activate()              → 发送 WM_ACTIVATE 激活消息
└── 模式切换
    ├── enable_background_mode()   → PostMessage 点击 + Xbox 手柄
    └── enable_foreground_mode()   → pyautogui 点击 + 键盘
```

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
- `click(pos, press_time, pc_alt)` — 后台 → `background_click()` / 前台 → `pyautogui`
- `gamepad_click(gamepad_key: list[str] | None)` — 后台 + pc_alt 手柄替代，高层调用
- `send_activate()` — 发送 `WM_ACTIVATE(WA_ACTIVE)` 到游戏窗口
- `background_click(pos, press_time)` — WM_ACTIVATE + PostMessage 点击
- `enable_background_mode()` — 开启后台模式（PostMessage + Xbox）
- `enable_foreground_mode()` — 开启前台模式（pyautogui + 键盘）

**`PcButtonController` 基类：**
- `tap(key)` — 单键按下释放
- `tap_combo(keys: list[str])` — 组合键：逐个 press → sleep → 逐个 release
- `press(key, press_time)` — 按下（press_time=None 不松开）
- `release(key)` — 释放

**`ScreenArea` 数据模型：**
- `gamepad_key: list[str] | None` — 后台模式手柄按键，默认不写入 YAML

## 前置条件

1. **ViGEmBus 驱动**：需要安装（安装器可集成）
2. **vgamepad Python 包**：`uv pip install vgamepad`
