import sys
from collections.abc import Callable
from typing import Any, Protocol

from one_dragon.base.operation.operation_base import OperationBase
from one_dragon.base.operation.operation_round_result import OperationRoundResult

DEFAULT_NODE_MAX_RETRY_TIMES: int = 3
"""既没有指定重试次数也没有指定超时时 节点的默认重试次数"""


class NodeTimeout(Protocol):
    """节点超时的提供者 用于超时秒数需要在运行时读取上下文的节点"""

    def resolve(self, ctx: Any) -> float:
        """获取超时秒数

        Args:
            ctx: 当前操作的上下文

        Returns:
            超时秒数
        """
        ...


class OperationNode:

    def __init__(
            self,
            cn: str,
            op_method: Callable[[OperationBase], OperationRoundResult] | None = None,
            op: OperationBase | None = None,
            retry_on_op_fail: bool = False,
            wait_after_op: float | None = None,
            timeout_seconds: float | NodeTimeout | None = None,
            is_start_node: bool = False,
            node_max_retry_times: int | None = None,
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
            timeout_seconds: 该节点的超时秒数 也可以是在运行时按上下文给出秒数的提供者
            is_start_node: 是否是开始节点
            node_max_retry_times: 当前节点的重试次数 通常与timeout_seconds二选一
                都不指定时为3次 只指定超时时不限制重试次数 由超时结束节点
                两者同时指定时仍都生效 以先到者为准 保证已有的第三方插件可以加载
            mute: 是否不显示当前节点的结果日志
            screenshot_before_round: 当前节点每次运行前是否自动截图
            save_status: 是否保存当前状态到列表中
        """
        self.cn: str = cn
        """节点名称"""

        self.op_method: Callable[[OperationBase], OperationRoundResult] | None = op_method
        """节点处理函数 这个是类方法 需要自己传入self"""

        self.op: OperationBase | None = op
        """节点操作指令"""

        self.retry_on_op_fail: bool = retry_on_op_fail
        """op指令失败时是否进入重试"""

        self.wait_after_op: float | None = wait_after_op
        """op指令后的等待时间"""

        self.timeout_seconds: float | NodeTimeout | None = timeout_seconds
        """该节点的超时秒数 或 超时提供者"""

        self.is_start_node: bool = is_start_node
        """是否开始节点"""

        if node_max_retry_times is not None:
            self.node_max_retry_times: int = node_max_retry_times
        elif timeout_seconds is not None:
            self.node_max_retry_times: int = sys.maxsize
        else:
            self.node_max_retry_times: int = DEFAULT_NODE_MAX_RETRY_TIMES
        """节点处理重试次数"""

        self.mute: bool = mute
        """是否不显示当前节点的结果日志"""

        self.screenshot_before_round: bool = screenshot_before_round
        """当前节点每次运行前是否自动截图"""

        self.save_status: bool = save_status
        """是否保存当前状态到列表中"""

    def get_timeout_seconds(self, ctx: Any) -> float | None:
        """获取当前的超时秒数

        Args:
            ctx: 当前操作的上下文 超时由提供者给出时用于读取配置

        Returns:
            超时秒数 没有超时时为None
        """
        if self.timeout_seconds is None or isinstance(self.timeout_seconds, int | float):
            return self.timeout_seconds
        return self.timeout_seconds.resolve(ctx)


def operation_node(
        name: str,
        retry_on_op_fail: bool = False,
        wait_after_op: float | None = None,
        timeout_seconds: float | NodeTimeout | None = None,
        is_start_node: bool = False,
        node_max_retry_times: int | None = None,
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
        func.operation_node_annotation = node
        return func

    return decorator
