import os
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor
from typing import Tuple, Optional, Callable

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
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
            self.check_and_update_display()
        else:
            self.update_display(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt(msg))

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        if not self.ctx.env_config.uv_path:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
            msg = gt('未配置 UV')
        elif not self.ctx.python_service.uv_check_sync_status(groups=['gamepad']):
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
            msg = gt('需更新')
        else:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            msg = f"{gt('已安装')}"

        return icon, msg

    def install_requirements(self, progress_callback: Optional[Callable[[float, str], None]]) -> Tuple[bool, str]:
        """
        安装依赖
        :return:
        """
        progress_callback(-1, '正在安装...安装过程可能需要安装驱动 正常安装即可')
        if not self.ctx.env_config.uv_path:
            return False, '未配置UV'
        success, msg = self.ctx.python_service.uv_sync(progress_callback, groups=['gamepad'])
        return success, msg
