from typing import Optional, Callable

from one_dragon.base.operation.operation_base import OperationBase
from one_dragon.base.operation.operation_round_result import OperationRoundResult


class OperationNode:

    def __init__(
            self,
            cn: str,
            op_method: Optional[Callable[[OperationBase], OperationRoundResult]] = None,
            op: Optional[OperationBase] = None,
            retry_on_op_fail: bool = False,
            wait_after_op: Optional[float] = None,
            timeout_seconds: Optional[float] = None,
            is_start_node: bool = False,
            node_max_retry_times: int = 3,
            mute: bool = False,
            screenshot_before_round: bool = True,
            save_status: bool = False,
    ):
        """

        Args:
            cn: 节点名称
            op_method: 该节点用于处理指令的函数 与op二选一 是指Operation类中的方法 优先使用func
            op: 该节点用于操作的指令 与func二选一 是值当前节点使用指定的Operation 优先使用func
            retry_on_op_fail: op指令失败时是否进入重试
            wait_after_op: op指令后的等待时间
            timeout_seconds: 该节点的超时秒数
            is_start_node: 是否是开始节点
            node_max_retry_times: 当前节点的重试次数
            mute: 是否不显示当前节点的结果日志
            screenshot_before_round: 当前节点每次运行前是否自动截图
            save_status: 是否保存当前状态到列表中
        """

        self.cn: str = cn
        """节点名称"""

        self.op_method: Optional[Callable[[OperationBase], OperationRoundResult]] = op_method
        """节点处理函数 这个是类方法 需要自己传入self"""

        self.op: Optional[OperationBase] = op
        """节点操作指令"""

        self.retry_on_op_fail: bool = retry_on_op_fail
        """op指令失败时是否进入重试"""

        self.wait_after_op: Optional[float] = wait_after_op
        """op指令后的等待时间"""

        self.timeout_seconds: Optional[float] = timeout_seconds
        """该节点的超时秒数"""

        self.is_start_node: bool = is_start_node
        """是否开始节点"""

        self.node_max_retry_times: int = node_max_retry_times
        """节点处理重试次数"""

        self.mute: bool = mute
        """是否不显示当前节点的结果日志"""

        self.screenshot_before_round: bool = screenshot_before_round
        """当前节点每次运行前是否自动截图"""

        self.save_status: bool = save_status
        """是否保存当前状态到列表中"""

def operation_node(
        name: str,
        retry_on_op_fail: bool = False,
        wait_after_op: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        is_start_node: bool = False,
        node_max_retry_times: int = 3,
        mute: bool = False,
        screenshot_before_round: bool = True,
        save_status: bool = False,
):
    def decorator(func):
        # 直接将 node 对象作为函数的一个属性附加到函数上
        node = OperationNode(
            cn=name,
            op_method=func,
            retry_on_op_fail=retry_on_op_fail,
            wait_after_op=wait_after_op,
            timeout_seconds=timeout_seconds,
            is_start_node=is_start_node,
            node_max_retry_times=node_max_retry_times,
            mute=mute,
            screenshot_before_round=screenshot_before_round,
            save_status=save_status,
        )
        setattr(func, 'operation_node_annotation', node)
        return func

    return decorator
