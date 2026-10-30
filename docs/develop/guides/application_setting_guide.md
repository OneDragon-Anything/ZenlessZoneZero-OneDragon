# 应用设置（Application Setting）开发指南

本文档介绍如何为应用（Application）添加设置界面，使其在运行列表的卡片上显示齿轮按钮，
点击后弹出设置界面供用户修改配置。

---

## 概念

| 术语 | 说明 |
|---|---|
| **AppSettingProvider** | 设置声明文件，告诉框架"这个应用有设置，用什么方式显示" |
| **AppSettingManager** | 设置管理器，自动扫描所有 Provider 并统一分发 |
| **SettingType.INTERFACE** | 推入式二级界面 — 替换主内容区，通过导航栏返回按钮返回 |
| **SettingType.FLYOUT** | 悬浮卡片 — 轻量弹窗，点击外部关闭 |

---

## 快速开始

只需 **两步**：

### 第一步：创建设置界面

根据需要选择 INTERFACE 或 FLYOUT 模式。

#### INTERFACE 模式

直接复用或新建一个 `BaseInterface` 子类。现有的子界面即可直接使用，无需额外封装。

#### FLYOUT 模式

继承 `AppSettingFlyout`，实现 `_setup_ui()` 和 `init_config()`：

```python
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard


class MyAppSettingFlyout(AppSettingFlyout):

    def _setup_ui(self, layout):
        self.option_a = ComboBoxSettingCard(
            icon='', title='选项A',
            options_enum=MyOptionEnum,
            margins=self.card_margins,        # 使用基类提供的边距
        )
        layout.addWidget(self.option_a)

        self.switch_b = SwitchSettingCard(
            icon='', title='开关B',
            margins=self.card_margins,
        )
        layout.addWidget(self.switch_b)

    def init_config(self):
        config = self.ctx.run_context.get_config(
            app_id='my_app',
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.option_a.init_with_adapter(get_prop_adapter(config, 'option_a'))
        self.switch_b.init_with_adapter(get_prop_adapter(config, 'switch_b'))
```

> `self.card_margins` 和 `self.group_id` 由基类自动提供。
> `init_config()` 在 `show_flyout()` 时被调用，用于读取当前配置初始化控件。

### 第二步：创建 Provider 声明文件

在应用目录下创建 `xxx_app_setting.py` 文件（文件名必须以 `_app_setting.py` 结尾）：

```
src/zzz_od/application/my_app/
    my_app_factory.py           # 已有
    my_app_app_setting.py       # ← 新建
```

文件内容：

```python
from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from my_module.my_app_const import APP_ID


class MyAppSetting(AppSettingProvider):
    app_id = APP_ID                             # 从 const 模块导入
    setting_type = SettingType.FLYOUT       # 或 SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from my_module import MyAppSettingFlyout    # 惰性导入，避免循环引用
        return MyAppSettingFlyout
```

完成。框架会自动发现这个文件并在运行卡片上显示设置按钮。

---

## 选择 INTERFACE 还是 FLYOUT

| 场景 | 推荐 |
|---|---|
| 设置项 ≤ 5 个，无复杂交互 | **FLYOUT** — 快速查看/修改，不离开当前页面 |
| 设置项较多，或需要多标签/列表等复杂布局 | **INTERFACE** — 有完整的页面空间 |
| 设置界面已有现成的 `BaseInterface` 子类 | **INTERFACE** — 直接复用，零成本 |

---

## 多标签设置界面

如果一个应用有多个相关的设置子页面，可以使用 `SegmentedSettingInterface` 将它们组合：

```python
from one_dragon_qt.widgets.segmented_setting_interface import SegmentedSettingInterface


class MyCombinedSettingInterface(SegmentedSettingInterface):
    def __init__(self, ctx):
        super().__init__(
            object_name='my_combined_setting',
            nav_text_cn='我的设置',
            sub_interfaces=[
                SubPageA(ctx),
                SubPageB(ctx),
            ],
        )
```

在 Provider 中引用这个组合界面即可。

---

## 工作原理

### 生命周期

```
应用启动
  │
  ├─ MainAppWindowBase.__init__()
  │    ├─ self.app_setting_manager = AppSettingManager(ctx)   ← 创建空壳
  │    └─ BackNavigationButton                                ← 创建导航栏返回按钮（默认禁用态）
  │
  ├─ CtxInitRunner (后台线程)
  │    ├─ ctx.init()
  │    │    └─ factory_manager.discover_factories()   ← 扫描 *_factory.py
  │    └─ window.on_ctx_ready()
  │         └─ app_setting_manager.discover()
  │              ├─ 遍历 factory_manager.plugin_infos 的目录
  │              ├─ 查找并导入 *_app_setting.py
  │              ├─ 注册 app_id → handler 映射
  │              └─ ready.emit()   ← 通知界面刷新设置按钮
  │
  ├─ 运行界面收到 ready 信号
  │    └─ _update_setting_btn_visibility()   ← 显示/隐藏齿轮按钮
  │
  └─ 用户点击齿轮 (INTERFACE 模式)
       ├─ PivotNavigatorInterface.push_setting_interface()
       │    └─ PageStackWrapper.push_setting()   ← 从右侧滑入动画
       ├─ secondary_state_changed(True)          ← 信号通知窗口
       └─ BackNavigationButton.set_active(True)  ← 返回按钮变为强调色
```

### 扫描规则

- 复用 `factory_manager` 已发现的插件目录（不做独立的全盘扫描）
- 在每个插件目录下查找 `*_app_setting.py`（非递归，仅当前目录）
- 动态导入模块，查找唯一的 `AppSettingProvider` 子类
- 重复的 `app_id` 会打印警告并跳过

### 显示分发

| SettingType | 行为 |
|---|---|
| **INTERFACE** | 通过 `PivotNavigatorInterface.push_setting_interface()` 推入二级页面（从右侧滑入动画），导航栏出现返回按钮，界面实例被缓存复用 |
| **FLYOUT** | 每次调用 `AppSettingFlyout.show_flyout()` 创建新的 `TeachingTip` 弹窗，同一时刻只显示一个 |

---

## GroupIdMixin

设置界面如果需要感知当前分组（group_id），可以混入 `GroupIdMixin`：

```python
from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin

class MySettingInterface(BaseInterface, GroupIdMixin):
    ...
```

`AppSettingManager` 在推入界面前会自动设置 `instance.group_id` 和所有 `sub_interfaces` 的 `group_id`。
Flyout 模式下，`group_id` 通过构造函数传入。

---

## 第三方插件

插件开发者使用完全相同的方式接入，无需修改框架代码：

```
plugins/my_plugin/
    my_plugin_factory.py            # 插件 factory（已有模式）
    my_plugin_app_setting.py        # ← 设置声明
```

扫描器会自动在 `THIRD_PARTY` 插件目录中发现并加载。

---

## 相关源码

| 文件 | 说明 |
|---|---|
| `one_dragon_qt/services/app_setting/app_setting_provider.py` | Provider 基类 + 枚举 |
| `one_dragon_qt/services/app_setting/app_setting_manager.py` | 管理器（扫描/注册/分发） |
| `one_dragon_qt/widgets/app_setting/app_setting_flyout.py` | Flyout 基类 |
| `one_dragon_qt/widgets/segmented_setting_interface.py` | 多标签设置组件 |
| `one_dragon_qt/widgets/page_stack_wrapper.py` | 二级页面推入/弹出栈（含滑入动画） |
| `one_dragon_qt/widgets/back_navigation_button.py` | 导航栏返回按钮 |
| `one_dragon_qt/widgets/pivot_navi_interface.py` | Pivot 导航界面（管理 PageStackWrapper） |
| `one_dragon_qt/widgets/teaching_tip.py` | 自定义 TeachingTip |
| `one_dragon_qt/windows/main_app_window_base.py` | 主窗口基类（返回按钮 + 设置管理器） |
| `one_dragon/utils/plugin_module_loader.py` | 模块动态加载工具 |
