# Antigravity 接手说明：完成 macOS 移植验证

## 先读这些内容

开始前请先阅读：

1. 仓库根目录 `AGENTS.md`。
2. `docs/develop/macos_support.md`。
3. `docs/develop/macos_porting_handoff.md`。

这些文件记录项目规范、macOS 设计和此前验证情况。如果本文件与实时 GitHub 状态或当前代码不一致，以实时状态和代码为准，并更新交接记录。

## 项目和 Git 边界

- 这是《绝区零一条龙》的 macOS 个人 fork，目标是 Apple Silicon Mac + PlayCover；游戏通过额外插件以 PC 逻辑接收输入，PlayCover 自带 Keymapping 关闭。
- 用户已要求移除手柄控制方案。继续保持只用前台键盘和鼠标，不要恢复手柄、后台输入或 Windows 专属设置。
- 用户要求工作只留在个人 fork，不要向 `OneDragon-Anything/ZenlessZoneZero-OneDragon` 上游推送、创建 PR 或合并。
- 截至 2026-11-05，个人 fork 内的 PR #1 已合并到个人 fork 的 `main`。之前的上游 PR #3015 已关闭，未合并。
- 既有工作区的 `origin` 曾指向上游仓库，而非个人 fork。开始工作前必须检查 `git remote -v`、当前分支和 `git status`，不要盲目向 `origin` 推送。需要远端操作时，明确使用个人 fork 仓库 `pokemc32ryan/ZenlessZoneZero-OneDragon-mac`。
- 本次接手说明不授权提交、推送、创建 PR 或合并；除非用户之后明确要求，否则只在工作区修改并验证。

## 首要任务：定位并安全修复邮件点击错位

用户亲自观察到：自动化本应点击邮件页“全部领取”，实际却点到旁边的“删除已读”，因此出现删除确认框。用户在确认前点击左上角返回，没有确认删除。不要声称邮件已领取，也不要把日志里的 `全部领取 → 确认` 当成领取成功证据：那个通用确认文字也可能来自删除弹窗。

此前代码已在 `src/one_dragon/base/controller/pc_controller_base.py` 中加入点击坐标日志，记录游戏坐标、目标桌面坐标和 PyAutoGUI 移动后的实际指针坐标；并在邮件确认逻辑中加入删除文字保护。点击前的 0.1 秒等待没有解决问题的实测证据，不要假定它有效。

按以下顺序处理：

1. 检查当前分支及个人 fork 的最新提交，确认 PR #1 的合并提交已包含在工作基线上；不要切换到上游仓库。
2. 阅读 `mac_game_window.py`、`pc_controller_base.py`、`macos_vhid.py`、`pil_screencapper.py`、`pc_screenshot_controller.py`、`screen_utils.py`、`assets/game_data/screen_info/email.yml` 和邮件应用实现。厘清游戏 1920×1080 坐标、窗口坐标、macOS 屏幕逻辑坐标、PyAutoGUI 指针坐标和虚拟 HID 按键报告的关系。
3. 在**不会触发领取、删除、确认或购买**的界面取得一张可信的当前游戏截图，核对画面实际尺寸、PlayCover 窗口 bounds、窗口标题栏裁切、OCR 命中中心、换算后的目标点、PyAutoGUI 指针位置。之前单独从终端调用 CoreGraphics 曾返回空图像；这不代表 GUI 内截图必然失败。优先从应用实际使用的截图路径诊断，不要绕过授权或仅凭旧截图推断当前坐标。
4. 查清偏移来源后再做最小修复。若坐标系统或 Retina 缩放存在差异，修正统一坐标转换，不要靠反复调整等待时间掩盖问题。确认虚拟 HID 客户端的鼠标报告只处理按键时，应将它与系统指针的职责分开验证。
5. 先用安全、可逆的界面按钮实测目标位置和点击落点，再判断是否可以恢复邮件流程验证。若安全目标不明确、截图不可信、屏幕录制/辅助功能权限不完整或游戏画面不是用户当前状态，先停下并请用户协助，不要盲目点击。

## 必须遵守的安全边界

- 严禁无人确认地点击邮件领取、删除、购买、兑换、确认或确定按钮；尤其不要确认任何删除弹窗。
- 不要因为 OCR 识别到“确认”“确定”就判断操作类型。需结合当前画面和明确的弹窗标题/正文判断；无法区分时跳过点击并报告。
- 不要自动运行完整“一条龙”或邮件流程来试点位，因为流程可能触发不可逆操作。
- 不要修改权限、所有者或递归处理配置目录。此前旧 root 进程留下的文件已知会导致普通用户写入失败，包括 `notice_cache/notice_cache.json` 和 `config/01/one_dragon/_group.yml`；如确需修复，先逐个检查并向用户说明具体路径及影响。
- GUI 应以当前登录用户运行；只有 Karabiner 虚拟 HID 客户端可按既有启动脚本单独使用管理员权限。不要用 `sudo` 启动整个 GUI。
- 不要因诊断失败而跳过 macOS 屏幕录制或辅助功能权限检查。

## 后续工作（先完成首要任务，再评估）

- 检查 macOS 启动、配置写入、窗口标题匹配以及运行期间仍会触发的 Windows 专属 API。
- 确认 PlayCover 窗口截图、OCR、键盘输入、鼠标点击和拖拽的职责及失败提示一致。
- macOS 分发打包尚未完成；本阶段不要打包，除非用户另行要求。
- 测试按项目规范放在独立测试仓 `zzz-od-test/`，不要把测试脚本或测试数据放入主仓。测试仓不存在时，记录缺少的验证，不要自行 clone 新仓。
- 任何验证报告必须区分“代码检查通过”“GUI 启动成功”“截图/OCR 已验证”“游戏内安全点击已验证”“邮件领取结果已验证”，不要将其中一项冒充另一项。

## 当前已知状态与验证记录（2026-11-05 更新）

- 个人 fork 仓库地址已写入 `config/repository.yml`（`https://github.com/pokemc32ryan/ZenlessZoneZero-OneDragon-mac.git`），防止 GUI 启动时自动将 `origin` 改回上游。
- 邮件点击错位与视角转向失效根因已定位并修复：
  - PlayCover 不会因 `pyautogui.moveTo()` 更新游戏内游标位置；现通过 Karabiner 虚拟 HID 客户端支持 `move <dx> <dy>` 与 `wheel <v> <h>`，在指针定位后发送微移 `(+1, 0)` / `(-1, 0)` 同步游标位置，并用虚拟 HID 相对位移支持大世界视角旋转 (`move_mouse_relative`)。
  - `MacGameWindowHandle.isActive` 改用 `NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()` 判断前台状态。
  - 邮件应用在 `click_confirm` 中重新截图检查是否包含“确认删除/确定删除/是否删除”。
- 广色域屏幕截图颜色偏移根因已定位并修复：`PilScreencapper._capture_mac_window()` 在裁剪窗口标题栏后通过 `CGBitmapContext` 转换到标准 `sRGB` 色彩空间，解决快捷手册等依赖 `color_range` 的画面识别问题。
- 已添加 PlayCover 桌面键鼠模式必要插件 `tools/macos/libUnityDesktopMode.dylib`。
- 自动战斗 macOS 声音闪避识别已修复并实现原生回环采集：新增 `tools/macos/sck_audio_capture.mm`（编译为 `.install/macos-vhid/libod_sck_audio.dylib`），通过 macOS `ScreenCaptureKit` 直接采集系统输出音频（32kHz 单声道），并在 `AudioRecorder.start_running_async` 中优先启用（同时兼容 `BlackHole` 虚拟声卡回退），避免加载 Windows 专属 `soundcard.mediafoundation` 触发 `cffi.CDefError`。
- 已在游戏内实测通过：**邮件领取**、**每日签到 / 吼吼饼铺**、**录像店营业**、**咖啡店**、**恶名狩猎（周期无剩余次数领奖）**、**迷失之地（含自动战斗与 ScreenCaptureKit 声音闪避识别）**、**体力刷本（实战模拟室 / 区域巡防连续轮次刷本）**。
- 已修复 `启动一条龙.command` 自动在同终端后台启动 `Karabiner-VirtualHIDDevice-Daemon`，并修复 `MacPcGameWindow.init_win` 排除自身进程及精确匹配窗口标题（防止误把一条龙 GUI 窗口识别为游戏窗口）。
- 已修复并实测通过 `体力刷本`（`实战模拟室` / `区域巡防` / `专业挑战室` / `恶名狩猎`）连续轮次卡在战斗结束或鼠标停留在右下角按钮区域的问题：
  1. `combat_simulation.py`、`area_patrol.py`、`expert_challenge.py`、`notorious_hunt.py`、`choose_predefined_team.py`、`withered_domain_app.py` 点击「下一步 / 预备出战 / 出战」后，以及 `deploy.py` 点击「按钮-出战」和 `check_next_after_battle.py` 点击「战斗结果-再来一次」后，统一将鼠标移至安全空白坐标 `Point(200, 200)`（替代原先紧贴右下角按钮与屏幕边缘的 `UID` `(1866, 1069)`），避免进入战斗结算画面时光标仍停在「战斗结果-完成」`(1731, 1028)` 上被残留的 `mouse_left` 普攻连段误点而提前退出结算页。
  2. `AutoBattleContext.check_battle_state` 在刚离开战斗画面（`was_in_battle -> not in_battle`）时立即重置 `_last_check_end_time = 0`，消除此前连携阶段触发冷却导致的 5 秒战斗结束识别延迟。
  3. `MacVirtualHIDMouse.nudge_cursor()` 调整为先左移 `(-1, 0)` 再右移 `(+1, 0)`，防止游戏窗口靠桌面右边缘时被系统屏幕边界截断。

## 可直接发送给 Antigravity 的提示

```text
请先阅读 AGENTS.md、docs/develop/macos_support.md 和 docs/develop/antigravity_handoff.md，检查当前分支、git status、git remote 和个人 fork 的最新状态。

继续完成 Apple Silicon Mac + PlayCover 的一条龙移植验证。用户已要求移除手柄方案，并明确只在个人 fork 工作：不要向 OneDragon-Anything/ZenlessZoneZero-OneDragon 上游推送、创建 PR 或合并。此前 origin 曾指向上游，不能盲目使用 origin。用户没有授权本次接手中的提交、推送或 PR 操作。

首要问题是邮件点击错位：用户看到自动化把“全部领取”点成了“删除已读”，出现删除确认框；用户在确认前点击返回，没有确认删除。旧日志的通用“确认”不能证明领取成功。请先追查坐标链（1920x1080 游戏坐标、窗口 bounds、macOS 屏幕逻辑坐标、PyAutoGUI 指针、虚拟 HID 按键），通过应用实际截图路径拿到可信画面，并只用安全、可逆、不会触发领取/删除/购买/确认的按钮验证。截图不可靠或目标不明确时停止并询问用户，不要自动点邮件流程。

代码已有 0.1 秒点击等待、目标/实际坐标日志、邮件删除确认文字保护，但效果尚未在游戏内验证。不要假定等待修复偏移；查明坐标变换后做最小修正。不要确认任何删除或领取弹窗。

GUI 以普通用户运行，Karabiner 虚拟 HID 客户端由启动脚本单独提权。不要递归更改权限或所有者；已知旧 root 文件导致 notice_cache/notice_cache.json 和 config/01/one_dragon/_group.yml 写入失败，先只读检查，需修改时先征求用户同意。不要打包。

测试只放独立 zzz-od-test 仓（如果已存在），不要在主仓增加测试文件。报告时分别说明代码检查、GUI、截图/OCR、安全点击、邮件领取验证状态；未验证的不得说已修复或已领取。
```
