# 第三方插件目录

此目录用于放置第三方插件。

## 特性

- ✅ **相对导入**：`from .utils import xxx`
- ✅ **导入主程序模块**：`from one_dragon.xxx import yyy`, `from zzz_od.xxx import yyy`
- ✅ **支持子包**：可以有多层目录结构

## 加载机制

加载插件时，`plugins/` 目录会被添加到 `sys.path`，使每个插件包成为独立的顶级模块。
插件根内支持嵌套子目录和 Python 子包，但第三方插件只扫描插件根第一层的 `*_factory.py`：

```python
# 加载过程
sys.path.insert(0, "project_root/plugins")  # 添加一次

# plugins/my_plugin/my_plugin_factory.py  → 会注册
# plugins/my_plugin/sub/helper.py         → 可以被插件代码导入
# plugins/my_plugin/sub/sub_factory.py    → 不会被自动发现或注册
```

## 插件根和运行文件边界

每个 `plugins/<插件名>/` 目录都是一个独立的插件根，主 `*_factory.py` 和对应的 `*_const.py` 必须直接放在插件根中。插件运行所需的代码、资源和配置必须全部位于插件根子树内。

可以在插件根内使用 `src/`、`assets/` 等目录：

```
plugins/
└── my_plugin/                   # 插件根
    ├── my_plugin_factory.py
    ├── my_plugin_const.py
    ├── src/
    │   └── ...
    └── assets/
        └── ...
```

不支持把 factory 放在 `src/` 深处，同时依赖 factory 目录之外的兄弟目录：

```
repository/
├── src/my_plugin/
│   ├── my_plugin_factory.py     # 这里会被识别为插件根
│   └── my_plugin_const.py
└── assets/                      # 插件根外，导入时不会安装
```

源码仓库可以使用任意开发布局，但交给插件管理器导入的 ZIP 必须包含一个自包含的运行包。当前导入器不读取 `plugin.json` 来声明插件根、源码根或额外安装目录。

插件内的 Python 模块可以用相对导入引用插件根内的代码，但不能越过插件根依赖外部文件。ZIP 外层的仓库目录、开发脚本和说明文件不会复制到 `plugins/`；原 ZIP 本身不会被修改。

## 集合 ZIP 和集合目录

一个 ZIP 或所选目录可以包含多个互不隶属的合法插件根。插件管理器只选择最外层合法根，并分别安装为 `plugins/<插件名>/`：

```
plugin_collection/
├── README.md                  # 不安装
├── plugin_a/
│   ├── plugin_a_factory.py
│   └── plugin_a_const.py
└── plugin_b/
    ├── plugin_b_factory.py
    └── plugin_b_const.py
```

如果来源根本身直接包含唯一 `*_factory.py` 和唯一 `*_const.py`，整个来源只作为一个插件，不再拆分其子目录。插件根内更深的 factory 仍是普通文件，不会成为第二个插件，也不会被运行时注册。

同一来源中插件目录名大小写不敏感地重复时，整个来源会在写盘前被拒绝。每个插件独立安装、覆盖和回滚；覆盖已存在插件时，不会重复处理同一来源中已经成功安装的其他插件。松散目录中的符号链接不能越出所属插件根或形成循环，插件根第一层的 Python 文件不能是符号链接。

## 目录结构示例

```
plugins/                          # ← 添加到 sys.path
├── README.md
├── plugin_a/                     # 插件 A
│   ├── __init__.py               # 推荐添加
│   ├── plugin_a_const.py         # 定义 APP_ID, APP_NAME, DEFAULT_GROUP, NEED_NOTIFY；可选 INTERNAL_APP
│   ├── plugin_a_factory.py       # 工厂类（必须以 _factory.py 结尾）
│   ├── plugin_a.py               # 应用实现
│   └── utils/                    # 子包
│       ├── __init__.py
│       └── helper.py
├── plugin_b/                     # 插件 B（含子包）
│   ├── __init__.py
│   ├── plugin_b_const.py
│   ├── plugin_b_factory.py       # 插件根第一层的唯一工厂
│   └── sub_feature/              # 普通子包
│       ├── __init__.py
│       └── helper.py
└── plugin_c/                     # 插件 C
    ├── __init__.py
    ├── plugin_c_const.py
    └── plugin_c_factory.py
```

## 开发指南

### 1. 创建插件目录

在 `plugins/` 下创建以插件名命名的目录，如 `plugins/my_plugin/`。

### 2. 定义常量文件

创建 `my_plugin_const.py`，定义应用的基本信息：

```python
# plugins/my_plugin/my_plugin_const.py

APP_ID = "my_plugin"
APP_NAME = "我的插件"
DEFAULT_GROUP = True  # 是否默认进入一条龙列表
NEED_NOTIFY = True    # 是否需要通知

# 可选，默认 False。设为 True 后只允许代码中的固定入口调用
# INTERNAL_APP = True

# 插件元数据（可选，用于 GUI 显示）
PLUGIN_AUTHOR = "作者名"
PLUGIN_HOMEPAGE = "https://github.com/author/my_plugin"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "插件功能描述"
```

### 3. 创建工厂类

创建 `my_plugin_factory.py`（**文件名必须以 `_factory.py` 结尾**）：

```python
# plugins/my_plugin/my_plugin_factory.py

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.context.zzz_context import ZContext  # ✅ 导入主程序模块

from . import my_plugin_const      # ✅ 相对导入
from .my_plugin import MyPlugin    # ✅ 相对导入


class MyPluginFactory(ApplicationFactory):
    def __init__(self, ctx: ZContext):
        super().__init__(my_plugin_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> MyPlugin:
        return MyPlugin(self.ctx)
```

### 应用入口字段

| `DEFAULT_GROUP` | `INTERNAL_APP` | 行为 |
|:---:|:---:|---|
| `True` | `False` | 默认进入一条龙，也可在通用“应用运行”页面及后端、HTTP、MCP 中选择 |
| `False` | `False` | 不进入一条龙，只在上述通用独立应用入口中选择 |
| `False` | `True` | 不进入通用列表，只允许专用页面、父应用或系统代码按固定 `app_id` 调用 |

`INTERNAL_APP` 省略时为 `False`。`DEFAULT_GROUP=True` 与 `INTERNAL_APP=True` 是非法组合，插件会加载失败。底层 `run_application()` 仍可运行 internal 应用，限制只作用于通用选择入口。

### 运行记录

`DEFAULT_GROUP=True` 的普通插件不用实现 `create_run_record()`。父工厂会创建基础 `AppRunRecord`，自动使用当前区服刷新时间划分游戏日；一条龙会根据记录跳过当天已经成功的应用。

`DEFAULT_GROUP=False` 的插件默认没有运行记录，也不会因为缺少记录而加载或运行失败。只有需要每周或其他周期重置、记录业务进度，或自定义完成判定时，才覆盖 `create_run_record()`。

手动入口始终允许执行，并与一条龙共享运行记录；手动成功后，一条龙会跳过同一账号当天已经完成的应用。

### 4. 实现应用逻辑

```python
# plugins/my_plugin/my_plugin.py

from one_dragon.base.operation.application_base import Application
from zzz_od.context.zzz_context import ZContext

from .utils.helper import do_something  # ✅ 相对导入子模块


class MyPlugin(Application):
    def __init__(self, ctx: ZContext):
        Application.__init__(self, ctx, "my_plugin", node_max_retry_times=3)

    def _execute_one_round(self):
        do_something()
        return self.round_success()
```

## 注意事项

1. **文件命名**：工厂文件必须以 `_factory.py` 结尾
2. **const 字段**：必须定义 `APP_ID`, `APP_NAME`, `DEFAULT_GROUP`, `NEED_NOTIFY`；`INTERNAL_APP` 可选，默认 `False`
3. **入口组合**：`DEFAULT_GROUP` 和 `INTERNAL_APP` 不能同时为 `True`
4. **`__init__.py`**：建议添加以支持相对导入，无 `__init__.py` 时会自动创建命名空间包
5. **模块名唯一性**：插件包名（目录名）应该唯一，避免与其他插件或主程序模块冲突
6. **备份**：此目录被 `.gitignore` 忽略，请自行备份
7. **热重载**：刷新应用时会卸载整个插件包并重新加载
8. **factory 层级**：第三方插件只注册插件根第一层的唯一 `_factory.py`，子目录中的 `_factory.py` 不会被扫描
