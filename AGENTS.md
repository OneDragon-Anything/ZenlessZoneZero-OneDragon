# AGENTS.md

本文件是项目级 AI 编码协作入口，只保留会直接影响实现落点与提交流程的约束。
详细规范与背景资料不要堆在这里，按需继续阅读：
- 开发环境与 Vibe Coding 配置：[docs/develop/README.md](docs/develop/README.md)
- 详细编码规范：[docs/develop/spec/agent_guidelines.md](docs/develop/spec/agent_guidelines.md)
- 一条龙整体架构：[docs/develop/one_dragon/one_dragon_architecture.md](docs/develop/one_dragon/one_dragon_architecture.md)
- 应用插件开发指引：[docs/develop/guides/application_plugin_guide.md](docs/develop/guides/application_plugin_guide.md)
- 应用设置界面开发指引：[docs/develop/guides/application_setting_guide.md](docs/develop/guides/application_setting_guide.md)

## 项目概述

- 项目：绝区零一条龙（ZenlessZoneZero-OneDragon），面向 Windows 的绝区零自动化工具。
- 语言与环境：Python 3.11、uv、PySide6。
- 代码布局：`src-layout`，源码在 `src/`，运行时配置在 `config/`，资源在 `assets/`，开发文档在 `docs/develop/`。
- 运行基准：1080p；配置以 YAML 为主。
- 测试仓库独立维护：`zzz-od-test/` 需要单独放在仓库根目录。

## 常用命令

```shell
uv sync --group dev
uv run --env-file .env src/zzz_od/gui/app.py
uv run --env-file .env pytest zzz-od-test/
uv run --env-file .env ruff check src/你修改的文件.py
uv run --env-file .env ruff format src/你修改的文件.py
```

- 只对自己修改的文件运行 `ruff check` / `ruff format`。
- 不要对整个 `src/` 目录运行 ruff，现有仓库尚未全面适配。
- 优先使用 Windows PowerShell 可直接执行的命令。

## 架构落点

### 1. 核心分层

- `src/one_dragon/`：通用基础框架、配置、环境、工具、YOLO 能力。
- `src/one_dragon_qt/`：通用 Qt GUI 框架与公共组件。
- `src/onnxocr/`：OCR 引擎。
- `src/zzz_od/`：绝区零业务代码，包括 application、operation、context、gui、yolo 等。

### 2. 功能开发优先路径

- 新功能优先评估是否应做成 `Application`，放在 `src/zzz_od/application/`，并通过 `ApplicationFactory` 接入。
- 不要直接把新流程硬塞进主线逻辑；先复用现有 Application、Operation、配置体系与界面组件。
- 新的设置界面优先沿用现有 setting card、`YamlConfigAdapter`、`AdapterInitMixin` 等模式。

### 3. 关键运行机制

- `ZContext` 管理懒加载服务与配置；实例级配置变更要走 `reload_instance_config()` 对应机制。
- 这里的 `Operation` 指框架里的基础操作单元；文档里提到的“流转 / flow”是由这些 `Operation` 节点组成的执行链。
- 操作链基于 `ZOperation` / `Operation` 编排；状态流转沿用现有 round 系列接口与节点声明方式。
- GPU/onnx session 的异步调用必须通过 `gpu_executor.submit`，不要并发直调多个 session。

## 开发硬约束

- 所有函数签名、类成员变量都要有类型注解；使用 `list[str]`、`X | Y`。
- 注释与 docstring 用中文，保持现有项目风格。
- 禁止相对导入；仅类型注解使用 `TYPE_CHECKING` 导入。
- `__init__.py` 默认不要暴露模块，除非已有明确模式或收到明确要求。
- 构造函数显式声明参数，不要用 `**kwargs`。
- 路径操作使用 `pathlib`，字符串格式化使用 f-string。
- GUI 优先复用 `pyside6-fluent-widgets` 与现有项目组件，保持 Fluent Design。
- 配置改动优先落到 YAML 与对应 `YamlConfig` 子类，不要随意散落硬编码配置。
- 1080p 坐标属于项目既有前提，可以按现有模式硬编码，不要额外做分辨率适配设计。

## 文档与测试要求

- 修改代码后，同步更新对应的 `docs/develop/` 文档与 `zzz-od-test/` 测试。
- 若测试依赖截图或环境变量，按 [docs/develop/README.md](docs/develop/README.md) 中说明准备 `.env` 与测试仓。
- 提交前至少验证自己改动直接影响的部分；若无法本地完成，要明确说明缺失前提。
- 复杂功能、架构调整或新自动化流程，先补设计/说明文档，再继续实现。

## 提交流程与协作边界

- 默认不要主动执行 `git commit`、`git push`、`git reset`、删分支等版本控制操作，除非用户明确要求。
- 如果用户明确要求切换分支，先 `stash` 当前改动，再切换。
- Review 关注逻辑错误、运行时崩溃、死循环、资源泄漏；不要为风格问题大改现有代码。
- 提交 PR 后，review comment 需要逐条回复或修正。

## 深入阅读

只在当前任务确实需要时继续看这些文档：
- 框架与模块架构：`docs/develop/one_dragon/`、`docs/develop/one_dragon/modules/`
- 游戏业务与专项设计：`docs/develop/zzz/`
- 打包与 RuntimeLauncher：`docs/develop/README.md`、`docs/develop/one_dragon/runtime_launcher.md`

## AI 工具接入

本仓库以根目录 `AGENTS.md` 作为统一入口；其他工具按 [docs/develop/README.md](docs/develop/README.md) 中的硬链接说明接入即可。
