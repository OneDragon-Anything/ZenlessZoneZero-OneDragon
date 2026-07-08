---
name: zzz-od-dev-plugin
description: 绝区零一条龙新增内置应用与第三方插件指南，覆盖工厂、常量、运行记录、设置界面和 screen_info 接入
version: 1.0.0
author: OneDragon-Anything
tags: [zzz, one-dragon, application, plugin, development]
---

# 新增应用 / 插件开发指南

本项目的“插件”本质上是可被 `ApplicationFactoryManager` 自动发现的 `ApplicationFactory`。有两种落点：

| 类型 | 目录 | 是否提交 | 导入方式 |
|---|---|---:|---|
| 内置应用 | `src/zzz_od/application/<app>/` | 是 | 绝对导入 |
| 第三方插件 | `plugins/<plugin>/` | 否，`plugins/` 被 gitignore | 插件内可相对导入 |

第三方插件必须放在 `plugins/` 的子目录，不能把 `_factory.py` 直接放在 `plugins/` 根目录。

## 1. 最小文件结构

### 内置应用

```text
src/zzz_od/application/my_app/
├── __init__.py
├── my_app_const.py
├── my_app_factory.py
├── my_app.py
└── my_app_run_record.py        # 需要运行记录时添加
```

### 第三方插件

```text
plugins/my_plugin/
├── __init__.py
├── my_plugin_const.py
├── my_plugin_factory.py
├── my_plugin.py
└── my_plugin_run_record.py     # 需要运行记录时添加
```

## 2. const 文件

`ApplicationFactory` 要求 const 模块必须有：

```python
APP_ID = 'my_plugin'
APP_NAME = '我的插件'
DEFAULT_GROUP = True
NEED_NOTIFY = True
```

字段含义：

| 字段 | 含义 |
|---|---|
| `APP_ID` | 全局唯一应用 ID，重复会被拒绝 |
| `APP_NAME` | GUI 展示名称 |
| `DEFAULT_GROUP` | `True` 进入一条龙默认运行列表；`False` 作为独立工具 |
| `NEED_NOTIFY` | 是否需要通知能力 |

第三方插件可额外提供 GUI 元数据：

```python
PLUGIN_AUTHOR = '作者名'
PLUGIN_HOMEPAGE = 'https://github.com/author/my_plugin'
PLUGIN_VERSION = '1.0.0'
PLUGIN_DESCRIPTION = '插件功能描述'
```

## 3. Application 类

应用继承 `ZApplication`，状态机写法与普通 `ZOperation` 一致。

```python
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext

from . import my_plugin_const


class MyPlugin(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=my_plugin_const.APP_ID,
            op_name=my_plugin_const.APP_NAME,
        )

    @operation_node(name='开始', is_start_node=True)
    def start(self) -> OperationRoundResult:
        return self.round_success()
```

内置应用按项目规范使用绝对导入：

```python
from zzz_od.application.my_app import my_app_const
```

第三方插件内部可以使用相对导入：

```python
from . import my_plugin_const
```

## 4. Factory 类

工厂文件必须以 `_factory.py` 结尾，同一个目录最多一个 `_factory.py`。

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application

from . import my_plugin_const
from .my_plugin import MyPlugin

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class MyPluginFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(self, my_plugin_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return MyPlugin(self.ctx)
```

如果应用需要运行记录，再实现 `create_run_record`。

```python
from one_dragon.base.operation.application_run_record import AppRunRecord
from .my_plugin_run_record import MyPluginRunRecord

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return MyPluginRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
```

如果应用需要配置，再实现 `create_config` 并返回 `ApplicationConfig` 子类。

## 5. 运行记录

```python
from one_dragon.base.operation.application_run_record import AppRunRecord


class MyPluginRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'my_plugin',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset,
        )
```

`AppRunRecord` 的 app id 要与 `APP_ID` 一致。

## 6. 设置界面

需要设置入口时，新增 `*_app_setting.py`，模式参考：

- `src/zzz_od/application/coffee/coffee_app_setting.py`
- `src/zzz_od/application/suibian_temple/suibian_temple_app_setting.py`
- `docs/develop/guides/application_setting_guide.md`

设置界面扫描器会复用已发现的插件信息，不需要自己全盘扫描。

## 7. 插件 screen_info

第三方插件可以携带自己的 screen YAML：

```text
plugins/my_plugin/
└── screen_info/
    └── my_screen.yml
```

`app_id` 可省略，加载时会自动使用插件的 `APP_ID`。示例：

```yaml
screen_id: my_plugin_main
screen_name: 我的插件-主界面
area_list:
  - area_name: 按钮-开始
    pc_rect: [100, 100, 200, 80]
    text: 开始
```

插件 screen 会进入对应应用的局部命名空间，避免污染其他应用。

## 8. 发现与刷新规则

扫描入口：`src/one_dragon/base/operation/application/application_factory_manager.py`

规则：

- 扫描所有 `_factory.py`。
- 同一目录存在多个 `_factory.py` 或多个 `_const.py` 时，该目录跳过。
- 每个 factory 模块最多一个 `ApplicationFactory` 子类。
- `APP_ID` 重复时，后注册者会被拒绝。
- 第三方插件通过 `plugins/` 作为 module root 加入 `sys.path`。
- 运行时可调用 `ctx.refresh_application_registration()` 重新扫描。

## 9. zip 包结构

GUI 导入第三方插件时，zip 顶层应包含插件目录：

```text
my_plugin.zip
└── my_plugin/
    ├── __init__.py
    ├── my_plugin_const.py
    ├── my_plugin_factory.py
    └── my_plugin.py
```

不要把文件直接压在 zip 根目录。

## 10. 验证清单

- [ ] `APP_ID` 全局唯一，且与运行记录 app id 一致。
- [ ] 同一目录只有一个 `_factory.py` 和一个 `_const.py`。
- [ ] factory 类继承 `ApplicationFactory`，并实现 `create_application`。
- [ ] 应用类继承 `ZApplication`，构造函数传入 `app_id` 和 `op_name`。
- [ ] 状态机只有一个 `is_start_node=True`。
- [ ] 第三方插件位于 `plugins/<plugin>/`，不是 `plugins/` 根目录。
- [ ] 如有设置界面，文件名为 `*_app_setting.py`。
- [ ] 如有 screen_info，区域名和代码中的 `round_by_find_area` / `round_by_click_area` 一致。
- [ ] 修改代码后只对改动文件运行 `uv run --env-file .env ruff check <file>`。