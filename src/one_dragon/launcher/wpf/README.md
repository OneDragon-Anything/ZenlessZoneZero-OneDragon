# OneDragon Launcher · WPF UI

基于 C#、WPF 和 WPF UI 4.3.0 的 Windows 启动器，源码位于一条龙主仓的 `src/one_dragon/launcher/wpf/`，由主仓统一管理。

## 运行

需要 Windows 10/11、.NET Framework 4.7.2 或更高版本，以及已经安装好的一条龙 Python 项目与运行环境。

以下产物路径均相对于本目录。发布单文件位于 **`artifacts/OneDragon-Launcher.exe`**，ZIP 包 `artifacts/OneDragon-Launcher-Windows.zip` 中也只有这个 EXE。部署时只需复制这个 EXE 到一条龙项目根目录（与 `src`、`.venv`、`.install` 同级），不需要随附 WPF UI DLL 或 `.exe.config`。也可以保留启动器在独立目录，通过参数指定项目：

```powershell
.\OneDragon-Launcher.exe --project "D:\ZenlessZoneZero-OneDragon"
```

Visual Studio 选择 **Debug** 后直接按 **F5**，未指定项目时默认进入界面预览，不需要 Python 源码或运行环境，也不请求管理员权限。Debug 下单独指定 `--dark` 仍然是预览。

需要联调真实 Python 后端时，在“项目属性 → 调试 → 命令行参数”填写 `--project "D:\ZenlessZoneZero-OneDragon"`；`--onedragon` 也会进入真实 CLI 流程。Release 默认保持真实启动。

也可以显式预览界面，不提权、不运行 Python、不更新代码：

```powershell
.\OneDragon-Launcher.exe --preview
.\OneDragon-Launcher.exe --preview --dark
```

正常启动时，环境检查通过后会请求管理员权限，保持原版行为。帮助、版本和预览模式不需要管理员权限。

## 窗口与行为

- 启动窗口：520 × 300 DIP，原始 Logo、标题、状态、动态进度条和“查看日志”，WPF UI 标题栏与按钮。
- 日志窗口：580 × 420 DIP，可调整大小；实时显示 UTF-8 标准输出/错误输出、清除 ANSI 控制码、选择与复制日志，支持 Esc 关闭和重新打开。
- 默认在启动时读取系统深浅色主题，也可用 `--dark` 指定深色。浅色使用参考截图的淡蓝渐变底色；这里没有复用 Slint 的 Mica/窗口 Hook 实现。原生圆角由支持的 Windows 版本提供。
- 按钮、日志图标和正常进度条使用 WPF UI 动态强调色资源，启动时读取 Windows 强调色，运行期间随系统个性化设置更新；失败进度条使用主题的错误色。强调色更新不改变已选择的深浅色模式。
- 启动期间使用不确定进度条，不展示完成百分比。日志匹配只更新阶段文字，通过阶段枚举防止倒退；失败后保留错误文字，进度条停止动画并显示整条错误色。
- 日志在底部时自动跟随；向上查看或选中文字时停止追尾。内存日志最多保留 10,000 条且不超过 1,048,576 个字符，复制的是当前保留日志。
- 检测到错误会自动打开日志。等待 30 秒仍未就绪时保留窗口并提示，之后继续监视，不静默隐藏失败。
- 每 500ms 检查本次启动进程及其子进程的可见窗口。启动期间没有错误或超时时，检测到“绝区零 一条龙”主界面后立即关闭启动窗口及日志窗口，并彻底退出启动器进程。
- 启动期间出现错误或等待超过 30 秒时，保留窗口和内存日志供检查；即使主界面随后出现也不自动关闭。可以手动关闭启动窗口，不会终止 Python。
- GUI 输出由已有 Python 进程内的线程通过内存管道转发。启动器退出后，线程继续读取并丢弃输出，避免 Python 及其子进程管道断开或阻塞；不新增日志文件或中转进程。Python 项目自身的日志策略保持不变。CLI 模式仍等待 Python 退出并返回退出码。

## 后端兼容

源码目录查找：显式 `--project` 优先，否则从 EXE 目录向上最多检查五层，以及当前工作目录；支持直接的 `src/zzz_od`，以及 `ZenlessZoneZero-OneDragon`、`ZenlessZoneZero-OneDragon-main` 子目录。

执行器优先级：项目或启动器目录中的 `.venv/Scripts/python.exe`、`.venv/python.exe`、`.install/python/python.exe` → 本地 `.install/uv/uv.exe` 或 `.install/uv.exe` → PATH 中的 uv → PATH 中的 Python。忽略 Windows Store 的 Python 占位别名。

工作目录固定为实际 Python 项目根目录，注入 `PYTHONPATH`、`PYTHONUNBUFFERED=1`、`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。

GUI 模式保留原版入口：

```python
from one_dragon.devtools.python_launcher import run_python
run_python(['zzz_od', 'gui', 'app'], piped=True)
```

GUI 和 CLI 模式均在导入 Python 启动器前注入 colorama 兼容 shim；只有缺少 colorama 时才启用，已安装的 colorama 不会被覆盖。隐藏控制台下的标准输入会立即提供 EOF，避免后端 `input()` 等待一个不存在的交互终端。

**Python 项目自身的限制**：`python_launcher.verify_working_directory()` 会拒绝含空格或中文的项目路径。C# 的参数引用与 UTF-8 处理不改变这项后端校验，部署建议使用例如 `D:\ZenlessZoneZero-OneDragon` 的路径。

## 命令行

```text
-h, --help                  帮助
-v, --version               版本
-o, --onedragon             一条龙 CLI 模式
-c, --close-game            运行后关闭游戏，需要 --onedragon
-s, --shutdown [秒]         运行后关机，默认 60 秒，需要 --onedragon
    --hibernate            运行后休眠，需要 --onedragon
    --sleep                运行后睡眠，需要 --onedragon
-i, --instance 1,2          账号实例，需要 --onedragon
    --project <目录>       Python 项目根目录
    --preview              仅预览界面
    --dark                 深色主题
```

`--shutdown`、`--hibernate`、`--sleep` 三选一，可与 `--close-game`、`--instance` 组合。休眠和睡眠参数不接受秒数。使用休眠或睡眠需要 Python 后端版本支持对应参数。

```powershell
# 运行账号 1、2，完成后关闭游戏并休眠
.\OneDragon-Launcher.exe -o -i 1,2 -c --hibernate

# 完成后睡眠
.\OneDragon-Launcher.exe -o --sleep
```

CLI 模式通过 `python -u -c` 先执行 colorama 兼容注入，再调用 `run_python(['zzz_od', 'application', 'zzz_application_launcher'], no_windows=False, args=..., piped=True)`，将 `--onedragon` 之外的后端参数透传并返回 Python 退出码。参数校验和管理员提权由 WPF 负责，无需导入依赖 pyuac 的 Python EXE 包装入口；需要提权时等待管理员进程并保留退出码。命令行里的关闭游戏、关机、休眠和睡眠行为由 Python 后端执行。

## 构建与验证

使用 Visual Studio 的“.NET 桌面开发”组件和 .NET Framework 4.7.2 targeting pack。依赖版本固定在 `packages.config`（包括 `Fody 6.9.3` 和 `Costura.Fody 6.2.0`），缺少程序包时构建脚本会自动通过 NuGet 还原到 `packages/`。

在一条龙仓库根目录运行（也可以在本目录运行 `./build.ps1`）：

```powershell
.\src\one_dragon\launcher\wpf\build.ps1
```

脚本定位 Visual Studio MSBuild，构建 Release，生成本目录下的 `artifacts/OneDragon-Launcher.exe` 与只包含该 EXE 的 ZIP。使用 `-SkipArchive` 可只生成 EXE。可用 Visual Studio 打开本目录的 `OneDragonLauncherWpf.slnx` 进行开发。

主仓要求测试存放在独立测试仓，因此本目录不包含原独立工程的 `tests/`，构建脚本只负责编译和打包。原工程的 GitHub Actions 发布工作流未迁入，当前需手动构建；后续接入主仓发布流程时再统一配置。

Release 使用 `FodyWeavers.xml` 配置的 Costura 将托管依赖嵌入 EXE，设置 `DisableCompression="true"` 关闭压缩，启动时直接从内存加载，省去解压步骤；不嵌入依赖的 PDB。单文件 EXE 约 7.08 MiB。Logo、图标和 XAML 本身已编入应用资源。Debug 保留普通 DLL 输出，便于 F5 调试。

`build.ps1` 固定构建 Release x64，生成的 EXE 需要 64 位 Windows。当前 `App.config` 只有 CLR 启动声明，单文件分发不需要它。若将来增加绑定重定向或其他外部配置，构建脚本会停止打包并提示检查，避免悄悄丢弃配置。`bin/x64/Release` 中剩余的 PDB、XML 文档和配置文件是构建输出，不属于单文件发布包。

Costura 只打包启动器的托管依赖，**不会把 .NET Framework、Python 解释器、一条龙源码、虚拟环境或 uv 打入 EXE**。这些运行要求与之前相同。

迁移验证可复用原独立工程的后端测试、Python bootstrap/输出桥接检查，以及单文件浅色和深色启动检查；运行时应指向这里的源码与产物。实际游戏/自动化流程和 UAC 授权仍需要在目标运行环境验证。

## 代码入口

以下文件均位于本目录的 `OneDragonLauncherWpf/` 下。

- `App.xaml(.cs)`：主题、参数解析、CLI 分支。
- `MainWindow.xaml(.cs)`：启动窗口和启动生命周期。
- `TerminalWindow.xaml(.cs)`：日志窗口与复制/滚动交互。
- `ViewModels/LauncherViewModel.cs`：进度与状态绑定。
- `Services/LaunchEnvironment.cs`：源码目录和 Python/uv 检测。
- `Services/PythonRunner.cs`：启动参数、UTF-8 管道和日志事件。
- `Services/WindowsIntegration.cs`：管理员重启、控制台接入与进程窗口监视。
- `Services/LauncherLog.cs`、`LaunchStage.cs`、`LauncherOptions.cs`：日志缓冲、阶段识别与命令行解析。
- `FodyWeavers.xml`：Release 依赖嵌入与压缩配置。
