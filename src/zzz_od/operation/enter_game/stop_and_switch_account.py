import time

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class StopExeAndSwitchAccount(ZOperation):

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        ZOperation.__init__(self, ctx, op_name=gt('停进程并切换账号'), need_check_game_win=False)

    @operation_node(name='打开下一个游戏', node_max_retry_times=3, is_start_node=True)
    def close_exe(self) -> OperationRoundResult:
        # 关闭游戏
        if self.ctx.controller.is_game_window_ready:
            # 第一次尝试
            res = self.ctx.controller.close_game()
            if res != 0:
                log.warning('关闭游戏失败，2秒后重试一次')
                time.sleep(2)
                # 第二次尝试
                res = self.ctx.controller.close_game()
            # 轮询等待窗口释放，最多15秒
            wait_left = 15
            while res == 0 and wait_left > 0:
                # 刷新窗口句柄，避免旧缓存导致误判
                self.ctx.controller.game_win.init_win()
                if not self.ctx.controller.is_game_window_ready:
                    break
                time.sleep(1)
                wait_left -= 1
            # 仍未关闭则返回重试，交给节点重试机制
            if self.ctx.controller.is_game_window_ready:
                return self.round_retry('关闭游戏失败', wait=5)

        # 有时候游戏关闭了, 游戏占用的配置等文件没关闭, 故需等一会
        log.info('等待游戏占用文件释放(10s)...')
        time.sleep(10)

        # 启动下一个账号的游戏
        from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
        op = OpenAndEnterGame(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    op = StopExeAndSwitchAccount(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
