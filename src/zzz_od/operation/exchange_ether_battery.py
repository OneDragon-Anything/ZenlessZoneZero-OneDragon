from typing import ClassVar

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class ExchangeEtherBattery(ZOperation):
    """
    从快捷手册资源栏进入以太电池合成，并完成电池兑换。
    """

    STATUS_CONTINUE_EXCHANGE: ClassVar[str] = '继续兑换'

    def __init__(self, ctx: ZContext, plan: ChargePlanItem) -> None:
        ZOperation.__init__(
            self,
            ctx=ctx,
            op_name='兑换以太电池'
        )
        self.config: ChargePlanConfig = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.plan: ChargePlanItem = plan

    @operation_node(name='点击以太电池', is_start_node=True)
    def click_ether_battery(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '快捷手册',
            '以太电池',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='点击以太电池')
    @operation_node(name='点击合成入口')
    def click_synthesize_entry(self) -> OperationRoundResult:
        return self.round_by_ocr_and_click(
            self.last_screenshot,
            '[获取]合成',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='点击合成入口')
    @operation_node(name='等待道具处理', timeout_seconds=20)
    def wait_item_process(self) -> OperationRoundResult:
        current_screen = self.check_and_update_current_screen(self.last_screenshot, ['道具处理'])
        if not current_screen:
            return self.round_retry('等待道具处理', wait=0.5)
        return self.round_success()

    @node_from(from_name='等待道具处理')
    @operation_node(name='检查合成素材')
    def check_material(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('道具处理', '详情标题')
        ocr_result = self.round_by_ocr(self.last_screenshot, '以太电池', area=area)
        if not ocr_result.is_success:
            return self.round_fail('当前可合成项目不是以太电池')

        result = self.round_by_find_area(self.last_screenshot, '道具处理', '合成素材不足')
        if result.is_success:
            # 返回失败让体力计划app自动跳过计划
            return self.round_fail('合成素材不足')
        return self.round_success()

    @node_from(from_name='检查合成素材')
    @node_from(from_name='兑换完成', status=STATUS_CONTINUE_EXCHANGE)
    @operation_node(name='点击合成')
    def click_synthesize(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '道具处理',
            '按钮-合成',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='点击合成')
    @operation_node(name='确认合成')
    def confirm_synthesize(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '道具处理-合成确认',
            '按钮-确认',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='确认合成')
    @operation_node(name='确认获得')
    def confirm_obtained(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '道具处理-获得', '标题-获得')
        if result.is_success:
            return self.round_by_find_and_click_area(
                self.last_screenshot,
                '道具处理-获得',
                '按钮-确认',
                success_wait=0.8,
                retry_wait=0.5,
            )

        result = self.round_by_find_area(self.last_screenshot, '道具处理', '标题-道具处理')
        if result.is_success:
            return self.round_success()

        return self.round_retry('等待获得弹窗', wait=0.5)

    @node_from(from_name='确认获得')
    @node_from(from_name='确认获得', success=False)
    @operation_node(name='兑换完成')
    def finish_exchange(self) -> OperationRoundResult:
        self.config.add_plan_run_times(self.plan)

        if self.plan.run_times < self.plan.plan_times:
            return self.round_success(self.STATUS_CONTINUE_EXCHANGE, wait=0.5)

        return self.round_success()
