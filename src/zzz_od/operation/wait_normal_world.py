from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class WaitNormalWorld(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        等待大世界画面的加载 有超时时间的设置
        :param ctx:
        """
        ZOperation.__init__(self, ctx,
                            op_name=gt('等待大世界画面')
                            )

    def handle_init(self):
        pass

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen(self) -> OperationRoundResult:
        """
        识别游戏画面
        :return:
        """
        screen = self.screenshot()

        return self.round_by_find_area(screen, '大世界', '信息',
                                       retry_wait=1)
