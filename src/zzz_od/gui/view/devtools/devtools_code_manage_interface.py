from qfluentwidgets import FluentIcon, LineEdit

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.password_switch_setting_card import (
    PasswordSwitchSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class DevtoolsCodeManageInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='devtools_code_manage_interface',
            parent=parent,
            nav_text_cn='源码管理', nav_icon=FluentIcon.DEVELOPER_TOOLS
        )
        self.ctx: OneDragonEnvContext = ctx

    def get_content_widget(self) -> Column:
        content_widget = Column()

        self.auto_update_code_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.SYNC, title='自动更新', content='使用exe启动时，自动检测并更新代码',
            password_hash='69fec7ebc9c57ba044c55deb4e30aa1a6d6788f1da67b824ef96a590f526d20a',
            reverse_mode=True
        )
        content_widget.add_widget(self.auto_update_code_opt)

        self.force_update_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='强制更新', content='不懂代码请开启，会将脚本更新到最新并将你的改动覆盖，不会使你的配置失效',
        )
        content_widget.add_widget(self.force_update_opt)

        self.custom_git_branch_lineedit = LineEdit()
        self.custom_git_branch_lineedit.setPlaceholderText(gt('自定义分支'))
        self.custom_git_branch_lineedit.editingFinished.connect(self._on_custom_branch_edited)

        self.custom_git_branch_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.EDIT,
            title='自定义分支',
            extra_btn=self.custom_git_branch_lineedit,
            password_hash='9eccbf284f363f3a5f416e879aa9bcb2c8d8445997f97740270fccc98d360a33'
        )
        content_widget.add_widget(self.custom_git_branch_opt)
        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.auto_update_code_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('auto_update_code'))
        self.force_update_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('force_update'))
        self.custom_git_branch_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('custom_git_branch'))
        self.custom_git_branch_lineedit.setText(self.ctx.env_config.git_branch)

    def _on_custom_branch_edited(self) -> None:
        text = self.custom_git_branch_lineedit.text()
        if text:
            self.ctx.env_config.git_branch = text
