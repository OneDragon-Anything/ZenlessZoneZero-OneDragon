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

### 1.3.测试

由于部分测试代码需要游戏截图，防止仓库过大，测试相关代码存放在另一个仓库中，见 [zzz-od-test](https://github.com/OneDragon-Anything/zzz-od-test)

可以将测试仓库在本项目根目录下克隆使用。请自行在IDE中设置为`Test Sources Root`。

#### 1.3.1.环境变量

部分测试需要对应环境变量，请将测试仓库中的 `.env.sample` 复制到主仓库的根目录下，重命名为 `.env`。

如果你不想弄这么多环境变量，本地上可以只保证自己修改部分的测试用例通过。

Github Action 有完整的环境变量配置，会运行所有的测试用例。

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