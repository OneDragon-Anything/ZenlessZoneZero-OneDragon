# 调试 Trace 总线设计

## 背景

OCR、模板匹配、YOLO 和 Operation 执行链会在运行时产生视觉框、决策记录、
时间线事件和性能指标。核心层只应表达这些调试事实，不应知道 Overlay、Qt、
颜色或展示时长。

`DebugTraceBus` 是框架级可选调试事件通道。Overlay 是当前消费者之一，未来还可
增加日志持久化、远程调试等消费者。

## 框架层契约

实现位于 `one_dragon.base.debug.debug_trace_bus`：

- `VisionTraceItem`：视觉识别框（来源、标签、坐标、置信度、业务元数据）。
- `DecisionTraceItem`：决策和流转记录。
- `TimelineTraceItem`：时间线事件。
- `PerfTraceItem`：性能指标。
- `DebugTraceSnapshot`：四类 trace 的当前快照。
- `DebugTraceBus`：线程安全的有界队列、快照、清理和视觉坐标偏移。

`OneDragonContext` 直接持有唯一的 `debug_trace_bus`。生产端通过构造参数显式注入
同一实例，不再使用 Overlay 命名、动态属性或兼容别名。

## Producer / Consumer 边界

### Producer

核心生产端直接构造通用 trace 数据类并调用：

- `add_vision()`
- `add_decision()`
- `add_timeline()`
- `add_perf()`

生产端只提供语义数据和业务 `meta`，不传颜色或 TTL。`enabled` 是核心层可读的
唯一通用门控；关闭后生产者在构造 trace 前直接返回，减少热路径开销。

### Consumer

`OverlayManager` 调用 `snapshot()`，自行决定：

- 展示 TTL：vision 1.8 秒、decision 30 秒、timeline 60 秒、perf 30 秒。
- 按 source、metric 等条件过滤。
- YOLO 框去重、排序和显示数量。
- 文案和颜色。

视觉颜色由 Overlay 的 source 映射决定。总线不会因某个消费者的 TTL 删除数据；
内部有界 `deque` 控制内存，不同消费者可以采用不同展示策略。

## 坐标偏移

### DebugTraceBus crop scope

`add_vision()` 会自动应用当前线程的 `crop_offset`。OCR 和模板匹配 emitter 只提交
当前输入图像内的相对坐标，不再手动加偏移。

`set_crop_offset()` / `reset_crop_offset()` 使用线程局部栈支持嵌套作用域：

1. 调用方读取父级 `crop_offset`。
2. 将父级与当前裁剪矩形偏移相加，压入累计绝对偏移。
3. 在 `try/finally` 中执行识别。
4. `reset_crop_offset()` 弹出当前层并恢复父级。

GPU executor 的 worker 不继承调用线程的 thread-local，因此 CV OCR 步骤会把已计算的
累计 offset 作为参数提交，并在真正执行 OCR 的 worker 中建立和恢复作用域。

### 三种坐标职责

以下坐标转换用途不同，不应混为一谈：

- `DebugTraceBus.crop_offset`：把 trace 相对坐标转换成外层/整屏坐标。
- `OcrService` 的 `ocr_result.add_offset()`：转换返回给业务调用方的 OCR 结果坐标。
- `CvPipelineContext.crop_offset`：记录 `display_image` 相对 pipeline source 的累计偏移，
  用于 CV contour、模板和 OCR 汇总结果。

`CvService` 先使用 pipeline offset 形成相对 pipeline source 的坐标；如果 pipeline
本身运行在更外层 crop scope，`DebugTraceBus.add_vision()` 再应用外层 bus offset。

## 线程安全与生命周期

- `threading.RLock` 保护四个有界 `deque`。
- crop offset 使用 `threading.local()`，各 worker 互不污染。
- `snapshot()` 在锁内浅拷贝队列，锁外由消费者过滤和渲染。
- `clear()` 在 Context 停止时清空所有 trace。
- `created <= 0` 的项目在入队时自动补当前时间。

## 已完成的迁移

阶段 1–5 已全部完成：

1. OCR 裁剪 offset 用 `try/finally` 恢复，异常导入捕获收窄，加入 `enabled` 门控。
2. 新增框架级 `DebugTraceBus` 和通用数据类。
3. 生产者方法统一为 `_emit_debug_*` 并改为构造注入。
4. Overlay 使用 `debug_trace_bus`，颜色归消费端。
5. 删除 `OverlayDebugBus` 兼容壳、旧数据类、旧 Context 属性和旧 API。

旧接口迁移关系：

| 旧接口 | 新接口 |
|---|---|
| `OverlayDebugBus` | `DebugTraceBus` |
| `VisionDrawItem` | `VisionTraceItem` |
| `TimelineItem` | `TimelineTraceItem` |
| `PerfMetricSample` | `PerfTraceItem` |
| `OverlayDebugSnapshot` | `DebugTraceSnapshot` |
| `add_performance()` | `add_perf()` |
| `snapshot.performance_items` | `snapshot.perf_items` |
| `ctx.overlay_debug_bus` | `ctx.debug_trace_bus` |
| 构造参数 `overlay_debug_bus` | `debug_trace_bus` |
