# Screen Scope 设计方案

## 1. 背景与问题

### 现状
- 所有 70 个 screen 注册在全局 `ScreenContext` 中
- 应用通过硬编码字符串引用 screen（如 `'迷失之地-入口'`）
- `round_by_goto_screen` 调用 `get_match_screen_name` 时，BFS 遍历可能扫描全部 70 个 screen
- 每次 screen 匹配涉及 OCR 或模板匹配，开销大

### 三个核心问题

| 问题 | 原因 | 影响 |
|------|------|------|
| 插件无法管理 screen | screen 只从 `assets/game_data/screen_info/` 加载，无注入点 | 第三方插件无法定义画面 |
| 全局污染 | 所有 screen 同一命名空间，BFS 搜索和路由计算混杂不相关 screen | 识别变慢 |
| 全局跳转慢 | `round_by_goto_screen` 无范围限制，BFS 可能检查大量无关 screen | 每轮匹配耗时高 |

## 2. 设计方案

### 核心概念：全局 screen 与局部 screen

```
┌─────────────────────────────────────────────┐
│              ScreenContext                   │
│                                              │
│  ┌────────────────────┐  ┌───────────────┐  │
│  │   全局 screen       │  │  局部 screen   │  │
│  │   (app_id 为空)     │  │  (app_id 非空) │  │
│  │                    │  │               │  │
│  │  菜单              │  │  迷失之地-入口  │  │
│  │  大世界-普通        │  │  迷失之地-大世界│  │
│  │  快捷手册-训练      │  │  零号空洞-入口  │  │
│  │  快捷手册-作战      │  │  随便观-入口    │  │
│  │  ...               │  │  ...           │  │
│  └────────────────────┘  └───────────────┘  │
│                                              │
│  活跃范围 = 全局 ∪ 当前应用的局部              │
└─────────────────────────────────────────────┘
```

- **全局 screen**：YAML 中 `app_id` 为空。始终参与匹配，如菜单、大世界、快捷手册等导航骨架
- **局部 screen**：YAML 中 `app_id` 非空。仅在对应应用运行时参与匹配

### 自动推导机制

1. **reload 或插件画面重建后**自动计算全局集合：`_global_screen_names = {无 app_id 的 screen}`
2. **应用启动** 时 `enter_scope(app_id)`，自动收集 `app_id` 匹配的局部 screen
3. **应用停止** 时 `exit_scope()`，恢复全量匹配

无需代码中手动维护字符串列表。

## 3. 数据模型变更

### ScreenInfo 新增 `app_id` 字段

```yaml
# 全局 screen（不设 app_id 或为空）
- screen_id: menu
  screen_name: 菜单
  pc_alt: false
  area_list: ...

# 局部 screen（设置 app_id）
- screen_id: lost_void_entry
  screen_name: 迷失之地-入口
  app_id: lost_void            # ← 与 Application.app_id 一致
  pc_alt: false
  area_list: ...
```

`app_id` 默认为空字符串，完全向后兼容。

## 4. API 设计

### ScreenContext

```python
class ScreenContext:
    # ---- Screen Scope 管理 ----

    def enter_scope(self, app_id: str) -> None:
        """进入应用 scope
        活跃范围 = 全局 screen + 该 app_id 的局部 screen
        仅当存在匹配的局部 screen 时才启用 scope
        """

    def exit_scope(self) -> None:
        """退出应用 scope，恢复全量匹配"""

    @property
    def active_screen_names(self) -> set[str] | None:
        """当前活跃的 screen 名称集合。None 表示全部活跃"""

    @property
    def active_screen_info_list(self) -> list[ScreenInfo]:
        """当前活跃的 ScreenInfo 列表"""

    def is_screen_active(self, screen_name: str) -> bool:
        """判断某个 screen 是否在活跃范围内"""
```

### Application 生命周期集成

```python
class Application(Operation):
    def handle_init(self):
        # 自动进入 scope（基于 self.app_id）
        self.ctx.screen_loader.enter_scope(self.app_id)
        ...

    def after_operation_done(self, result):
        # 自动退出 scope
        self.ctx.screen_loader.exit_scope()
        ...
```

应用无需额外代码，scope 通过 `app_id` + YAML `app_id` 字段自动匹配。

## 5. 匹配优化

### BFS 搜索优化

`get_match_screen_name_from_last` 中：
- 非活跃 screen **跳过匹配**（避免 OCR/模板匹配开销）
- 非活跃 screen **仍展开邻居**（保持图连通性，确保能找到活跃 screen）
- fallback 遍历仅搜索活跃 screen

### 效果估算

| 场景 | 改动前 | 改动后 |
|------|--------|--------|
| 迷失之地运行时 BFS 匹配范围 | ~70 screen | ~30 screen（全局 ~16 + 局部 ~14） |
| 每轮 OCR/模板匹配次数（最坏） | ~70 次 | ~30 次 |
| Floyd 路由计算 | O(70³) ≈ 34万次 | 不变（全局路由表共用） |

### 路由不变

全局路由表（Floyd）在 reload 或插件画面增删重建时计算，scope 不影响。
`round_by_goto_screen` 使用全局路由表查找路径，scope 仅影响 screen 识别的搜索范围。

## 6. 向后兼容性

| 场景 | 行为 |
|------|------|
| 所有 YAML 未设 `app_id`（当前现状） | 全部为全局 → `enter_scope` 无匹配 → 不启用 scope → 行为不变 |
| 部分 YAML 设了 `app_id` | 该应用启用 scope，其他应用不受影响 |
| 应用本身无匹配 screen | `enter_scope` 跳过 → 行为不变 |

**零风险渐进迁移**：全部不改 YAML 时与现在一模一样，改一个应用的 YAML 只影响该应用。

## 7. 迁移指南

### 步骤 1：给局部 screen 的 YAML 添加 `app_id`

以迷失之地为例，给 14 个 screen 各加一行：

```yaml
- screen_id: lost_void_entry
  screen_name: 迷失之地-入口
  app_id: lost_void              # ← 新增
  pc_alt: false
  area_list: ...
```

### 步骤 2：完成

无需修改任何 Python 代码。`Application.handle_init` 自动调用 `enter_scope(self.app_id)`，
匹配到 YAML 中 `app_id: lost_void` 的 screen，scope 自动生效。

### 建议迁移顺序

实际业务 screen 的 local 化范围与分层迁移顺序见
[screen_scope_rollout.md](screen_scope_rollout.md)。

## 8. 插件 Screen 加载

插件画面按「来源目录」登记，需要时全量重建；插件安装/卸载不触发主画面配置的 `reload`。
语义参考 MaaFramework `ProjectInterfaceV2` 的 `resource.path` 数组：资源按来源加载，
单个来源增删只重建资源层，不重载全局配置。

### 加载机制

```
OneDragonContext.init()
├── register_application_factory()         ← 扫描插件，填充 plugin_infos
├── _load_plugin_screens(rebuild=False)    ← 先登记插件画面来源目录（不重建）
└── reload_screens()                       ← 一次建好主 screen YAML + 插件画面

refresh_application_registration()           ← 运行时安装/卸载/更新插件
├── clear_applications + discover_factories  ← 重新扫描
└── _load_plugin_screens()                 ← 只重设来源并重建插件画面，不 reload 主配置
```

- 来源表 `_extra_screen_dirs`：目录 → `default_app_id`，只由 `load_extra_screen_dir()` /
  `set_extra_screen_dirs()` 写。
- 派生表 `_extra_screen_ids`（画面 id）与 `_extra_screen_paths`（id → yml）：
  每次 `_load_extras()` 全量重建，任何分支不手改。
- 重建是「先构建、成功后整体替换」：`_build_base()` / `_build_extras()` 只读文件或内存，
  构建失败（base YAML/ScreenInfo 抛错等）时保留原状态并返回失败；成功后 `_apply_state()`
  一次性替换四张内存表、两张派生表并重建路由/global/scope。
- 同名或同 id 冲突时先遍历到的优先；遍历顺序显式按目录路径/文件名 casefold 排序，结果可预测。
  插件画面不覆盖主配置：冲突文件跳过并告警（带 id 与文件路径）。
- 显式重载主配置走 `OneDragonContext.reload_screens()`，返回是否成功；失败时调用方不要继续
  `save()`（devtools 的「更新」已据此处理）。`ScreenContext.reload()` 不建议直接调用。

### 插件目录结构

```
plugins/
  my_plugin/
    __init__.py
    my_plugin_const.py       # APP_ID = 'my_plugin'
    my_plugin_factory.py
    my_plugin.py
    screen_info/             # ← 新增，放 screen YAML
      my_screen.yml
```

### 插件 Screen YAML 示例

```yaml
# plugins/my_plugin/screen_info/my_screen.yml
screen_id: my_plugin_main
screen_name: 我的插件-主界面
# app_id 可省略，自动使用插件的 APP_ID
pc_alt: false
area_list:
  - area_name: 返回按钮
    id_mark: true
    pc_rect: [82, 13, 150, 90]
    template_id: back
    template_sub_dir: menu
    goto_list:
      - 大世界-普通
```

### 冲突处理

- 插件 screen_name 或 screen_id 与主 YAML / 先加载的插件画面冲突时，跳过并输出警告日志，不覆盖已有画面。
- `default_app_id` 仅在 YAML 未显式设置 `app_id` 时使用。
- `save()` 只写主配置：按 `_extra_screen_ids` 排除插件画面；插件画面自身的增删改走
  `_save_extra_screen()`（按 `_extra_screen_paths` 定位文件），不会把主配置写进插件 YAML。

## 9. 文件变更清单

| 文件 | 变更 |
|------|------|
| `src/one_dragon/base/screen/screen_info.py` | `ScreenInfo` 新增 `app_id` 字段 |
| `src/one_dragon/base/screen/screen_loader.py` | `ScreenContext` 新增 scope 管理、插件画面来源表与按来源全量重建（`_load_extras`） |
| `src/one_dragon/base/screen/screen_utils.py` | BFS 匹配适配活跃范围 |
| `src/one_dragon/base/operation/application_base.py` | `Application` 生命周期自动 enter/exit scope |
| `src/one_dragon/base/operation/one_dragon_context.py` | 新增 `_load_plugin_screens()`，init 和 refresh 时加载插件 screen |
