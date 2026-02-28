# 开发指南

## 1.开发

### 1.1.开发环境

项目使用 [uv](https://github.com/astral-sh/uv/releases/latest) 进行依赖管理，使用以下命令可安装对应环境。

```shell
uv sync --group dev
```

项目整体布局使用`src-layout`结构，源代码位于`src/`目录下。请自行在IDE中设置为`Sources Root`，或增加环境变量`PYTHONPATH=src`。

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

## 1.4.代码提交

提交PR后

- reviewer: 任何需要确定 or 修改的内容，都通过start review提交。后续解决后由reviewer点击resolve。
- 提交者: 所有AI或reviewer提交的review comment，都需要回复 or 修改，后续由reviewer点击resolve。

## 2.Vibe Coding

### Agent指南

推荐使用 [agent_guidelines.md](spec/agent_guidelines.md) 指导Agent进行编程

可以通过创建硬链接到各个编程工具所需位置

- Qwen Coder - `New-Item -ItemType HardLink -Path "QWEN.md" -Target "docs/develop/spec/agent_guidelines.md"`
- Lingma Rules - `New-Item -ItemType HardLink -Path ".lingma/rules/project_rule.md" -Target "docs/develop/spec/agent_guidelines.md"`
- Gemini CLI - `New-Item -ItemType HardLink -Path "GEMINI.md" -Target "docs/develop/spec/agent_guidelines.md"`
- Claude Code - `New-Item -ItemType HardLink -Path "CLAUDE.md" -Target "docs/develop/spec/agent_guidelines.md"`


### 推荐MCP

- [context7](https://github.com/upstash/context7) - 查询各个库的文档。

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

> 详细设计文档见 [runtime-launcher.md](runtime-launcher.md)

#### 架构概述

集成启动器将 Python 运行时直接嵌入发行包，无需用户单独安装 Python / uv。

- **PyInstaller 目录模式**：`contents_directory='.runtime'`，运行时文件放在 `.runtime/` 子目录
- **最小打包**：仅打包 `one_dragon.launcher`、`one_dragon.version` 模块和二进制依赖（pygit2 等）
- **源码加载**：借助 `hook_path_inject.py` 运行时钩子，将 `<exe_dir>/src` 注入 `sys.path`，其余模块从 `src/` 目录加载
- **自动更新**：首次运行时自动克隆代码仓库；后续运行时根据 `auto_update` 配置自动拉取最新代码
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
