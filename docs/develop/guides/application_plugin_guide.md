# 应用开发指引

> 本文档指引如何创建新应用并接入插件系统。架构细节请参考 [application_plugin_system.md](../one_dragon/modules/application_plugin_system.md)。

---

## 快速开始

创建一个新应用只需以下文件：

```
src/zzz_od/application/my_app/    # 内置应用
├── __init__.py
├── my_app_const.py                # ★ 必需：常量定义
├── my_app_factory.py              # ★ 必需：工厂类
└── my_app.py                      # 应用实现
```

### 步骤 1: 创建 const 文件

```python
# my_app_const.py

APP_ID = "my_app"
APP_NAME = "我的应用"
DEFAULT_GROUP = True   # True → 出现在一条龙列表; False → 独立工具
NEED_NOTIFY = True     # 是否需要通知
```

### 步骤 2: 创建工厂类

```python
# my_app_factory.py

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.application.my_app import my_app_const
from zzz_od.application.my_app.my_app import MyApp


class MyAppFactory(ApplicationFactory):

    def __init__(self, ctx):
        ApplicationFactory.__init__(self, my_app_const)
        self.ctx = ctx

    def create_application(self, instance_idx, group_id):
        return MyApp(self.ctx)
```

**命名约定**:
- 工厂文件必须以 `_factory.py` 结尾
- 常量文件必须以 `_const.py` 结尾
- 同一目录最多各一个

完成后重启程序，系统会自动发现并注册你的应用。

---

## 创建第三方插件

第三方插件放在 `plugins/` 目录下：

```
plugins/my_plugin/
├── __init__.py              # 推荐添加
├── my_plugin_const.py
├── my_plugin_factory.py
└── my_plugin.py
```

### const 文件

```python
# my_plugin_const.py

APP_ID = "my_plugin"
APP_NAME = "我的插件"
DEFAULT_GROUP = True
NEED_NOTIFY = True

# 可选元数据（用于 GUI 显示）
PLUGIN_AUTHOR = "作者名"
PLUGIN_HOMEPAGE = "https://github.com/author/my_plugin"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "插件功能描述"
```

### 工厂类

```python
# my_plugin_factory.py

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.context.zzz_context import ZContext

from . import my_plugin_const
from .my_plugin import MyPlugin


class MyPluginFactory(ApplicationFactory):
    def __init__(self, ctx: ZContext):
        super().__init__(my_plugin_const)
        self.ctx = ctx

    def create_application(self, instance_idx, group_id):
        return MyPlugin(self.ctx)
```

### 第三方插件特性

- ✅ 相对导入可用：`from .utils import helper`
- ✅ 可导入主程序模块：`from one_dragon.xxx`、`from zzz_od.xxx`
- ✅ 支持嵌套子目录和子包
- ✅ 必须放在 `plugins/` 的子目录中（不能直接放在根目录）

---

## 通过 GUI 导入插件

1. 打开设置 → 插件管理
2. 点击"导入插件"按钮
3. 选择 `.zip` 格式的插件压缩包
4. 插件自动解压到 `plugins/` 并注册

### zip 包结构

```
my_plugin.zip
└── my_plugin/
    ├── __init__.py
    ├── my_plugin_const.py
    ├── my_plugin_factory.py
    └── my_plugin.py
```

---

## 运行时刷新

无需重启程序即可加载新插件或更新已有插件：

```python
ctx.refresh_application_registration()
```

刷新流程：清空注册 → 重新扫描 → 重载模块 → 重新注册 → 更新默认组。

---

## 应用分组

| 分组 | `DEFAULT_GROUP` | 场景 |
|------|:---------------:|------|
| 默认组 | `True` | 出现在一条龙列表，用于日常任务（体力刷本、咖啡店、邮件等） |
| 非默认组 | `False` | 不出现在一条龙列表，作为独立工具（自动战斗、截图工具等） |

---

## 自定义插件目录

默认目录由 `OneDragonContext.application_plugin_dirs` 自动计算。如需额外目录，可在子类中覆盖：

```python
from functools import cached_property

class MyContext(OneDragonContext):

    @cached_property
    def application_plugin_dirs(self):
        from pathlib import Path
        from one_dragon.base.operation.application.plugin_info import PluginSource
        return [
            (Path(__file__).parent.parent / 'application', PluginSource.BUILTIN),
            (Path(__file__).parent.parent / 'plugins', PluginSource.THIRD_PARTY),
            (Path(__file__).parent.parent / 'custom_apps', PluginSource.THIRD_PARTY),
        ]
```

---

## 注意事项

1. **APP_ID 全局唯一**：重复的 APP_ID 会被拒绝，先注册者胜
2. **一模块一工厂**：每个 `_factory.py` 中只定义一个 `ApplicationFactory` 子类
3. **const 必需字段**：`APP_ID`、`APP_NAME`、`DEFAULT_GROUP`、`NEED_NOTIFY`
4. **同目录冲突**：同目录下多个 `_factory.py` 或 `_const.py` 时整个目录被跳过
5. **第三方插件备份**：`plugins/` 被 gitignore，用户需自行备份
6. **设置界面**：如需为应用添加设置界面，请参考 [application_setting_guide.md](application_setting_guide.md)
