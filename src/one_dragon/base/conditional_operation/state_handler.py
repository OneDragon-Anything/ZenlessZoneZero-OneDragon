from typing import List, Optional, Set

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_task import OperationTask
from one_dragon.base.conditional_operation.state_cal_tree import (
    StateCalNode, StateCalNodeType, StateCalOpType
)
from one_dragon.utils.log_utils import log


class StateHandler:

    def __init__(self,
                 expr: str,
                 state_cal_tree: StateCalNode,
                 sub_handlers: Optional[List] = None,
                 operations: Optional[List[AtomicOp]] = None,
                 interrupt_cal_tree: Optional[StateCalNode] = None,
                 debug_name: Optional[str] = None,  # 新增参数
                 ):
        """
        一个状态处理器 包含状态判断 + 对应指令
        :param state_cal_tree: 状态判断树
        :param operations: 执行指令
        :param interrupt_cal_tree: 可以被这些状态打断
        """
        self.expr: str = expr
        self.debug_name: Optional[str] = debug_name  # 新增属性
        self.state_cal_tree: StateCalNode = state_cal_tree
        self.sub_handlers: List[StateHandler] = sub_handlers
        self.operations: List[AtomicOp] = operations
        self.interrupt_cal_tree: StateCalNode = interrupt_cal_tree

    def _merge_interrupt_trees(self, task_interrupt_tree: Optional[StateCalNode],
                              self_interrupt_tree: Optional[StateCalNode]) -> Optional[StateCalNode]:
       """
       合并两个中断树，使用OR逻辑创建复合中断条件

       :param task_interrupt_tree: 任务现有的中断树
       :param self_interrupt_tree: 当前处理器的中断树
       :return: 合并后的中断树，如果任一为None则返回另一个，否则返回新的OR节点
       """
       if task_interrupt_tree is None:
           return self_interrupt_tree
       if self_interrupt_tree is None:
           return task_interrupt_tree

       # 两个中断树都存在时，使用OR逻辑合并
       return StateCalNode(
           node_type=StateCalNodeType.OP,
           op_type=StateCalOpType.OR,
           left_child=task_interrupt_tree,
           right_child=self_interrupt_tree
       )

    def get_operations(self, trigger_time: float) -> Optional[OperationTask]:
        """
        根据触发时间 和优先级 获取符合条件的场景下的指令
        :param trigger_time:
        :return:
        """
        if self.state_cal_tree.in_time_range(trigger_time):
            if self.sub_handlers is not None and len(self.sub_handlers) > 0:
                for sub_handler in self.sub_handlers:
                    task = sub_handler.get_operations(trigger_time)
                    if task is not None:
                        task.add_expr(self.expr, self.debug_name)
                        if self.interrupt_cal_tree is not None:
                            if task.interrupt_cal_tree is not None:
                                # 合并两个中断树
                                task.interrupt_cal_tree = self._merge_interrupt_trees(
                                    task.interrupt_cal_tree,
                                    self.interrupt_cal_tree
                                )
                            else:
                                task.set_interrupt_cal_tree(self.interrupt_cal_tree)
                        return task
            else:
                task = OperationTask(self.operations)
                task.add_expr(self.expr, self.debug_name)  # 修改：传入debug_name
                task.set_interrupt_cal_tree(self.interrupt_cal_tree)
                return task

        return None

    def get_usage_states(self) -> set[str]:
        """
        获取使用的状态
        :return:
        """
        states: set[str] = set()
        if self.state_cal_tree is not None:
            states = states.union(self.state_cal_tree.get_usage_states())
        if self.sub_handlers is not None:
            for sub in self.sub_handlers:
                states = states.union(sub.get_usage_states())
        return states


    def dispose(self) -> None:
        """
        销毁
        :return:
        """
        if self.state_cal_tree is not None:
            self.state_cal_tree.dispose()
        if self.operations is not None:
            for op in self.operations:
                op.dispose()
        if self.sub_handlers is not None:
            for sub in self.sub_handlers:
                sub.dispose()
