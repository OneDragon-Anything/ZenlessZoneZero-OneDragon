from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_operation import BagelOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelReturn(BagelOperation):
    """从已处理完物资的结算仓库返回贝果入口，不寻找或移动到达塔。"""

    def __init__(self, ctx: ZContext) -> None:
        """由调用者先完成物资处理，再返回研究站开始下一局。"""
        super().__init__(ctx, op_name='贝果-返回研究站入口', timeout_seconds=60)
        self.reward_confirmed: bool = False

    def handle_init(self) -> None:
        """重跑时允许处理本次返回的奖励提示。"""
        super().handle_init()
        self.reward_confirmed = False

    @operation_node(name='返回研究站', is_start_node=True, timeout_seconds=15)
    def return_station(self) -> OperationRoundResult:
        """只在结算仓库点返回，不替调用者搬运或出售物资。"""
        if not self.round_by_find_area(self.last_screenshot, '贝果-仓库', '放入仓库').is_success:
            return self.round_retry('未到结算仓库', wait=1)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '返回研究站', success_wait=1,
        )

    @node_from(from_name='返回研究站')
    @operation_node(name='等待研究站加载', timeout_seconds=25)
    def wait_station(self) -> OperationRoundResult:
        """先确认本次撤离奖励，再等 HUD 与落地动画后按 F。"""
        if (self.round_by_find_area(self.last_screenshot, '贝果-研究站', '标题').is_success
                and self.round_by_find_area(self.last_screenshot, '贝果-研究站', '前往空洞').is_success):
            return self.round_success('已到贝果入口')
        if all(self.round_by_find_area(
            self.last_screenshot, '贝果-仓库', area,
        ).is_success for area in ('撤离奖励标题', '撤离奖励说明')):
            if self.reward_confirmed:
                return self.round_fail('撤离奖励提示未关闭，已停止重复确认')
            result = self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-仓库', '撤离奖励确认',
                success_wait=1, retry_wait=0.5,
            )
            if result.is_success:
                self.reward_confirmed = True
                return self.round_wait('等待撤离奖励提示关闭', wait=0.5)
            return result
        if not self.round_by_find_area(self.last_screenshot, '大世界-普通', '快捷手册').is_success:
            return self.round_wait('等待返回研究站加载', wait=0.5)
        return self.round_success(wait=1)

    @node_from(from_name='等待研究站加载')
    @operation_node(name='加载后直接交互')
    def interact_after_loading(self) -> OperationRoundResult:
        """已知落点在达塔交互范围内，直接按 F，不再识别名字位置。"""
        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        return self.round_success(wait=1)

    @node_from(from_name='加载后直接交互')
    @node_from(from_name='等待研究站加载', status='已到贝果入口')
    @operation_node(name='打开贝果入口', timeout_seconds=15)
    def open_hub(self) -> OperationRoundResult:
        """核对对话再选择出发，直到入口按钮出现。"""
        if (self.round_by_find_area(self.last_screenshot, '贝果-研究站', '标题').is_success
                and self.round_by_find_area(self.last_screenshot, '贝果-研究站', '前往空洞').is_success):
            return self.round_success('已返回贝果入口')
        if not self.round_by_find_area(self.last_screenshot, '贝果-研究站', '对话人').is_success:
            if (self.round_by_find_area(self.last_screenshot, '大世界-普通', '快捷手册').is_success
                    and self.round_by_find_area(self.last_screenshot, '贝果-研究站', '接待员名称').is_success):
                self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            return self.round_retry('等待达塔对话', wait=1)
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-研究站', '出发对话',
        )
        if result.is_success:
            return self.round_wait('等待贝果入口', wait=1)
        return result
