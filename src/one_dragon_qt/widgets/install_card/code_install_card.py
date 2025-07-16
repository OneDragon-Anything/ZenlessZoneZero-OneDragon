from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor
from typing import Tuple

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard
from one_dragon.utils.i18_utils import gt


class CodeInstallCard(BaseInstallCard):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):

        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='代码版本',
            install_method=ctx.git_service.fetch_latest_code,
            install_btn_icon=FluentIcon.SYNC,
            install_btn_text_cn='代码同步',
            parent=parent
        )

        self.updated: bool = False  # 是否已经更新了

    def after_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调，由子类自行实现
        :param success: 是否成功
        :param msg: 提示信息
        :return:
        """
        if success:
            self.check_and_update_display()
            self.updated = True
        else:
            msg = msg + ' 可考虑设置-脚本环境-代码源选择Gitee 但不能保证是最新版本'
            self.update_display(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt(msg, 'ui'))

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        git_path = self.ctx.env_config.git_path
        current_branch = self.ctx.git_service.get_current_branch()
        if git_path == '':
            return FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt('未配置Git', 'ui')
        elif current_branch is None:
            return FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt('未同步代码', 'ui')
        elif current_branch != self.ctx.env_config.git_branch:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
            msg = f"{gt('当前分支', 'ui')}: {current_branch}; {gt('建议分支', 'ui')}: {self.ctx.env_config.git_branch}; {gt('不自动同步', 'ui')}"
            return icon, msg
        else:
            latest, msg = self.ctx.git_service.is_current_branch_latest()
            if latest:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
                msg = f"{gt('已同步代码', 'ui')}" + ' ' + current_branch
            else:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)

            if self.updated:
                msg += ' ' + gt('更新后需重启脚本生效。如不能运行，尝试使用安装器更新运行依赖，或更新安装器', 'ui')

            return icon, msg
