import os
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor
from typing import Optional, Tuple

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import DEFAULT_GIT_PATH
from one_dragon_qt.widgets.install_card.wtih_existed_install_card import WithExistedInstallCard
from one_dragon.utils.i18_utils import gt


class GitInstallCard(WithExistedInstallCard):

    def __init__(self, ctx: OneDragonEnvContext):
        WithExistedInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='Git',
            install_method=ctx.git_service.install_default_git
        )

    def get_existed_os_path(self) -> Optional[str]:
        """
        获取系统环境变量中的路径，由子类自行实现
        :return:
        """
        return self.ctx.git_service.get_os_git_path()

    def on_existed_chosen(self, file_path: str) -> None:
        """
        选择了本地文件之后的回调，由子类自行实现
        :param file_path: 本地文件的路径
        :return:
        """
        self.ctx.env_config.git_path = file_path
        self.check_and_update_display()
        WithExistedInstallCard.on_existed_chosen(self, file_path)

    def after_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调，由子类自行实现
        :param success: 是否成功
        :param msg: 提示信息
        :return:
        """
        if success:
            self.ctx.env_config.git_path = DEFAULT_GIT_PATH
            self.check_and_update_display()
        else:
            self.update_display(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt(msg))

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        git_path = self.ctx.env_config.git_path

        if git_path == '':
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('未安装。可选择你自己的 git.exe')
        elif not os.path.exists(git_path):
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('文件不存在')
        else:
            git_version = self.ctx.git_service.get_git_version()
            if git_version is None:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
                msg = gt('无法获取 Git 版本') + ' ' + git_path
            else:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
                msg = f"{gt('已安装')}" + ' ' + git_path

        return icon, msg
