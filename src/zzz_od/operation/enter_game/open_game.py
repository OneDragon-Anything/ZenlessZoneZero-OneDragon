import os
import subprocess

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext


class OpenGame(Operation):

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        Operation.__init__(self, ctx, op_name=gt('打开游戏'),
                           need_check_game_win=False)

    @operation_node(name='打开游戏', is_start_node=True, screenshot_before_round=False)
    def open_game(self) -> OperationRoundResult:
        """
        打开游戏
        :return:
        """
        if self.ctx.game_account_config.game_path == '':
            return self.round_fail('未配置游戏路径，请前往 [ 账户管理 ] -> [ 游戏路径 ] 手动设置')
        full_path = self.ctx.game_account_config.game_path
        dir_path = os.path.dirname(full_path)
        exe_name = os.path.basename(full_path)
        log.info('尝试自动启动游戏 路径为 %s', full_path)
        # 获取文件夹路径
        command = f'cmd /c "start "" /d "{dir_path}" "{exe_name}"'
        if self.ctx.game_config.launch_argument:
            screen_size = self.ctx.game_config.screen_size
            screen_width = screen_size.split('x')[0]
            screen_height = screen_size.split('x')[1]
            full_screen = self.ctx.game_config.full_screen
            popup_window = "-popupwindow" if self.ctx.game_config.popup_window else ""
            monitor = self.ctx.game_config.monitor
            arguement = f'{self.ctx.game_config.launch_argument_advance} -screen-width {screen_width} -screen-height {screen_height} -screen-fullscreen {full_screen} {popup_window} -monitor {monitor}'
            command = f'{command} {arguement}'
        command = f'{command} & exit"'
        log.info('命令行指令 %s', command)

        try:
            subprocess.Popen(command)

            # 埋点：游戏启动事件
            if hasattr(self.ctx, 'telemetry') and self.ctx.telemetry:
                self.ctx.telemetry.track_custom_event('game_launched', {
                    'launch_method': 'auto_launch',
                    'has_launch_arguments': self.ctx.game_config.launch_argument,
                    'screen_size': self.ctx.game_config.screen_size if hasattr(self.ctx.game_config, 'screen_size') else 'unknown',
                    'full_screen': self.ctx.game_config.full_screen if hasattr(self.ctx.game_config, 'full_screen') else False,
                    'event_category': 'game_lifecycle'
                })

            return self.round_success(wait=5)
        except Exception as e:
            # 埋点：游戏启动失败事件
            if hasattr(self.ctx, 'telemetry') and self.ctx.telemetry:
                self.ctx.telemetry.track_custom_event('game_launch_failed', {
                    'launch_method': 'auto_launch',
                    'error_type': type(e).__name__,
                    'event_category': 'game_lifecycle'
                })
            raise
