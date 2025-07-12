from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.enter_game import EnterGame
from zzz_od.operation.zzz_operation import ZOperation


class SwitchAccount(ZOperation):

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        ZOperation.__init__(self, ctx, op_name=gt('切换账号'))

    @operation_node(name='打开菜单', is_start_node=True)
    def open_menu(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='菜单')

    @node_from(from_name='打开菜单')
    @operation_node(name='点击更多')
    def click_more(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('菜单', '底部列表')
        return self.round_by_ocr_and_click(screen, '更多', area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='点击更多')
    @operation_node(name='更多选择登出')
    def more_click_logout(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('菜单', '更多功能')
        return self.round_by_ocr_and_click(screen, '登出', area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='更多选择登出')
    @operation_node(name='更多登出确认')
    def more_logout_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '菜单', '更多登出确认',
                                                 success_wait=10, retry_wait=1)

    @node_from(from_name='更多登出确认')
    @operation_node(name='等待切换账号可按', node_max_retry_times=20)
    def wait_switch_can_click(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_area(screen, '打开游戏', '点击进入游戏',
                                       retry_wait=1)

    @node_from(from_name='等待切换账号可按')
    @operation_node(name='进入游戏')
    def enter_game(self) -> OperationRoundResult:
        op = EnterGame(self.ctx, switch=True)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = SwitchAccount(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
