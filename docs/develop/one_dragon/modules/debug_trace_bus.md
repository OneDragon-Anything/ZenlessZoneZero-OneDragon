# 调试 Trace 总线设计

## 背景

核心层（OCR、模板匹配、YOLO、Operation 执行链）在运行时产生大量调试信息：
视觉识别框、决策流转记录、时间线事件、性能指标。这些 trace 原以
`_emit_overlay_*` 方式直接写入 `OverlayDebugBus`，类名、方法名、数据字段中
混入了 Overlay/Qt 的展示概念（color、ttl_seconds），违反了核心层不应知道
展示层的分层原则。

## 目标

- 核心层产出通用 trace 数据，不关心谁来消费、怎么展示。
- Overlay 只是 consumer 之一，未来可以有日志持久化、远程调试等消费者。
- 框架级 `DebugTraceBus` 无 Qt 依赖，可在 worker 线程安全使用。
- 旧 `OverlayDebugBus` 作为兼容壳逐步淘汰。

## 非目标

- 不改变 trace 数据的实时性语义（仍然是追加式队列）。
- 不提供持久化、远程传输等高级 consumer 实现（由具体 consumer 自行决定）。
- 不要求所有消费者立即切换新接口。

## 框架层设计

### 数据类（`debug_trace_bus.py`）

```
VisionTraceItem    — 视觉识别框（source、label、坐标、置信度）
DecisionTraceItem  — 决策/流转记录（触发、条件、操作、状态）
TimelineTraceItem  — 时间线事件（类别、标题、详情、级别）
PerfTraceItem      — 性能指标（指标名、值、单位）
DebugTraceSnapshot — 以上四类的快照集合
```

与旧数据类（`VisionDrawItem` 等）的关键差异：

- 无 `color`、`ttl_seconds`：展示属性归消费端，不做跨层传递。
- 类型命名去掉 `Overlay` 前缀，改为通用 `Debug`/`Trace`。

### 总线（`DebugTraceBus`）

- 线程安全：`threading.RLock` 保护内部 `deque`（有界 `maxlen`）。
- `add_vision()` 自动应用 thread-local `crop_offset`，生产者无需手动加偏移。
- `add_decision()` / `add_timeline()` / `add_perf()` 纯追加。
- `snapshot()` 返回浅拷贝，避免锁内耗时操作。
- `crop_offset` 为 thread-local，通过 `set_crop_offset()` / `reset_crop_offset()` 管理。

### 兼容壳（`OverlayDebugBus`）

继承 `DebugTraceBus`，保留旧 API：

- `add_*` 方法接受旧数据类（`VisionDrawItem`、`DecisionTraceItem`、
  `TimelineItem`、`PerfMetricSample`），内部转换后存入父类队列。
- `snapshot()` 返回旧格式 `OverlayDebugSnapshot`，兼容现有 overlay 面板。
- `color` / `ttl_seconds` 暂存 `meta["_color"]` / `meta["_ttl_seconds"]`，
  转换时恢复。
- 新增 `enabled` 标志（默认 `True`），由 `OverlayManager` 同步
  `OverlayConfig.enabled`，关闭时生产者跳过 trace 构造。

## Producer / Consumer 边界

```
┌────────────────────────────────────────────┐
│  Producer（核心层）                          │
│  operation.py / template_matcher.py / ...   │
│  调用 _emit_debug_* 方法                     │
│  构造旧数据类 → 写入 OverlayDebugBus          │
│                     │                       │
│  ═══════════════════│══════════════════════ │
│                     │  框架边界               │
│  ═══════════════════│══════════════════════ │
│                     ▼                       │
│  DebugTraceBus（通用存储）                    │
│  snapshot() → DebugTraceSnapshot            │
│                     │                       │
│  Consumer A: Overlay 面板 (Qt)               │
│  Consumer B: （未来）日志持久化               │
│  Consumer C: （未来）远程调试                 │
└────────────────────────────────────────────┘
```

## 迁移路径

1. **阶段 1**：止血——加 `try/finally`、`enabled` 门控、窄化异常。
2. **阶段 2**：`DebugTraceBus` 上线，`OverlayDebugBus` 继承委托。
3. **阶段 3**：生产者重命名 `_emit_overlay_*` → `_emit_debug_*`，
   构造注入 `debug_trace_bus`。
4. **阶段 4**：Overlay 侧切到 `debug_trace_bus` 命名，
   颜色全由 `_VISION_SOURCE_COLOR` 按 source 决定。
5. **阶段 5**（未来）：淘汰 `OverlayDebugBus` 兼容壳，
   生产者直接使用新数据类和 `DebugTraceBus` API。
