# 应用插件系统架构

> 本文档描述应用插件系统的内部架构。开发指引请参考 [application_plugin_guide.md](../../guides/application_plugin_guide.md)。

---

## 概述

应用插件系统提供了一种动态发现和注册应用的机制，允许在运行时刷新应用列表，而不需要在代码中硬编码应用注册逻辑。

## 插件来源

| 来源 | 目录位置 | 加载方式 | 相对导入 | 导入主程序 |
|------|----------|----------|----------|------------|
| **BUILTIN** | `src/zzz_od/application/` | `spec_from_file_location` | 需完整路径 | ✅ |
| **THIRD_PARTY** | `plugins/` (项目根目录) | `spec_from_file_location` | ✅ 支持 | ✅ |

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
- `app_const`: 应用常量模块（`types.ModuleType`），自动解析 `REQUIRED_CONST_FIELDS` 中定义的字段

**类常量**:
- `REQUIRED_CONST_FIELDS`: app_const 模块必须定义的字段（`APP_ID`, `APP_NAME`, `DEFAULT_GROUP`, `NEED_NOTIFY`）
- `OPTIONAL_PLUGIN_FIELDS`: 可选的插件元数据字段（`PLUGIN_AUTHOR`, `PLUGIN_HOMEPAGE`, `PLUGIN_VERSION`, `PLUGIN_DESCRIPTION`）
- 可选 app 常量字段：`PRIORITY`（整数，默认组 app 的排序优先级）

## 目录结构

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
        ├── __init__.py
        ├── my_plugin_const.py
        ├── my_plugin_factory.py   # 只扫描插件根第一层
        ├── my_plugin.py
        └── sub/
            ├── __init__.py
            └── helper.py          # 普通子模块，不扫描子目录 factory
```

## 应用分组

### 默认组应用 (default_group=True)

- 会出现在"一条龙"运行列表中
- 可以被用户排序和启用/禁用
- 适用于：体力刷本、咖啡店、邮件等日常任务
- 可选定义 `PRIORITY` 整数；数值越小越靠前。显式 priority 相同的 app 按 `app_id` 排序，未定义 priority 的 app 排在全部显式 priority app 之后。
- priority 只决定初始默认/候选顺序，不会覆盖用户保存的应用组顺序。

可运行以下开发入口查看内置应用与 `plugins/` 中第三方应用的实际 priority：

```shell
uv run python src/zzz_od/application/devtools/application_priority_scanner.py
```

入口只解析应用目录中的 factory/const 文件，不会初始化游戏上下文或启动 GUI。输出按 priority 排序，并包含默认组、来源、app ID、名称和 const 文件位置。

### 非默认组应用 (default_group=False)

- 默认不会出现在"一条龙"运行列表中
- 如果某个实例的一条龙配置文件中已经存在该应用、状态为启用且应用仍然注册，则继续显示
- 配置中已禁用的非默认组应用会被永久移除，不会再次加入一条龙列表
- 从配置文件中不存在的非默认组应用不会自动加入一条龙列表
- 适用于：自动战斗、闪避助手、截图工具等独立工具

## 插件加载机制

所有插件统一使用 `importlib.util.spec_from_file_location()` 加载。
模块名通过 `factory_file.relative_to(module_root)` 统一计算，BUILTIN 和 THIRD_PARTY 使用相同的逻辑。

### 模块根目录 (module_root)

- **BUILTIN**: 调用 `find_src_dir()` 反向查找路径中最后一个 `src` 目录作为 module_root
- **THIRD_PARTY**: 使用扫描根目录（如 `plugins/`）作为 module_root

### 内置插件 (BUILTIN)

模块名从 `src` 目录开始计算：

```
src/zzz_od/application/my_app/my_app_factory.py
→ module_root: src/
→ 模块名: zzz_od.application.my_app.my_app_factory
```

### 第三方插件 (THIRD_PARTY)

将 `plugins/` 目录加入 `sys.path`，模块名从 plugins 目录开始计算。第三方插件只发现 `plugins/<插件根>/*_factory.py`；插件根内的嵌套子目录仍可作为普通 Python 子包导入，但其中的 factory 不会注册。

```
plugins/my_plugin/my_plugin_factory.py
→ module_root: plugins/
→ 模块名: my_plugin.my_plugin_factory

plugins/my_plugin/sub/helper.py
→ 可由 my_plugin 内的代码导入，不参与 factory 发现
```

### 中间包加载

`import_module_from_file()` 在加载工厂模块前，会确保所有中间包都已注册到 `sys.modules`：

1. 如果中间目录有 `__init__.py`，使用 `spec_from_file_location` 加载
2. 如果没有 `__init__.py`，创建命名空间包（设置 `__path__` 和 `__package__`）
3. 已在 `sys.modules` 中的包会被跳过

### 热更新卸载策略

`_get_unload_prefix()` 确定模块卸载范围：

- **THIRD_PARTY**: 卸载整个插件包（如 `my_plugin` 及其所有子模块）
- **BUILTIN**: 仅卸载 factory 所在的父包（如 `zzz_od.application.my_app` 下的模块）

**sys.path 管理**:
- `plugins/` 目录仅添加一次到 sys.path
- 使用集合跟踪已添加的路径，避免重复

## 插件导入边界

`PluginImportService` 把 ZIP 或松散目录视为一个“来源”。来源根直接包含唯一 `*_factory.py` 和唯一 `*_const.py` 时，整个来源是一个插件；否则识别多个互不隶属的最外层合法插件根。

- 每个插件根分别映射到 `plugins/<插件名>/`，来源包装目录和根外文件不安装。
- 插件根内的深层 factory 不参与根识别，也不会被第三方运行时扫描。
- 同一来源中大小写不敏感的重复插件目录名会在写盘前拒绝。
- ZIP 中本次选中插件根的解压后总体积受 512 MiB 上限约束。
- 松散目录中的符号链接不能越出所属插件根或形成复制循环；插件根第一层的 Python 文件不能是符号链接。
- 每个插件独立使用临时目录、覆盖和失败回滚；覆盖重试按“来源路径 + 插件名”选择，不重复处理同来源中已成功的插件。

旧的 `preview_plugin()`、`import_plugin()`、`preview_directory()`、`import_directory()` 保持单插件语义；插件管理界面使用一对多来源接口。

## 插件生命周期流程

```
OneDragonContext.init()
│
├── if 首次:  register_application_factory()
│   │
│   ├── factory_manager.discover_factories()
│   │   │
│   │   ├── 遍历 application_plugin_dirs
│   │   │   ├── (zzz_od/application, BUILTIN)
│   │   │   └── (plugins,            THIRD_PARTY)
│   │   │
│   │   ├── _scan_directory()          ─── 对每个目录
│   │   │   ├── BUILTIN: rglob("*.py")
│   │   │   ├── THIRD_PARTY: 枚举真实插件根后 glob("*.py")，跳过符号链接目录和文件
│   │   │   ├── 冲突检测              ─── 同目录多个 factory/const → 跳过 + 记录
│   │   │   └── _load_factory_from_file()  ─── 对每个 factory 文件
│   │   │       ├── resolve_module_name()  ─── 计算 dotted name + module_root
│   │   │       ├── ensure_sys_path()      ─── THIRD_PARTY: plugins → sys.path
│   │   │       ├── import_module_from_file()
│   │   │       │   ├── _ensure_parent_packages()
│   │   │       │   └── spec_from_file_location + exec_module
│   │   │       └── _find_factory_in_module()
│   │   │           ├── 找到 ApplicationFactory 子类 → 实例化
│   │   │           └── _register_plugin_metadata()
│   │   │               ├── 读取同目录 *_const.py
│   │   │               ├── APP_ID 唯一性检查
│   │   │               └── 可选元数据 (author, version, ...)
│   │   │
│   │   └── return (non_default_factories, default_factories)
│   │
│   └── run_context.registry_application(factories)
│       └── 注册到 _factory_map: {app_id: factory}
│
└── ... 后续初始化 (OCR, 控制器, ...)
```

## 运行时刷新流程

```
refresh_application_registration()
│
├── run_context.clear_applications()         # 清空工厂注册表
├── factory_manager.discover_factories(reload_modules=True)
│   ├── _plugin_infos.clear()                # 清空元数据
│   ├── _scan_failures.clear()               # 清空失败记录
│   └── _scan_directory(...)                  # 重新扫描
│       └── _load_factory_from_file(...)
│           └── _unload_plugin_modules()      # 先卸载旧模块
│               ├── THIRD_PARTY: 卸载整个包 (my_plugin.*)
│               └── BUILTIN: 卸载当前应用目录 (zzz_od.application.xxx.*)
│
├── run_context.registry_application(...)     # 重新注册
├── app_group_manager.set_default_apps(...)   # 更新默认组
├── app_group_manager.clear_config_cache()    # 清除配置缓存
└── del self.__dict__['notify_config']        # 刷新通知配置
```

## 共享工具模块: plugin_module_loader

`src/one_dragon/utils/plugin_module_loader.py` 提供被 `ApplicationFactoryManager` 和 `AppSettingManager` 共同使用的加载函数：

| 函数 | 说明 |
|------|------|
| `resolve_module_name(file, source, base_dir)` | 计算 dotted module name 和 module_root |
| `ensure_sys_path(directory, added_paths)` | 将目录加入 `sys.path`（去重） |
| `import_module_from_file(file, name, root)` | 通过 `spec_from_file_location` 导入；自动创建中间包 |

## 与设置系统的协作

`AppSettingManager`（GUI 层）复用 `factory_manager.plugin_infos` 来发现设置界面：

```
AppSettingManager.discover()
│
├── _discover_providers()
│   ├── 遍历 factory_manager.plugin_infos
│   │   └── 对每个 plugin_info.plugin_dir
│   │       └── 查找 *_app_setting.py 文件
│   │           └── 动态导入，找到 AppSettingProvider 子类
│   │               └── 注册 app_id → handler
│   └── 同样使用 plugin_module_loader 加载模块
│
└── ready.emit()     # Signal 通知 UI 层可以显示设置按钮
```

详见 [application_setting_guide.md](../../guides/application_setting_guide.md)。

## 数据流总览

```
┌──────────────────────────────────────────────────────────┐
│                    OneDragonContext                       │
│                                                          │
│  application_plugin_dirs ──► ApplicationFactoryManager    │
│     (BUILTIN, THIRD_PARTY)        │                      │
│                                   │ discover_factories() │
│                                   ▼                      │
│                         ┌─────────────────┐              │
│                         │ _plugin_infos   │              │
│                         │ {app_id: Info}  │              │
│                         └────────┬────────┘              │
│                                  │                       │
│            ┌─────────────────────┼──────────────────┐    │
│            ▼                     ▼                   │    │
│  ApplicationRunContext    AppSettingManager (GUI)     │    │
│  ┌──────────────────┐    ┌────────────────────┐     │    │
│  │ _factory_map      │    │ _app_setting_map   │     │    │
│  │ {app_id: factory} │    │ {app_id: handler}  │     │    │
│  └────────┬─────────┘    └────────┬───────────┘     │    │
│           │                       │                  │    │
│           ▼                       ▼                  │    │
│     create_application()    show_app_setting()       │    │
│     create_config()         (INTERFACE / FLYOUT)     │    │
│     create_run_record()                              │    │
└──────────────────────────────────────────────────────────┘
```

## 错误处理汇总

| 场景 | 行为 |
|------|------|
| 目录不存在 | 跳过 |
| 同目录多个 factory/const 文件 | 整个目录跳过，记录到 `scan_failures` |
| 模块导入失败 | 记录到 `scan_failures`，继续扫描其他文件 |
| 缺少 `*_const.py` | `ImportError`，记录到 `scan_failures` |
| const 缺少必需字段 | 工厂 `__init__` 抛出 `AttributeError`，记录到 `scan_failures` |
| APP_ID 重复 | `ImportError`（先注册者胜），记录到 `scan_failures` |
| 第三方插件直接放在 plugins 根目录 | `ImportError` |
| factory 模块中无 ApplicationFactory 子类 | 记录 "No ApplicationFactory subclass found" |

所有失败都不会中断整体扫描流程，可通过 `factory_manager.scan_failures` 查看详情。
