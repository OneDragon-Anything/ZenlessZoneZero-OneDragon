from functools import cached_property

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.state_cal_tree import StateCalNode


class ExecutionInfo:

    def __init__(
        self,
        op_list: list[AtomicOp],
        interrupt_cal_tree: StateCalNode | None = None,
    ):
        """
        保存触发操作的相关信息
        """
        self.trigger: str | None = None  # 触发器
        self.interrupt_cal_tree: StateCalNode | None = interrupt_cal_tree  # 打断状态判断树
        self.priority: int | None = None  # 优先级 只能被高等级的打断；为None时可以被随意打断

        self.op_list: list[AtomicOp] = op_list  # 需要执行的指令列表
        self.state_list: list[str] = []  # 匹配到的状态列表 是配置中的 states 列表

    def add_state(self, state: str, display_name: str | None = None) -> None:
        """
        增加一个状态表达式

        Args:
            state: 状态表达式
            display_name: 显示名称
        """
        if display_name is not None:
            self.state_list.append(display_name)
        else:
            self.state_list.append(state)

    @cached_property
    def expr_display(self) -> str:
        return ' ← '.join(self.state_list) if self.state_list else '/'

    @cached_property
    def priority_display(self) -> str:
        return '无优先级' if self.priority is None else str(self.priority)

    @cached_property
    def trigger_display(self) -> str:
        return '主循环' if self.trigger is None else self.trigger
