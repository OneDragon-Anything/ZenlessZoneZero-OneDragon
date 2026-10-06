# 开发指南

> `docs/develop/` 的入口与索引。开发环境与流程见 §1–§3；各类专题文档按下索引查阅。

## 文档索引

- **开发环境与工具**：[快速开始](setup/quickstart.md) · [相关仓库](setup/repositories.md) · [AI 编码助手接入](setup/ai_coding.md)
- **编码规范**：[agent_guidelines.md](spec/agent_guidelines.md)
- **开发流程**：[端到端开发流程](development_workflow.md)
- **架构设计**：[一条龙整体架构](one_dragon/one_dragon_architecture.md) · [集成启动器 RuntimeLauncher](one_dragon/runtime_launcher.md) · [Git 服务与代码源回退](one_dragon/modules/git_service.md) · [资源下载源与候选回退](one_dragon/modules/resource_download.md) · [项目工作目录](one_dragon/modules/work_directory.md) · [模块文档](one_dragon/modules/)
- **开发指引**：[应用插件开发](guides/application_plugin_guide.md) · [应用设置界面](guides/application_setting_guide.md)
- **游戏业务**：[自动战斗](zzz/auto_battle.md) · [进游戏](zzz/enter_game.md) · [转向与灵敏度](zzz/turn_sensitivity.md) · [功能模块](zzz/application/) · [迷失之地](zzz/application/lost_void/) · [后端服务层](zzz/backend/) · [截图存档](zzz/screenshot_archive.md)
- **AI Harness 工程**：[总览与路线图](harness/README.md)
- **设计文档**：[屏幕区域识别设计](screen_scope_design.md) · [屏幕区域推进](screen_scope_rollout.md)
- **测试与画面**：[测试方法论](testing/) · [截图存档](zzz/screenshot_archive.md)

## 1.开发

### 1.1.开发环境

见 [setup/quickstart.md](setup/quickstart.md)（从零把项目跑起来）。

### 1.2.代码规范

参考 [agent_guidelines.md](spec/agent_guidelines.md)

#### 1.2.1.多线程

当前使用 onnxruntime-dml 在多线程下同时访问多个session是会出现各种意想不到的异常的，因此需要异步使用onnx session时，需统一使用 `gpu_executor.submit` 来提交，保证只有一个session被访问。

另外，onnx session 的线程池默认会自旋等待，空闲时也占用 CPU。本项目都是间歇调用，统一在创建 session 时关闭自旋（见 `onnxocr/inference_engine.py`、`one_dragon/yolo/onnx_model_loader.py`）。

### 1.3.测试

由于部分测试代码需要游戏截图，防止仓库过大，测试相关代码存放在另一个仓库中，见 [zzz-od-test](https://github.com/OneDragon-Anything/zzz-od-test)

可以将测试仓库在本项目根目录下克隆使用。请自行在IDE中设置为`Test Sources Root`。

#### 1.3.1.环境变量

部分测试需要对应环境变量，请将测试仓库中的 `.env.sample` 复制到主仓库的根目录下，重命名为 `.env`。

如果你不想弄这么多环境变量，本地上可以只保证自己修改部分的测试用例通过。

Github Action 有完整的环境变量配置，会运行所有的测试用例。

#### 1.3.2.运行测试

```shell
uv run --env-file .env pytest zzz-od-test/
```

> 测试方法论(测试基建 / FixtureController 流程测试 / 画面截图存档)见 [testing/](testing/)。

### 常用业务文档

- [转向与灵敏度配置](zzz/turn_sensitivity.md) - 说明 `turn_dx`、`gamepad_turn_speed`、前台/后台模式，以及锄大地、录像店营业、迷失之地、式舆防卫战各自的转向链路。

## 1.4.代码提交

提交PR后

- reviewer: 任何需要确定 or 修改的内容，都通过start review提交。后续解决后由reviewer点击resolve。
- 提交者: 所有AI或reviewer提交的review comment，都需要回复 or 修改，后续由reviewer点击resolve。

## 2.Vibe Coding

- AI 编码工具（Claude Code / GitHub Copilot / Qwen / Gemini 等）的接入方式、MCP 与扩展配置见 [setup/ai_coding.md](setup/ai_coding.md)。
- AI Coding Harness 工程的设计决策、skill 清单与 MCP 路线图见 [harness/](harness/README.md)。

## 3.打包

进入 deploy 文件夹，运行 `build_full.bat` 可一键打包所有组件。

### 3.1.安装器

生成spec文件并打包

```shell
uv run pyinstaller --onefile --windowed --uac-admin --icon="../assets/ui/installer_logo.ico" --add-data "../config/project.yml;config" --add-data "../config/repository.yml;config" ../src/zzz_od/gui/zzz_installer.py -n "OneDragon-Installer"
```

使用spec打包

```shell
uv run pyinstaller --noconfirm --clean "OneDragon-Installer.spec"
```

### 3.2.启动器（原始）

使用 spec 打包。`project.yml` 和 `repository.yml` 会随启动器写入 `resources/config`；原始启动器创建环境上下文时显式开启包内配置优先，其他入口仍读取仓库配置。

```shell
uv run pyinstaller --noconfirm --clean "OneDragon-Launcher.spec"
```

启动器的 `--version` 固定按 UTF-8 输出：版本描述含中文，按系统本地编码输出时，英文、日文、韩文等系统的本地编码无法表示这些字符，启动器会直接报错退出。旧版启动器仍按系统本地编码输出，因此版本查询先捕获原始字节，再依次尝试 UTF-8 与本地编码；不能依赖父 Python 的默认文本编码，也不要求用户关闭全局 UTF-8 模式。该路径只解析 stdout，stderr 的编码不应影响版本识别。

### 3.3.集成启动器（RuntimeLauncher）

> 详细设计文档见 [runtime_launcher.md](one_dragon/runtime_launcher.md)

#### 架构概述

集成启动器将 Python 运行时直接嵌入发行包，无需用户单独安装 Python / uv。

- **PyInstaller 目录模式**：`contents_directory='.runtime'`，运行时文件放在 `.runtime/` 子目录
- **冻结启动内核**：通用层定义启动流程和 profile 抽象基类，绝区零冻结入口注入项目子类；正常与恢复业务入口通过字符串动态导入
- **两棵完整源码**：正常模式只使用安装目录 `src/`；ready 前失败时，新进程只使用 `.runtime/builtin_src/src/` 进入恢复模式
- **恢复边界**：恢复模式只提供下载设置、版本选择和一键重装，不初始化自动化上下文；下载进度直接显示在恢复窗口内
- **自动更新**：外部源码仍可通过 Git 更新；恢复重装由不依赖 Qt 的恢复服务按固定 tag 编排下载、校验、代码检出和最终替换
- **两类清单**：`module_manifest.py` 检查第三方依赖兼容性，`builtin_src/manifest.json` 校验内置源码版本和 SHA-256

#### 打包命令

```shell
uv run pyinstaller --noconfirm --clean "OneDragon-RuntimeLauncher.spec"
```

#### 关键文件

| 文件 | 说明 |
|------|------|
| `deploy/OneDragon-RuntimeLauncher.spec` | 只冻结启动内核和第三方依赖的 PyInstaller 配置 |
| `src/one_dragon/launcher/runtime_launcher_bootstrap/launcher.py` | 通用冻结启动内核与进程级回退 |
| `src/one_dragon/launcher/runtime_launcher_bootstrap/profile.py` | 项目 profile 抽象基类 |
| `src/zzz_od/win_exe/runtime_launcher_profile.py` | 绝区零项目入口、显示名称和必要源码文件 |
| `src/zzz_od/win_exe/runtime_launcher_bootstrap.py` | 绝区零冻结入口 |
| `deploy/generate_builtin_source.py` | 生成完整内置源码和 SHA-256 清单 |
| `deploy/generate_module_manifest.py` | 生成第三方依赖清单 |
| `deploy/module_manifest.py` | 自动生成的依赖清单（打包时生成） |
| `src/zzz_od/win_exe/runtime_launcher.py` | 正常业务动态入口 |
| `src/zzz_od/win_exe/recovery_app.py` | 只提供资源下载的恢复入口 |
