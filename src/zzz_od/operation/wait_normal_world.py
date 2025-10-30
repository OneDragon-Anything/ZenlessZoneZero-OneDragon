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
        # 大世界有两种画面：大世界-普通 / 大世界-勘域
        current_screen = self.check_and_update_current_screen(
            self.last_screenshot, screen_name_list=['大世界-普通', '大世界-勘域']
        )
        if current_screen in ['大世界-普通', '大世界-勘域']:
            return self.round_success(current_screen)

        return self.round_retry('未到达大世界', wait=1)
