from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class WaitNormalWorld(ZOperation):

    def __init__(self, ctx: ZContext, check_once: bool = False):
        """
        等待大世界画面的加载 有超时时间的设置
        :param ctx:
        :param check_once: 只检测一次，直接返回上级
        """
        self.check_once = check_once
        ZOperation.__init__(self, ctx,
                            op_name=gt('等待大世界画面')
                            )

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen(self) -> OperationRoundResult:
        """
        识别游戏画面
        :return:
        """
        # 大世界有两种画面：大世界-普通 / 大世界-勘域
        world_screens = ['大世界-普通', '大世界-勘域']
        current = self.check_and_update_current_screen(
            self.last_screenshot,
            screen_name_list=world_screens,
        )
        if current in world_screens:
            return self.round_success(status=current)

        result = self.round_by_find_area_binary(self.last_screenshot, '大世界', '信息')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_area(self.last_screenshot, '大世界', '星期')
        if result.is_success:
            return self.round_success(result.status)

        # 只检测一次直接返回
        if self.check_once:
            return self.round_fail('未到达大世界')

        return self.round_retry('未到达大世界', wait=1)
