import os
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor
from typing import Tuple, Optional, Callable

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import DEFAULT_VENV_DIR_PATH
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard
from one_dragon.utils import cmd_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class GamepadInstallCard(BaseInstallCard):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        self.ctx: OneDragonEnvContext = ctx
        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='虚拟手柄',
            install_method=self.install_requirements,
            parent=parent
        )

    def after_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调，由子类自行实现
        :param success: 是否成功
        :param msg: 提示信息
        :return:
        """
        if success:
            self.ctx.env_config.update('vgamepad_requirement', self.get_requirement_time())
            self.check_and_update_display()
        else:
            self.update_display(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt(msg))

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        last = self.ctx.env_config.get('vgamepad_requirement', '')

        if last != self.get_requirement_time():
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
            msg = gt('需更新，请使用安装器更新')
        else:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            msg = f"{gt('已安装')}" + ' ' + last

        return icon, msg

    def get_requirement_time(self) -> Optional[str]:
        """
        获取 requirements.txt 的最后更新时间
        :return:
        """
        log.info('获取依赖文件的最后修改时间')
        return cmd_utils.run_command([self.ctx.env_config.git_path, 'log', '-1', '--pretty=format:"%ai"', '--', self.get_requirement_path()])

    def install_requirements(self, progress_callback: Optional[Callable[[float, str], None]]) -> Tuple[bool, str]:
        """
        安装依赖
        :return:
        """
        progress_callback(-1, '正在安装...安装过程可能需要安装驱动 正常安装即可')
        if not self.ctx.env_config.uv_path:
            return False, '未配置UV'
        os.environ["VIRTUAL_ENV"] = DEFAULT_VENV_DIR_PATH
        result = cmd_utils.run_command([self.ctx.env_config.uv_path, 'pip', 'install', '--upgrade',
                                        '-r', self.get_requirement_path(),
                                        '--index-url', self.ctx.env_config.pip_source,
                                        '--trusted-host', self.ctx.env_config.pip_trusted_host])
        success = result is not None
        msg = '运行依赖安装成功' if success else '运行依赖安装失败'
        return success, msg

    def get_requirement_path(self) -> str:
        return os.path.join(
            os_utils.get_work_dir(),
            self.ctx.project_config.get('vgamepad_requirements', 'requirements-gamepad.txt')
        )
