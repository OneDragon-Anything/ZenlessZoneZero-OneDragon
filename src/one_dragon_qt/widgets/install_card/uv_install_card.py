import os
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor
from typing import Optional, Tuple

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import DEFAULT_UV_PATH
from one_dragon_qt.widgets.install_card.wtih_existed_install_card import WithExistedInstallCard
from one_dragon.utils.i18_utils import gt


class UVInstallCard(WithExistedInstallCard):
    def __init__(self, ctx: OneDragonEnvContext):
        WithExistedInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='UV',
            install_method=ctx.python_service.install_default_uv
        )

    def get_existed_os_path(self) -> Optional[str]:
        """
        获取系统环境变量中的路径，由子类自行实现
        :return:
        """
        return self.ctx.python_service.get_os_uv_path()

    def on_existed_chosen(self, file_path: str) -> None:
        """
        选择了本地文件之后的回调，由子类自行实现
        :param file_path: 本地文件的路径
        :return:
        """
        self.ctx.env_config.uv_path = file_path
        self.check_and_update_display()

    def after_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调，由子类自行实现
        :param success: 是否成功
        :param msg: 提示信息
        :return:
        """
        if success:
            self.ctx.env_config.uv_path = DEFAULT_UV_PATH
            self.check_and_update_display()
        else:
            self.update_display(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt(msg))

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        uv_path = self.ctx.env_config.uv_path

        if uv_path == '':
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('未安装。可选择你自己的 uv.exe')
        elif not os.path.exists(uv_path):
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('文件不存在') + ' ' + uv_path
        else:
            uv_version = self.ctx.python_service.get_uv_version()
            if uv_version is None:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
                msg = gt('无法获取 UV 版本') + ' ' + uv_path
            else:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
                msg = f"{gt('已安装')}" + ' ' + uv_path

        return icon, msg