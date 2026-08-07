from collections.abc import Callable

from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import GitBranchEnum
from one_dragon.envs.git_service import GitSyncStatus
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard


class CodeInstallCard(BaseInstallCard):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):

        self.git_branches = [opt.value for opt in GitBranchEnum]
        self.git_branch_opt = ComboBox()
        self.git_branch_opt.set_items(self.git_branches)
        self.git_branch_opt.init_with_value(ctx.env_config.git_branch)
        self.git_branch_opt.currentIndexChanged.connect(self.on_git_branch_changed)
        self._last_sync_status = GitSyncStatus.FAILED

        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='代码版本',
            install_method=self.fetch_latest_code,
            install_btn_icon=FluentIcon.SYNC,
            install_btn_text_cn='代码同步',
            parent=parent,
            left_widgets=[self.git_branch_opt]
        )

        self.updated: bool = False  # 是否已经更新了

    @property
    def last_sync_status(self) -> GitSyncStatus:
        """获取最近一次代码同步状态。"""
        return self._last_sync_status

    def fetch_latest_code(
        self,
        progress_callback: Callable[[float, str], None],
    ) -> tuple[bool, str]:
        """同步代码，并保存用于界面提示的 Git 状态。"""
        status, message = self.ctx.git_service.fetch_latest_code(progress_callback)
        self._last_sync_status = status
        return status in (GitSyncStatus.SUCCESS, GitSyncStatus.UP_TO_DATE), message

    def on_git_branch_changed(self, index: int) -> None:
        self.ctx.env_config.git_branch = self.git_branches[index].value
        self.check_and_update_display()

    def after_progress_done(self, success: bool, msg: str) -> None:
        """根据最近一次 Git 同步状态更新提示。"""
        status = self._last_sync_status
        if status is GitSyncStatus.SUCCESS:
            self.updated = True
            message = f'{msg}, {gt("重启后生效")}'
        elif status is GitSyncStatus.RUNTIME_INCOMPATIBLE:
            message = f'{msg}, {gt("请先更新启动器")}'
        elif status is GitSyncStatus.BUILTIN_TAG_UNAVAILABLE:
            message = f'{msg}, {gt("请稍后重试")}'
        elif status is GitSyncStatus.REMOTE_UNAVAILABLE:
            message = f'{msg}, {gt("请稍后重试或切换代码源")}'
        elif status is GitSyncStatus.LOCAL_CHANGES:
            message = f'{msg}, {gt("可开启“强制更新”后重试")}'
        elif status is GitSyncStatus.LOCAL_UPDATE_FAILED:
            message = f'{msg}, {gt("请重启后重试；仍然失败时请重新安装")}'
        elif status is GitSyncStatus.FAILED:
            message = f'{msg}, {gt("请稍后重试；仍然失败时请查看日志")}'
        else:
            message = msg

        if status in (GitSyncStatus.SUCCESS, GitSyncStatus.UP_TO_DATE):
            color = FluentThemeColor.DEFAULT_BLUE.value
        elif status in (
            GitSyncStatus.RUNTIME_INCOMPATIBLE,
            GitSyncStatus.BUILTIN_TAG_UNAVAILABLE,
            GitSyncStatus.REMOTE_UNAVAILABLE,
            GitSyncStatus.LOCAL_CHANGES,
        ):
            color = FluentThemeColor.GOLD.value
        else:
            color = FluentThemeColor.RED.value

        self.update_display(FluentIcon.INFO.icon(color=color), message)

    def get_display_content(self) -> tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        current_branch = self.ctx.git_service.get_current_branch()
        if current_branch is None:
            return FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt('未同步代码')
        elif current_branch != self.ctx.env_config.git_branch:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
            msg = f"{gt('当前分支')}: {current_branch}; {gt('建议分支')}: {self.ctx.env_config.git_branch}; {gt('不自动同步')}"
            return icon, msg
        else:
            latest, msg = self.ctx.git_service.is_current_branch_latest()
            if latest:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
                msg = f"{gt('代码已同步')}" + ' ' + current_branch
            else:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)

            if self.updated:
                msg += ' ' + gt('更新后需重启脚本生效。如不能运行，请更新启动器')

            return icon, msg
