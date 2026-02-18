---
applyTo: "**"
---

# General Instructions
- **Language**: 请始终使用 **简体中文** 回复。
- **Thinking**: 遇到复杂问题时，优先使用 `sequential-thinking` 工具制定计划。
- **Documentation**: 使用 `context7` 工具查找文档。
- **Environment**: 项目启动前要 `activate uv`，把源根加入 `PYTHONPATH`。

# Coding Standards (Best Practices)
- **Python Version**: 目标 Python 3.11+。使用现代特性（如 `list[str]` 代替 `List[str]`，`|` 代替 `Union`）。
- **Type Hinting**: 所有函数和方法必须包含类型注解 (Type Hints)。
- **Path Handling**: 优先使用 `pathlib` 库处理路径，而非 `os.path`。
- **String Formatting**: 优先使用 f-string 进行字符串格式化。
- **Error Handling**: 避免不必要的 try-catch。除非能进行有意义的处理，否则让异常抛出。
- **KISS Principle**: 保持代码简单。不要增加无用的代码、过度设计或非必要的抽象。
- **Testing/Docs**: 除非明确要求，否则不要主动创建测试脚本或文档。

# Code Review Guidelines (PR Review)
在进行代码审查或生成代码时，请严格遵守以下规则以减少无用的噪音：
1. **环境假设**：本项目主要针对 **1080p 分辨率** 和 **PC 平台**。
   - **允许** 硬编码像素坐标（基于 1080p）。
   - **允许** 硬编码键盘按键（如 '`', 'esc'）。
   - **不要** 建议添加分辨率适配或控制器类型检查，除非逻辑完全错误。
2. **代码风格**：
   - **忽略** 缩进、空行、空格等格式微调（由 Ruff/Linter 处理）。
   - **允许** 在逻辑简单时使用 Magic Number（如 `1000`），不要强制要求提取常量。
3. **审查重点**：
   - **只关注**：严重的逻辑错误、死循环、潜在的运行时崩溃 (Runtime Error)、资源泄漏。
   - **不关注**：代码风格、过度工程化的“最佳实践”、非必要的抽象。