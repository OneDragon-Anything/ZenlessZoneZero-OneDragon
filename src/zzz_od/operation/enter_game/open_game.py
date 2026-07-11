import os
import subprocess

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.auto_hdr import DisableAutoHDR, EnableAutoHDR


class OpenGame(Operation):

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        Operation.__init__(self, ctx, op_name=gt('打开游戏'),
                           need_check_game_win=False)

    @operation_node(name='打开游戏', is_start_node=True, screenshot_before_round=False)
    def open_game(self) -> OperationRoundResult:
        """禁用自动 HDR + 启动游戏 exe。"""
        hdr_op = DisableAutoHDR(self.ctx)
        hdr_op.execute()

        if self.ctx.game_account_config.game_path == '':
            return self.round_fail('未配置游戏路径，请前往 [ 账户管理 ] -> [ 游戏路径 ] 手动设置')
        full_path = self.ctx.game_account_config.game_path
        dir_path = os.path.dirname(full_path)
        exe_name = os.path.basename(full_path)
        log.info('尝试自动启动游戏 路径为 %s', full_path)
        command = f'cmd /c "start "" /d "{dir_path}" "{exe_name}"'
        if self.ctx.game_config.launch_argument:
            screen_size = self.ctx.game_config.screen_size
            screen_width = screen_size.split('x')[0]
            screen_height = screen_size.split('x')[1]
            full_screen = self.ctx.game_config.full_screen
            popup_window = "-popupwindow" if self.ctx.game_config.popup_window else ""
            monitor = self.ctx.game_config.monitor
            arguement = (f'{self.ctx.game_config.launch_argument_advance}'
                         f' -screen-width {screen_width} -screen-height {screen_height}'
                         f' -screen-fullscreen {full_screen} {popup_window} -monitor {monitor}')
            command = f'{command} {arguement}'
        command = f'{command} & exit"'
        log.info('命令行指令 %s', command)

        # CREATE_BREAKAWAY_FROM_JOB:启动器用进程组管理时,使子进程逃离 jobobject,
        # 避免 OneDragon-Launcher.exe 退出后游戏被杀死。
        subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB
        )

        return self.round_success(wait=5)

    @node_from(from_name='打开游戏')
    @operation_node(name='等待游戏打开', node_max_retry_times=60, screenshot_before_round=False)
    def wait_game(self) -> OperationRoundResult:
        """等游戏窗口就绪 → 激活窗口 + 恢复 HDR。"""
        self.ctx.controller.init_game_win()
        if self.ctx.controller.is_game_window_ready:
            self.ctx.controller.active_window()
            hdr_op = EnableAutoHDR(self.ctx)
            hdr_op.execute()
            return self.round_success()
        else:
            return self.round_retry(wait=1)
