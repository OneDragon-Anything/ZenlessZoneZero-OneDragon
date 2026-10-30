---
name: zzz-od-dev-state-machine
description: 绝区零一条龙 Operation 状态机开发指南，说明如何用节点、边和轮次结果编排自动化流程
version: 1.0.0
author: OneDragon-Anything
tags: [zzz, one-dragon, operation, state-machine, development]
---

# Operation 状态机开发指南

本项目的“状态机”通常指 `Operation` 节点图：

- 普通流程继承 `ZOperation`：`src/zzz_od/operation/zzz_operation.py`
- 完整应用继承 `ZApplication`：`src/zzz_od/application/zzz_application.py`
- 底层执行引擎：`src/one_dragon/base/operation/operation.py`
- 节点声明：`operation_node`
- 边声明：`node_from`
- 单轮结果：`OperationRoundResult`

## 1. 最小结构

```python
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class MyOperation(ZOperation):

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name='我的流程')

    @operation_node(name='入口', is_start_node=True)
    def start(self) -> OperationRoundResult:
        return self.round_success('下一步')

    @node_from(from_name='入口', status='下一步')
    @operation_node(name='处理')
    def do_work(self) -> OperationRoundResult:
        return self.round_success()
```

## 2. 节点与边

### `@operation_node`

常用参数：

| 参数 | 用途 |
|---|---|
| `name` | 节点名，必须稳定，`node_from.from_name` 会精确匹配 |
| `is_start_node` | 入口节点，一个流程只应有一个 |
| `node_max_retry_times` | 当前节点最大重试次数 |
| `timeout_seconds` | 当前节点超时时间 |
| `mute` | 高频节点不输出过多日志 |
| `save_status` | 保存节点状态，供后续节点读取 |
| `screenshot_before_round` | 当前节点每一轮执行前是否自动截图，默认 `True` |

### `@node_from`

常用匹配方式：

```python
@node_from(from_name='入口')                      # 上游成功即可进入
@node_from(from_name='入口', success=False)       # 上游失败进入
@node_from(from_name='入口', status='指定状态')    # 上游 status 精确匹配
@node_from(from_name='入口', success=True, status='指定状态')
```

同一个节点可以声明多个 `@node_from`，表示多个入口都能流转到这里。

## 3. 轮次结果怎么选

| 方法 | 含义 | 典型场景 |
|---|---|---|
| `round_success(status=None)` | 当前节点完成，进入下一条匹配边 | 点击成功、识别到目标、分支选择完成 |
| `round_retry(status=None, wait=...)` | 当前节点失败一次，消耗重试次数 | 暂时没识别到按钮、等待页面加载 |
| `round_wait(status=None, wait=...)` | 当前节点等待，不消耗重试次数 | 高频轮询、等待动画、持续战斗检测 |
| `round_fail(status=None)` | 当前 Operation 失败终止 | 必要条件缺失、没有可执行方案 |

规则：

- 需要继续停在当前节点时，用 `round_retry` 或 `round_wait`。
- 等待外部状态变化且不希望耗尽重试次数时，用 `round_wait`。
- `status` 是流转条件的一部分；被 `@node_from(status=...)` 使用的字符串不要随意改。

## 4. 截图时机

`Operation.execute()` 每次循环调用 `_execute_one_round()`。如果当前节点是 `@operation_node` 方法，且该节点的 `screenshot_before_round=True`，框架会在调用节点方法前执行一次 `self.screenshot()`，更新：

- `self.last_screenshot`
- `self.last_screenshot_time`

默认 `screenshot_before_round=True`。

### 4.1 返回值和截图关系

| 返回值 | 下一步 | 是否会自动重新截图 |
|---|---|---|
| `round_retry(...)` | 继续执行同一个节点的下一轮，消耗重试次数 | 下一轮进入同一节点前会重新截图 |
| `round_wait(...)` | 继续执行同一个节点的下一轮，不消耗重试次数 | 下一轮进入同一节点前会重新截图 |
| `round_success(...)` | 查找匹配的下一节点；没有下一节点则 Operation 成功结束 | 有下一节点时，下一轮进入下一节点前会重新截图 |
| `round_fail(...)` | 查找失败分支；没有下一节点则 Operation 失败结束 | 有下一节点时，下一轮进入下一节点前会重新截图 |

结论：返回值本身不会截图；它只决定是否进入下一轮。真正截图发生在下一轮节点方法执行前。

### 4.2 同一个节点方法内部不会自动重新截图

在一次节点方法调用期间，`self.last_screenshot` 是同一张图，除非你显式调用：

```python
screen = self.screenshot()
```

因此同一个节点里连续写多次识别，默认都基于同一张截图：

```python
@operation_node(name='识别并点击', is_start_node=True)
def check_and_click(self) -> OperationRoundResult:
    # 这里使用本轮开始前自动截取的 last_screenshot
    result = self.round_by_find_area(self.last_screenshot, '画面', '按钮')
    if result.is_success:
        self.round_by_click_area('画面', '按钮')

    # 这里仍然是同一轮的 last_screenshot，不会因为刚才点击过就自动刷新
    result = self.round_by_find_area(self.last_screenshot, '画面', '点击后出现的按钮')
    return self.round_retry('等待点击后界面刷新', wait=1)
```

这种场景应拆成两个节点，或在点击后显式截图：

```python
self.round_by_click_area('画面', '按钮')
self.screenshot()
return self.round_by_find_area(self.last_screenshot, '画面', '点击后出现的按钮')
```

### 4.3 辅助方法默认不主动截图

多数 `round_by_find_area`、`round_by_find_and_click_area`、`round_by_goto_screen`、`round_by_ocr...` 辅助方法在 `screen=None` 时使用 `self.last_screenshot`。不要误以为传 `None` 就会立即截图。

需要新画面时，先调用 `self.screenshot()`，或让本轮返回 `round_retry` / `round_wait`，等下一轮自动截图。

## 5. 常见状态机模式

### 5.1 入口识别后分流

```python
@operation_node(name='画面识别', is_start_node=True)
def check_screen(self) -> OperationRoundResult:
    current = self.check_and_update_current_screen(self.last_screenshot)
    if current == '大世界':
        return self.round_success('已在大世界')
    if current == '菜单':
        return self.round_success('需要返回')
    return self.round_retry('未识别当前画面', wait=1)

@node_from(from_name='画面识别', status='需要返回')
@operation_node(name='返回大世界')
def back_to_world(self) -> OperationRoundResult:
    ...
```

### 5.2 调用子 Operation

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    op = BackToNormalWorld(self.ctx)
    return self.round_by_op_result(op.execute())
```

适合把通用流程拆成可复用 Operation。不要把子 Operation 的内部节点复制到当前类里。

### 5.3 查找并点击画面区域

```python
@operation_node(name='点击按钮')
def click_button(self) -> OperationRoundResult:
    return self.round_by_find_and_click_area(
        self.last_screenshot,
        '快捷手册',
        '今日最大活跃度',
        success_wait=1,
        retry_wait=1,
    )
```

区域名来自 `assets/game_data/screen_info/`。新增或改动区域时，要同步检查 screen YAML。

### 5.4 高频轮询

```python
@operation_node(name='画面识别', mute=True)
def check_screen(self) -> OperationRoundResult:
    self.ctx.auto_battle_context.check_battle_state(self.last_screenshot)
    return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)
```

高频节点建议设置 `mute=True`，避免日志淹没真正错误。

### 5.5 失败兜底

```python
@node_from(from_name='确认', success=False)
@operation_node(name='返回大世界')
def back_after_fail(self) -> OperationRoundResult:
    op = BackToNormalWorld(self.ctx)
    op.execute()
    return self.round_fail('确认失败，已尝试返回')
```

失败兜底可以清理现场，但不要把业务失败伪装成成功。

## 6. Application 写法

应用状态机继承 `ZApplication`，节点写法与 `ZOperation` 相同。

```python
from zzz_od.application.zzz_application import ZApplication


class MyApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=my_app_const.APP_ID,
            op_name=my_app_const.APP_NAME,
        )
```

应用还需要工厂、常量、可选配置和运行记录。新增应用/插件见 `zzz-od-dev-plugin`。

## 7. 编写检查清单

- [ ] 节点名稳定，`@node_from(from_name=...)` 能精确对应。
- [ ] 只有一个 `is_start_node=True`。
- [ ] 所有会被边匹配的 `status` 都是固定字符串或类常量。
- [ ] 等待外部变化用 `round_wait`，失败重试用 `round_retry`。
- [ ] 需要点击后识别新画面时，拆节点或显式调用 `self.screenshot()`。
- [ ] 子流程优先封装为子 `Operation`，通过 `round_by_op_result` 接入。
- [ ] 高频轮询节点使用 `mute=True`。
- [ ] 失败节点返回 `round_fail`，不要吞掉关键错误。
- [ ] 修改代码后只对改动文件运行 `ruff check`。