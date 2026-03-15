# 开发规范

本文档规定了项目开发过程中需要遵守的编码规范和最佳实践。

## 关键开发原则

1. **最小化设计** - 只实现满足需求的最小功能集，避免过度设计
2. **文档同步** - 修改模块后必须更新对应的文档文件

## Python 代码规范

### 文档字符串

- 所有函数必须有 Google 风格的文档字符串
- 文档字符串使用中文编写
- 类和重要逻辑也需要添加注释说明

### 类型提示

- 所有类成员变量和函数签名必须包含类型提示 (Type Hints)
- 使用内置泛型类型 (`list`, `dict`) 而不是从 `typing` 模块导入 (`List`, `Dict`)
- 示例：
  ```python
  def process_items(items: list[str]) -> dict[str, int]:
      ...
  ```

### 导入规范

编写源码时需要遵循以下导入规范：

- **使用绝对路径导入**：禁止使用相对路径导入
  ```python
  # 正确
  from one_dragon.base.operation import Operation

  # 错误
  from ..operation import Operation
  ```

- **类型注解导入**：仅用于类型注解的导入应使用 `TYPE_CHECKING`
  ```python
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from one_dragon.base.operation import Operation
  ```

### 类构造函数

- 类的构造函数 `__init__` 必须显式声明所有必需的和可选的参数
- 尽量避免使用 `**kwargs` 来传递未知参数
- 这有助于提高代码的可读性和类型检查的准确性

### 父类构造函数调用

- 在所有子类的 `__init__` 方法中，调用父类构造函数时必须显式传入所有必需参数
- 允许使用 `super().__init__(...)`，但必须确保所有参数都显式传递
- 示例：
  ```python
  super().__init__(arg1=value1, arg2=value2)
  ```

### 代码风格

- **禁止特殊字符**：禁止在代码中使用表情符号和特殊 Unicode 符号（如 emoji、数学符号等）
- **显式数据结构**：应该定义一个对象，而不是使用 dict
- **不暴露任何模块**：没有收到指示的情况下，不要在 `__init__.py` 中新增暴露任何模块

### GUI 组件

- 前端组件优先使用 `pyside6-fluent-widgets` 库中现有组件
- 如需实现新组件，需按照 Fluent Design 实现样式效果

### 代码格式化

- 使用 ruff 进行代码格式化和检查
- 使用 pyright 进行静态类型检查
- 运行 `uv run ruff check src/ tests/` 检查代码
- 运行 `uv run ruff format src/ tests/` 格式化代码
- 运行 `uv run pyright src/` 检查类型
