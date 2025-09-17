from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_dispatch import (
    SuibianTempleAdventureDispatch,
    SuibianTempleAdventureDispatchDuration,
)
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleAdventureSquad(ZOperation):

    def __init__(
        self,
        ctx: ZContext,
        claim: bool = True,
        dispatch: bool = True,
    ):
        """
        随便观 - 游历

        需要在游历画面时候调用，完成后返回随便观主界面

        操作步骤
        1. 如果进行收获，则点击游历小队；否则跳到4
        2. 点击游历完成，如果有的话
            2.1. 点击 可收获 -> 确认
            2.2. 点击 自动选择邦布
            2.3. 邦布电量不足 -> 返回第1步
            2.4. 开启了饮茶仙 且本次不是目标不是派遣 -> 返回第1步
            2.5. 派遣 -> 返回第1步
        3. 没有游历完成了，返回到游历的主界面
        4. 如果进行派遣 则进入5；否则进入6
        5. 点击 可派遣小队，如果有的话
            5.1. 执行派遣op
        6. 返回随便观
        Args:
            ctx: 上下文
        """
        ZOperation.__init__(
            self, ctx, op_name=f"{gt('随便观', 'game')} {gt('游历', 'game')}"
        )

        self.claim: bool = claim  # 是否收获
        self.dispatch: bool = dispatch  # 是否派遣
        self.config: SuibianTempleConfig = self.ctx.run_context.get_config(app_id='suibian_temple')  # type: ignore

    @node_from(from_name='收获后重新派遣')
    @node_from(from_name='收获后重新派遣', success=False)
    @operation_node(name='点击游历小队', is_start_node=True)
    def click_squad_team(self) -> OperationRoundResult:
        if not self.claim:
            return self.round_success(status='跳过收获')

        target_cn_list: list[str] = [
            '游历小队',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击游历小队', status='游历小队')
    @operation_node(name='点击游历完成')
    def click_finish(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '游历完成',
            '游历小队',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击游历完成', status='游历完成')
    @operation_node(name='点击可收获')
    def click_claim(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '可收获',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击可收获', status='可收获')
    @operation_node(name='点击确认')
    def click_confirm(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '确认',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击确认', status='确认')
    @operation_node(name='收获后重新派遣')
    def execute_dispatch_1(self) -> OperationRoundResult:
        if not self.dispatch:
            return self.round_success(status='跳过派遣')
        op = SuibianTempleAdventureDispatch(
            self.ctx,
            SuibianTempleAdventureDispatchDuration[self.config.squad_duration],  # type: ignore
        )
        return self.round_by_op_result(op.execute())

    @node_from(from_name='点击游历小队', status='跳过收获')
    @node_from(from_name='点击游历完成', success=False)
    @node_from(from_name='点击游历完成', status='游历小队')
    @node_from(from_name='选择新派遣', status='派遣成功')
    @operation_node(name='点击可派遣小队')
    def click_dispatch_team(self) -> OperationRoundResult:
        if not self.dispatch:
            return self.round_success(status='跳过派遣')
        target_cn_list: list[str] = [
            '可派遣小队',
        ]
        # TODO: 可派遣小队一直在同一个位置 后续需要增加派遣选项
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击可派遣小队')
    @operation_node(name='选择新派遣')
    def execute_dispatch_2(self) -> OperationRoundResult:
        op = SuibianTempleAdventureDispatch(
            self.ctx,
            SuibianTempleAdventureDispatchDuration[self.config.squad_duration],  # type: ignore
        )
        return self.round_by_op_result(op.execute())

    @node_from(from_name='选择新派遣')  # 除了派遣成功都是失败 跳过后续
    @node_from(from_name='点击可派遣小队', status='跳过派遣')
    @node_from(from_name='点击可派遣小队', success=False)
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
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleAdventureSquad(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()