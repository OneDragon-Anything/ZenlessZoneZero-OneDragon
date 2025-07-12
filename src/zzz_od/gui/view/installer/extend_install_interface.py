from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import ProgressBar, IndeterminateProgressBar, SettingCardGroup, \
    FluentIcon

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon.utils.i18_utils import gt
from zzz_od.gui.view.installer.gamepad_install_card import GamepadInstallCard


class ExtendInstallInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        VerticalScrollInterface.__init__(self, object_name='extend_install_interface',
                                         parent=parent, content_widget=None,
                                         nav_text_cn='扩展安装', nav_icon=FluentIcon.DEVELOPER_TOOLS)
        self.ctx: OneDragonEnvContext = ctx

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        v_layout = QVBoxLayout(content_widget)

        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setVisible(False)
        v_layout.addWidget(self.progress_bar)

        self.progress_bar_2 = IndeterminateProgressBar()
        self.progress_bar_2.setVisible(False)
        v_layout.addWidget(self.progress_bar_2)

        self.gamepad_opt = GamepadInstallCard(self.ctx)

        update_group = SettingCardGroup(gt('运行环境'))
        update_group.addSettingCard(self.gamepad_opt)

        v_layout.addWidget(update_group)

        log_group = SettingCardGroup(gt('安装日志'))
        self.log_card = LogDisplayCard()
        log_group.addSettingCard(self.log_card)
        v_layout.addWidget(log_group)

        return content_widget

    def on_interface_shown(self) -> None:
        """
        页面加载完成后 检测各个组件状态并更新显示
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.gamepad_opt.check_and_update_display()
        self.log_card.start()

    def on_interface_hidden(self) -> None:
        """
        子界面隐藏时的回调
        :return:
        """
        VerticalScrollInterface.on_interface_hidden(self)
        self.log_card.stop()

    def update_progress(self, progress: float, message: str) -> None:
        """
        进度回调更新
        :param progress: 进度 0~1
        :param message: 当前信息
        :return:
        """
        if progress == -1:
            self.progress_bar.setVisible(False)
            self.progress_bar_2.setVisible(True)
            self.progress_bar_2.start()
        else:
            self.progress_bar.setVisible(True)
            self.progress_bar.setVal(progress)
            self.progress_bar_2.setVisible(False)
            self.progress_bar_2.stop()
