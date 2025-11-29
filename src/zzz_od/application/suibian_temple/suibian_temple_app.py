from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import node_notify, NotifyTiming
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.suibian_temple import suibian_temple_const
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_squad import (
    SuibianTempleAdventureSquad,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_auto_manage import SuibianTempleAutoManage
from zzz_od.application.suibian_temple.operations.suibian_temple_boo_box import (
    SuibianTempleBooBox,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_craft import (
    SuibianTempleCraft,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_good_goods import (
    SuibianTempleGoodGoods,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_pawnshop import (
    SuibianTemplePawnshop,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_sales_stall import (
    SuibianTempleSalesStall,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_yum_cha_sin import (
    SuibianTempleYumChaSin,
)
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class SuibianTempleApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=suibian_temple_const.APP_ID,
            op_name=suibian_temple_const.APP_NAME,
        )
        self.config: SuibianTempleConfig = self.ctx.run_context.get_config(
            app_id=suibian_temple_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
        current_screen_name, can_go = self.check_screen_with_can_go(self.last_screenshot, '快捷手册-目标')
        if can_go is not None and can_go == True:
            return self.round_by_goto_screen(self.last_screenshot, '快捷手册-目标',
                                             success_wait=1, retry_wait=1)

        current_screen_name, can_go = self.check_screen_with_can_go(self.last_screenshot, '随便观-入口')
        if can_go is not None and can_go == True:
            return self.round_success(status='随便观-入口')

        return self.round_retry(status='未识别初始画面', wait=1)

    @node_from(from_name='识别初始画面', status='未识别初始画面', success=False)
    @operation_node(name='开始前返回大世界')
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='快捷手册-目标')
    @node_from(from_name='开始前返回大世界')
    @operation_node(name='前往快捷手册-目标')
    def goto_category(self) -> OperationRoundResult:
        return self.round_by_goto_screen(self.last_screenshot, '快捷手册-目标')

    @node_from(from_name='前往快捷手册-目标')
    @operation_node(name='前往随便观', node_max_retry_times=10)
    def goto_suibian_temple(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '前往随便观',
            '确认',
        ]

        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            if result.status == '累计获得称愿':
                self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
            return self.round_wait(status=result.status, wait=1)

        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='识别初始画面', status='随便观-入口')
    @node_from(from_name='前往随便观')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理饮茶仙-只提交')
    def handle_yum_cha_sin_submit_only(self) -> OperationRoundResult:
        op = SuibianTempleYumChaSin(self.ctx, submit_only=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理饮茶仙-只提交')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理自动托管')
    def handle_auto_manage(self) -> OperationRoundResult:
        op = SuibianTempleAutoManage(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理游历')
    def handle_adventure_squad(self) -> OperationRoundResult:
        op = SuibianTempleAdventureSquad(
            self.ctx,
            claim=True,
            dispatch=not self.config.yum_cha_sin,  # 开启饮茶仙就不收获
        )
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理游历')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理饮茶仙')
    def handle_yum_cha_sin_submit(self) -> OperationRoundResult:
        if self.config.yum_cha_sin:
            op = SuibianTempleYumChaSin(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启')

    @node_from(from_name='处理饮茶仙')  # 只有开启了饮茶仙 才需要在饮茶仙之后再进一次游历
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='饮茶仙后处理游历')
    def handle_adventure_squad_2(self) -> OperationRoundResult:
        op = SuibianTempleAdventureSquad(self.ctx, claim=False, dispatch=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理饮茶仙', status='未开启')
    @node_from(from_name='饮茶仙后处理游历')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理制造坊')
    def handle_craft(self) -> OperationRoundResult:
        op = SuibianTempleCraft(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理制造坊')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理售卖铺')
    def handle_sales_stall(self) -> OperationRoundResult:
        op = SuibianTempleSalesStall(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理售卖铺')
    @node_from(from_name='处理自动托管')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理好物铺')
    def handle_good_goods(self) -> OperationRoundResult:
        if self.config.good_goods_purchase_enabled:
            op = SuibianTempleGoodGoods(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启')

    @node_from(from_name='处理好物铺')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理邦巢')
    def handle_boo_box(self) -> OperationRoundResult:
        """检查是否启用邦巢购买功能，决定后续流程"""
        if self.config.boo_box_purchase_enabled:
            op = SuibianTempleBooBox(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启')

    @node_from(from_name='处理邦巢')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理德丰大押')
    def handle_pawnshop(self) -> OperationRoundResult:
        if self.config.pawnshop_crest_enabled or self.config.pawnshop_omnicoin_enabled:
            op = SuibianTemplePawnshop(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启')

    @node_from(from_name='处理德丰大押')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    app = SuibianTempleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
