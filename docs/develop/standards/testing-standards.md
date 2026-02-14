# 测试规范

本文档规定了项目测试编写和执行的规范。

## 关键测试原则

1. **测试数据清理** - 开发/生产共用数据库，测试后必须清理数据

## 测试框架

- 使用 `pytest` 进行测试
- 涉及异步函数时，使用 `pytest-asyncio` 进行测试

## 测试命令

```bash
uv run --env-file .env pytest zzz-od-test/                    # 运行所有测试
uv run --env-file .env pytest zzz-od-test/tests/zzz_od/       # 运行特定模块
uv run --env-file .env pytest -k test_name                    # 运行特定测试
```

## 测试文件组织

### 目录结构约定

测试文件的目录路径应该是被测文件的包路径 + 被测文件名的文件夹。

**示例：**
- 被测文件：`one_dragon/base/operation/one_dragon_context.py`
- 测试目录：`zzz-od-test/tests/one_dragon/base/operation/one_dragon_context/`
- 该目录下存放多个测试用例文件

### 单方法测试文件

每个 Python 测试文件应专门用于测试单个方法的各种场景。

**示例：**
- 要测试 `method_a` 方法
- 创建一个名为 `test_method_a.py` 的文件
- 该文件应包含专门针对 `method_a` 方法的所有测试用例

### 测试类组织

- 测试文件必须使用测试类（以 `Test` 为前缀）来组织相关的测试方法
- 示例：
  ```python
  class TestScreenInfo:
      def test_init(self):
          ...

      def test_add_area(self):
          ...
  ```

## 测试夹具 (Fixtures)

### 使用 Fixture 管理依赖

- 使用 `pytest.fixture` 来管理测试依赖和状态（如对象实例创建和清理）
- 这能提高代码的复用性和可维护性
- 注意指定 fixture 的作用域 (scope)，避免重复调用

### 公共 Fixture

- 测试根目录下有一个公共夹具 `zzz-od-test/test/conftest.py`
- 里面提供基础的运行上下文 `TestContext`
- 测试文件中可以通过 `test_context: TestContext` 引入

**示例：**
```python
def test_something(test_context: TestContext):
    ctx = test_context
    # 使用 ctx 进行测试
```

## 测试包规范

### 禁止创建测试包

- 测试目录下**严禁创建** `__init__.py` 文件

**原因：**
- 测试目录（如 `tests/zzz_mcp/`）若包含 `__init__.py`
- 会被 Python 识别为包
- 与源代码目录（如 `src/zzz_mcp/`）产生命名冲突
- 导致导入失败

**正确做法：**
- 测试目录应保持为普通目录结构，不形成 Python 包

## 导入约定

由于项目使用 `src-layout`，测试文件中的导入路径不得包含 `src` 目录。

**正确示例：**
```python
from one_dragon.base.operation import Operation
```

**错误示例：**
```python
from src.one_dragon.base.operation import Operation
```

## 依赖 Mock

- Mock 外部依赖（如 `controller`、`screenshot` 等）
- 使用 `zzz-od-test/test/conftest.py` 中提供的 `TestContext`
- 该 context 已包含 mock 的 controller 和相关工具

## 异步测试超时

- 所有异步测试方法必须包含超时设置
- 使用 `pytest.mark.timeout(3)` 防止测试无限期挂起
- 示例：
  ```python
  @pytest.mark.timeout(3)
  async def test_async_operation():
      ...
  ```

## 临时文件

- 使用当前工作目录下的 `.temp` 目录来存储临时文件
- 测试结束后应及时清理临时文件

## 测试数据管理

### 数据清理原则

- 当前项目没有区分开发和生产数据库
- 所有环境共用同一个数据库实例
- 因此测试数据清理尤为重要，必须确保测试后正确清理
- 避免影响开发和使用体验

### 测试前准备

- 考虑测试过程产生脏数据的情况
- 在测试设计阶段就需要考虑清理方案

## 测试覆盖要求

- 修改任何模块后，必须更新 `zzz-od-test/` 中的测试文件
- 确保修改后的代码已被覆盖且所有测试都通过
- 除非源代码逻辑有错误，否则不能因为测试不通过而修改源代码
