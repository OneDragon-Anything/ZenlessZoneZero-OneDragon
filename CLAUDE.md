# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

详细的项目介绍和快速开始请参考：[@docs/develop/project-overview.md](docs/develop/project-overview.md)

## 规范说明

- **开发流程**: [@docs/develop/standards/workflow-standard.md](docs/develop/standards/workflow-standard.md)
- **编码规范**: [@docs/develop/standards/coding-standards.md](docs/develop/standards/coding-standards.md)
- **测试规范**: [@docs/develop/standards/testing-standards.md](docs/develop/standards/testing-standards.md)
- **文档规范**: [@docs/develop/standards/documentation-standards.md](docs/develop/standards/documentation-standards.md)

## 工具使用规范

### Bash工具规范

- 优先使用Bash工具的后台运行能力，避免在命令最后使用 `&` 来实现后台运行。
- 禁止使用 `python`, `python3`, `pip`, `pip3` 等命令，使用 `uv` 运行python相关命令。
- `uv run` 时，必须使用 `--env-file .env` 加载环境变量。

### 其他工具规范

- 积极使用 `context7` 工具查询依赖库的用法，包括类、属性、方法、参数等。
