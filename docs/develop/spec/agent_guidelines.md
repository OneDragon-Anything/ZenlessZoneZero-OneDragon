# 项目开发指南

请按照下述要求规范进行文档编写、代码开发、覆盖测试。

## 项目概述
- **Python 3.11智能Agent框架**，采用事件驱动、插件化架构
- **包管理器**: `uv`
- **测试**: 使用`pytest`和`pytest-asyncio`进行测试
- **项目布局**: 本项目使用`src-layout`结构，源代码位于`src/`目录下

### 常用指令说明
```bash
uv sync --group dev # 开发环境安装依赖项

uv run pytest tests/ # 运行所有测试

uv run ruff check src/ tests/ # 检查代码质量
uv run ruff format src/ tests/ # 格式化代码
```

## 开发规范
- **文件编码**: 编写文件时始终使用 UTF-8 格式，以确保正确的字符编码支持。
- **保持测试同步**: 修改任何模块后，您必须更新 `tests/` 中的测试文件。确保修改后的代码已被覆盖且所有测试都通过。
- **保持文档同步**: 修改任何模块后，您必须更新 `docs/develop/` 中对应的文档文件。确保文档准确反映更改。
- **Git 工作流**: 你的职责是根据用户请求编写和修改代码。不要执行任何 `git` 操作，如 `commit` 或 `push`。用户将处理所有版本控制操作。
- **使用 context7**: 当你写代码时遇到使用库的问题时，请使用 `context7` 搜索库的文档。

## 文档编写规范
- **Markdown(.md)文件**: 所有文档使用markdown格式编写，保存为 `.md` 后缀的文件。
- **Mermaid语法规范**: md文件中编写mermaid相关内容时，需遵循以下规范：
  - **节点文本引用**: 节点文本必须用双引号(`"`)包裹以避免解析错误。例如，使用`I["用户界面(CLI)"]`而不是`I[用户界面(CLI)]`。
  - **避免loop**，避免使用循环结构和"loop"作为变量名。
- **避免具体代码**: 文档中应该尽量不写入具体代码，只允许写入类定义、核心变量定义、核心方法定义、以及详细注释。  

## python代码规范
- **注释docstring**: 所有函数必须有Google风格的文档字符串，用中文编写。
- **类型提示**: 所有类成员变量和函数签名必须包含类型提示(type-hinting)。
- **导入**: 在 `one_dragon` 包内编写源码导入包时，需要遵循以下规范：
  - **使用绝对路径导入**: 禁止使用相对路径导入。
  - **类型注解导入**: 仅用于类型注解的导入应使用`TYPE_CHECKING`。
- **内置泛型**: 使用内置泛型类型(`list`, `dict`)而不是从`typing`模块导入的类型(`List`, `Dict`)。
  - **正确示例**: `my_list: list[str] = []`
  - **错误示例**: 
    ```python
    from typing import List
    my_list: List[str] = []
    ```
- **显式父类构造函数调用**:
    - **规则**: 在所有子类`__init__`方法中，你**必须**直接调用父类构造函数(例如，`ParentClass.__init__(self, ...)`）。你**不得**使用`super().__init__()`。
    - **原因**: 这是一个强制性的项目特定编码标准，以确保代码的清晰性和显式性。
    - **示例**:
      ```python
      # 正确示例:
      class MySubclass(MyBaseClass):
          def __init__(self, name, value):
              # 直接调用父类的__init__
              MyBaseClass.__init__(self, name)
              self.value = value
      ```
      ```python
      # 错误示例:
      class MySubclass(MyBaseClass):
          def __init__(self, name, value):
              # 不要使用super()进行初始化
              super().__init__(name)
              self.value = value
      ```
- **不暴露任何模块**: 没有收到指示的情况下，不要在 `__init__.py` 中新增暴露任何模块。

## 测试代码规范
- **测试类和夹具**: 测试文件必须使用测试类(以`Test`为前缀)来组织相关测试方法。你必须使用`pytest.fixture`来管理测试依赖和状态(如对象实例创建和清理)以提高代码复用性和可维护性。
- **导入约定**: 由于项目使用`src-layout`，测试文件中的导入路径不得包含`src`目录。
  - **正确示例**: `from one_dragon.base.operation import Operation`
  - **错误示例**: `from src.one_dragon.base.operation import Operation`
- **单方法测试文件**: 每个Python测试文件应专门用于测试单个方法的各种场景。
  - **示例**: 要测试`execute_main_loop`方法，创建一个名为`test_execute_main_loop.py`的文件。该文件应包含专门针对`execute_main_loop`方法的所有测试用例。
- **测试文件路径约定**: 测试文件的目录路径必须与被测模块的包路径一致。
  - **示例**: 对于`one_dragon_agent.core.agent.agent`模块中的`Agent`类，其测试文件应放置在`tests/one_dragon_agent/core/agent/agent/`目录中。测试文件本身应以其测试的特定方法命名(例如，`test_execute_main_loop.py`)。
- **异步测试超时**: 所有异步测试方法必须包含超时设置(例如，使用`pytest.mark.timeout(3)`)以防止测试无限期挂起。
- **临时文件**: 使用当前工作目录下的`.temp`目录存储临时文件。
