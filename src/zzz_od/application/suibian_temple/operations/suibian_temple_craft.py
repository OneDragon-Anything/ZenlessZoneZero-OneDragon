from typing import Optional

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.suibian_temple.operations.suibian_temple_craft_dispatch import SuibianTempleCraftDispatch
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleCraft(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 制造

        需要在随便观主界面时候调用，完成后返回随便观主界面

        操作步骤
        0. 前往制造台画面(可看见开工)
        1. 点击开工，没有 -> 最后一步
        2. 所需材料不足 -> 选择新的商品
        3. 没有新的商品 -> 最后一步
        4. 制造
        5. 返回随便观
        Args:
            ctx: 上下文
        """
        ZOperation.__init__(
            self, ctx, op_name=f"{gt('随便观', 'game')} {gt('制造', 'game')}"
        )
        self.config: Optional[SuibianTempleConfig] = self.ctx.run_context.get_config(
            app_id="suibian_temple"
        )

        self.last_item_list: list[str] = []  # 上一次的商品列表
        self.chosen_item_list: list[str] = []  # 已经选择过的商品列表
        self.scroll_after_choose: bool = False  # 选择后是否已经滑动了
        self.drag_times: int = 0  # 下拉次数

    @operation_node(name='前往制造', is_start_node=True)
    def goto_craft(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-制造坊'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        target_cn_list: list[str] = [
            '经营',
            '制造',
        ]
        ignore_cn_list: list[str] = [
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='前往制造')
    @node_from(from_name='制造派驻', status='已派驻')
    @operation_node(name='点击开工')
    def click_lets_go(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '开工',
            '开物',
            '制造暂停',
        ]
        ignore_cn_list: list[str] = [
            "开物",
        ]
        self.drag_times = 0
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_cn_list, ignore_cn_list=ignore_cn_list,
            success_wait=1, retry_wait=0.5)

    @node_from(from_name='点击开工')
    @operation_node(name='制造派驻')
    def craft_dispatch(self) -> OperationRoundResult:
        op = SuibianTempleCraftDispatch(
            self.ctx,
            from_craft=True,
            chosen_item_list=self.chosen_item_list,
        )
        op_result = op.execute()
        if op_result.success and op_result.data == True:
            return self.round_success(status='已派驻')
        else:
            return self.round_success(status='派驻失败')

    @node_from(from_name='点击开工', success=False)
    @node_from(from_name='制造派驻', status='派驻失败')
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
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleCraft(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
