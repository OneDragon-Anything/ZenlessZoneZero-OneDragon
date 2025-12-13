# back_to_world 方法使用指南

## 概述

`back_to_world` 方法是 ZZZ-OD 项目中用于返回大世界的标准方法。经过重构后，该方法现在在 `ZApplication` 基类中提供了统一的默认实现，大大简化了应用开发过程。

## 基本使用

### 默认实现

大多数应用可以直接使用基类提供的默认实现，无需在子类中重写该方法：

```python
class MyApp(ZApplication):
    def __init__(self, ctx: ZContext):
        super().__init__(ctx)

    # 无需实现 back_to_world 方法，直接继承基类实现

    def _execute_one_round(self) -> OperationRoundResult:
        # 应用的主要逻辑
        # ...

        # 需要返回大世界时，直接调用
        return self.back_to_world()
```

### 自定义状态消息

如果需要在返回大世界时显示自定义状态消息，可以通过 `custom_status` 参数传递：

```python
class ChargePlanApp(ZApplication):
    def back_to_world(self) -> OperationRoundResult:
        # 使用自定义状态消息
        return super().back_to_world(custom_status=f'剩余电量 {self.charge_power}')
```

## 使用场景

### 场景 1：标准返回流程

**适用情况**：
- 应用只需要简单的返回大世界功能
- 不需要特殊的前置或后置处理
- 不需要自定义状态消息

**实现方式**：
```python
# 无需实现任何代码，直接继承基类实现
class EmailApp(ZApplication):
    pass  # back_to_world 方法自动可用
```

**适用的应用类型**：
- EmailApp（邮件）
- ScratchCardApp（刮刮卡）
- RandomPlayApp（录像店营业）
- NotoriousHuntApp（恶名狩猎）
- LifeOnLineApp（生活在线/真拿命验收）
- CityFundApp（丽都城慕）
- CoffeeApp（咖啡店）

### 场景 2：自定义状态消息

**适用情况**：
- 需要在返回大世界时显示应用特定的状态信息
- 基本返回流程不变，只是状态消息不同

**实现方式**：
```python
class ChargePlanApp(ZApplication):
    def back_to_world(self) -> OperationRoundResult:
        return super().back_to_world(custom_status=f'剩余电量 {self.charge_power}')
```

### 场景 3：特殊业务逻辑

**适用情况**：
- 需要在返回大世界前后执行特殊操作
- 有不同的返回路径或条件判断
- 需要完全自定义的返回逻辑

**实现方式**：
```python
class TransportByCompendium(ZApplication):
    def back_to_world(self) -> OperationRoundResult:
        # 特殊的勘域处理逻辑
        if self.is_in_exploration_area():
            return self.handle_exploration_exit()
        else:
            return super().back_to_world()

class LostVoidLottery(ZApplication):
    def back_to_world(self) -> OperationRoundResult:
        # 完全自定义的返回逻辑
        return self.custom_void_exit_logic()
```

## 方法签名

```python
def back_to_world(self, custom_status: Optional[str] = None) -> OperationRoundResult:
    """
    返回大世界的默认实现

    大部分应用可以直接使用此默认实现。仅在以下情况需要覆盖：
    1. 需要在返回大世界前/后执行额外操作
    2. 返回路径需要特殊处理（如 TransportByCompendium 的勘域场景）
    3. 完全不同的返回逻辑（如 LostVoid 相关操作）

    :param custom_status: 自定义状态消息，用于在操作结果中添加额外信息
    :return: 操作结果
    """
```

## 参数说明

### custom_status

- **类型**：`Optional[str]`
- **默认值**：`None`
- **用途**：自定义状态消息，会显示在操作结果中
- **示例**：
  - `"剩余电量 85%"`
  - `"任务完成，获得奖励 1000"`
  - `"当前进度 3/5"`

## 最佳实践

### 1. 优先使用默认实现

除非有特殊需求，否则应该优先使用基类的默认实现：

```python
# ✅ 推荐：使用默认实现
class SimpleApp(ZApplication):
    def _execute_one_round(self) -> OperationRoundResult:
        # 应用逻辑
        return self.back_to_world()

# ❌ 不推荐：重复实现相同逻辑
class SimpleApp(ZApplication):
    def back_to_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        op_result = op.execute()
        return self.round_by_op_result(op_result)
```

### 2. 合理使用自定义状态

只在有意义的情况下使用自定义状态消息：

```python
# ✅ 推荐：有意义的状态信息
def back_to_world(self) -> OperationRoundResult:
    return super().back_to_world(custom_status=f'剩余电量 {self.charge_power}')

# ❌ 不推荐：无意义的状态信息
def back_to_world(self) -> OperationRoundResult:
    return super().back_to_world(custom_status="返回大世界")
```

### 3. 保持方法简洁

如果需要复杂的逻辑，考虑将其分解为多个方法：

```python
# ✅ 推荐：逻辑清晰
class ComplexApp(ZApplication):
    def back_to_world(self) -> OperationRoundResult:
        self._cleanup_before_exit()
        status = self._generate_status_message()
        return super().back_to_world(custom_status=status)

    def _cleanup_before_exit(self):
        # 清理逻辑
        pass

    def _generate_status_message(self) -> str:
        # 状态消息生成逻辑
        return f"完成任务，获得 {self.rewards} 奖励"
```

## 错误处理

基类实现已经包含了基本的错误处理，但在自定义实现时需要注意：

```python
class CustomApp(ZApplication):
    def back_to_world(self) -> OperationRoundResult:
        try:
            # 自定义前置处理
            self._pre_exit_processing()

            # 调用基类实现
            return super().back_to_world(custom_status=self._get_status())

        except Exception as e:
            self.ctx.logger.error(f"返回大世界失败: {e}")
            return OperationRoundResult(success=False, status=f"返回大世界失败: {str(e)}")
```

## 迁移指南

### 从旧实现迁移

如果你的应用之前有自己的 `back_to_world` 实现，可以按以下步骤迁移：

1. **检查现有实现**：
   ```python
   # 旧实现
   def back_to_world(self) -> OperationRoundResult:
       op = BackToNormalWorld(self.ctx)
       op_result = op.execute()
       return self.round_by_op_result(op_result)
   ```

2. **删除标准实现**：
   如果实现与上述代码相同，直接删除该方法。

3. **转换为参数化调用**：
   ```python
   # 如果有自定义状态
   def back_to_world(self) -> OperationRoundResult:
       op = BackToNormalWorld(self.ctx)
       op_result = op.execute()
       return self.round_by_op_result(op_result, status="自定义状态")

   # 转换为
   def back_to_world(self) -> OperationRoundResult:
       return super().back_to_world(custom_status="自定义状态")
   ```

4. **保留特殊逻辑**：
   如果有特殊的业务逻辑，保持现有实现不变。

## 常见问题

### Q: 什么时候需要覆盖 back_to_world 方法？

A: 只在以下情况需要覆盖：
- 需要自定义状态消息
- 需要在返回前后执行特殊操作
- 有不同的返回路径或逻辑
- 需要特殊的错误处理

### Q: 如何知道我的应用是否需要自定义实现？

A: 检查以下几点：
- 是否需要显示应用特定的状态信息？
- 是否需要在返回前清理资源或保存状态？
- 返回路径是否与标准流程不同？
- 如果都不需要，使用默认实现即可。

### Q: 可以在 custom_status 中使用什么内容？

A: custom_status 可以包含任何有意义的状态信息：
- 进度信息：`"3/5 任务完成"`
- 资源状态：`"剩余电量 85%"`
- 奖励信息：`"获得金币 1000"`
- 错误信息：`"部分任务失败"`

### Q: 基类实现的性能如何？

A: 基类实现与之前的重复代码在性能上完全相同，因为使用了相同的底层操作。重构只是消除了代码重复，不会影响运行性能。