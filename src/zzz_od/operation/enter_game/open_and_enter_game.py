from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.auto_hdr import EnableAutoHDR, DisableAutoHDR
from zzz_od.operation.enter_game.open_game import OpenGame


class OpenAndEnterGame(Operation):

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        Operation.__init__(self, ctx, op_name=gt('打开并登录游戏'),
                           need_check_game_win=False)

    @operation_node(name='打开游戏', is_start_node=True)
    def open_game(self) -> OperationRoundResult:
        """
        打开游戏
        :return:
        """
        hdr_op = DisableAutoHDR(self.ctx)
        hdr_op.execute()
        op = OpenGame(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开游戏')
    @operation_node(name='等待游戏打开', node_max_retry_times=60)
    def wait_game(self) -> OperationRoundResult:
        if self.ctx.game_config.platform == 'PC':
            self.ctx.controller.game_win.init_win()
            if self.ctx.controller.is_game_window_ready:
                self.ctx.controller.active_window()
                hdr_op = EnableAutoHDR(self.ctx)
                hdr_op.execute()
                return self.round_success()
            else:
                return self.round_retry(wait=1)
        if self.ctx.game_config.platform == 'Emulator':
            pass#TODO打开模拟器要改到这里来 还有云绝适配

    @node_from(from_name='等待游戏打开')
    @operation_node(name='进入游戏')
    def enter_game(self) -> OperationRoundResult:
        if self.ctx.game_config.platform == 'PC':
            from zzz_od.operation.enter_game.enter_game import EnterGame
            op = EnterGame(self.ctx)
            return self.round_by_op_result(op.execute())
        if self.ctx.game_config.platform == 'Emulator':
            pass
