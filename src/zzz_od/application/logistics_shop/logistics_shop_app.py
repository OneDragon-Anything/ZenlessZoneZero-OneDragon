from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.logistics_shop import logistics_shop_const
from zzz_od.application.logistics_shop.logistics_shop_config import LogisticsShopConfig
from zzz_od.application.logistics_shop.operations.logistics_shop_buy import (
    LogisticsShopBuy,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class LogisticsShopApp(ZApplication):

    """哨站后勤:快捷手册商店月购储值电卡(限购×10 @120 零号业绩)。
    可选用深度清扫服务卡购买不限购储值电卡(默认关闭)。消耗零号业绩。"""

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=logistics_shop_const.APP_ID,
            op_name=logistics_shop_const.APP_NAME,
        )
        self.config: LogisticsShopConfig = self.ctx.run_context.get_config(
            app_id=logistics_shop_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

    @operation_node(name='返回大世界', is_start_node=True)
    def back_to_normal_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx, ensure_normal_world=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='购买电卡', timeout_seconds=600)
    def buy_power_card(self) -> OperationRoundResult:
        op = LogisticsShopBuy(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='购买电卡')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'logistics_shop'
    ctx.run_context.current_group_id = 'one_dragon'
    app = LogisticsShopApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
