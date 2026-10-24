from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.operation.back_to_normal_world import BackToNormalWorld

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelReturn(BagelOperation):
    """从已处理完物资的结算仓库返回，区分贝果主界面与大世界。"""

    def __init__(self, ctx: ZContext) -> None:
        """由调用者先完成物资处理；返回大世界时不再与达塔交互。"""
        super().__init__(ctx, op_name='贝果-返回入口', timeout_seconds=60)
        self.reward_confirmed: bool = False
        self.world_recovery_attempted: bool = False

    def handle_init(self) -> None:
        """重跑时允许处理本次返回的奖励提示。"""
        super().handle_init()
        self.reward_confirmed = False
        self.world_recovery_attempted = False

    @node_from(from_name='等待返回入口', success=False, status=BagelOperation.STATUS_TIMEOUT)
    @operation_node(name='入口加载超时恢复', screenshot_before_round=False)
    def recover_world(self) -> OperationRoundResult:
        """加载超时后仅尝试一次通用恢复，由下一次入场重新准备入口。"""
        if self.world_recovery_attempted:
            return self.round_fail('通用返回大世界后仍无法继续贝果返回，停止并保留现场')
        self.world_recovery_attempted = True
        operation = BackToNormalWorld(self.ctx, ensure_normal_world=True)
        operation.timeout_seconds = min(20, max(0, self.timeout_seconds - self.operation_usage_time))
        result = operation.execute()
        if not result.success:
            return self.round_by_op_result(result)
        return self.round_success('已返回大世界')

    @operation_node(name='返回研究站', is_start_node=True, timeout_seconds=15)
    def return_station(self) -> OperationRoundResult:
        """按钮仍名为返回研究站，但实际落点由游戏的入场来源决定。"""
        if not self.round_by_find_area(self.last_screenshot, '贝果-仓库', '放入仓库').is_success:
            return self.round_retry('未到结算仓库', wait=1)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '返回研究站', success_wait=1,
        )

    @node_from(from_name='返回研究站')
    @operation_node(name='等待返回入口', timeout_seconds=25)
    def wait_entry(self) -> OperationRoundResult:
        """先处理撤离奖励提示，再核对完整入口；黑屏和渐显期间只等待。"""
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
        if self._at_bagel_activity():
            # 结算返回也可能落在活动页；该页也有「前往空洞」，点它回到选图页。
            return self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-研究站', '前往空洞',
                until_find_all=[('贝果-选图', '前往备战')],
                success_wait=1, retry_wait=1,
            )
        if self._at_bagel_hub():
            return self.round_success('已返回贝果入口')
        if self._has('快捷手册', '大世界-普通'):
            return self.round_success('已返回大世界')
        return self.round_wait('等待返回贝果主界面或大世界', wait=0.5)
