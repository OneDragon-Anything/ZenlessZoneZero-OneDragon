from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_container import BagelContainerOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.application.bagel.bagel_container import ContainerRecovery
    from zzz_od.context.zzz_context import ZContext


class BagelOpenBox(BagelContainerOperation):
    """打开武备箱并确认搜查面板，不触发全部拾取。"""

    def __init__(self, ctx: ZContext, recovery: ContainerRecovery | None = None) -> None:
        """与靠近导航共享一次容器恢复预算。"""
        super().__init__(ctx, target='box', op_name='贝果-打开普通武备箱', recovery=recovery)

    @operation_node(name='打开武备箱', is_start_node=True)
    def open_box(self) -> OperationRoundResult:
        """已有面板直接继续，否则按当前目标提示交互。"""
        return self.interact_container()

    @node_from(from_name='打开武备箱')
    @operation_node(name='等待武备箱搜查面板')
    def wait_search(self) -> OperationRoundResult:
        """限次补按或向执行器申请重新靠近。"""
        result = self.interact_container()
        if result.is_success:
            if result.status == '容器已打开':
                return self.round_success('已进入武备箱搜查')
            return self.round_wait('武备箱未打开，补按一次交互', wait=0.25)
        return result
