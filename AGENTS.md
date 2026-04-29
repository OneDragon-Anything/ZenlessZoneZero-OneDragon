# AGENTS.md

本文件为 AI 编码助手（Copilot、Claude Code、Cursor、Qwen Coder、Gemini CLI 等）提供项目上下文。
详细开发规范见 [docs/develop/spec/agent_guidelines.md](docs/develop/spec/agent_guidelines.md)。

## 项目简介

**绝区零一条龙 (ZenlessZoneZero-OneDragon)** —— 绝区零游戏自动化工具。
核心功能：自动战斗（40+ 角色模板）、闪避辅助（声音+图像ML识别）、日常一条龙（19个应用模块）、空洞零号（LLM识别）、定时任务、多账号管理。
运行平台：**Windows**，分辨率基准 **1080p**。

## 技术栈

- **语言**: Python 3.11（不使用 3.12+）
- **包管理**: [uv](https://github.com/astral-sh/uv)（不是 pip）
- **GUI**: PySide6 + [pyside6-fluent-widgets](https://qfluentwidgets.com/)（Fluent Design 风格，46+ 自定义组件）
- **ML 推理**: onnxruntime-directml（GPU）、OpenCV、YOLO（检测+分类）
- **OCR**: 自研 onnxocr（PaddleOCR 移植）
- **音频**: librosa（闪避声音识别）
- **格式化/Lint**: Ruff（Black 兼容，行长 88）
- **测试**: pytest + pytest-asyncio（测试代码在独立仓库 [zzz-od-test](https://github.com/OneDragon-Anything/zzz-od-test)）
- **打包**: PyInstaller（安装器 + 启动器 + 集成运行时 RuntimeLauncher）

## 项目结构

```text
src/
  one_dragon/          # 核心框架
    base/              #   基类和工具（config、controller、cv_process、matcher、screen、push...）
    envs/              #   环境配置（project_config、env_config、git_service、download_service）
    utils/             #   工具模块（cv2_utils、cal_utils、gpu_executor、http_utils...）
    yolo/              #   YOLO 推理（onnx_model_loader、yolov8_onnx_cls、yolov8_onnx_det）
  one_dragon_qt/       # Qt GUI 框架
    view/              #   通用视图（setting、devtools、one_dragon、standalone_app_run...）
    widgets/           #   通用组件（setting_card/、download_card/、install_card/...46个组件）
    services/          #   服务（theme_manager、styles_manager、pip、unpack_runner）
    windows/           #   窗口（app_window_base、main_app_window_base、PhosTitleBar）
  onnxocr/             # ONNX OCR 引擎（PaddleOCR 移植）
  zzz_od/              # 绝区零游戏业务逻辑
    application/       #   30个应用模块（一条龙日常 + 独立工具）
      battle_assistant/  #   战斗助手（auto_battle、dodge_assistant）
      hollow_zero/       #   空洞零号（lost_void、withered_domain）
      world_patrol/      #   锄大地
      notorious_hunt/    #   恶名狩猎
      shiyu_defense/     #   式舆防卫战
      ...更多日常应用
    auto_battle/       #   自动战斗核心（state machine、agent_state、atomic_op、target_state）
    config/            #   游戏配置（game_config、team_config、model_config）
    context/           #   上下文（ZContext - 管理 30+ 懒加载服务）
    controller/        #   PC 控制器（键鼠/手柄模拟）
    gui/               #   GUI 界面
      view/            #     页面（home、game_assistant、one_dragon、hollow_zero、setting...）
      app_setting/     #     应用设置（14个应用的独立配置界面）
      widgets/         #     游戏专用组件
    hollow_zero/       #   空洞零号核心逻辑（event、game_data、hollow_map）
    operation/         #   操作模块（enter_game、goto、transport、deploy...）
    screen_area/       #   截图区域定义
    yolo/              #   游戏专用 YOLO（flash_classifier、hollow_event_detector）
config/                # 运行时配置 YAML
  auto_battle_state_handler/  # 40+ 角色战斗状态处理器
  world_patrol_route/         # 锄大地路线
  project.yml / env.yml / model.yml  # 项目/环境/模型配置
assets/                # 游戏资源（模板图片、模型、文本）
docs/                  # 开发文档（docs/develop/）
deploy/                # PyInstaller 打包配置
zzz-od-test/           # 测试仓库（需单独克隆到根目录）
```

## 常用命令

```shell
uv sync --group dev                              # 安装依赖
uv run --env-file .env src/zzz_od/gui/app.py     # 运行 GUI
uv run --env-file .env pytest zzz-od-test/        # 运行测试
uv run ruff check src/你修改的文件.py              # Lint（仅检查自己改的文件）
uv run ruff format src/你修改的文件.py             # 格式化（仅格式化自己改的文件）
```

⚠️ **不要** 对整个 `src/` 目录运行 ruff，现有代码库尚未全面适配 ruff 规则，全量运行会导致大量文件被意外格式化。

优先使用 Windows PowerShell 支持的指令。环境变量在 `.env` 文件中。

## 关键架构概念

### 应用插件系统

所有游戏功能（体力刷本、锄大地、恶名狩猎等）都是独立的"应用"（Application），通过 `ApplicationFactory` 创建，在一条龙运行时由 `ApplicationLauncher` 统一调度。

- `DEFAULT_GROUP=True` 的应用出现在一条龙列表中
- `DEFAULT_GROUP=False` 的应用作为独立工具运行
- 新应用开发指引：[docs/develop/guides/application_plugin_guide.md](docs/develop/guides/application_plugin_guide.md)

### 上下文 (ZContext)

`ZContext` 是全局上下文，管理 30+ 个懒加载的服务和配置（`@cached_property`）。切换账号实例时通过 `reload_instance_config()` 刷新实例级配置。

### 操作链 (Operation)

所有游戏操作继承 `Operation` 基类，通过 `RoundBase` 编排成操作链。操作之间通过 `node_state` 传递状态。

### 自动战斗 (Auto Battle)

基于状态机的自动战斗系统：
- `AutoBattleOperator` 持有多个 `context`（agent、target、dodge、custom）
- `atomic_op` 定义原子操作（普攻、特殊技、终结技等）
- `agent_state` 定义角色状态（站场、速切、闪A等）
- 战斗模板在 `config/auto_battle_state_handler/` 中配置

### 多线程注意事项

onnxruntime-dml 多线程同时访问多个 session 会异常。异步使用 onnx session 时必须通过 `gpu_executor.submit` 提交，保证只有一个 session 被访问。

## 关键编码规范

- **类型提示**: 所有函数签名和类成员变量**必须**有类型注解。使用 `list[str]` 不用 `List[str]`，`X | Y` 不用 `Union`。
- **中文注释**: 注释和 docstring 使用中文（Google 风格），可以中英混用。不要建议翻译。
- **绝对导入**: 禁止相对导入。仅类型注解的导入用 `TYPE_CHECKING`。
- **构造函数**: 显式声明所有参数，避免 `**kwargs`。
- **路径**: 用 `pathlib`，不用 `os.path`。
- **字符串**: 用 f-string。
- **异常处理**: 代码应从简，try-catch 仅用于网络请求、文件读写等真正的高风险操作，其余情况让异常冒泡。
- **`__init__.py`**: 除非明确指示，不暴露模块。
- **Fluent Design**: GUI 组件优先用 pyside6-fluent-widgets 现有组件，新组件遵循 Fluent Design。
- **硬编码**: 允许硬编码 1080p 像素坐标和按键名，不要建议分辨率适配。
- **配置**: 运行时配置使用 YAML（`config/` 目录），通过 `YamlConfig` 基类管理。

## 贡献规范

### 复用优先

**不接受重复造轮子**。提交的功能应优先复用仓库中已有实现——包括基类、工具函数、GUI 组件、配置模式等。提交 PR 前先确认项目中是否已有类似功能，避免引入重复的抽象或工具。

### 插件优先

实现新功能时，**优先以插件形式完成**。参照 [应用开发指引](docs/develop/guides/application_plugin_guide.md)，将功能封装为独立的 Application（`src/zzz_od/application/`），通过 `ApplicationFactory` 注册，而非直接修改一条龙主流程。

### 复杂功能需先出文档

增加复杂功能（新模块、架构变更、新的自动化流程等）时，**需优先提交文档站说明**，提供动/静态架构图（推荐使用 Mermaid），让审查者和社区理解设计意图。可以使用 AI 辅助编写文档。

## 审查重点

- **只关注**: 逻辑错误、死循环、运行时崩溃、资源泄漏
- **不关注**: 代码风格（交给 Ruff）、过度工程化的最佳实践、Magic Number

## PR 流程

- 提交 PR 后，请按顺序完成：**自测 → 其他开发者测试 → 再呼叫审查**。人工审查人力紧张，未经测试的 PR 会被退回。
- Reviewer 通过 start review 提交意见，解决后由 reviewer 点 resolve
- 提交者需回复或修改所有 review comment

## 开发文档索引

### 核心框架 (one_dragon)

| 文档 | 说明 |
|------|------|
| [one_dragon_architecture.md](docs/develop/one_dragon/one_dragon_architecture.md) | 一条龙整体架构 |
| [initialization.md](docs/develop/one_dragon/initialization.md) | 初始化流程 |
| [runtime_launcher.md](docs/develop/one_dragon/runtime_launcher.md) | 集成运行时启动器（PyInstaller 目录模式） |
| [pip_mode_design.md](docs/develop/one_dragon/pip_mode_design.md) | pip 模式设计 |
| [background_mode_design.md](docs/develop/one_dragon/background_mode_design.md) | 后台模式设计 |

### 模块架构 (one_dragon/modules)

| 文档 | 说明 |
|------|------|
| [application_plugin_system.md](docs/develop/one_dragon/modules/application_plugin_system.md) | 应用插件系统架构 |
| [application.md](docs/develop/one_dragon/modules/application.md) | 应用模块设计 |
| [operation.md](docs/develop/one_dragon/modules/operation.md) | 操作模块（Operation 基类与操作链） |
| [conditional_operation.md](docs/develop/one_dragon/modules/conditional_operation.md) | 条件操作框架 |
| [cv_pipeline_architecture.md](docs/develop/one_dragon/modules/cv_pipeline_architecture.md) | CV 流水线架构（截图→识别→匹配） |
| [push.md](docs/develop/one_dragon/modules/push.md) | 推送通知模块 |
| [sqlite.md](docs/develop/one_dragon/modules/sqlite.md) | SQLite 存储模块 |

### 开发指南 (guides)

| 文档 | 说明 |
|------|------|
| [application_plugin_guide.md](docs/develop/guides/application_plugin_guide.md) | 应用插件开发指引（新功能必读） |
| [application_setting_guide.md](docs/develop/guides/application_setting_guide.md) | 应用设置界面开发指引 |

### 游戏业务 (zzz)

| 文档 | 说明 |
|------|------|
| [target_state_module_developer_guide.md](docs/develop/zzz/target_state_module_developer_guide.md) | 自动战斗目标状态模块开发者指南 |
| [charge_plan.md](docs/develop/zzz/application/charge_plan.md) | 体力计划应用 |
| [world_patrol.md](docs/develop/zzz/application/world_patrol.md) | 锄大地应用 |
| [intel_board.md](docs/develop/zzz/application/intel_board.md) | 情报板应用 |
| [suibian_temple.md](docs/develop/zzz/application/suibian_temple.md) | 随便观应用 |
| [web-architecture.md](docs/develop/zzz/web/web-architecture.md) | Web 架构 |

### 规范与流程

| 文档 | 说明 |
|------|------|
| [agent_guidelines.md](docs/develop/spec/agent_guidelines.md) | 详细编码规范和测试规范 |
| [README.md](docs/develop/README.md) | 开发环境搭建 + Vibe Coding 配置 |

## AI 工具配置

本项目根目录的 `AGENTS.md` 是 AI 编码助手的统一入口。各工具通过硬链接读取：

```powershell
# GitHub Copilot 已自动读取 .github/copilot-instructions.md（已配置指向本文件）
# 其他工具创建硬链接：
New-Item -ItemType HardLink -Path "QWEN.md" -Target "AGENTS.md"
New-Item -ItemType HardLink -Path ".lingma/rules/project_rule.md" -Target "AGENTS.md"
New-Item -ItemType HardLink -Path "GEMINI.md" -Target "AGENTS.md"
New-Item -ItemType HardLink -Path "CLAUDE.md" -Target "AGENTS.md"
```
