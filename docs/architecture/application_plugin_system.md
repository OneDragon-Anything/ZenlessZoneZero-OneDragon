# 应用插件系统设计文档

## 概述

应用插件系统提供了一种动态发现和注册应用的机制，允许在运行时刷新应用列表，而不需要在代码中硬编码应用注册逻辑。系统还支持通过 GUI 界面导入第三方插件。

## 插件来源

系统支持两种插件来源：

| 来源 | 目录位置 | 加载方式 | 相对导入 | 导入主程序 |
|------|----------|----------|----------|------------|
| **BUILTIN** | `src/zzz_od/application/` | `import_module` | 需完整路径 | ✅ |
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

应用工厂管理器，负责扫描、加载和刷新应用工厂。

**文件位置**: `src/one_dragon/base/operation/application/application_factory_manager.py`

**主要功能**:
- `add_plugin_dir(plugin_dir)`: 添加插件目录
- `discover_factories()`: 扫描所有插件目录，发现并加载应用工厂
- `refresh_applications()`: 刷新应用注册
- `plugin_infos`: 获取所有已加载的插件信息
- `third_party_plugins`: 获取第三方插件列表

### PluginInfo

插件信息数据模型，存储插件的元数据。

**文件位置**: `src/one_dragon/base/operation/application/plugin_info.py`

**属性**:
- `app_id`, `app_name`, `default_group`: 核心信息
- `author`, `homepage`, `version`, `description`: 插件元数据
- `plugin_dir`: 插件目录路径
- `source`: 插件来源（BUILTIN/THIRD_PARTY）
- `is_third_party`: 是否为第三方插件

### PluginImportService

插件导入服务，处理 zip 文件的导入、解压和验证。

**文件位置**: `src/one_dragon/base/operation/application/plugin_import_service.py`

**主要功能**:
- `import_plugin(zip_path)`: 导入单个插件
- `import_plugins(zip_paths)`: 批量导入插件
- `delete_plugin(plugin_dir)`: 删除插件

### ApplicationFactory

应用工厂基类，新增 `default_group` 参数。

**文件位置**: `src/one_dragon/base/operation/application/application_factory.py`

**新增参数**:
- `default_group`: 是否属于默认应用组（一条龙运行列表），默认为 `True`

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
│           └── another_app/
│               └── ...
└── plugins/                   # 第三方插件（THIRD_PARTY，gitignore）
    └── my_plugin/
        ├── __init__.py        # 推荐添加
        ├── my_plugin_const.py
        ├── my_plugin_factory.py
        ├── my_plugin.py
        └── utils/             # 可以有子目录
            ├── __init__.py
            └── helper.py      # 可使用 from .utils.helper import xxx
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
NEED_NOTIFY = False  # 可选，是否需要通知
DEFAULT_GROUP = True  # 是否属于默认应用组（一条龙列表）
```

**说明**:
- `DEFAULT_GROUP = True`: 应用会出现在一条龙运行列表中
- `DEFAULT_GROUP = False`: 应用不会出现在一条龙列表中（如工具类应用）

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
            default_group=my_app_const.DEFAULT_GROUP,  # 从 const 读取
        )
        self.ctx = ctx

    def create_application(self, instance_idx, group_id):
        return MyApp(self.ctx)
```

**重要**:
- 文件名必须以 `_factory.py` 结尾
- 必须在构造函数中传递 `default_group` 参数

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
    ├── my_plugin_const.py # 必须包含 APP_ID, APP_NAME, DEFAULT_GROUP
    ├── my_plugin_factory.py # 必须，工厂类
    └── my_plugin.py       # 应用实现
```

或者直接在根目录：

```
my_plugin.zip
├── my_plugin_const.py
├── my_plugin_factory.py
└── my_plugin.py
```

## 自定义插件目录

默认的插件目录通过 `application_plugin_dirs` 属性（`@cached_property`）自动计算。如果需要自定义，可以在子类中覆盖：

```python
from functools import cached_property

class MyContext(OneDragonContext):

    @cached_property
    def application_plugin_dirs(self):
        from pathlib import Path
        return [
            Path(__file__).parent.parent / 'application',
            Path(__file__).parent.parent / 'plugins',
            Path(__file__).parent.parent / 'custom_apps',  # 额外的插件目录
        ]
```

## 注意事项

1. **文件命名**: 工厂文件必须以 `_factory.py` 结尾
2. **const 文件**: 必须定义 `DEFAULT_GROUP` 常量
3. **模块缓存**: 刷新应用时会重新加载模块，支持代码热更新
4. **错误处理**: 加载失败的工厂会被跳过并记录警告日志
5. **第三方插件**: 第三方插件目录被 gitignore，用户需要自行备份
6. **插件元数据**: 建议填写 `PLUGIN_AUTHOR`、`PLUGIN_VERSION` 等元数据以便用户识别
7. **相对导入**: 第三方插件完整支持相对导入，建议添加 `__init__.py` 文件
8. **导入主程序**: 第三方插件可以直接 `from one_dragon.xxx` 或 `from zzz_od.xxx` 导入主程序模块

## 插件加载机制

所有插件统一使用 `importlib.util.spec_from_file_location()` 加载。

### 内置插件 (BUILTIN)

模块名从 `src` 目录开始计算：

```
src/zzz_od/application/my_app/my_app_factory.py
→ 模块名: zzz_od.application.my_app.my_app_factory
```

### 第三方插件 (THIRD_PARTY)

将 `plugins/` 目录加入 `sys.path`，模块名为 `插件包名.文件名`：

```
plugins/my_plugin/my_plugin_factory.py
→ 模块名: my_plugin.my_plugin_factory
```

```python
# 加载过程
# 1. 将 plugins 目录加入 sys.path（仅首次）
sys.path.insert(0, "project_root/plugins")

# 2. 使用 spec_from_file_location 加载模块
spec = spec_from_file_location(module_name, file_path, ...)
module = module_from_spec(spec)
spec.loader.exec_module(module)
```

**导入主程序模块**:
- 由于程序运行时 `src/` 目录已在 `sys.path` 中，插件可以直接 `from one_dragon.xxx` 或 `from zzz_od.xxx`

**sys.path 管理**:
- `plugins/` 目录仅添加一次到 sys.path
- 使用集合跟踪已添加的路径，避免重复
- 路径会保留以支持插件运行时的模块导入
