from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_const import CONTAINER_PROMPT_AREAS
from zzz_od.application.bagel.bagel_container import BagelContainerOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.application.bagel.bagel_container import ContainerRecovery
    from zzz_od.context.zzz_context import ZContext

# 一次交互直接开箱的容器。电子保险箱不在其中：它要先点开光圈解锁界面，
# 由 BagelUnlockSafe 承担那一步。
DIRECT_OPEN_TARGETS: tuple[str, ...] = ('box', 'mech')


class BagelOpenBox(BagelContainerOperation):
    """打开不需要光圈解锁的容器并确认搜查面板，不触发全部拾取。

    两种容器走这里：武备箱（点按交互）和机械保险箱（长按交互）。
    两者流程相同 —— 长按时长由 `bagel_container.interact_container` 按
    容器类型分派，本类不用关心。
    """

    def __init__(
        self,
        ctx: ZContext,
        recovery: ContainerRecovery | None = None,
        target: str = 'box',
    ) -> None:
        """与靠近导航共享一次容器恢复预算。"""
        if target not in DIRECT_OPEN_TARGETS:
            raise ValueError(f'该容器没有直接打开流程：{target}')
        name = '贝果-打开普通武备箱' if target == 'box' else '贝果-长按打开机械保险箱'
        super().__init__(ctx, target=target, op_name=name, recovery=recovery)

    @operation_node(name='按交互键开箱', is_start_node=True)
    def open_box(self) -> OperationRoundResult:
        """已有面板直接继续，否则按当前目标提示交互。"""
        return self.interact_container()

    @node_from(from_name='按交互键开箱')
    @operation_node(name='等待容器搜查面板')
    def wait_search(self) -> OperationRoundResult:
        """限次补按或向执行器申请重新靠近。"""
        result = self.interact_container()
        if result.is_success:
            if result.status == '容器已打开':
                return self.round_success('已进入搜查面板')
            return self.round_wait(f'{CONTAINER_PROMPT_AREAS[self.target]}未打开，补按一次交互', wait=0.25)
        return result
