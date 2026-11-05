# macOS 移植交接记录

本文面向之后继续处理本仓库的开发者或 AI 助手，记录移植目标、已完成内容和剩余工作。当前移植尚未完成，不要把本文或现有代码当作已验证可发布版本。

## 项目目标与已确认决定

- 这是专为 macOS 开发的 fork，不需要保留 Windows 支持。
- 目标设备是 Apple Silicon Mac；游戏通过 PlayCover 运行，并由额外插件切换为 PC 逻辑接收输入。用户确认 PlayCover 内置 Keymapping（键位映射）关闭，不应将它当作当前输入方案。
- 游戏内操作、识别和自动化流程应尽量沿用原有实现。
- 用户明确要求移除整个项目的手柄控制方案；自动化只走前台键鼠输入。
- 游戏窗口需要可见并处于前台。运行需要 macOS 辅助功能权限和屏幕录制权限。

## 当前修改进度

### 已有实现

- `pyproject.toml` 已将 macOS 的 ONNX Runtime、PyObjC 框架设为依赖；DirectML、pywin32、pyuac 和手柄依赖组已移除，`uv` 解析平台限制已改为 macOS。
- 新增 `src/one_dragon/base/controller/mac_game_window.py`，通过 macOS 窗口信息定位和激活 PlayCover 窗口。
- PC 窗口控制、截图、剪贴板、相对鼠标移动、应用错误提示和游戏入口已有 macOS 分支。截图按 PlayCover 窗口 ID 获取，不会把遮挡它的桌面窗口截进游戏画面；截图会裁掉窗口标题栏并缩放至项目标准分辨率。
- macOS 下由用户先在 PlayCover 启动游戏，一条龙等待游戏窗口，不尝试运行 Windows 游戏启动命令。
- 覆盖层、调试图片剪贴板和关闭 PlayCover 游戏目前不支持。
- 鼠标点击仅在对应屏幕区域设置 `pc_alt=True` 时按住 Option/Alt；不要在 macOS 上把 Option/Alt 加到所有游戏点击中。大世界中需要解锁鼠标的按钮会使用该标记，菜单和邮件等界面点击不应无条件按住。

### 手柄控制清理（已完成）

- 移除了 Xbox/DS4 按键配置、后台手柄模式及手柄动作映射。
- 游戏设置页仅保留键盘按键和输入方式；移除了 HDR 注册表按钮、Windows 游戏启动参数和手柄设置。
- 移除了游戏助手、指令调试中的后台模式开关，以及扩展安装页的虚拟手柄安装卡。
- 前台键鼠成为控制器唯一模式；战斗助手启动节点改为“启用键鼠”。
- 画面区域、截图工具和 MCP 区域配置接口不再提供 `gamepad_key` 字段；旧 YAML 中残留的同名字段会被忽略，不会触发手柄输入。
- 删除了 Xbox、DS4、虚拟手柄控制器模块和手柄设置卡片。
- `uv lock` 已按 macOS 平台重新生成；锁文件检查通过，Python 源码中没有残留手柄控制引用。
- 依赖解析为 283 个包；`pyproject.toml` 和 `uv.lock` 中没有手柄或 Windows 专属依赖。
- macOS 预检不再要求 Windows 游戏程序路径；PlayCover 启动后由一条龙等待游戏窗口。
- 修改文件的 Ruff、源码编译、`import zzz_od.gui.app`、`import one_dragon.launcher.runtime_launcher` 和 `uv lock --check` 均已通过。
- GUI 初始化崩溃已定位并修复：`ZPcController` 原先在 `CtxInitRunner` 工作线程内创建 `pynput` 键鼠控制器；`pynput` 的监听线程还会调用当前 PyObjC 环境中无法解析的 `AXIsProcessTrusted`，并在键盘监听时查询系统键盘布局。控制器现在在 GUI 主线程创建，macOS 键鼠监听器直接运行 Quartz 事件循环，避免上述调用。监听器启动/停止检查通过；修复后的 GUI 已加载 OCR、19 个默认应用组和 13 个设置提供者，未再出现 SIGTRAP 或 `AXIsProcessTrusted` 异常。
- 邮件应用验证未完成：用户观察到自动点击落在“删除已读”，并弹出删除确认框；用户在确认前点击左上角返回，没有确认删除。日志中的“全部领取 → 确认”仅表示 OCR 找到通用确认文字，不能证明领取成功，也不能排除识别到删除确认框。邮件应用现增加删除文字保护：OCR 发现“确认删除”“确定删除”或“是否删除”时不执行通用确认点击。鼠标点击现记录游戏坐标、目标桌面坐标和移动后的实际指针坐标，便于继续定位错位；尚未通过安全的游戏内操作确认坐标与点击落点一致。
- 独立截图诊断确认：以普通用户运行同一窗口截图代码，可截取 PlayCover 窗口并生成 1920×1080 RGB 图像；同一截图经项目 OCR 能识别为“菜单”。sudo GUI 的截图结果尚未单独诊断；已去掉不必要的 root 启动，后续应以普通用户重测。重新启动时发现先前 root 运行遗留的 `notice_cache/notice_cache.json` 由 root 拥有，导致普通用户无法保存缓存；应用其余初始化仍正常。
- 用户后来反馈“一条龙可以工作，但会弹出很多窗口”，并确认弹窗属于“屏幕与系统音频录制”，是在自动化鼠标操作时出现。鼠标操作流程会连续截图识别画面；未授权时反复调用截图 API 可能重复请求权限。用户提供的系统设置截图显示 GitHub Copilot 已获屏幕录制权限；此前运行中的一条龙及虚拟 HID 客户端实际属于 root。启动脚本现让 GUI 以普通用户运行，并只对 Karabiner 虚拟 HID 客户端使用 sudo。截图控制器先检查当前进程授权，未授权时不调用截图 API，只记录一次提示；用户需授权实际运行一条龙的程序。

## 尚未完成与后续计划

1. **检查平台残留**：继续搜索应用启动和运行时会触发的 Win32 API、注册表、Windows 消息框及旧打包逻辑，确认哪些应移除或改为 macOS 实现。
2. **检查用户配置与窗口识别**：验证配置写入位置适用于 macOS；确认 PlayCover 实际窗口标题能匹配，必要时保留用户可配置标题。
3. **虚拟 HID 点击已接入**：PyAutoGUI、pynput、Quartz 和 macOS 系统脚本发送的自动点击未触发游戏界面；用户确认实体鼠标点击正常。经用户同意，已安装并批准 Karabiner-DriverKit-VirtualHIDDevice 8.7.0，协议版本为 7。仓库现包含常驻 C++ 客户端源码 `tools/macos/vhid_click_client.cpp` 和构建脚本 `tools/macos/build_vhid_click_client.sh`；首次构建从官方 v8.7.0 标签取得协议头文件并生成 `.install/macos-vhid/vhid-click-client`。`MacVirtualHIDMouse` 在自动化运行前启动客户端并确认虚拟指点设备就绪，macOS 点击先移动鼠标，再经官方客户端发送按下和松开；客户端在控制器清理时关闭。点击断连或客户端异常会返回失败，不回退到已证实无效的 PyAutoGUI 点击。启动脚本以普通用户构建并运行 GUI，仅对虚拟 HID 客户端申请管理员授权。Option/Alt 仍只用于 `pc_alt=True`。
4. **重新验证屏幕录制权限**：同一 PlayCover 窗口图像曾在普通用户下被项目 OCR 识别为“菜单”，但 sudo GUI 的邮件流程无法识别画面。现已去掉 GUI 的 sudo 启动；关闭旧 root 进程后，以普通用户重新运行，并按系统提示授权实际运行的一条龙进程，再确认截图与 OCR 是否正常。
5. **完成 macOS 分发**：设计并验证 Apple Silicon `.app` 构建，检查资源打包、可写配置目录、首次启动权限提示和签名要求。

## 最近一次 PlayCover 验证

- 游戏窗口即使被其他桌面窗口遮挡，也能按窗口 ID 获取干净截图；控制器输出为 1920×1080 RGB，OCR 能精确识别「菜单」。
- 从菜单启动「邮件」应用后，流程进入「邮件」并执行「全部领取」，随后完成返回大世界，最终状态为「大世界-普通」。
- 本次没有识别到「确认」或「确定」弹窗；邮件流程会在没有确认弹窗时继续返回，因此只能确认自动化流程完成，不能确认是否领取到奖励。
- `pynput` 初始化监听器时仍出现 PyObjC `AXIsProcessTrusted` 的 `KeyError`。本次流程仍完成，但该异常的影响尚未查清。
- 实体鼠标可以点击 PlayCover 游戏界面；此前官方虚拟 HID 客户端也曾成功打开游戏内邮件。控制器现已改为用该客户端发送点击、鼠标按键和拖拽按键；本次构建验证通过，但尚未在当前游戏画面重复端到端验证。Option/Alt 仍只应在屏幕区域设置 `pc_alt=True` 时按住。
- 最新 GUI 以普通用户启动并越过 `CtxInitRunner` 初始化，OCR 和应用设置提供者加载完成，未见崩溃。自动化启动时，普通用户版虚拟 HID 客户端被 Karabiner 拒绝（`Permission denied`）；启动器现改为预先验证一次管理员身份，客户端以 `sudo -n` 单独启动，GUI 本身不提权。之后用户确认点击实际落在“删除已读”并出现删除确认框；用户返回而未确认删除。尽管日志随后记录识别到通用“确认”并返回菜单，这不能作为“全部领取”点击成功的证据。点击发送前虽已加入短暂等待，但错位仍未解决；鼠标坐标诊断已加入。重启 GUI 后尝试从终端截取游戏画面，但 CoreGraphics 返回空图像，因此没有发送任何测试点击；普通用户写入通知缓存时遇到旧 root 文件的权限错误。

## 关键文件

- `pyproject.toml`、`uv.lock`：平台与依赖。
- `src/one_dragon/base/controller/mac_game_window.py`：PlayCover 窗口发现与激活。
- `src/one_dragon/base/controller/pc_game_window.py`：窗口控制入口。
- `src/one_dragon/base/controller/pc_screenshot/pc_screenshot_controller.py`：截图策略与分辨率处理。
- `src/one_dragon/base/controller/pc_screenshot/pil_screencapper.py`：macOS 按窗口 ID 截取 PlayCover 画面。
- `src/one_dragon/base/controller/pc_controller_base.py`：前台点击路由和虚拟 HID 客户端生命周期。
- `src/one_dragon/base/controller/macos_vhid.py`：Python 与常驻原生客户端的命令通道。
- `tools/macos/vhid_click_client.cpp`、`tools/macos/build_vhid_click_client.sh`：Karabiner 官方客户端桥接程序及构建脚本。
- `src/zzz_od/controller/zzz_pc_controller.py`：前台键鼠输入。
- `src/one_dragon/base/controller/pc_clipboard.py`：剪贴板输入。
- `src/zzz_od/operation/enter_game/open_game.py`：PlayCover 游戏等待入口。
- `docs/develop/macos_support.md`：面向开发者的 macOS 支持说明。

## 继续工作时的注意事项

- 先读仓库根目录 `AGENTS.md`，并检查 `git status`；不要覆盖尚未提交的工作区改动。
- 本项目要求 Python 3.11、`uv`，源码目录为 `src/`。启动项目前先激活 `uv` 环境，并把 `src/` 加入 `PYTHONPATH`。
- macOS 上可双击仓库根目录的 `启动一条龙.command`，以当前登录用户启动 GUI；启动器只会为 Karabiner 虚拟 HID 客户端请求管理员授权。macOS 屏幕录制和辅助功能授权针对实际运行的程序，授权给 GitHub Copilot 不会自动授权给一条龙。
- 点击需由此启动脚本运行；首次启动要联网并安装 Xcode Command Line Tools，以构建 Karabiner 官方 v8.7.0 客户端。Karabiner 虚拟 HID 驱动需已安装、批准并保持守护进程运行。
- 测试位于独立仓 `zzz-od-test/`，目前工作区未确认有该仓；不要把测试写入主仓。
- 以上为此前记录；当前分支和远程状态以文末的「接手状态更新」为准。

## 2026-11-05 接手状态更新

- macOS 移植和手柄移除改动已提交为 `b2162f57`。个人 fork 内的 PR #1 已合并到 `pokemc32ryan/ZenlessZoneZero-OneDragon-mac` 的 `main`；此前误开的上游 PR #3015 已关闭且未合并。用户明确要求后续只在个人 fork 工作。
- `config/repository.yml` 中的 GitHub 远端地址已更新为个人 fork `https://github.com/pokemc32ryan/ZenlessZoneZero-OneDragon-mac.git`，避免 GUI 启动时把 `origin` 自动重写回上游仓库。
- 查明并修复了 PlayCover 鼠标点击错位与视角转向失效问题：
  - `pyautogui.moveTo()` 移动系统指针不会触发 PlayCover 更新游戏内游标位置；现通过 Karabiner 虚拟 HID 客户端新增 `move <dx> <dy>` 与 `wheel <v> <h>` 命令，在指针移动后微移 `(+1, 0)` / `(-1, 0)` 同步游戏内游标位置，并用虚拟 HID 相对位移实现大世界视角转向 (`move_mouse_relative`)。
  - `MacGameWindowHandle.isActive` 改用 `NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()` 判断前台应用，避免 PlayCover 下 `NSRunningApplication.isActive()` 恒为 `False` 导致每次点击重复激活窗口。
  - 邮件确认节点在点击前重新截图再检查是否含“确认删除/确定删除/是否删除”。
- 查明并修复了广色域屏幕截图颜色偏移问题：`PilScreencapper._capture_mac_window()` 改为在裁剪标题栏后通过 `CGBitmapContext` 转换到标准 `sRGB` 色彩空间，修复了快捷手册等依赖 `color_range` 的画面识别问题。
- 修复了自动战斗在 macOS 启动时加载 `soundcard.mediafoundation` 导致的 `cffi.CDefError` 崩溃：非 Windows 平台跳过 `AudioRecorder.start_running_async`。
- 已完成游戏内实测验证的功能：**邮件领取**、**每日签到 / 吼吼饼铺**、**录像店营业**。

### 旧提示（已由 Antigravity 接手说明取代）

以下提示已过时，勿照此执行。当前任务与 Git 边界见 [`antigravity_handoff.md`](antigravity_handoff.md)。

```text
请先阅读仓库根目录 AGENTS.md 和 docs/develop/macos_porting_handoff.md，并先检查 git status；本工作区有大量未提交的 macOS 移植与手柄移除改动，必须保留，不要重置、覆盖或只挑最近几处提交。

目标是继续把这个 Windows 项目移植到 macOS（Apple Silicon + PlayCover），用户已要求移除手柄方案，并接入已验证可工作的 Karabiner 虚拟 HID 鼠标。当前最急的问题是邮件自动化误点到“删除已读”，出现删除确认框；用户在确认前点击返回，没有确认删除。旧日志里识别到“确认”不能证明领取成功。代码现在对“确认删除/确定删除/是否删除”加了保护，并会记录目标坐标和鼠标实际坐标，但这些修复尚未在游戏内验证。

严禁自动点击任何领取、删除、确定或确认按钮。用户仅允许在非破坏性界面做点击验证。上次通过终端 CoreGraphics 截图得到空图像，因此没有执行任何测试点击；需要先解决截图取图/授权问题，或请用户提供当前画面和安全目标，再进行验证。不要假定 0.1 秒等待修好了偏移。

GUI 以普通用户身份运行；Karabiner 虚拟 HID 客户端由 sudo 单独启动。不要递归修改 root 遗留文件的所有权或权限。已知普通用户写配置失败的路径包括 notice_cache/notice_cache.json 和 config/01/one_dragon/_group.yml。

当前分支 pokemc32ryan-macos-support 与本地 main 指向同一提交；用户已明确授权把当前工作区的 macOS 移植改动提交到该分支并创建目标为项目 main 的 PR。该授权不包括直接合并 PR。提交前的定向 Ruff（忽略 I001）、py_compile 和 git diff --check 通过；鼠标错位与实际邮件领取仍未验证。
```
