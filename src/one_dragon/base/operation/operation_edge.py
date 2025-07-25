from functools import wraps

from typing import Optional

from one_dragon.base.operation.operation_node import OperationNode


class OperationEdge:

    def __init__(self, node_from: OperationNode, node_to: OperationNode,
                 success: bool = True, status: Optional[str] = None, ignore_status: bool = True):
        """
        带状态指令的边
        :param node_from: 上一个指令
        :param node_to: 下一个指令
        :param success: 是否成功才进入下一个节点
        :param status: 上一个节点的结束状态 符合时才进入下一个节点
        :param ignore_status: 是否忽略状态进行下一个节点 不会忽略success
        """

        self.node_from: OperationNode = node_from
        """上一个节点"""

        self.node_to: OperationNode = node_to
        """下一个节点"""

        self.success: bool = success
        """是否成功才执行下一个节点"""

        self.status: Optional[str] = status
        """
        执行下一个节点的条件状态 
        一定要完全一样才会执行 包括None
        """

        self.ignore_status: bool = False if status is not None else ignore_status
        """
        是否忽略状态进行下一个节点
        一个节点应该最多只有一条边忽略返回状态
        忽略返回状态只有在所有需要匹配的状态都匹配不到时才会用做兜底
        """


class OperationEdgeDesc:

    def __init__(
            self,
            node_from_name: str,
            node_to_name: str | None = None,
            success: bool = True,
            status: Optional[str] = None,
            ignore_status: bool = True
    ):
        """
        边描述
        """
        self.node_from_name: str = node_from_name
        self.node_to_name: str = node_to_name
        self.success: bool = success
        self.status: Optional[str] = status
        self.ignore_status: bool = ignore_status


def node_from(
        from_name: str,
        success: bool = True,
        status: Optional[str] = None,
        ignore_status: bool = True,
):
    """
    一个用于给函数附加 OperationEdgeDesc 元数据的装饰器。
    它不会改变原函数的行为，并且支持在同一个函数上多次使用。
    """

    def decorator(func):
        # 检查函数是否已经有关联的边列表，如果没有则创建一个
        if not hasattr(func, 'operation_edge_annotation'):
            setattr(func, 'operation_edge_annotation', [])

        # 获取边列表并添加新的边描述
        edge_list = getattr(func, 'operation_edge_annotation')
        edge_list.append(
            OperationEdgeDesc(
                node_from_name=from_name,
                node_to_name=None,  # to_name 会在图构建时被自动填充
                success=success,
                status=status,
                ignore_status=ignore_status,
            )
        )

        # 返回未被修改的原始函数
        return func

    return decorator
