# WindowAnchorTracker 设计说明

## 1. 背景
在后台窗口追踪模式下，目标不是移动鼠标到目标点，而是移动游戏窗口，让“窗口客户区锚点”对齐到当前鼠标位置，再发送后台消息点击/拖拽。

该模式的核心挑战：
- 窗口移动与输入发送存在时序差。
- 锚点切换后立即点击，可能命中旧位置。
- 最小化、非前台、透明穿透等状态切换容易导致窗口状态不一致。

## 2. 设计目标
- 保持输入命中稳定：点击/拖拽前确保锚点已对齐。
- 降低主控制器复杂度：追踪线程和伪最小化状态收敛集中在单模块。
- 维持后台体验：窗口尽量不抢焦点，支持透明+穿透的伪最小化策略。

## 3. 模块职责
实现位置：[src/one_dragon/base/controller/window_anchor_tracker.py](src/one_dragon/base/controller/window_anchor_tracker.py)

### 对外接口
- `start()`：启动追踪线程，并进入伪最小化状态。
- `stop()`：停止追踪线程，恢复窗口为可见可交互状态，并居中。
- `ensure_ready()`：确保追踪线程可用。
- `set_anchor(anchor)`：设置客户区锚点。
- `reset_anchor()`：锚点恢复窗口中心。
- `apply_pseudo_minimize(hwnd)` / `revert_pseudo_minimize(hwnd)`：伪最小化状态切换。
- `running`：追踪器运行状态。
- `settle_time`：锚点切换后等待收敛时间。

### 内部职责
- `_loop()`：16ms 周期执行，将锚点对齐到鼠标位置。
- `_move_window_client_to_cursor()`：计算窗口边框偏移并移动窗口。
- 最小化时自动 `ShowWindow(..., SW_SHOWNOACTIVATE)`，避免客户区变成 0x0。

## 4. 关键流程
调用位置：[src/one_dragon/base/controller/pc_controller_base.py](src/one_dragon/base/controller/pc_controller_base.py)

### 点击流程（窗口追踪模式）
1. `ensure_mouse_mode()` 切到键鼠输入识别。
2. `ensure_ready()` 确保追踪线程可用。
3. 根据目标点计算客户区坐标 `(cx, cy)`。
4. `set_anchor((cx, cy))` 切换锚点。
5. 等待 `settle_time`。
6. 发送 `WM_LBUTTONDOWN/UP`（携带对应 `lParam`）。
7. 抬起后再等待一个稳定窗口（当前实现为 `settle_time`）。
8. `reset_anchor()` 恢复默认中心锚点。

### 拖拽流程（窗口追踪模式）
1. 起点锚点对齐并等待 `settle_time`。
2. 发送 `WM_LBUTTONDOWN`。
3. 分步更新锚点并发送 `WM_MOUSEMOVE`。
4. 发送 `WM_LBUTTONUP`。
5. 结束后 `reset_anchor()`。

## 5. settle_time 的作用
`settle_time` 是“锚点切换后的收敛等待时间”，默认值在 [src/one_dragon/base/controller/window_anchor_tracker.py](src/one_dragon/base/controller/window_anchor_tracker.py#L30) 定义为 `0.06` 秒。

它的目的不是延迟输入本身，而是给追踪线程一个窗口对齐周期：
- 追踪线程以约 `0.016s` 一次循环（约 60Hz）运行。
- 0.06 秒通常覆盖约 3~4 个循环，能显著降低“点击早于窗口到位”的概率。
- 在点击抬起后，仍需一个短等待窗口，防止“锚点立即复位”被游戏侧误判为拖动。

### 调整建议
- 命中偏移明显：适当增大（如 0.08~0.12）。
- 点击响应偏慢：在命中稳定前提下可减小（如 0.04~0.05）。
- 若机器负载高或窗口切换频繁，建议优先增大 `settle_time` 再观察。

## 6. 异常与容错策略
- 线程循环内异常吞掉并继续：保障长时间运行稳定。
- 关键调用点（点击/拖拽）做失败日志并返回失败。
- `stop()` 内使用短时收敛循环，尽量恢复到“非最小化 + 非穿透 + 不透明”。

## 7. 与主控制器边界
- 主控制器负责“何时调用”（业务编排、输入发送）。
- 追踪模块负责“如何跟踪”（线程、锚点、窗口状态）。

这种边界让主控制器保持可读性，同时保留追踪逻辑的独立演进能力。
