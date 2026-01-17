from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt

from zzz_od.application.cloud_queue.cloud_queue import CloudGameQueue
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class CloudQueueApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(self, ctx, 'cloud_queue',
                              op_name=gt('云·排队'),
                              need_check_game_win=True,
                              need_notify=True,
                              run_record=ctx.cloud_queue_record,
        )

    def handle_init(self) -> None:
        pass

    @operation_node(name='检查并处理排队', is_start_node=True)
    def run_cloud_queue(self) -> OperationRoundResult:
        if self.ctx.game_account_config.is_cloud_game:
            result = self.round_by_find_area(self.last_screenshot, '云游戏', '国服PC云-切换窗口')
            if result.is_success:
                op = CloudGameQueue(self.ctx)
                return self.round_by_op_result(op.execute())

        return self.round_success()

    @node_from(from_name='检查并处理排队', status='点击进入游戏')
    @operation_node(name='进入游戏')
    def enter_game(self) -> OperationRoundResult:
        from zzz_od.operation.enter_game.enter_game import EnterGame
        op = EnterGame(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = CloudQueueApp(ctx)
    app._init_before_execute()
    app.run_cloud_queue()


if __name__ == '__main__':
    __debug()
