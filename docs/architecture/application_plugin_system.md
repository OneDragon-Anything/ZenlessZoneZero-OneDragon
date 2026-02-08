# 应用插件系统设计文档

## 概述

应用插件系统提供了一种动态发现和注册应用的机制，允许在运行时刷新应用列表，而不需要在代码中硬编码应用注册逻辑。系统还支持通过 GUI 界面导入第三方插件。

## 插件来源

系统支持两种插件来源：

| 来源 | 目录位置 | 加载方式 | 相对导入 | 导入主程序 |
|------|----------|----------|----------|------------|
| **BUILTIN** | `src/zzz_od/application/` | `spec_from_file_location` | 需完整路径 | ✅ |
| **THIRD_PARTY** | `plugins/` (项目根目录) | `spec_from_file_location` | ✅ 支持 | ✅ |

### 第三方插件特性

第三方插件位于项目根目录的 `plugins/` 目录下，使用 `spec_from_file_location` 加载：

```python
# plugins/my_plugin/utils.py
def helper():
    return "hello"

# plugins/my_plugin/my_plugin_factory.py
from .utils import helper                    # ✅ 相对导入可用
from one_dragon.xxx import yyy               # ✅ 可以导入主程序模块
from zzz_od.context.zzz_context import ZContext  # ✅ 可以导入主程序模块
```

## 核心组件

### ApplicationFactoryManager

应用工厂管理器，负责扫描和加载应用工厂。

**文件位置**: `src/one_dragon/base/operation/application/application_factory_manager.py`

**主要功能**:
- `discover_factories()`: 扫描所有插件目录，发现并加载应用工厂
- `plugin_infos`: 获取所有已加载的插件信息
- `third_party_plugins`: 获取第三方插件列表
- `scan_failures`: 获取最近一次扫描的失败记录

> 注意：刷新/注册应用的完整流程由 `OneDragonContext.refresh_application_registration()` 编排，
> `ApplicationFactoryManager` 仅负责工厂的发现和加载。

**内部方法**:
- `_scan_directory()`: 扫描单个目录，检测冲突，加载工厂
- `_load_factory_from_file()`: 从文件加载工厂类，解析模块路径
- `_import_module_from_file()`: 统一的模块导入，自动加载所有中间包
- `_find_factory_in_module()`: 在模块中查找并实例化工厂类（每个模块最多一个）
- `_register_plugin_metadata()`: 验证 const 字段、检测重复 APP_ID、注册到 `_plugin_infos`
- `_get_unload_prefix()`: 确定热更新时需要卸载的模块前缀

### PluginInfo

插件信息数据模型，存储插件的元数据。

**文件位置**: `src/one_dragon/base/operation/application/plugin_info.py`

**属性**:
- `app_id`, `app_name`, `default_group`: 核心信息
- `author`, `homepage`, `version`, `description`: 插件元数据
- `plugin_dir`: 插件目录路径
- `source`: 插件来源（BUILTIN/THIRD_PARTY）
- `is_third_party`: 是否为第三方插件

### ApplicationFactory

应用工厂基类。

**文件位置**: `src/one_dragon/base/operation/application/application_factory.py`

**构造参数**:
- `app_id`: 应用唯一标识符
- `app_name`: 显示名称
- `default_group`: 是否属于默认应用组（一条龙运行列表），默认为 `True`
- `need_notify`: 是否需要通知，默认为 `False`

## 目录结构

### 完整目录结构

```
project_root/
├── src/
│   └── zzz_od/
│       └── application/       # 内置应用（BUILTIN，版本控制）
│           ├── my_app/
│           │   ├── my_app_const.py
│           │   └── my_app_factory.py
│           └── battle_assistant/   # 支持嵌套子目录
│               ├── auto_battle/
│               │   └── auto_battle_app_factory.py
│               └── dodge_assistant/
│                   └── dodge_assistant_factory.py
└── plugins/                   # 第三方插件（THIRD_PARTY，gitignore）
    └── my_plugin/
        ├── __init__.py        # 推荐添加（无 __init__.py 时自动创建命名空间包）
        ├── my_plugin_const.py
        ├── my_plugin_factory.py
        ├── my_plugin.py
        └── sub/               # 支持嵌套子目录
            ├── __init__.py
            ├── sub_feature_const.py
            ├── sub_feature_factory.py
            └── helpers/
                └── utils.py
```

### 第三方插件目录

第三方插件位于项目根目录的 `plugins/` 目录下，该目录被 `.gitignore` 忽略：

```
plugins/
├── README.md              # 说明文档
└── my_plugin/             # 用户安装的插件
    ├── __init__.py
    ├── my_plugin_const.py
    ├── my_plugin_factory.py
    └── my_plugin.py
```

## 使用方式

### 1. 创建新应用（内置）

#### 步骤 1: 创建 const 文件

在应用目录下创建 `xxx_const.py` 文件，定义应用的基本信息：

```python
# src/zzz_od/application/my_app/my_app_const.py

APP_ID = "my_app"
APP_NAME = "我的应用"
DEFAULT_GROUP = True  # 是否属于默认应用组（一条龙列表）
NEED_NOTIFY = True    # 是否需要通知
```

> 字段顺序和必须字段请参考 `app_const_schema.py`。

**说明**:
- `DEFAULT_GROUP = True`: 应用会出现在一条龙运行列表中
- `DEFAULT_GROUP = False`: 应用不会出现在一条龙列表中（如工具类应用）
- `NEED_NOTIFY = True`: 应用支持发送通知

#### 步骤 2: 创建工厂类

在应用目录下创建 `xxx_factory.py` 文件：

```python
# src/zzz_od/application/my_app/my_app_factory.py

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.application.my_app import my_app_const
from zzz_od.application.my_app.my_app import MyApp

class MyAppFactory(ApplicationFactory):

    def __init__(self, ctx):
        ApplicationFactory.__init__(
            self,
            app_id=my_app_const.APP_ID,
            app_name=my_app_const.APP_NAME,
            default_group=my_app_const.DEFAULT_GROUP,
            need_notify=my_app_const.NEED_NOTIFY,
        )
        self.ctx = ctx

    def create_application(self, instance_idx, group_id):
        return MyApp(self.ctx)
```

**重要**:
- 文件名必须以 `_factory.py` 结尾
- 必须在构造函数中传递 `default_group` 和 `need_notify` 参数（从 const 模块读取）

### 2. 创建第三方插件

第三方插件放在项目根目录的 `plugins/` 目录下，支持相对导入和导入主程序模块：

```
plugins/
└── my_plugin/
    ├── __init__.py           # 推荐添加
    ├── my_plugin_const.py
    ├── my_plugin_factory.py
    ├── my_plugin.py
    └── helpers/
        ├── __init__.py
        └── utils.py
```

```python
# my_plugin/my_plugin_const.py

APP_ID = "my_plugin"
APP_NAME = "我的插件"
DEFAULT_GROUP = True
NEED_NOTIFY = True

# 插件元数据（可选，用于 GUI 显示）
PLUGIN_AUTHOR = "作者名"
PLUGIN_HOMEPAGE = "https://github.com/author/my_plugin"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "插件功能描述"
```

```python
# my_plugin/my_plugin_factory.py
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.context.zzz_context import ZContext  # ✅ 可以导入主程序模块

from .helpers.utils import calculate_damage  # ✅ 相对导入可用
from . import my_plugin_const                 # ✅ 相对导入 const
from .my_plugin import MyPlugin


class MyPluginFactory(ApplicationFactory):
    def __init__(self, ctx: ZContext):
        super().__init__(
            app_id=my_plugin_const.APP_ID,
            app_name=my_plugin_const.APP_NAME,
            default_group=my_plugin_const.DEFAULT_GROUP,
            need_notify=my_plugin_const.NEED_NOTIFY,
        )
        self.ctx = ctx

    def create_application(self, instance_idx, group_id):
        return MyPlugin(self.ctx)
```

**第三方插件优势**:
- ✅ 完整支持相对导入 (`from .xxx import yyy`)
- ✅ 可以导入主程序模块 (`from one_dragon.xxx`, `from zzz_od.xxx`)
- ✅ 更好的代码组织（可以有子目录）
- ✅ 独立于 src 目录，开发体验接近独立项目

详细的开发指南请参考 `plugins/README.md`。

### 3. 通过 GUI 导入插件

1. 打开设置 → 插件管理
2. 点击"导入插件"按钮
3. 选择一个或多个 `.zip` 格式的插件压缩包
4. 插件会自动解压到 `plugins` 目录并注册

### 4. 运行时刷新应用

可以在运行时调用 `refresh_application_registration()` 方法刷新应用列表：

```python
# 刷新应用注册
ctx.refresh_application_registration()
```

这会：
1. 清空现有的应用注册
2. 重新扫描插件目录（`application` 和 `plugins`）
3. 重新加载所有工厂模块（支持代码热更新）
4. 重新注册所有应用
5. 更新默认应用组配置

## 应用分组

### 默认组应用 (default_group=True)

- 会出现在"一条龙"运行列表中
- 可以被用户排序和启用/禁用
- 适用于：体力刷本、咖啡店、邮件等日常任务

### 非默认组应用 (default_group=False)

- 不会出现在"一条龙"运行列表中
- 作为独立工具使用
- 适用于：自动战斗、闪避助手、截图工具等

## GUI 插件管理

### 插件管理界面

**文件位置**: `src/zzz_od/gui/view/setting/setting_plugin_interface.py`

**功能**:
- 显示已安装的第三方插件列表
- 导入插件（支持多选 zip 文件）
- 删除插件
- 刷新插件列表
- 打开插件目录
- 跳转到插件主页

### 插件 zip 包结构

有效的插件 zip 包应包含以下结构：

```
my_plugin.zip
└── my_plugin/
    ├── __init__.py        # 可选
    ├── my_plugin_const.py # 必须包含 APP_ID, APP_NAME, DEFAULT_GROUP, NEED_NOTIFY
    ├── my_plugin_factory.py # 必须，工厂类
    └── my_plugin.py       # 应用实现
```

## 自定义插件目录

默认的插件目录通过 `application_plugin_dirs` 属性（`@cached_property`）自动计算。如果需要自定义，可以在子类中覆盖：

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
            (Path(__file__).parent.parent / 'custom_apps', PluginSource.THIRD_PARTY),  # 额外的插件目录
        ]
```

## 注意事项

1. **文件命名**: 工厂文件必须以 `_factory.py` 结尾
2. **一模块一工厂**: 每个 `_factory.py` 文件中应只定义一个 `ApplicationFactory` 子类
3. **const 必须字段**: 必须定义 `APP_ID`, `APP_NAME`, `DEFAULT_GROUP`, `NEED_NOTIFY`（见 `app_const_schema.py`）
4. **字段顺序**: const 文件字段顺序统一为 `APP_ID → APP_NAME → DEFAULT_GROUP → NEED_NOTIFY`
5. **模块缓存**: 刷新应用时会重新加载模块，支持代码热更新
6. **错误处理**: 工厂实例化失败时异常会被记录到 `scan_failures` 并跳过，不会影响其他插件
7. **APP_ID 唯一性**: 重复的 APP_ID 会被 `_register_plugin_metadata` 检测并拒绝，后来者不加载
8. **第三方插件**: 第三方插件目录被 gitignore，用户需要自行备份
9. **插件元数据**: 建议填写 `PLUGIN_AUTHOR`、`PLUGIN_VERSION` 等元数据以便用户识别
10. **相对导入**: 第三方插件完整支持相对导入，建议添加 `__init__.py` 文件
11. **导入主程序**: 第三方插件可以直接 `from one_dragon.xxx` 或 `from zzz_od.xxx` 导入主程序模块
12. **同目录冲突**: 同一目录下不允许多个 `_factory.py` 或 `_const.py` 文件，发现时整个目录被跳过

## 插件加载机制

所有插件统一使用 `importlib.util.spec_from_file_location()` 加载。
模块名通过 `factory_file.relative_to(module_root)` 统一计算，BUILTIN 和 THIRD_PARTY 使用相同的逻辑。

### 模块根目录 (module_root)

`_load_factory_from_file()` 在加载前确定模块名的起算目录，使用共享的 `find_src_dir()` 工具函数：

- **BUILTIN**: 调用 `find_src_dir()` 反向查找路径中最后一个 `src` 目录作为 module_root
- **THIRD_PARTY**: 使用扫描根目录（如 `plugins/`）作为 module_root

### 内置插件 (BUILTIN)

模块名从 `src` 目录开始计算：

```
src/zzz_od/application/my_app/my_app_factory.py
→ module_root: src/
→ 模块名: zzz_od.application.my_app.my_app_factory

src/zzz_od/application/battle_assistant/auto_battle/auto_battle_app_factory.py
→ module_root: src/
→ 模块名: zzz_od.application.battle_assistant.auto_battle.auto_battle_app_factory
```

### 第三方插件 (THIRD_PARTY)

将 `plugins/` 目录加入 `sys.path`，模块名从 plugins 目录开始计算。
**支持嵌套子目录**，中间包会自动加载或创建为命名空间包：

```
plugins/my_plugin/my_plugin_factory.py
→ module_root: plugins/
→ 模块名: my_plugin.my_plugin_factory

plugins/my_plugin/sub/sub_feature_factory.py
→ module_root: plugins/
→ 模块名: my_plugin.sub.sub_feature_factory
→ 中间包: my_plugin（加载 __init__.py）、my_plugin.sub（加载 __init__.py 或创建命名空间包）
```

### 中间包加载

`_import_module_from_file()` 在加载工厂模块前，会确保所有中间包都已注册到 `sys.modules`：

1. 如果中间目录有 `__init__.py`，使用 `spec_from_file_location` 加载
2. 如果没有 `__init__.py`，创建命名空间包（设置 `__path__` 和 `__package__`）
3. 已在 `sys.modules` 中的包会被跳过

### 热更新卸载策略

`_get_unload_prefix()` 确定模块卸载范围：

- **THIRD_PARTY**: 卸载整个插件包（如 `my_plugin` 及其所有子模块）
- **BUILTIN**: 仅卸载 factory 所在的父包（如 `zzz_od.application.my_app` 下的模块）

```python
# 加载过程
# 1. 解析 module_root
module_root = find_src_dir(factory_file) if source == BUILTIN else base_dir

# 2. 统一计算模块名
relative_path = factory_file.relative_to(module_root)
module_name = '.'.join(relative_path.parts[:-1] + [factory_file.stem])

# 3. 加载所有中间包 + 工厂模块
module = _import_module_from_file(factory_file, module_name, module_root)
```

**导入主程序模块**:
- 由于程序运行时 `src/` 目录已在 `sys.path` 中，插件可以直接 `from one_dragon.xxx` 或 `from zzz_od.xxx`

**sys.path 管理**:
- `plugins/` 目录仅添加一次到 sys.path
- 使用集合跟踪已添加的路径，避免重复
- 路径会保留以支持插件运行时的模块导入
