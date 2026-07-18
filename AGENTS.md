# AGENTS.md

本文件是项目级 AI 编码协作入口，只保留会直接影响实现落点与提交流程的约束。
详细规范与背景资料不要堆在这里，按需继续阅读：
- 开发环境与打包：[docs/develop/README.md](docs/develop/README.md)
- 详细编码规范：[docs/develop/spec/agent_guidelines.md](docs/develop/spec/agent_guidelines.md)
- 一条龙整体架构：[docs/develop/one_dragon/one_dragon_architecture.md](docs/develop/one_dragon/one_dragon_architecture.md)
- 应用插件开发指引：[docs/develop/guides/application_plugin_guide.md](docs/develop/guides/application_plugin_guide.md)
- 应用设置界面开发指引：[docs/develop/guides/application_setting_guide.md](docs/develop/guides/application_setting_guide.md)

## 项目概述

- 项目：绝区零一条龙（ZenlessZoneZero-OneDragon），面向 Windows 的绝区零自动化工具。
- 语言与环境：Python 3.11、uv、PySide6。
- 代码布局：`src-layout`，源码在 `src/`，运行时配置在 `config/`，资源在 `assets/`，开发文档在 `docs/develop/`。
- 运行基准：1080p；配置以 YAML 为主。
- 所有测试统一在独立仓 `zzz-od-test/test/`(`.gitignore`,须 clone 到仓库根目录才能读/改;clone 见 [quickstart §②](docs/develop/setup/quickstart.md),测试规范见 [testing/](docs/develop/testing/README.md))。主仓不保留测试。AI 查测试用 `Read`/`grep` 显式指定 `zzz-od-test/`(默认搜索会跳过 .gitignore)。
- 相关仓库全貌(测试仓 / yolo 训练仓 / 数据集 / 官网 blog)见 [相关仓库](docs/develop/setup/repositories.md);外部贡献者需 fork 后开发。

## 常用命令

```shell
uv sync --group dev
uv run --env-file .env src/zzz_od/gui/app.py
uv run --env-file .env pytest zzz-od-test/
uv run --env-file .env ruff check src/你修改的文件.py
uv run --env-file .env ruff check --fix src/你修改的文件.py
```

- 只对自己修改的文件运行 `ruff check`。
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

## 开发流程（端到端）

游戏自动化功能的开发链路(bug 修复 / 性能 / UI 等其他类型后续补充,详细判据见 [development_workflow.md](docs/develop/development_workflow.md)):

1. **画面建档**(涉及新画面时):按 `zzz-od-dev-screen-onboarding` skill 截图 / 分析 / 建模 / 留档。功能知识按**四文档分工**(gameplay 玩法 / mechanics 通用机制 / screen 画面 / develop application 自动化,见 [doc_organization.md](docs/develop/harness/doc_organization.md))。
2. **开发**:做成 `Application`(`ApplicationFactory` 接入)+ `Operation`,复用现有配置 / 界面模式(架构细则见上方「功能开发优先路径」)。
3. **测试**:用留档截图在测试仓补流程测试(见 [testing/](docs/develop/testing/))。
4. **提 PR**:assign **DoctorReid / ShadowLemoon**,按 `zzz-od-dev-pr-finishing` skill 走 review / resolve。
5. **配套(按需)**:模型 → [yolo/dataset 仓](docs/develop/setup/repositories.md);使用说明 → blog(**用户可见变化**才更新)。

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
- 测试方法论（测试基建 / FixtureController 流程测试 / 画面截图存档）见 [docs/develop/testing/](docs/develop/testing/README.md)。
- 若测试依赖截图或环境变量，按 [docs/develop/README.md](docs/develop/README.md) 中说明准备 `.env` 与测试仓。
- 提交前至少验证自己改动直接影响的部分；若无法本地完成，要明确说明缺失前提。
- 复杂功能、架构调整或新自动化流程，先补设计/说明文档，再继续实现。

## 提交流程与协作边界

- 默认不要主动执行 `git commit`、`git push`、`git reset`、删分支等版本控制操作，除非用户明确要求。
- 测试改动在独立仓 `zzz-od-test` 提交:主仓 `git add zzz-od-test/...` 会被 `.gitignore` **静默跳过**(不报错但未加入)→ 须 `git -C zzz-od-test add test/ && git -C zzz-od-test commit` 单独提交,否则 PR 丢测试。
- 如果用户明确要求切换分支，先 `stash` 当前改动，再切换。
- Review 关注逻辑错误、运行时崩溃、死循环、资源泄漏；不要为风格问题大改现有代码。
- 提交 PR 后，review comment 需要逐条回复或修正。

## 自维护指南（改 AI 入口文件）

`AGENTS.md` / `.claude/CLAUDE.md` / `.github/copilot-instructions.md` 是 **AI 入口文件**（每次会话完整进 context）。改它们时按 [entry_files.md](docs/develop/harness/entry_files.md)：
- **只放指令，不掺元信息**：入口只写给 AI 的指令（做什么）；维护注释 / TODO / 变更说明 → commit / docs，不进入口。
- **只留每次会话总要看的**：逐条问「删了会出错吗」，不会错就砍（入口要精简，不是知识库）；特定任务流程转 skill / 指针。
- **一处维护**：`AGENTS.md` 是源，其他入口（CLAUDE.md 等）`@import` 引入，不复制。
- **共享先确认**：入口文件团队共享，改前问用户，不静默重写。
- **写得清晰易懂**：改入口文件 / 方法论文档时，用直白表述（首次出现的术语给定义 + 给例子），让首次接触的 AI 也读得懂；术语定义指向 [context_layering](docs/develop/harness/context_layering.md) / [entry_files](docs/develop/harness/entry_files.md)。

## 产出前先判断：信息放哪、写什么

写 doc / skill 前（以及信息重复、边界不清时），先判断放哪层、写什么，别盲目堆：
- **方法 → skill，具体 → doc**：方法 = 怎么做（建档流程 / 判据 / 排查思路）；具体 = 是什么（键位 / 坐标 / 游戏机制）。详见 [doc_organization](docs/develop/harness/doc_organization.md) + [context_layering](docs/develop/harness/context_layering.md)。
- **玩法 vs 自动化 分开**：玩法机制（玩家视角：目标 / 循环 / 资源）和自动化实现（脚本流程 / config / 节点编排）是两个维度，各进各的 doc、互引不混写。
- **不重复（单一源）**：同一事实只留一处；复述 → 引用；多 doc 共有的共性 → 抽到上一层 doc（如通用机制抽进 `mechanics/`）。
- **分不清 / 不确定 → 问用户，或把判据写进对应方法论 skill**（别含混带过）。

## 深入阅读

只在当前任务确实需要时继续看这些文档：
- AI 协作 harness（知识分层 / 上下文工程）：[harness/README.md](docs/develop/harness/README.md)
- 框架与模块架构：`docs/develop/one_dragon/`、`docs/develop/one_dragon/modules/`
- 游戏业务与专项设计：`docs/develop/zzz/`
- 游戏知识库（给智能体理解游戏）：`docs/game/`（画面描述 `screens/` + 玩法 `gameplay/`）
- 后端服务 / MCP 对外能力：`docs/develop/zzz/backend/`（入口 README；开发 MCP tool 前先看 design-principles）
- 打包与 RuntimeLauncher：`docs/develop/README.md`、`docs/develop/one_dragon/runtime_launcher.md`
