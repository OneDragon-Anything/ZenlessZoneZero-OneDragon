from __future__ import annotations

from functools import cached_property
from typing import Any, Callable

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.execution_info import ExecutionInfo
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.state_cal_tree import (
    StateCalNode,
    StateCalNodeType,
    StateCalOpType,
    construct_state_cal_tree,
)
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.utils.log_utils import log


class StateHandler:

    def __init__(
        self,
        data: dict[str, Any]
    ):
        self.original_data: dict[str, Any] = data
        # TODO 后续改为 state_handler_template
        self.state_template: str | None = data.get("state_template")  # 状态处理器模板 存在时忽略所有其他属性 需额外加载模板
        # TODO 后续改为 display_name
        self.display_name: str | None = data.get("debug_name")  # 调试时显示的名称
        self.states: str = data.get("states", "")  # 状态表达式 命中哪些状态组合就使用本个处理器
        self.interrupt_states: str | None = data.get("interrupt_states")  # 状态表达式 命中哪些状态组合就中断本个处理器的执行
        self.operations: list[OperationDef] = [OperationDef(i) for i in data.get("operations", [])] # 操作列表
        self.sub_handlers: list[StateHandler] = [StateHandler(i) for i in data.get("sub_handlers", [])]  # 子处理器 存在时忽略 operations

        self.op_list: list[AtomicOp] = []  # 操作列表
        self.state_cal_tree: StateCalNode | None = None  # 状态判断树
        self.interrupt_states_cal_tree: StateCalNode | None = None  # 可被打断的状态判断树

        # TODO 调试代码 后续删除
        for k in data.keys():
            if k not in ["state_template", "debug_name", "states", "interrupt_states", "operations", "sub_handlers"]:
                raise ValueError(f"未知字段 {k} {data}")

    def set_sub_handlers(self, sub_handlers: list[StateHandler]) -> None:
        """
        更新子处理器列表
        Args:
            sub_handlers: 子处理器列表
        """
        self.sub_handlers = sub_handlers
        self.original_data["sub_handlers"] = [i.original_data for i in sub_handlers]
        if "operations" in self.original_data:  # 两者不会共存
            del self.original_data["operations"]

    def set_operations(self, operations: list[OperationDef]) -> None:
        """
        更新操作列表
        Args:
            operations: 操作列表
        """
        self.operations = operations
        self.original_data["operations"] = [i.original_data for i in operations]
        if "sub_handlers" in self.original_data:  # 两者不会共存
            del self.original_data["sub_handlers"]

    def build(
        self,
        state_recorder_getter: Callable[[str], StateRecorder],
        op_getter: Callable[[OperationDef], AtomicOp],
        parent_interrupt_states_cal_tree: StateCalNode | None = None,
    ) -> None:
        """
        构建状态处理器

        Args:
            state_recorder_getter: 状态记录获取器
            op_getter: 原子操作获取器
            parent_interrupt_states_cal_tree: 父级的打断状态判断树
        """
        log.debug('构造状态判断树 ' + (self.display_name or self.states))
        self.state_cal_tree = construct_state_cal_tree(self.states, state_recorder_getter)
        self.interrupt_states_cal_tree = self._build_interrupt_tree(state_recorder_getter, parent_interrupt_states_cal_tree)

        if len(self.sub_handlers) > 0:
            for i in self.sub_handlers:
                i.build(
                    state_recorder_getter=state_recorder_getter,
                    op_getter=op_getter,
                    parent_interrupt_states_cal_tree=self.interrupt_states_cal_tree
                )
        elif len(self.operations) > 0:
            self.op_list = [
                op_getter(i)
                for i in self.operations
            ]

    def _build_interrupt_tree(
        self,
        state_recorder_getter: Callable[[str], StateRecorder],
        parent_tree: StateCalNode | None,
    ) -> StateCalNode | None:
        """
        构建当前的打断状态判断树
        是自身的打断状态 OR 父节点的打断状态

        Args:
            state_recorder_getter: 状态记录获取器
            parent_tree: 父级打断状态判断树

        Returns:
            当前打断状态判断树
        """
        if self.interrupt_states is not None:
            self_interrupt_tree = construct_state_cal_tree(self.interrupt_states, state_recorder_getter)
        else:
            self_interrupt_tree = None

        if parent_tree is None:
            return self_interrupt_tree

        if self_interrupt_tree is None:
            return parent_tree

        # 两个中断树都存在时，使用OR逻辑合并
        return StateCalNode(
           node_type=StateCalNodeType.OP,
           op_type=StateCalOpType.OR,
           left_child=parent_tree,
           right_child=self_interrupt_tree
        )

    @cached_property
    def usage_states(self) -> set[str]:
        """
        当前场景需要用到的所有状态
        """
        states: set[str] = set()
        if self.state_cal_tree is not None:
            states = states.union(self.state_cal_tree.usage_states)
        if self.interrupt_states_cal_tree is not None:
            states = states.union(self.interrupt_states_cal_tree.usage_states)
        for handler in self.sub_handlers:
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
        if self.state_cal_tree.in_time_range(trigger_time):
            if self.sub_handlers is not None and len(self.sub_handlers) > 0:
                for sub_handler in self.sub_handlers:
                    info = sub_handler.match_execution(trigger_time)
                    if info is not None:
                        info.add_state(self.states, self.display_name)
                        return info
            else:
                info = ExecutionInfo(self.op_list, self.interrupt_states_cal_tree)
                info.add_state(self.states, self.display_name)
                return info

        return None
