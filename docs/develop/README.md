# 开发指南

## Vibe Coding

### Agent指南

推荐使用 [agent_guidelines.md](spec/agent_guidelines.md) 指导Agent进行编程

可以通过创建硬链接到各个编程工具所需位置

- Qwen Coder - `New-Item -ItemType HardLink -Path "QWEN.md" -Target "docs/develop/spec/agent_guidelines.md"`
- Lingma Rules - `New-Item -ItemType HardLink -Path ".lingma/rules/project_rule.md" -Target "docs/develop/spec/agent_guidelines.md"`
- Gemini CLI - `New-Item -ItemType HardLink -Path "GEMINI.md" -Target "docs/develop/spec/agent_guidelines.md"`
- Claude Code - `New-Item -ItemType HardLink -Path "CLAUDE.md" -Target "docs/develop/spec/agent_guidelines.md"`


### 推荐MCP

- [context7](https://github.com/upstash/context7) - 查询各个库的文档。 