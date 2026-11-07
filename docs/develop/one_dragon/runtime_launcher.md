# 集成启动器（RuntimeLauncher）详细设计文档

## 概述

集成启动器是一种将 Python 运行时直接嵌入发行包的启动方案。与原始启动器（需要用户单独安装 Python 和 uv）不同，集成启动器解压即可运行，适合首次安装或不熟悉 Python 环境的用户。

## 整体架构

### 两种启动器对比

| 特性 | 原始启动器 | 集成启动器 |
|------|-----------|-----------|
| 运行方式 | exe → 子进程调用系统 Python | exe 内嵌 Python，直接 import 运行 |
| Python 环境 | 用户自行安装 | 打包在 `.runtime/` 目录中 |
| 代码加载 | 通过系统 Python 执行 `src/` | 通过运行时钩子注入 `src/` 到 `sys.path` |
| 更新机制 | 只更新源码 | 源码自动更新 + 清单兼容性检查 |
| 发行体积 | exe 很小，虚拟环境约 1GB | exe + .runtime 约 100 MB |

### 继承关系

```
LauncherBase          → 基础参数解析、run() 入口
  └── ExeLauncher     → 版本显示、参数构建、pyuac 管理员提升
        └── RuntimeLauncher  → 集成启动器基类：代码同步、控制台隐藏、致命错误弹窗、模板方法
              └── ZLauncher  → 绝区零专用入口（导入 app.py / zzz_application_launcher.py）
```

- `LauncherBase` 和 `ExeLauncher` 位于 `src/one_dragon/launcher/`，是框架通用代码
- `RuntimeLauncher` 也在框架层，提供集成启动器的通用能力
- `ZLauncher` 在 `src/zzz_od/win_exe/runtime_launcher.py`，是具体游戏的入口

## 打包机制

### PyInstaller 目录模式

集成启动器使用 PyInstaller 的目录模式（非单文件），运行时文件存放在 `.runtime/` 子目录中。最终目录结构如下：

```
安装目录/
├── OneDragon-RuntimeLauncher.exe    ← 启动入口
├── .runtime/                        ← Python 运行时 + 冻结模块
│   ├── module_manifest.py           ← 外部依赖清单
│   ├── config/project.yml           ← 项目配置与运行时协议字段
│   ├── config/repository.yml        ← 项目仓库列表、回退策略和地区预设
│   └── ...                          ← Python DLL、so、pyd 等
└── src/                             ← 源代码目录（通过 git 同步）
    ├── one_dragon/
    ├── one_dragon_qt/
    ├── zzz_od/
    └── onnxocr/
```

### 最小打包策略

为了控制体积和避免冻结代码与 src/ 中的源码冲突，spec 文件只保留极少量必须冻结的模块，其余全部排除。

打包保留的模块（KEEP_TREES）：
- `one_dragon.launcher` — 启动器自身需要的代码
- `one_dragon.version` — 版本号

这些模块及其所有父包和子模块会被保留，其余 `one_dragon.*`、`zzz_od.*` 等全部排除。

### 运行时钩子与路径注入

`hook_path_inject.py` 是 PyInstaller 的 runtime_hook，在主脚本执行前运行，完成两件事：

1. 将 `src/` 加入 `sys.path` — 使 `zzz_od`、`one_dragon_qt` 等未冻结的顶层包可以被导入
2. 将 `src/one_dragon` 追加到冻结 `one_dragon` 包的 `__path__` — 使 `one_dragon.envs`、`one_dragon.utils` 等未冻结子模块能被找到

第 2 步之所以必要，是因为 `one_dragon` 这个包同时存在于两个位置：`.runtime/` 中有冻结的 `one_dragon.launcher` 和 `one_dragon.version`，`src/one_dragon/` 中有其余子模块。Python 的包系统需要 `__path__` 同时包含两个路径才能正确解析所有子模块。

**维护要点**：如果 KEEP_TREES 中新增了不同的顶层包前缀（比如某天需要冻结 `one_dragon_qt.xxx`），则 `hook_path_inject.py` 中也需要对应追加该包的 `__path__` 扩展。两个文件中都有 NOTE 注释标注了这个耦合关系。

## 模块清单机制

### 问题背景

集成启动器的二进制依赖（pygit2、PySide6 等）打包在 `.runtime/` 中，不会随代码更新而变化。如果代码更新后 `import` 了一个新的外部库，而 `.runtime/` 中没有该库，就会导致 `ModuleNotFoundError`。

### 解决方案

`module_manifest.py` 文件记录了打包时所有源码文件的外部依赖 import 语句。这个文件既打包进 `.runtime/`（作为本地清单），又提交到 git 仓库（作为远程清单）。它记录的是源码直接引用的导入，不是打包产物包含的全部模块；PyInstaller 还会递归收集这些依赖引用的模块，并通过 hook 补充模块和文件。

代码更新时，职责分为两部分：

- `one_dragon.envs.runtime_compatibility` 负责读取冻结运行时的打包清单、解析导入要求并探测新增依赖，不依赖 Git 仓库、提交 ID 或更新流程。
- `GitService` 负责从目标提交读取清单并调用兼容性检查；不兼容时，在首次同步、更新或回滚修改工作区前停止，保留现有同步结果与提示。

兼容性检查先比较清单内容，相同则直接允许更新；不同时通过 AST 提取导入要求，不执行清单代码：

- 仅换行、注释、顺序、别名或导入分组改变，以及删除导入，不阻止更新。
- 本地清单已有的导入作为打包基准，不重复加载，避免为了检查重新导入全部可选依赖。
- 对目标清单新增的导入，使用当前冻结解释器的正常导入机制检查。即使模块没有写在本地清单中，只要已由 PyInstaller 递归收集或通过 hook 打包，仍可使用。
- `from package import name` 同时检查已有属性和可导入的子模块，不能只看顶层包存在。缺少模块、导入名称，或导入时发生 DLL 等加载错误，均阻止更新，并将具体依赖和异常写入日志。
- 两份清单不同时，解析失败、相对导入或通配符导入无法可靠比较，继续阻止更新；当前生成器只产生绝对、具名导入。

检查只导入当前运行时中的新增依赖，不执行目标版本的业务源码，也不修改模块搜索路径。新增依赖的初始化代码会在检查时运行；冻结模块继续从 EXE 加载，磁盘源码仅补齐未冻结模块。

此检查只能确认新增导入在当前运行时可用，不能证明依赖版本、函数签名、运行行为、动态导入或资源文件完全兼容。依赖升级、增加尚未打包的依赖或资源时，仍应更新整个集成启动器。

官方依据：[onedir 的依赖复用条件](https://pyinstaller.org/en/stable/operating-mode.html#bundling-to-one-folder)明确区分只改代码与新增、替换、升级依赖；[依赖分析](https://pyinstaller.org/en/stable/operating-mode.html#analysis-finding-the-files-your-program-needs)说明递归收集；[hidden imports](https://pyinstaller.org/en/stable/when-things-go-wrong.html#listing-hidden-imports)说明静态分析不能发现全部动态导入。这里放宽的是“清单文字必须相同”的限制，不是让旧运行时自动升级依赖。

代码源配置、候选源顺序和 fetch 回退机制见 [Git 服务与代码源回退](modules/git_service.md)。

### 清单路径配置

远程清单的路径不是硬编码的，而是从目标 commit 的 `config/project.yml` 中的 `manifest_path` 字段读取。这样即使清单文件改名或移动位置，只要 `project.yml` 正确指向它就能找到。

### 生成时机

- **打包时**：spec 文件通过 `importlib` 动态加载 `generate_module_manifest.py`，在 Analysis 阶段生成 `module_manifest.py`
- **CI 自动构建**：`build-running-resources.yml` 工作流每次推送到 main 或者 pr 更新时运行 `generate_module_manifest.py`，如果清单有变化则自动提交
- **CI 兼容性检查**：`runtime-compatibility.yml` 在推送到 main 或手动触发时，下载最新正式版 RuntimeLauncher。检查脚本提取 EXE 内的 PYZ 和冻结导入器，使用同版本 Python 加载 `.runtime` 中的标准库、扩展模块和 DLL，再调用同一套新增导入检查。确认不兼容时打开或评论同一个未关闭 issue，并提醒仓库变量 `COMPATIBILITY_NOTIFY_USER` 指定的 GitHub 用户；变量缺失、为空或不是合法用户名时，Action 失败且不打开 issue。下载、解压或检查进程异常同样只让 Action 失败，不打开 issue。

检查只使用发布列表中第一个非草稿、非预发布版本；该正式版缺少 RuntimeLauncher 资产时直接失败，不回退到较旧版本。两个 CI 下载脚本仅在协议、主机名和有效端口均相同时保留 Authorization，其他来源的重定向移除凭据；携带凭据的 HTTPS 请求重定向到 HTTP 时直接拒绝。兼容性子进程开启 UTF-8，并在检查期间持有 `.runtime` 的 DLL 搜索目录句柄。

## 代码同步流程

集成启动器的 `_sync_code()` 方法在每次启动时执行：

1. 记录当前 `sys.modules` 快照（用于后续清理）
2. 延迟导入并创建框架 `OneDragonEnvContext`（来自 `src/`），由它统一加载环境、项目和仓库配置
3. 判断首次 checkout 是否完成（检查配置的目标本地分支是否存在；仅有 `.git` 和远程引用仍算未完成）
4. 首次正式发布包 → 按集成启动器内置版本号拉取对应 Git tag；非正式版本或后续运行 → 根据 `auto_update_code` 配置决定是否更新分支
5. tag 拉取成功 → peel 到 commit 并建立目标本地分支；分支更新 → checkout 前检查目标代码与当前集成运行时是否兼容
6. `SUCCESS` → 清除同步期间加载的源码模块，并调用 `importlib.invalidate_caches()`
7. `UP_TO_DATE` → 直接继续启动，不做无意义的模块清理
8. 可以确认磁盘代码未变化的阻断状态 → 显示警告并继续使用当前版本
9. `LOCAL_UPDATE_FAILED` 或兜底 `FAILED` → 停止启动，避免加载可能只更新了一部分的磁盘代码

步骤 6 的模块清理确保主程序后续导入的是更新后的代码，而非同步过程中缓存的旧版本。首次安装包已经包含与 `.runtime` 匹配的 `src/`；正式发布包只按同版本 tag 初始化，不会退化到最新分支。

各状态的启动规则如下：

| 状态 | 启动器提示 | 行为 |
|---|---|---|
| `SUCCESS` | `更新完成` | 清理源码模块后继续启动 |
| `UP_TO_DATE` | `当前已是最新版本` | 不清理模块，直接继续 |
| `RUNTIME_INCOMPATIBLE` | `新版本需要更新启动器才能使用，继续使用当前版本` | 继续启动 |
| `BUILTIN_TAG_UNAVAILABLE` | `暂时无法获取当前版本所需文件，继续使用内置版本` | 继续启动；下次仍重试同一内置版本 |
| `REMOTE_UNAVAILABLE` | `暂时无法获取更新，继续使用当前版本` | 已有 checkout 时继续；首次且没有可用 checkout 时退出 |
| `LOCAL_CHANGES` | `检测到程序文件有改动，未自动更新，继续使用当前版本` | 继续启动 |
| `LOCAL_UPDATE_FAILED` | `更新没有完成，请重新运行启动器；仍然失败时请重新安装` | 退出 |
| `FAILED` | `更新失败，请查看日志后重试` | 退出 |

用户提示只说明结果、影响和下一步，不展示 tag、checkout、reset、OID 或模块清单等实现细节。具体错误继续写日志。

## 界面重启

代码同步完成后的“立即重启”、语言切换等入口统一通过 `app_utils.start_one_dragon()` 启动新进程。集成启动器重新运行当前 exe；源码模式运行工作目录中的 `OneDragon-Launcher.exe`。

启动时直接传递可执行文件参数列表，以项目目录作为工作目录，并创建独立控制台，避免路径中的空格或特殊字符被命令解释器处理。仅在创建进程成功后退出当前程序；创建失败时保留当前程序并抛出异常。

新进程的环境副本必须设置 `PYINSTALLER_RESET_ENVIRONMENT=1`，让 PyInstaller 将其作为独立程序初始化，避免复用旧进程的运行时环境。不要修改当前进程的环境变量。此要求见 [PyInstaller 重启说明](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#using-sys-executable-to-spawn-subprocesses-that-outlive-the-application-process-implementing-application-restart)。

## 错误处理

### 集成启动器的 try/except

`RuntimeLauncher.run_gui_mode()` 和 `run_onedragon_mode()` 将整个执行流程（包括 `_sync_code()` 和子类的 `_do_run_gui()` / `_do_run_onedragon()`）包裹在 try/except 中。任何未捕获的异常都会通过 `_show_fatal_error()` 弹出 Windows MessageBox 并退出，避免闪退后用户看不到错误信息。

### app.py 的模块级 try

`app.py` 顶层有一个 try/except 包裹所有 import 语句。这是因为 import 阶段的错误（如依赖缺失）发生在 `main()` 被调用之前，集成启动器的 try/except 也能捕获到，但模块级 try 提供了更精确的错误信息。

### ZLauncher 的 src 目录检查

`ZLauncher` 的入口文件在模块级检查 `src/` 目录是否存在。如果用户只解压了 exe 和 .runtime 而遗漏了 src/，会立即弹出 MessageBox 提示，避免后续出现难以理解的 ImportError。

## 发行产物

CI 构建生成以下集成启动器相关产物：

| 文件 | 内容 | 用途 |
|------|------|------|
| `{version}-WithRuntime-Full.zip` | 集成启动器 exe + .runtime + src + 模型 | 首次部署，解压即用且无需额外下载模型 |
| `{version}-WithRuntime.zip` | 集成启动器 exe + .runtime + src | 首次部署，模型按需下载 |
| `RuntimeLauncher.zip` | 集成启动器 exe + .runtime（不含 src） | 就地升级已有环境 |

两个 WithRuntime 包都包含 src/，因为首次部署时还没有 .git 目录，无法通过 git clone 获取源码。用户解压后首次启动，集成启动器会自动初始化 git 仓库并设置远程跟踪。WithRuntime-Full 复用普通 Full 包准备好的模型，将其写入压缩包的 `assets/models/`；CI 不会因此重复下载模型。

## 启动器下载卡（UI）

`LauncherDownloadCard` 提供了一个类型下拉框，让用户在「原始启动器」和「集成启动器」之间切换。切换时会：

1. 断开旧版本检查器的信号连接（防止竞态覆盖）
2. 创建新的版本检查器（指向对应的 exe 文件）
3. 重置版本状态并触发重新检查

版本检查会调用所选启动器的 `--version` 参数。查询时会临时使用普通权限，并要求 PyInstaller 启动全新进程，避免 Windows 兼容性提权或父启动器遗留的临时环境导致界面误报“未安装”；这些设置只影响版本查询，不改变用户正常启动启动器时的权限

下载时的备份/回滚机制：
- 下载前将当前 exe 重命名为 `.bak`（集成启动器还会重命名 `.runtime` 为 `.runtime.bak`）
- 下载成功 → 删除备份
- 下载失败 → 回滚备份
