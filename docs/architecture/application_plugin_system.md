# 应用插件系统设计文档

## 概述

应用插件系统提供了一种动态发现和注册应用的机制，允许在运行时刷新应用列表，而不需要在代码中硬编码应用注册逻辑。系统还支持通过 GUI 界面导入第三方插件。

## 核心组件

### ApplicationPluginManager

应用插件管理器，负责扫描、加载和刷新应用工厂。

**文件位置**: `src/one_dragon/base/operation/application/application_plugin_manager.py`

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

### 内置应用目录

内置应用位于 `zzz_od/application/` 目录下，由版本控制管理：

```
zzz_od/
├── application/           # 内置应用（版本控制）
│   ├── my_app/
│   │   ├── my_app_const.py
│   │   └── my_app_factory.py
│   └── another_app/
│       └── ...
└── plugins/               # 第三方插件（gitignore）
    └── ...
```

### 第三方插件目录

第三方插件位于 `zzz_od/plugins/` 目录下，该目录被 `.gitignore` 忽略：

```
plugins/
├── __init__.py            # 保留
├── README.md              # 保留
└── my_plugin/             # 用户安装的插件
    ├── my_plugin_const.py
    └── my_plugin_factory.py
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

第三方插件需要添加额外的元数据信息：

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

框架会自动查找上下文类所在目录的同级 `application` 目录。例如：
- `zzz_od/context/zzz_context.py` → 扫描 `zzz_od/application/`

### 3. 运行时刷新应用

可以在运行时调用 `refresh_application_registration()` 方法刷新应用列表：

```python
# 刷新应用注册
ctx.refresh_application_registration()
```

这会：
1. 清空现有的应用注册
2. 重新扫描插件目录
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

如果需要自定义插件目录，可以覆盖 `get_application_plugin_dirs()` 方法：

```python
class MyContext(OneDragonContext):

    def get_application_plugin_dirs(self):
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
