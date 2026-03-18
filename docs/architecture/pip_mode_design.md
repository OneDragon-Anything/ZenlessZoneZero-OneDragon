# 画中画（PiP）模式设计文档

## 概述

画中画模式允许用户在游戏切到后台时，通过一个始终置顶的小窗口实时预览游戏画面。点击画中画窗口可快速切回游戏，右键或关闭按钮可暂时隐藏画中画。

## 架构

```
┌──────────┐       ┌──────────────────┐       ┌──────────────────┐
│ PipButton│──────▶│ PipModeManager   │──────▶│ PipCaptureWorker │
│ (导航栏) │       │ (生命周期管理)    │       │ (截图线程)       │
└──────────┘       └────────┬─────────┘       └────────┬─────────┘
                            │                          │
                            │                          │ frame_ready
                            ▼                          ▼
                   ┌──────────────────┐       ┌──────────────────┐
                   │ PipConfig        │       │ PipWindow        │
                   │ (YAML 持久化)    │       │ (显示窗口)       │
                   └──────────────────┘       └──────────────────┘
```

## 组件职责

### PipButton

**文件**: `src/one_dragon_qt/widgets/pip_button.py`

导航栏上的开关按钮，封装画中画模式的开启/关闭逻辑。

- 点击切换画中画模式的开/关状态
- 持久化 `enabled` 状态到 `PipConfig`
- 应用启动时自动恢复上次的开启状态
- `dispose()` 时停止并释放 `PipModeManager`

> **注意**: `PipButton` 在 `app.py` 中通过**延迟导入**（local import）引入，避免 cv2 在 QApplication DPI 初始化之前加载导致 `SetProcessDpiAwarenessContext() failed` 警告。

### PipModeManager

**文件**: `src/one_dragon_qt/services/pip/pip_mode_manager.py`

核心协调器，管理截图控制器、工作线程和窗口的生命周期。

**轮询状态机**（`POLL_INTERVAL_MS = 200ms`）：

| 阶段 | 条件 | 行为 |
|------|------|------|
| 1 - 等待 Controller | `ctx.controller` 为 None | 空转等待 |
| 2 - 初始化截图 | Controller 就绪，窗口 ready | 创建 `PcScreenshotController` |
| 3 - 前后台切换 | 截图控制器已就绪 | 根据游戏窗口状态显示/隐藏画中画 |

**阶段 3 切换逻辑**：
- **游戏切前台** → 重置 `_dismissed` 标志，隐藏窗口，暂停截图
- **游戏切后台** → 若 `_dismissed` 则跳过；否则显示窗口，恢复截图

**`_dismissed` 标志**：用户右键关闭画中画后置为 `True`，游戏下次切到前台时自动重置为 `False`。这使得用户关闭画中画后不会反复弹出，直到游戏再次切前台。

**资源复用**：窗口和工作线程在整个会话期间复用（隐藏时 `hide()` + `pause()`），仅在 `stop()` 时通过 `_release_resources()` 销毁。

### PipCaptureWorker

**文件**: `src/one_dragon_qt/services/pip/pip_capture_worker.py`

基于 `QThread` 的截图工作线程。

- 以目标帧率（默认 30fps）循环调用 `capture_fn` 获取帧
- 通过 `frame_ready` 信号将 numpy 帧传递到主线程
- 使用 `threading.Event` 实现 `pause()` / `resume()` / `stop()` 控制
- `frame.copy()` 确保跨线程数据安全

### PipWindow

**文件**: `src/one_dragon_qt/widgets/pip_window.py`

纯显示组件：无边框、半透明、始终置顶的 `Tool` 窗口。

**视觉规格**：

| 属性 | 值 | 说明 |
|------|----|------|
| 边框宽度 | 1px | 灰色 `QColor(83,83,83,144)` |
| 圆角比例 | 3% | `min(width, height) * 0.03` |
| 关闭按钮 | 32×32px | 固定大小，右上角，margin=8 |
| 关闭图标 | 8px | 白色 X，画笔宽度 1.5 |
| 最小内容宽度 | 320px | |
| 最大内容宽度 | 1920px | |

**窗口尺寸公式**：

```
窗口宽度 = 内容宽度 + BORDER_WIDTH × 2
窗口高度 = int(内容宽度 × 宽高比) + BORDER_WIDTH × 2
```

Config 中 `width` 存储的是**内容宽度**（不含边框）。

**交互行为**：

| 操作 | 行为 |
|------|------|
| 左键单击 | 发出 `clicked` 信号（切回游戏） |
| 左键拖拽 | 移动窗口（超过 5px 阈值才触发） |
| 边缘拖拽 | 缩放窗口（保持宽高比） |
| 右键点击 | 隐藏窗口，发出 `closed` 信号 |
| 关闭按钮 | 同右键点击 |
| 滚轮 | 缩放（步长 40px，鼠标锚点） |

**关闭按钮三态显示**：
- **鼠标在窗口外** → 隐藏
- **鼠标在窗口内** → 白色 X + 浅色背景（alpha=20）
- **鼠标悬停在按钮上** → 白色 X + 深色背景（alpha=80）

### PipConfig

**文件**: `src/one_dragon/base/config/pip_config.py`

基于 `YamlConfig` 的持久化配置，保存到 `config/pip.yml`。

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | False | 画中画模式开关 |
| `width` | int | 480 | 内容宽度（不含边框） |
| `x` | int | -1 | 窗口 X 坐标（-1 表示自动定位到右下角） |
| `y` | int | -1 | 窗口 Y 坐标 |

## 数据流

```
截图控制器 ──get_screenshot(resize=False)──▶ PipCaptureWorker
                                               │
                                          frame.copy()
                                               │
                                        frame_ready 信号
                                               │
                                               ▼
                                          PipWindow.on_frame_ready()
                                               │
                                    numpy → QImage → QPixmap
                                               │
                                           paintEvent()
```

截图使用 `resize=False` 获取原始分辨率帧，由 `PipWindow.paintEvent` 中的 `drawPixmap` 缩放绘制到内容区域。

## 关键设计决策

1. **原始分辨率截图**：截图不做缩放（`resize=False`），让 Qt 的 `SmoothPixmapTransform` 在绘制时处理缩放，保证画质。

2. **窗口复用而非重建**：画中画窗口和工作线程在模式激活期间持续存在，通过 `hide()/show()` 和 `pause()/resume()` 切换可见性，避免频繁创建销毁的开销。

3. **`_dismissed` 语义**：用户主动关闭画中画后，不应在游戏仍处于后台时反复弹出。通过 `_dismissed` 标志实现"关闭后静默，前台后重置"的行为。

4. **鼠标锚点缩放**：滚轮缩放使用固定步长（40px），参照 `ZoomableImageLabel` 的锚点思路——计算鼠标在内容区的相对位置，缩放后调整窗口坐标使鼠标指向的屏幕位置不变。
