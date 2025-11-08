from functools import cached_property
from typing import Any, Callable

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.execution_info import ExecutionInfo
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.state_handler import StateHandler
from one_dragon.base.conditional_operation.state_recorder import StateRecorder


class Scene:

    def __init__(
        self,
        data: dict[str, Any]
    ):
        self.original_data: dict[str, Any] = data
        self.priority: int | None = data.get("priority")  # 优先级 只能被高等级的打断；为None时可以被随意打断
        self.triggers: list[str] = data.get("triggers", [])  # 可以被哪些状态触发
        self.interval_seconds: float = data.get("interval", 0.5)  # 触发间隔(秒)
        self.handlers: list[StateHandler] = [
            StateHandler(i)
            for i in data.get("handlers", [])
        ]

        # TODO 调试代码 后续删除
        for k in data.keys():
            if k not in ["priority", 'triggers', 'interval', 'handlers']:
                raise ValueError(f'未知字段 {k}')

    def set_handlers(self, handlers: list[StateHandler]) -> None:
        """
        更新状态处理器列表

        Args:
            handlers: 新的状态处理器列表
        """
        self.handlers = handlers
        self.original_data["handlers"] = [i.original_data for i in handlers]

    def build(
        self,
        state_recorder_getter: Callable[[str], StateRecorder],
        op_getter: Callable[[OperationDef], AtomicOp],
    ) -> None:
        """
        构建场景
        """
        for handler in self.handlers:
            handler.build(
                state_recorder_getter=state_recorder_getter,
                op_getter=op_getter,
            )

    @cached_property
    def usage_states(self) -> set[str]:
        """
        当前场景需要用到的所有状态
        """
        states: set[str] = set()
        for trigger in self.triggers:
            states.add(trigger)

        for handler in self.handlers:
            states = states.union(handler.usage_states)

        return states

    def match_execution(self, trigger_time: float) -> ExecutionInfo | None:
        """
        根据触发时间和优先级 获取符合条件的场景下的执行信息

        Args:
            trigger_time: 触发时间

        Returns:
            符合条件的场景下的执行信息
        """
        for handler in self.handlers:
            info = handler.match_execution(trigger_time)
            if info is not None:
                return info