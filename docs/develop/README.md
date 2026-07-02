# 开发指南

> `docs/develop/` 的入口与索引。开发环境与流程见 §1–§3；各类专题文档按下索引查阅。

## 文档索引

- **开发环境与工具**：[快速开始](setup/quickstart.md) · [AI 编码助手接入](setup/ai_coding.md)
- **编码规范**：[agent_guidelines.md](spec/agent_guidelines.md)
- **架构设计**：[一条龙整体架构](one_dragon/one_dragon_architecture.md) · [集成启动器 RuntimeLauncher](one_dragon/runtime_launcher.md) · [模块文档](one_dragon/modules/)
- **开发指引**：[应用插件开发](guides/application_plugin_guide.md) · [应用设置界面](guides/application_setting_guide.md)
- **游戏业务**：[自动战斗](zzz/auto_battle.md) · [进游戏](zzz/enter_game.md) · [转向与灵敏度](zzz/turn_sensitivity.md) · [功能模块](zzz/application/) · [后端服务层](zzz/backend/)
- **AI Harness 工程**：[总览与路线图](harness/README.md)
- **设计文档**：[屏幕区域识别设计](screen_scope_design.md) · [屏幕区域推进](screen_scope_rollout.md)

## 1.开发

### 1.1.开发环境

见 [setup/quickstart.md](setup/quickstart.md)（从零把项目跑起来）。

### 1.2.代码规范

参考 [agent_guidelines.md](spec/agent_guidelines.md)

#### 1.2.1.多线程

当前使用 onnxruntime-dml 在多线程下同时访问多个session是会出现各种意想不到的异常的，因此需要异步使用onnx session时，需统一使用 `gpu_executor.submit` 来提交，保证只有一个session被访问。

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
uv run pyinstaller --onefile --windowed --uac-admin --icon="../assets/ui/installer_logo.ico" --add-data "../config/project.yml;config" ../src/zzz_od/gui/zzz_installer.py -n "OneDragon-Installer"
```

使用spec打包

```shell
uv run pyinstaller --noconfirm --clean "OneDragon-Installer.spec"
```

### 3.2.启动器（原始）

使用spec打包，会自动生成种子文件

```shell
uv run pyinstaller --noconfirm --clean "OneDragon-Launcher.spec"
```

### 3.3.集成启动器（RuntimeLauncher）

> 详细设计文档见 [runtime_launcher.md](one_dragon/runtime_launcher.md)

#### 架构概述

集成启动器将 Python 运行时直接嵌入发行包，无需用户单独安装 Python / uv。

- **PyInstaller 目录模式**：`contents_directory='.runtime'`，运行时文件放在 `.runtime/` 子目录
- **最小打包**：仅打包 `one_dragon.launcher`、`one_dragon.version` 模块和二进制依赖（pygit2 等）
- **源码加载**：借助 `hook_path_inject.py` 运行时钩子，将 `<exe_dir>/src` 注入 `sys.path`，其余模块从 `src/` 目录加载
- **自动更新**：首次运行时自动克隆代码仓库；后续运行时根据 `auto_update_code` 配置自动拉取最新代码
- **Manifest 兼容性检查**：`module_manifest.py` 记录打包时的外部依赖清单，更新代码后如新增依赖不在清单中，提示用户更新启动器

#### 打包命令

```shell
uv run pyinstaller --noconfirm --clean "OneDragon-RuntimeLauncher.spec"
```

#### 关键文件

| 文件 | 说明 |
|------|------|
| `deploy/OneDragon-RuntimeLauncher.spec` | PyInstaller 打包配置 |
| `deploy/hook_path_inject.py` | 运行时钩子，注入 `src/` 到 `sys.path` |
| `deploy/generate_module_manifest.py` | 生成外部依赖清单 |
| `deploy/module_manifest.py` | 自动生成的依赖清单（打包时生成） |
| `src/zzz_od/win_exe/runtime_launcher.py` | 集成启动器入口 |
