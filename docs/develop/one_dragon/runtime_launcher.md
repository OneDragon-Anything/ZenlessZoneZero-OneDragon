# 集成启动器（RuntimeLauncher）详细设计文档

## 概述

集成启动器把 Python 运行时和第三方依赖放在 `.runtime/` 中，同时保留可独立更新的安装目录 `src/`。为了在外部源码损坏时仍能修复环境，发行包还携带一套完整内置源码。

集成启动器分为三层：

- **启动内核**：冻结在 exe 中的最小代码，负责参数、版本、源码选择、启动监控和进程级回退。
- **外部源码**：安装目录 `src/`，正常模式使用，可由 Git 更新。
- **内置源码**：`.runtime/builtin_src/src/`，构建时从完整 `src/` 复制，只用于恢复模式。

正常模式和恢复模式每次只能选择一棵业务源码树，不按模块混合加载，也不在同一进程中热切换。

## 目录结构

```text
安装目录/
├── OneDragon-RuntimeLauncher.exe
├── .runtime/
│   ├── module_manifest.py
│   ├── builtin_src/
│   │   ├── manifest.json
│   │   └── src/
│   │       ├── one_dragon/
│   │       ├── one_dragon_qt/
│   │       ├── zzz_od/
│   │       └── onnxocr/
│   └── ... Python DLL、pyd 和第三方依赖
└── src/
    ├── one_dragon/
    ├── one_dragon_qt/
    ├── zzz_od/
    └── onnxocr/
```

`RuntimeLauncher.zip` 不带安装目录的外部 `src/`，但必须带 `.runtime/builtin_src`。两个 WithRuntime 包同时带外部 `src/` 和内置源码。

## 冻结启动内核

启动内核源码位于 `src/one_dragon/launcher/runtime_launcher_bootstrap/`，作为启动器子包维护，并与统一版本模块 `src/one_dragon/version.py` 配合。通用层只定义 `RuntimeLauncherProfile` 抽象基类；具体项目在自己的代码层继承它，提供入口模块、显示名称、必要源码文件和必须固定在启动器中的稳定模块。绝区零实现位于 `src/zzz_od/win_exe/runtime_launcher_profile.py`，冻结入口位于 `src/zzz_od/win_exe/runtime_launcher_bootstrap.py`。PyInstaller spec 分析项目侧冻结入口，由它把项目 profile 注入通用启动流程，并把 profile 声明的稳定模块加入 hidden imports。

启动内核负责：

1. 解析 GUI、一条龙、版本和内部恢复参数。
2. 输出冻结版本号。
3. 校验外部源码必要入口。
4. 在 `sys.path` 中只激活选中的源码根。
5. 动态导入业务入口，避免 PyInstaller 把业务源码收进 PYZ。
6. 记录应用是否越过 ready 边界。
7. ready 前失败时写入错误日志，并用新进程进入恢复模式。
8. 校验内置源码版本、运行时标识、文件大小和 SHA-256。

启动内核不依赖 PyInstaller 私有导入器顺序，也不再使用 `KEEP_TREES`、业务模块 `excludes` 或自定义 runtime hook。当前 PyInstaller 版本为 6.21.0，spec 直接分析 `src/zzz_od/win_exe/runtime_launcher_bootstrap.py`，保留 `contents_directory='.runtime'`。项目侧冻结入口及 profile 会进入 PYZ，但正常业务入口和恢复业务入口仍只以字符串声明，不会因此静态收集 `one_dragon_qt`、`zzz_od` 和 `onnxocr` 的业务包树。运行时根据 profile 的入口名称，从外部或内置源码目录动态加载业务代码。

## 源码选择

启动内核通过以下环境变量把选择结果传给业务代码：

- `ONE_DRAGON_SOURCE_ROOT`：当前唯一启用的源码根。
- `ONE_DRAGON_RUNTIME_MODE`：`external` 或 `recovery`。

`one_dragon.utils.runtime_source` 提供统一读取接口。正常模式把安装目录 `src/` 追加到模块搜索路径末尾；恢复模式只追加 `.runtime/builtin_src/src/`。切换前会从 `sys.path` 中移除两棵候选源码树，防止同时存在。项目 profile 会在冻结入口中提前加载，因此启动内核还会根据正常和恢复入口模块名，把选中源码树追加到已缓存业务入口父包的搜索路径末尾。已有冻结路径保持在前面，磁盘源码只补齐未冻结模块。Git、下载、更新、启动器替换事务和恢复编排等稳定模块由 profile 的 `frozen_import_modules` 声明并冻结在启动器中，不随外部业务源码切换；恢复界面及其他业务入口仍从选中的源码树动态加载。

恢复模式设置 `sys.dont_write_bytecode = True`，不在内置快照中写入 `pyc`。

## 正常启动与 ready

正常启动顺序：

1. 校验安装目录 `src/` 和必要入口。
2. 激活外部源码。
3. 调用项目 profile 的 `sync_source()`。需要自动同步的项目自行实现；默认实现不改源码。
4. 如果源码发生变化，清除本轮从外部源码加载的模块并刷新导入缓存。
5. 动态导入 `zzz_od.win_exe.runtime_launcher`。
6. 启动 GUI 或命令行一条龙。
7. 完整上下文初始化成功后，由业务入口回调启动内核标记 ready。

GUI 的 ready 定义为：窗口已经创建，且 `ZContext.init()` 完整成功。命令行一条龙的 ready 定义为同步上下文初始化成功。

ready 前的导入、同步、窗口创建或上下文初始化失败会触发恢复进程。GUI 在 ready 前被用户正常关闭时按正常退出处理，不触发恢复。ready 后的运行错误只显示错误并退出，不自动切换源码。

## 恢复模式

恢复模式由同一个 exe 以内部参数启动，但只加载内置源码。恢复窗口保留项目标题栏，使用固定布局的恢复页面，不再套用纵向滚动资源管理页面；页面左侧显示 160×160 Logo，右侧显示 320×60 一键重装按钮、正式版/测试版通道选择和设置入口，执行时切换为进度环、状态文字和取消按钮，不创建代码同步、启动器下载、OCR 或业务模型卡片。

恢复页面只让用户选择正式版或测试版，不展示具体 tag。点击重装后，服务从代码仓库读取标签并按版本从新到旧检查启动器附件：正式版只尝试稳定标签；测试版先尝试测试标签，全部不存在时再尝试稳定标签。某个标签的启动器附件在所有配置源都返回 404 时自动顺延到下一候选；网络错误或无法确认附件状态时直接报错，不误判为版本不存在。选中可用附件后，下载和代码检出始终使用同一个锁定 tag，不请求 Release 的 `latest` 地址。工作区存在未提交改动时才弹覆盖确认；确认范围绑定当时的路径、状态、暂存对象和文件内容。下载或远程拉取期间工作区发生任何变化时，真正检出代码前必须重新确认，不能沿用第一次授权。确认后锁定界面，只允许查看进度和取消，取消完成后才恢复设置。最终检出前仍可取消；进入代码检出后进入不可取消的提交阶段，必须继续完成启动器替换，避免代码与启动器版本不一致，此时界面会禁用取消按钮。流程先下载、解压并校验启动器包，再按同一 tag 检出代码，最后执行启动器替换并重启。未知来源的旧 exe/.runtime 备份不自动删除。恢复业务核心不依赖 Qt，通过回调通知窗口；进度、阶段、下载源、错误和取消按钮直接显示在恢复窗口内，不再弹出下载队列窗口。

外部源码启动失败原因继续写入启动日志，不在恢复页面上额外叠加说明区或错误文本框。

恢复模式使用 `RecoveryContext`，只提供项目配置、环境配置、仓库服务和 `ModelConfig`。它不继承 `OneDragonContext`，因此不会注册应用、创建 OCR session、控制器、键鼠监听、Overlay、推送服务或自动化运行上下文。

恢复窗口只提供下载设置、版本选择、一键重装和窗口内进度状态，不提供主页、一条龙、应用运行、开发工具、账号或其他设置入口。恢复模式也不加载安装目录第三方插件。

## 内置源码完整性清单

`deploy/generate_builtin_source.py` 在构建后复制完整 `src/`，忽略 `__pycache__` 和 `pyc`，并生成 `.runtime/builtin_src/manifest.json`。

清单记录：

- 清单格式版本；
- 集成启动器发行版本；
- Python 实现、主次版本、平台和机器架构组成的运行时标识；
- 由项目 profile 声明的恢复模式必要入口；
- 每个文件的相对路径、大小和 SHA-256。

恢复启动前由 `BuiltinSourceValidator` 逐项校验。版本、运行时标识、必要入口、文件摘要或清单外文件不一致时，恢复模式停止启动并显示致命错误，不递归回退。启动监督器只负责选择源码树并调用校验器。

## 第三方依赖模块清单

`module_manifest.py` 继续保留。它与内置源码完整性清单职责不同：

- 构建时作为 PyInstaller 的第三方依赖种子；
- 外部源码更新前，用于确认新源码是否需要当前 `.runtime` 中不存在的依赖。

尊重 `sys.path` 只能决定模块从哪棵源码树加载，不能保证对应第三方依赖已经打包。因此，只要外部源码仍能独立更新，模块清单兼容检查就不能删除。

`OneDragon-RuntimeLauncher.spec` 在 Analysis 阶段运行 `generate_module_manifest.py`，但不再扫描并冻结业务包树。`module_manifest.py` 仍作为数据文件写入 `.runtime/`，供 `GitService` 比较目标代码清单。

## 与更新服务的边界

普通模式的资源下载、暂存、替换和回滚仍由 `UpdateService` 与现有资源下载页面负责。附件是否存在由 `launcher_asset_probe` 探测，备份、回滚和清理由 `LauncherUpdateTransaction` 管理；`UpdateService` 只组织这两步。恢复模式的一键重装由不依赖 Qt 的 `RecoveryRepairService` 按选版本、下载校验、确认检出、替换启动器四步编排：它固定同一个 Git tag，检查具体 Release 附件，下载并校验暂存包，按同一 tag 检出代码，最后调用 `UpdateService` 执行备份、替换和回滚。替换事务的标记只在回滚或备份清理确实完成后删除；文件占用等错误导致事务未完成时保留标记，下次启动继续处理。

资源管理页和恢复页共用 `DownloadSourceSettingsGroup` 维护下载源与代理设置。资源页额外保留立即获取免费代理和资源自动下载；恢复页只把同一组件放进设置弹窗。

恢复窗口只通过 Qt 适配器接收恢复服务回调，不复用下载队列弹窗；进度、阶段、下载源、错误和取消操作直接显示在窗口内。`RuntimeLauncher.zip` 中的 `.runtime` 必须包含完整内置源码和对应清单，使最终替换时运行时、内置源码和启动内核保持同一发行版本。

## 发行产物

| 文件 | 内容 | 用途 |
|---|---|---|
| `{version}-WithRuntime-Full.zip` | exe + `.runtime` + 外部 `src` + 内置源码 + 模型 | 首次部署，模型齐全 |
| `{version}-WithRuntime.zip` | exe + `.runtime` + 外部 `src` + 内置源码 | 首次部署，模型按需下载 |
| `RuntimeLauncher.zip` | exe + `.runtime` + 内置源码，不含外部 `src` | 已有环境就地升级 |

发布整理脚本会在打包前确认外部入口、恢复入口、内置清单和发行版本一致。`RuntimeLauncher.zip` 通过排除顶层 `src/` 保留“只有内置源码”的更新包结构；内置快照位于 `.runtime` 内，不会被排除。

## 关键文件

| 文件 | 说明 |
|---|---|
| `src/one_dragon/launcher/runtime_launcher_bootstrap/launcher.py` | 冻结启动内核 |
| `src/one_dragon/launcher/runtime_launcher_bootstrap/profile.py` | 定义项目 profile 抽象基类 |
| `src/zzz_od/win_exe/runtime_launcher_profile.py` | 提供绝区零入口、显示名称和必要源码文件 |
| `src/zzz_od/win_exe/runtime_launcher_bootstrap.py` | 使用绝区零 profile 启动通用内核 |
| `src/one_dragon/version.py` | 统一发行版本 |
| `src/one_dragon/launcher/runtime_launcher_bootstrap/runtime_identity.py` | 运行时标识 |
| `src/one_dragon/launcher/runtime_launcher_bootstrap/builtin_manifest.py` | 内置清单协议 |
| `src/one_dragon/launcher/runtime_launcher_bootstrap/builtin_source_validator.py` | 内置源码清单校验 |
| `src/one_dragon/envs/launcher_asset_probe.py` | 启动器附件存在性探测 |
| `src/one_dragon/envs/launcher_update_transaction.py` | 启动器备份、回滚和清理事务 |
| `src/one_dragon_qt/widgets/setting_card/download_source_settings_group.py` | 资源页和恢复页共用的下载源与代理设置 |
| `deploy/generate_builtin_source.py` | 生成完整内置源码和 SHA-256 清单 |
| `deploy/OneDragon-RuntimeLauncher.spec` | 只冻结启动内核和第三方依赖 |
| `src/zzz_od/win_exe/source_sync.py` | 绝区零外部源码同步策略 |
| `src/one_dragon/utils/runtime_source.py` | 当前源码根和模式读取接口 |
| `src/zzz_od/win_exe/runtime_launcher.py` | 正常业务动态入口 |
| `src/zzz_od/win_exe/recovery_app.py` | 恢复模式发行入口薄封装 |
| `src/zzz_od/context/recovery_context.py` | 恢复专用轻量上下文 |
| `src/one_dragon/envs/recovery_repair_service.py` | 不依赖 Qt 的恢复重装流程 |
| `src/one_dragon_qt/services/recovery_repair_adapter.py` | 恢复服务的 Qt 回调适配 |
| `src/one_dragon_qt/view/recovery_repair_interface.py` | 固定布局恢复界面、进度和取消操作 |
