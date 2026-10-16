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
    """从已处理完物资的结算仓库返回贝果入口，不寻找或移动到达塔。"""

    def __init__(self, ctx: ZContext) -> None:
        """由调用者先完成物资处理，再返回研究站开始下一局。"""
        super().__init__(ctx, op_name='贝果-返回研究站入口', timeout_seconds=60)
        self.reward_confirmed: bool = False
        self.world_recovery_attempted: bool = False

    def handle_init(self) -> None:
        """重跑时允许处理本次返回的奖励提示。"""
        super().handle_init()
        self.reward_confirmed = False
        self.world_recovery_attempted = False

    def _can_interact(self) -> bool:
        """头顶名称不足以确认交互范围，还需核对当前画面的交互按钮。"""
        return all(self.round_by_find_area(self.last_screenshot, screen, area).is_success
                   for screen, area in (
                       ('大世界-普通', '快捷手册'),
                       ('贝果-研究站', '接待员名称'),
                       ('战斗画面', '按键-交互'),
                   ))

    def recover_world(self) -> OperationRoundResult:
        """页面挡住返回时复用通用操作，每次返回仅尝试一次。"""
        if self.world_recovery_attempted:
            return self.round_fail('通用返回大世界后仍无法继续贝果返回，停止并保留现场')
        self.world_recovery_attempted = True
        operation = BackToNormalWorld(self.ctx, ensure_normal_world=True)
        operation.timeout_seconds = min(20, max(0, self.timeout_seconds - self.operation_usage_time))
        result = operation.execute()
        if not result.success:
            return self.round_by_op_result(result)
        return self.round_success('已返回大世界')

    @node_from(from_name='加载后直接交互', success=False, status=BagelOperation.STATUS_TIMEOUT)
    @node_from(from_name='打开贝果入口', success=False, status=BagelOperation.STATUS_TIMEOUT)
    @node_from(from_name='等待研究站加载', success=False, status=BagelOperation.STATUS_TIMEOUT)
    @operation_node(name='研究站加载超时恢复', screenshot_before_round=False)
    def recover_station_loading(self) -> OperationRoundResult:
        """返回加载或入口切换等满节点时限后，才尝试有限的通用恢复。"""
        return self.recover_world()

    @node_from(from_name='研究站加载超时恢复', status='已返回大世界')
    @node_from(from_name='等待研究站加载', status='已返回大世界')
    @node_from(from_name='打开贝果入口', status='已返回大世界')
    @operation_node(name='通用返回完成', screenshot_before_round=False)
    def finish_world_return(self) -> OperationRoundResult:
        """让正式任务从大世界重新检查入场，避免在其他落点盲按达塔交互。"""
        return self.round_success('已返回大世界')

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
        """先确认本次撤离奖励；入口渐显和页面阻挡均等节点超时后恢复。"""
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
    @operation_node(name='加载后直接交互', timeout_seconds=10)
    def interact_after_loading(self) -> OperationRoundResult:
        """只在大世界、达塔目标和可交互按钮同时出现时按 F。"""
        if not self._can_interact():
            return self.round_wait('等待达塔目标和可交互按钮', wait=0.5)
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
            if self._can_interact():
                self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            else:
                return self.round_wait('等待达塔对话或贝果入口', wait=0.5)
            return self.round_retry('等待达塔对话', wait=1)
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-研究站', '出发对话',
        )
        if result.is_success:
            return self.round_wait('等待贝果入口', wait=1)
        return result
