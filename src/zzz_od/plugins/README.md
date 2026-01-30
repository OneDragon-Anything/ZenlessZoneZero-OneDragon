# ZZZ OneDragon 第三方插件目录

此目录用于存放用户安装的第三方应用插件。

## 目录结构

该目录被 `.gitignore` 忽略，不会被版本控制。

```
plugins/
├── __init__.py          # 包标识文件
├── README.md            # 说明文档
└── my_plugin/           # 你的插件目录
    ├── __init__.py          # 包标识文件
    ├── my_plugin_const.py   # 应用常量和元数据
    ├── my_plugin_factory.py # 应用工厂
    └── my_plugin_app.py     # 应用实现
```

## 安装插件

1. **通过 GUI 导入**：
   - 打开设置 -> 插件管理
   - 点击"导入插件"按钮
   - 选择 `.zip` 格式的插件压缩包

2. **手动安装**：
   - 将插件文件夹复制到此目录下
   - 重启应用或在插件管理界面点击"刷新"

## 开发插件

### 文件结构要求

- 插件目录必须放在 `src/zzz_od/plugins/` 下
- 必须包含 `__init__.py` 文件
- 必须包含 `*_factory.py` 文件
- 建议包含 `*_const.py` 文件存放元数据

### const 文件格式

```python
# my_plugin/my_plugin_const.py
APP_ID = 'my_plugin'           # 应用唯一标识
APP_NAME = '我的插件'           # 应用显示名称
DEFAULT_GROUP = True            # 是否在默认分组显示

# 插件元数据（可选）
PLUGIN_AUTHOR = '作者名'         # 作者名称
PLUGIN_HOMEPAGE = 'https://...'  # 项目主页
PLUGIN_VERSION = '1.0.0'         # 版本号
PLUGIN_DESCRIPTION = '插件描述'   # 简短描述
```

### factory 文件格式

```python
# my_plugin/my_plugin_factory.py
from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory

# 使用完整模块路径导入
from zzz_od.plugins.my_plugin import my_plugin_const

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class MyPluginFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=my_plugin_const.APP_ID,
            app_name=my_plugin_const.APP_NAME,
            default_group=my_plugin_const.DEFAULT_GROUP
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str):
        # 使用完整模块路径导入
        from zzz_od.plugins.my_plugin.my_plugin_app import MyPluginApp
        return MyPluginApp(self.ctx)
```

### app 文件格式

```python
# my_plugin/my_plugin_app.py
from one_dragon.base.operation.application.application_base import ApplicationBase
from zzz_od.context.zzz_context import ZContext


class MyPluginApp(ApplicationBase):

    def __init__(self, ctx: ZContext):
        ApplicationBase.__init__(self, ctx)

    def handle_init(self):
        pass

    def handle_start(self):
        # 在这里实现你的应用逻辑
        pass

    def handle_stop(self):
        pass
```

## 导入规则

**重要**：插件内部的导入必须使用完整模块路径：

```python
# ✅ 正确 - 使用完整路径
from zzz_od.plugins.my_plugin import my_plugin_const
from zzz_od.plugins.my_plugin.my_plugin_app import MyPluginApp

# ❌ 错误 - 使用短路径（会导致 ModuleNotFoundError）
from my_plugin import my_plugin_const
from .my_plugin_app import MyPluginApp
```

## 打包插件

将插件目录压缩为 `.zip` 文件即可分发：

```
my_plugin.zip
└── my_plugin/
    ├── __init__.py
    ├── my_plugin_const.py
    ├── my_plugin_factory.py
    └── my_plugin_app.py
```

## 注意事项

- 插件目录名应与插件 ID 一致
- 确保 const 文件和 factory 文件命名正确
- 所有导入必须使用 `zzz_od.plugins.xxx` 完整路径
- 如遇问题，请查看日志获取详细错误信息
