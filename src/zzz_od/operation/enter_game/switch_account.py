import time

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from one_dragon.utils.log_utils import log
from zzz_od.operation.enter_game.enter_game import EnterGame
from zzz_od.operation.zzz_operation import ZOperation


class SwitchAccount(ZOperation):

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        ZOperation.__init__(self, ctx, op_name=gt('切换账号'))
        self._is_exe_same: bool = True

    @operation_node(name='准备切换账号', is_start_node=True)
    def prepare_to_switch_account(self) -> OperationRoundResult:
        if self._is_exe_same:
            return self.round_success()
        return self.round_success('需要切换游戏区服')

    @node_from(from_name='准备切换账号', status='需要切换游戏区服')
    @operation_node(name='切换游戏区服', node_max_retry_times=3, screenshot_before_round=False)
    def close_exe(self) -> OperationRoundResult:
        # 关闭游戏
        if self.ctx.controller_prev_user.is_game_window_ready:
            # 第一次尝试
            res = self.ctx.controller_prev_user.close_game()
            if res != 0:
                log.warning('关闭游戏失败，2秒后重试一次')
                time.sleep(2)
                # 第二次尝试
                res = self.ctx.controller_prev_user.close_game()
            # 轮询等待窗口释放，最多15秒
            wait_left = 15
            while res == 0 and wait_left > 0:
                # 刷新窗口句柄，避免旧缓存导致误判
                self.ctx.controller_prev_user.game_win.init_win()
                if not self.ctx.controller_prev_user.is_game_window_ready:
                    break
                time.sleep(1)
                wait_left -= 1
            # 仍未关闭则返回重试，交给节点重试机制
            if self.ctx.controller_prev_user.is_game_window_ready:
                return self.round_retry('关闭游戏失败', wait=5)

        # 有时候游戏关闭了, 游戏占用的配置等文件没关闭, 故需等一会
        log.info('等待游戏占用文件释放(10s)...')
        time.sleep(10)

        # 启动下一个账号的游戏
        from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
        op = OpenAndEnterGame(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='准备切换账号')
    @operation_node(name='打开菜单')
    def open_menu(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='菜单')

    @node_from(from_name='打开菜单')
    @operation_node(name='点击更多')
    def click_more(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('菜单', '底部列表')
        return self.round_by_ocr_and_click(self.last_screenshot, '更多', area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='点击更多')
    @operation_node(name='更多选择登出')
    def more_click_logout(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('菜单', '更多功能')
        return self.round_by_ocr_and_click(self.last_screenshot, '登出', area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='更多选择登出')
    @operation_node(name='更多登出确认')
    def more_logout_confirm(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '菜单', '更多登出确认',
                                                 success_wait=10, retry_wait=1)

    @node_from(from_name='更多登出确认')
    @operation_node(name='等待切换账号可按', node_max_retry_times=20)
    def wait_switch_can_click(self) -> OperationRoundResult:
        return self.round_by_find_area(self.last_screenshot, '打开游戏', '点击进入游戏',
                                       retry_wait=1)

    @node_from(from_name='等待切换账号可按')
    @operation_node(name='进入游戏')
    def enter_game(self) -> OperationRoundResult:
        op = EnterGame(self.ctx, switch=True)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.init_ocr()
    ctx.run_context.start_running()
    op = SwitchAccount(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
