<!-- markdownlint-restore -->
<div align="center">

<img src="https://socialify.git.ci/DoctorReid/ZenlessZoneZero-OneDragon/image?description=1&font=Inter&language=1&logo=https%3A%2F%2Fgithub.com%2FDoctorReid%2FZenlessZoneZero-OneDragon%2Fblob%2Fmain%2F.github%2Fimage%2Fellen.png%3Fraw%3Dtrue&name=1&owner=1&pattern=Charlie+Brown&theme=Light" alt="ZenlessZoneZero-OneDragon"/>
<div>

---

</div>

__ZenlessZoneZero-OneDragon__


<div>
    <img alt="platform" src="https://img.shields.io/badge/platform-Windows-blueviolet">
    <img alt="commit" src="https://img.shields.io/github/commit-activity/m/DoctorReid/ZenlessZoneZero-OneDragon?color=blue">
</div>
<div>
    <img alt="stars" src="https://img.shields.io/github/stars/DoctorReid/ZenlessZoneZero-OneDragon?style=social">
    <img alt="GitHub all releases" src="https://img.shields.io/github/downloads/DoctorReid/ZenlessZoneZero-OneDragon/total?style=social">
</div>

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/OneDragon-Anything/ZenlessZoneZero-OneDragon)

学习实践 __图像识别 & 自动化__ 的智能解决方案

✨ 如果喜欢本项目，欢迎右上角点亮`Star`支持 ✨

</div>

## 🍎 macOS 安装与使用指南（怎么打开、怎么用）

本分支支持在 **Apple Silicon Mac** 上通过 **PlayCover** 运行《绝区零》并使用一条龙自动化。

### 一、前置准备

1. **PlayCover 与游戏设置**
   - 在 PlayCover 中安装并运行《绝区零》（窗口标题支持 `绝区零` / `絕區零` / `ZenlessZoneZero`）。
   - 游戏需注入仓库内置的 [`tools/macos/libUnityDesktopMode.dylib`](../tools/macos/libUnityDesktopMode.dylib) 插件，使游戏以 **PC 桌面模式**接收键鼠输入，并**关闭 PlayCover 内置的键位映射（Keymapping）**。
   - 建议将游戏窗口比例保持为 **16:9**（例如 `1920x1080`）。

2. **安装虚拟鼠标驱动（Karabiner VirtualHIDDevice）**
   - 安装并启用 **Karabiner-DriverKit-VirtualHIDDevice**（如果您已安装 Karabiner-Elements，即已包含该驱动）。
   - 首次安装后，请前往 **系统设置 -> 通用 -> 登录项与扩展 -> 驱动程序扩展** 中批准启用 Karabiner 驱动。

3. **安装 `uv` 与 Xcode Command Line Tools**
   - 打开终端（Terminal），确保已安装 Xcode 命令行工具与 `uv`：
     ```bash
     xcode-select --install
     curl -LsSf https://astral.sh/uv/install.sh | sh
     ```

4. **克隆仓库并初始化虚拟环境（仅首次需要）**
   - 将整个仓库 clone 下来，并在仓库根目录执行 `uv sync`：
     ```bash
     git clone https://github.com/pokemc32ryan/ZenlessZoneZero-OneDragon-mac.git
     cd ZenlessZoneZero-OneDragon-mac
     uv sync
     ```

---

### 二、怎么打开一条龙

日常启动只需 **1 个终端窗口**，无需手动开两个终端：

- **方式 A（推荐，双击启动）**：在 Finder 中打开仓库根目录，直接双击 **`启动一条龙.command`**。
- **方式 B（终端命令启动）**：在仓库根目录下执行：
  ```bash
  ./启动一条龙.command
  ```
  *(注意：**不要**加 `sudo` 执行脚本；脚本内部会在需要时自动提示输入一次开机密码，用于在当前终端后台拉起 Karabiner 虚拟 HID 守护进程，退出一条龙时会自动清理。)*

#### 首次打开时的 macOS 权限授权
首次运行弹出系统权限提示时，请在 **系统设置 -> 隐私与安全性** 中为**实际运行脚本的终端（如 Terminal / iTerm）及 Python** 授予：
1. **屏幕录制与系统录音权限**（用于按窗口 ID 截取游戏画面，以及通过 `ScreenCaptureKit` 直接识别自动战斗闪避音效，无需切换虚拟声卡）。
2. **辅助功能权限（Accessibility）**与**输入监控权限（Input Monitoring）**（用于监听快捷键 `F9` / `F10` 等并发送键鼠控制）。

---

### 三、怎么使用

1. **打开游戏**：先在 PlayCover 中启动《绝区零》（停留在**登录画面「点击进入游戏」**或**游戏内大世界**均可）。
2. **首次基础配置**：
   - 在一条龙界面左侧进入 **账户管理**，选择对应的游戏区服（国服 / B服 / 国际服）。
   - 在 **一条龙 -> 运行设置** 中勾选需要执行的日常任务（如邮件、每日签到、咖啡店、录像店营业、刮刮乐、恶名狩猎、体力刷本、迷失之地等），并在对应模块配置好配队与体力计划。
3. **开始 / 暂停运行**：
   - 点击界面右下角的 **「开始」** 按钮（或直接按快捷键 **`F9`**）启动。
   - 若启动时游戏正停留在登录画面，一条龙会自动点击第一次「点击进入游戏」、等待「加载配置数据中」进度跑完、再次点击「点击进入游戏」进入大世界后开始执行任务。
   - 运行过程中：
     - 游戏需要保持在**前台**接收键鼠输入（请勿在运行期间移动鼠标或切换窗口）。
     - 按 **`F9`** 可随时暂停 / 继续，按 **`F10`** 可立即停止当前任务。

## 🚀 功能介绍

<div align="left">

🤖 __自动战斗__：支持自定义逻辑、技能标记、条件、变量等进阶用法

🛡️ __闪避助手__：基于声音、图像一体化模型识别，轻占用，高准确

🧹 __日常清理__：影像店、刮刮乐、咖啡店、材料、奖励等全日常清理

☕ __空洞作战__：基于大模型训练的识别、事件、寻路的功能模块

⏲️ __更多功能__： 定时启动、多账号切换、定时任务、自动对话……

</div>

## 📸 页面预览

<div align="center">

![App Interface](./image/app.webp#gh-light-mode-only "操作界面")
*✨ 简洁直观的操作界面 ✨*

</div>

## ⚠️ 免责声明

📌 本项目仅供学习交流，开发者团队保留最终解释权

🎨 项目LOGO版权归[巡夜子](https://github.com/yokuminto)及全体开发者所有

⚖️ 使用本工具产生的一切风险需自行承担

🚫 本项目未授权任何个人、商家、自媒体账号等进行售卖

🚫 若您遇到商家使用本软件进行代练并收费，产生的任何问题及后果与本软件无关

🚫 开发者团队不会为您提供任何"售后"服务

## 🌟 贡献者们

<div>

感谢参与项目的所有贡献者 ([完整名单](https://github.com/DoctorReid/ZenlessZoneZero-OneDragon/graphs/contributors))：

![Contributors](https://contrib.rocks/image?repo=DoctorReid/ZenlessZoneZero-OneDragon&columns=12)

是你们的参与共同构建了这个项目，让这个项目越来越好♡
如果想要参与开发，欢迎查看 [贡献者招募](../docs/develop/RECRUITING.md)（技术栈 / 参与方式 / 成长故事），并按 [快速开始](../docs/develop/setup/quickstart.md) 把项目跑起来，期待你的加入 ✨

</div>

## 📢 官方渠道

<div>

🔗 [官方网站](https://one-dragon.com/)
> 项目简介 | 新手入门 | 功能说明 | 配置说明

💬 [官方频道](https://pd.qq.com/g/onedrag00n)
> 公告要闻 | 软件科研 | 游戏攻略 | 趣闻分享

❓ [官方文档](https://docs.qq.com/doc/p/7add96a4600d363b75d2df83bb2635a7c6a969b5)
> 常见问题 | 故障速查 | 疑难诊断 | 更新指南

👉 [官方议题](https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/issues)
> 故障反馈 | 问题讨论 | 优化建议 | 建言收集

👨‍👨‍👦‍👦 玩家社群
> 闲聊吹水 | 趣闻互动 | 交流同好 | 晒卡吸欧
>
> 见频道关联群聊，入群前先对该项目点个 ⭐star，入群问题的项目仓库的答案为ZenlessZoneZero-OneDragon，入群后需校验你的 Github 账号的 username
>
> 提示：推荐 GitHub 用户加入，并注意 username 和 Name 的区别，请遵守群规，友善交流

</div>

## 📝 签名策略 (Code Signing Policy)

免费代码签名由 [SignPath.io](https://signpath.io/) 提供，证书由 [SignPath Foundation](https://signpath.org/) 颁发

审批人：[DoctorReid](https://github.com/DoctorReid) [ShadowLemoon](https://github.com/ShadowLemoon)

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/)

Approvers: [DoctorReid](https://github.com/DoctorReid) [ShadowLemoon](https://github.com/ShadowLemoon)

## 🔒 隐私政策 (Privacy Policy)

本程序的隐私政策详见：[隐私政策](PRIVACY.md)。

See the [Privacy Policy](PRIVACY.md).

## ☕ 支持我们

<div align="center">

如果本项目为您带来便利，欢迎支持服务器维护：

<img src="./image/sponsor.png" width = "480" alt="图片名称" align=center />

💖 查看[致谢名单](https://onedragon-anything.github.io/other/zh/like/thanks_2024.html)

</div>
