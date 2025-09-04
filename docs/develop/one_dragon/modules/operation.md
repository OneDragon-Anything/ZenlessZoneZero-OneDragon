# Operation

## 1. 概述

OneDragon 的 Operation 模块构成了整个框架的核心执行引擎，采用基于状态机的操作流程控制，为复杂的游戏自动化任务提供了强大而灵活的执行框架。

## 2. 核心设计理念

### 2.1 分层架构
- **OperationBase**: 最基础的操作抽象层 (后续考虑删除)
- **Operation**: 具体的操作实现层，支持节点图执行
- **Application**: 应用层，封装完整的业务逻辑
- **OneDragonApp**: 一条龙应用层，支持多应用编排和调度 (后续替换成分组应用)

### 2.2 状态机驱动
- 基于节点图的状态转换机制
- 支持条件分支和循环控制
- 内置重试和错误处理机制

### 2.3 事件驱动
- 全局事件总线机制
- 支持异步事件处理
- 松耦合的组件通信

## 3. 核心组件详解

### 3.1 OperationBase (操作基类)

**职责**: 定义所有操作的基本接口和结果结构

**核心类**:
```python
class OperationResult:
    success: bool      # 执行结果
    status: str        # 状态描述
    data: Any          # 返回数据

class OperationBase:
    def execute(self) -> OperationResult
    def op_success(status, data) -> OperationResult
    def op_fail(status, data) -> OperationResult
```

**设计特点**:
- 统一的结果返回格式
- 简洁的成功/失败状态表示
- 支持任意类型的数据返回

### 3.2 Operation (操作执行引擎)

**职责**: 实现基于节点图的复杂操作流程控制

**核心属性**:
- `ctx: OneDragonContext` - 全局上下文
- `_node_map: dict[str, OperationNode]` - 节点映射
- `_node_edges_map: dict[str, list[OperationEdge]]` - 边映射
- `_current_node: OperationNode` - 当前执行节点

**执行流程**:
1. **初始化阶段**: 构建节点图，确定起始节点
2. **执行循环**: 按节点图执行，处理状态转换
3. **结果处理**: 根据最终状态返回操作结果

**关键方法**:
- `_init_network()`: 构建操作节点网络
- `_execute_one_round()`: 执行单轮操作
- `_get_next_node()`: 根据结果选择下一个节点

### 3.3 OperationNode (操作节点)

**职责**: 表示操作流程中的单个执行步骤

**核心属性**:
```python
class OperationNode:
    cn: str                    # 节点名称
    func: Callable             # 节点处理函数
    op_method: Callable        # 类方法处理函数
    op: OperationBase          # 子操作
    retry_on_op_fail: bool     # 失败时是否重试
    node_max_retry_times: int  # 最大重试次数
    timeout_seconds: float     # 超时时间
```

**注解支持**:
```python
@operation_node(name='节点名称', is_start_node=True)
def node_method(self) -> OperationRoundResult:
    # 节点逻辑实现
    return self.round_success()
```

### 3.4 OperationEdge (操作边)

**职责**: 定义节点间的连接关系和转换条件

**核心属性**:
```python
class OperationEdge:
    node_from: OperationNode   # 源节点
    node_to: OperationNode     # 目标节点
    success: bool              # 成功条件
    status: str                # 状态匹配条件
    ignore_status: bool        # 是否忽略状态
```

**注解支持**:
```python
@node_from(from_name='源节点', status='特定状态')
@operation_node(name='目标节点')
def target_node(self) -> OperationRoundResult:
    # 目标节点逻辑
```

### 3.5 OperationRoundResult (轮次结果)

**职责**: 表示单轮操作的执行结果

**结果类型**:
```python
class OperationRoundResultEnum(Enum):
    RETRY = 0    # 重试
    SUCCESS = 1  # 成功
    WAIT = 2     # 等待
    FAIL = -1    # 失败
```

**便捷方法**:
- `round_success()`: 创建成功结果
- `round_fail()`: 创建失败结果
- `round_retry()`: 创建重试结果
- `round_wait()`: 创建等待结果
