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
2. 点击“导入 ZIP”或“导入目录”
3. 选择插件压缩包、单个插件目录或包含多个插件的集合目录
4. 插件分别安装到 `plugins/<插件名>/` 并注册

### ZIP 包结构

一个可安装插件包必须在插件根目录直接放置一个主 `*_factory.py` 和一个 `*_const.py`：

```
my_plugin.zip
└── my_plugin/                 # 插件根目录
    ├── __init__.py
    ├── my_plugin_const.py
    ├── my_plugin_factory.py   # 唯一 factory
    ├── my_plugin.py
    ├── src/
    │   └── ...
    └── assets/
        └── ...
```

ZIP 外层可以有仓库目录、发布目录或说明文件。导入器会把主 factory 所在目录作为插件根，只导入该目录的子树：

```
repository-main/
├── README.md                  # 不导入
├── registry.json             # 不导入
└── my_plugin/                 # 从这里开始导入
    ├── my_plugin_const.py
    ├── my_plugin_factory.py
    └── operations/
```

第三方插件只注册插件根第一层的主 factory。插件根子目录可以放置普通 Python 模块和资源，但其中的 `*_factory.py` 不会被自动发现或注册。

一个 ZIP 可以包含多个互不隶属的合法插件根。插件管理界面会把它视为插件集合，分别预览、安装、覆盖和报告结果：

```
plugin_bundle.zip
└── repository-main/
    ├── README.md              # 不安装
    ├── plugin_a/              # 安装到 plugins/plugin_a/
    │   ├── plugin_a_factory.py
    │   └── plugin_a_const.py
    └── plugin_b/              # 安装到 plugins/plugin_b/
        ├── plugin_b_factory.py
        └── plugin_b_const.py
```

如果 ZIP 根本身已经是合法插件根，整个 ZIP 只作为一个插件，根内更深的 factory 不会再拆成其他插件。集合中大小写不敏感的插件目录名重复时，整个来源会在写盘前被拒绝。

### 插件根和运行文件边界

主 factory 所在目录就是可安装插件根。导入器只安装该目录及其子树，插件运行所需的代码、资源和配置必须全部放在这个范围内。当前导入器不读取 `plugin.json` 来声明插件根、源码根或额外安装目录。

可以在插件根内使用 `src/`、`assets/` 等目录：

```
my_plugin/                     # 插件根
├── my_plugin_factory.py       # 主 factory
├── my_plugin_const.py
├── src/
│   └── ...
└── assets/
    └── ...
```

不能把运行资源放在主 factory 目录之外：

```
repository/
├── src/
│   └── my_plugin/
│       ├── my_plugin_factory.py   # 导入器会把这里识别为插件根
│       └── my_plugin_const.py
└── assets/                        # 位于插件根外，不会安装
```

源码仓库可以自由使用 `src-layout`、测试目录和构建脚本，但提供给插件管理器的 ZIP 必须包含一个自包含的运行包。可以在发布时整理成上面的 `my_plugin/` 结构，也可以在源码仓库中直接维护一个独立的运行包目录。

插件内的 Python 模块可以使用相对导入引用插件根内的代码；不能越过插件根依赖外部代码或文件。导入器不会修改原 ZIP，但插件根外的内容不会复制到 `plugins/`。

导入目录时，如果所选目录本身是合法插件根，就按单个插件处理；否则向下查找多个互不隶属的最外层合法插件根。集合目录本身和各插件根之外的文件不会复制到 `plugins/`。目录中的符号链接不能指向所属插件根之外，也不能形成复制循环；插件根第一层的 Python 文件不能是符号链接。

导入器会拒绝绝对路径、上级路径、重复落盘路径和文件/目录冲突；`__MACOSX`、`.DS_Store` 等系统元数据不会参与结构判断。一个 ZIP 中所有本次选中插件根的解压后总体积不能超过 512 MiB。每个插件独立使用临时目录和替换回滚，一个插件失败不会撤销同一来源中其他已成功插件；覆盖重试也只处理用户确认的插件。

插件管理、覆盖和删除都以 `plugins/<插件目录>/` 为单位，不要求插件目录名与 `APP_ID` 相同，但插件目录名必须唯一。

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
| 默认组 | `True` | 默认出现在一条龙列表，用于日常任务（体力刷本、咖啡店、邮件等） |
| 非默认组 | `False` | 默认不出现在一条龙列表；若实例配置中已有该应用且处于启用状态，则继续显示，禁用后永久移除 |

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
