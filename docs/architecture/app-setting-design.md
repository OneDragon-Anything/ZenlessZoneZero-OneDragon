# 应用设置（App Setting）架构设计

## 1. 背景与动机

原实现中，`shared_dialog_manager` 作为 `ZContext`（核心上下文）的 `@cached_property` 存在，
导致 GUI 对象（设置界面类）被核心层直接引用，违反了分层架构的依赖方向。
同时，所有应用的设置映射关系硬编码注册，无法支持第三方插件扩展自己的设置界面。

**目标**：
1. 将设置管理器移出核心上下文，归属 GUI 窗口层
2. 用文件名约定发现（`*_app_setting.py`）替代硬编码注册
3. 内置应用和第三方插件使用完全相同的接入方式

---

## 2. 窗口类层次

```
PhosWindow                          # 纯 UI 框架（标题栏、窗口拖拽）
  └── AppWindowBase                  # 应用通用基础设施（导航栏、界面生命周期）
        ├── InstallerWindowBase      # 安装器，不涉及 app setting
        ├── DevtoolsAppWindow        # 开发工具，不涉及 app setting
        └── MainAppWindowBase        # ★ 主应用基类：持有 AppSettingManager
              └── AppWindow           # ZZZ 游戏主窗口
```

`MainAppWindowBase` 是本次新增的层级，在 `AppWindowBase` 之上添加：
- 接收 `OneDragonContext`
- 启动时自动扫描所有 `*_app_setting.py` 文件
- 构建 `self.app_setting_manager` 实例

---

## 3. 模块位置

```
src/one_dragon/
└── utils/
    └── plugin_module_loader.py         # ★ 共享工具：模块路径解析 + 动态导入

src/one_dragon_qt/
├── services/
│   └── app_setting/                    # ★ 核心服务层（无 UI 依赖）
│       ├── __init__.py
│       ├── app_setting_provider.py     # ABC 基类 + SettingType 枚举
│       ├── app_setting_scanner.py      # 文件扫描（使用 plugin_module_loader）
│       └── app_setting_manager.py      # app_id → handler 映射
├── widgets/
│   └── app_setting/                    # UI 组件
│       └── app_setting_flyout.py       # Flyout 设置弹窗
└── windows/
    └── main_app_window_base.py         # ★ 窗口基类（组装上述组件）
```

---

## 4. 核心组件

### 4.0 plugin_module_loader（共享工具）

**文件**：`one_dragon/utils/plugin_module_loader.py`

从 `ApplicationFactoryManager` 和 `AppSettingScanner` 中提取的共享逻辑：

| 函数 | 职责 |
|------|------|
| `resolve_module_name(file, source, base_dir)` | 根据文件路径和插件来源计算 dotted module name 和 module_root |
| `ensure_sys_path(directory, added_paths)` | 确保目录在 sys.path 中（第三方插件用） |
| `import_module_from_file(file, name, root, reload)` | 动态导入模块，自动处理中间包的 `__init__.py` |

### 4.1 AppSettingProvider

**文件**：`one_dragon_qt/services/app_setting/app_setting_provider.py`

抽象基类，每个应用的设置声明需继承此类：

```python
class SettingType(Enum):
    INTERFACE = "interface"  # 推入二级界面
    FLYOUT = "flyout"       # 弹窗

class AppSettingProvider(ABC):
    app_id: str                # 必须匹配对应 app 的 APP_ID
    setting_type: SettingType  # SettingType.INTERFACE 或 SettingType.FLYOUT

    @staticmethod
    @abstractmethod
    def get_setting_cls() -> type:
        """惰性返回设置界面类（避免循环导入）。"""
        ...
```

### 4.2 AppSettingScanner

**文件**：`one_dragon_qt/services/app_setting/app_setting_scanner.py`

核心函数 `scan_app_settings(plugin_dirs)`:
1. 接收 `list[tuple[Path, PluginSource]]`——与 `ApplicationFactoryManager` 共用相同的插件目录列表
2. 递归扫描每个目录下所有 `*_app_setting.py` 文件
3. 通过 `importlib.util.spec_from_file_location` 动态导入模块
4. 在模块中查找唯一的 `AppSettingProvider` 子类，实例化并收集
5. 检测重复 `app_id`，跳过加载失败的文件（打印警告日志）
6. 返回 `list[AppSettingProvider]`

### 4.3 AppSettingManager

**文件**：`one_dragon_qt/services/app_setting/app_setting_manager.py`

```python
class AppSettingManager:
    def __init__(self, ctx, providers: list[AppSettingProvider]) -> None
    def show_app_setting(self, app_id, parent, group_id, target) -> None
    @property
    def settable_app_ids(self) -> set[str]
```

初始化时根据每个 provider 的 `setting_type` 构建 `app_id → handler` 映射：
- **SettingType.INTERFACE**：界面实例缓存在 `_interface_cache` 中，通过 `PivotNavigatorInterface.push_setting_interface()` 推入二级界面
- **SettingType.FLYOUT**：每次调用 `flyout_cls.show_flyout()` 创建临时弹窗

### 4.4 MainAppWindowBase

**文件**：`one_dragon_qt/windows/main_app_window_base.py`

```python
class MainAppWindowBase(AppWindowBase):
    def __init__(self, ctx: OneDragonContext, win_title, project_config, ...):
        providers = scan_app_settings(ctx.application_plugin_dirs)
        self.app_setting_manager = AppSettingManager(ctx, providers)
        AppWindowBase.__init__(self, ...)
```

---

## 5. 数据流

```
┌─── 启动阶段 ─────────────────────────────────────────────────────┐
│ MainAppWindowBase.__init__(ctx)                                  │
│   │                                                              │
│   ├─ scan_app_settings(ctx.application_plugin_dirs)              │
│   │   │  遍历 BUILTIN + THIRD_PARTY 目录                          │
│   │   │  rglob("*.py") → 过滤 *_app_setting.py                   │
│   │   │  动态导入 → 查找 AppSettingProvider 子类                    │
│   │   └─ 返回 list[AppSettingProvider]                            │
│   │                                                              │
│   └─ AppSettingManager(ctx, providers)                           │
│       遍历每个 provider                                           │
│       interface → _make_push_handler(get_cls)                   │
│       flyout → _make_flyout_handler(get_cls)                     │
│       存入 _app_setting_map[app_id] = handler                    │
└──────────────────────────────────────────────────────────────────┘

┌─── 运行阶段 ─────────────────────────────────────────────────────┐
│ 用户点击设置按钮                                                  │
│   → AppRunCard 发射 setting_clicked(app_id) 信号                  │
│   → OneDragonRunInterface.on_app_setting_clicked(app_id)         │
│       mgr = getattr(self.window(), 'app_setting_manager', None)  │
│       mgr.show_app_setting(app_id, parent, group_id, target)     │
│         interface → 惰性创建界面实例 → 推入 PivotNavigatorInterface     │
│         flyout → flyout_cls.show_flyout(ctx, group_id, target)   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Provider 文件约定

### 命名规则

文件名必须以 `_app_setting.py` 结尾，放在对应 app 目录下：

```
src/zzz_od/application/charge_plan/
    charge_plan_app_factory.py      # 已有
    charge_plan_app_setting.py      # ★ 设置提供者
    charge_plan_const.py            # 已有
```

### Push 模板（二级界面）

```python
from one_dragon_qt.services.app_setting.app_setting_provider import AppSettingProvider, SettingType

class ChargePlanAppSetting(AppSettingProvider):
    app_id = "charge_plan"
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanInterface
        return ChargePlanInterface
```

### Flyout 模板（弹窗）

```python
from one_dragon_qt.services.app_setting.app_setting_provider import AppSettingProvider, SettingType

class DriveDiscDismantleAppSetting(AppSettingProvider):
    app_id = "drive_disc_dismantle"
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.drive_disc_dismantle_setting_flyout import (
            DriveDiscDismantleSettingFlyout,
        )
        return DriveDiscDismantleSettingFlyout
```

### 已注册的 13 个内置 Provider

| 类型 | app_id | 设置界面类 |
|------|--------|-----------|
| interface | `charge_plan` | `ChargePlanInterface` |
| interface | `coffee` | `CoffeeSettingInterface` |
| interface | `notorious_hunt` | `NotoriousHuntSettingInterface` |
| interface | `redemption_code` | `RedemptionCodeSettingInterface` |
| interface | `shiyu_defense` | `ShiyuDefenseSettingInterface` |
| interface | `suibian_temple` | `SuibianTempleSettingInterface` |
| interface | `lost_void` | `LostVoidCombinedSettingInterface` |
| interface | `withered_domain` | `WitheredDomainCombinedSettingInterface` |
| interface | `world_patrol` | `WorldPatrolCombinedSettingInterface` |
| flyout | `drive_disc_dismantle` | `DriveDiscDismantleSettingFlyout` |
| flyout | `intel_board` | `IntelBoardSettingFlyout` |
| flyout | `life_on_line` | `LifeOnLineSettingFlyout` |
| flyout | `random_play` | `RandomPlaySettingFlyout` |

---

## 7. 第三方插件接入

插件开发者在插件目录下创建 `*_app_setting.py`，遵循相同约定即可自动被发现：

```
plugins/my_plugin/
    my_plugin_factory.py            # 插件 factory（已有模式）
    my_plugin_app_setting.py        # ★ 设置提供者
    my_plugin_const.py              # 常量定义（已有模式）
```

无需修改任何框架代码。扫描器会自动在 `THIRD_PARTY` 插件目录中发现并加载。
