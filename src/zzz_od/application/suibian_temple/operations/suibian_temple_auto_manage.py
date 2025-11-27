from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig

from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleAutoManage(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 自动托管

        需要在随便观主界面时候调用，完成后返回随便观主界面

        操作步骤
        0. 前往自动托管面板
            - 点击自动托管入口 再检测自动托管标签 用于确认自动管理画面正确打开
        1. 检查托管状态 (检查按钮文本)
            - 如果是停止托管 说明托管还没结束 -> 最后一步
            - 如果是开始托管 说明托管还没开始 -> 进入第3步 开始托管
            - 如果是领取收益 说明托管已结束 -> 进入第2步 领取收益
        2. 领取收益 -> 返回第1步 重新检查状态
        3. 开始托管 -> 最后一步
        4. 返回随便观
        Args:
            ctx: 上下文
        """
        ZOperation.__init__(
            self, ctx, op_name=f"{gt('随便观', 'game')} {gt('自动托管', 'game')}"
        )
        self.config: SuibianTempleConfig = self.ctx.run_context.get_config(
            app_id="suibian_temple",
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )


    @operation_node(name='前往自动托管', is_start_node=True)
    def goto_auto_manage(self) -> OperationRoundResult:
        # 1: 打开面板
        result = self.round_by_find_and_click_area(self.last_screenshot, screen_name='随便观-入口',
                                                   area_name='按钮-托管入口')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        # 2: 点标签 确认进了面板
        result = self.round_by_find_and_click_area(self.last_screenshot, screen_name='随便观-自动托管',
                                                   area_name='标签-自动托管')
        if result.is_success:
            return self.round_success(status=result.status, wait=1)

        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='前往自动托管')
    @node_from(from_name='领取收益')
    @operation_node(name='检查托管状态')
    def check_claim_reward(self) -> OperationRoundResult:
        if self.round_by_find_area(self.last_screenshot, screen_name='随便观-自动托管',
                                                   area_name='按钮-开始托管').is_success:
            return self.round_success(status="未开始", wait=1)
        if self.round_by_find_area(self.last_screenshot, screen_name='随便观-自动托管',
                                                   area_name='按钮-停止托管').is_success:
            return self.round_success(status="未结束", wait=1)
        if self.round_by_find_area(self.last_screenshot, screen_name='随便观-自动托管',
                                                   area_name='按钮-领取收益').is_success:
            return self.round_success(status="待领取", wait=1)

        return self.round_retry(status="未知状态", wait=1)

    @node_from(from_name='检查托管状态', status='未开始')
    @operation_node(name='开始托管')
    def start_auto_manage(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '随便观-自动托管',
            '按钮-开始托管',
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='检查托管状态', status='待领取')
    @operation_node(name='领取收益')
    def claim_reward(self) -> OperationRoundResult:
        # 1: 领取奖励
        result = self.round_by_find_and_click_area(self.last_screenshot, screen_name='随便观-自动托管',
                                                   area_name='按钮-领取收益')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        # 2: 点确认
        result = self.round_by_find_and_click_area(self.last_screenshot, screen_name='随便观-自动托管',
                                                   area_name='按钮-确认')
        if result.is_success:
            return self.round_success(status=result.status, wait=1)

        return self.round_retry(status=result.status, wait=1)


    @node_from(from_name='开始托管')
    @node_from(from_name='检查托管状态', status='未结束')
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'

    op = SuibianTempleAutoManage(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()