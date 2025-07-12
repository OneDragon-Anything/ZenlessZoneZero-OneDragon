from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class OpenCompendium(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        打开快捷手册
        使用了打开菜单 会包含返回大世界的操作
        """
        ZOperation.__init__(
            self,
            ctx=ctx,
            op_name=gt('打开快捷手册'),
        )

    @operation_node(name='打开菜单', is_start_node=True)
    def open_menu(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='菜单')

    @node_from(from_name='打开菜单')
    @operation_node(name='点击更多')
    def click_more(self) -> OperationRoundResult:
        """
        点击更多
        """
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('菜单', '底部列表')
        return self.round_by_ocr_and_click(screen, '快捷手册', area=area,
                                           success_wait=1, retry_wait=1)
