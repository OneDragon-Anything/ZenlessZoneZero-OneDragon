import os
import subprocess
import sys

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.auto_hdr import DisableAutoHDR, EnableAutoHDR


class OpenGame(Operation):

    # 游戏窗口已经出现、但连续这么多次都激活不了，就判定启动失败，避免一直重试掩盖问题
    ACTIVE_WINDOW_MAX_FAIL_TIMES = 5

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        self.activate_fail_times: int = 0
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

        if not getattr(sys, 'frozen', False):
            # CREATE_BREAKAWAY_FROM_JOB:启动器用进程组管理时,使子进程逃离 jobobject,
            # 避免 OneDragon-Launcher.exe 退出后游戏被杀死。
            subprocess.Popen(
                command,
                creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB
            )
        else:
            subprocess.Popen(command)

        return self.round_success(wait=5)

    @node_from(from_name='打开游戏')
    @operation_node(name='等待游戏打开', node_max_retry_times=60, screenshot_before_round=False)
    def wait_game(self) -> OperationRoundResult:
        """等游戏窗口就绪 → 激活窗口 + 恢复 HDR。

        窗口出现不代表能激活（例如系统弹窗占据前台、窗口句柄失效）。激活失败时不能再无脑返回成功，
        否则后面会进入登录识别连续报"未知画面"；这里重试几次后直接失败并说明原因。
        """
        self.ctx.controller.init_game_win()
        if not self.ctx.controller.is_game_window_ready:
            # 窗口还没出现不算一次激活失败，计数归零，保证统计的是连续失败
            self.activate_fail_times = 0
            return self.round_retry(wait=1)

        if self.ctx.controller.active_window():
            self.activate_fail_times = 0
            hdr_op = EnableAutoHDR(self.ctx)
            hdr_op.execute()
            return self.round_success()

        self.activate_fail_times += 1
        if self.activate_fail_times >= self.ACTIVE_WINDOW_MAX_FAIL_TIMES:
            # 启动失败也要把 HDR 恢复回去，否则下次 DisableAutoHDR 会把"已禁用"当成原始值存下来，
            # 用户原本的 HDR 设置就再也回不来了
            EnableAutoHDR(self.ctx).execute()
            return self.round_fail(
                f'游戏窗口已打开但连续 {self.activate_fail_times} 次激活失败，'
                '请检查是否有系统弹窗或其他窗口抢占前台'
            )
        return self.round_retry(wait=1)
