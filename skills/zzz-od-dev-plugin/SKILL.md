---
name: zzz-od-dev-plugin
description: 当要新增或修改绝区零一条龙的内置应用、第三方应用插件或插件接入配置时使用。
version: 2.0.0
author: OneDragon-Anything
tags: [zzz, one-dragon, application, plugin, development]
---

# 新增应用 / 插件开发指南

本项目的“插件”本质上是可被 `ApplicationFactoryManager` 自动发现的 `ApplicationFactory`。有两种落点：

| 类型 | 目录 | 是否提交 | 导入方式 |
|---|---|---:|---|
| 内置应用 | `src/zzz_od/application/<app>/` | 是 | 绝对导入 |
| 第三方插件 | `plugins/<plugin>/` | 否，`plugins/` 被 gitignore | 插件内可相对导入 |

## 先读文档

文件命名、const 字段、入口组合、工厂、运行记录、`plugin.json`、仓库布局、数据目录、ZIP 导入、插件商店发布、刷新规则，都以下面这份文档为准，**先完整读它再动手**，本 skill 不重复其内容：

- [docs/develop/guides/application_plugin_guide.md](../../docs/develop/guides/application_plugin_guide.md)

按需再读：

- 架构与调用链：[application_plugin_system.md](../../docs/develop/one_dragon/modules/application_plugin_system.md)
- 设置界面：[application_setting_guide.md](../../docs/develop/guides/application_setting_guide.md)

文档与代码不一致时，以代码为准，并顺手修正文档。

## Application 类

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

内置应用按项目规范使用绝对导入（`from zzz_od.application.my_app import my_app_const`）；第三方插件内部可以使用相对导入。

## 自定义运行记录

先确认基础每日记录无法表达需求（默认行为见文档「运行记录」），再新增自定义记录，`AppRunRecord` 的 app id 要与 `APP_ID` 一致：

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

然后在工厂里覆盖 `create_run_record()` 返回它，并传入 `self.ctx.game_account_config.game_refresh_hour_offset`。

## 插件 screen_info

第三方插件可以携带自己的 screen YAML：

```text
plugins/my_plugin/
└── screen_info/
    └── my_screen.yml
```

`app_id` 可省略，加载时会自动使用插件的 `APP_ID`。插件 screen 进入对应应用的局部命名空间，不污染其他应用。

```yaml
screen_id: my_plugin_main
screen_name: 我的插件-主界面
area_list:
  - area_name: 按钮-开始
    pc_rect: [100, 100, 200, 80]
    text: 开始
```

## 验证清单

- [ ] 已按文档确认文件命名、const 字段和入口组合合法。
- [ ] `APP_ID` 全局唯一，且与运行记录 app id 一致。
- [ ] 同一目录只有一个工厂文件和一个常量文件。
- [ ] factory 类继承 `ApplicationFactory`，并实现 `create_application` 和 `create_config`。
- [ ] 应用类继承 `ZApplication`，构造函数传入 `app_id` 和 `op_name`。
- [ ] 状态机只有一个 `is_start_node=True`。
- [ ] 第三方插件位于 `plugins/<plugin>/` 子目录，运行所需文件都在插件根内。
- [ ] 需要持久化数据时用 `self.data_dir`，不写到插件目录或 `config/`。
- [ ] 如有设置界面，按设置界面文档接入。
- [ ] 如有 screen_info，区域名和代码中的 `round_by_find_area` / `round_by_click_area` 一致。
