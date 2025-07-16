from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import QWidget, QTableWidgetItem
from qfluentwidgets import TableWidget, PipsPager, FluentIcon, VBoxLayout, ToolButton, LineEdit, Dialog
from typing import Callable, List

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.git_service import GitLog
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.password_switch_setting_card import PasswordSwitchSettingCard
from one_dragon_qt.widgets.install_card.code_install_card import CodeInstallCard
from one_dragon_qt.widgets.install_card.git_install_card import GitInstallCard
from one_dragon.utils.app_utils import start_one_dragon
from one_dragon.utils.i18_utils import gt


class FetchTotalRunner(QThread):

    finished = Signal(int)

    def __init__(self, method: Callable[[], int]):
        super().__init__()
        self.method: Callable[[], int] = method

    def run(self) -> None:
        self.finished.emit(self.method())


class FetchPageRunner(QThread):

    finished = Signal(list)

    def __init__(self, method: Callable[[], List[GitLog]]):
        super().__init__()
        self.method: Callable[[], List[GitLog]] = method

    def run(self) -> None:
        self.finished.emit(self.method())


class CodeInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        content_widget = QWidget()

        self.page_num: int = -1
        self.page_size: int = 9

        v_layout = VBoxLayout(content_widget)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.force_update_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='强制更新', content='不懂代码请开启，会将脚本更新到最新并将你的改动覆盖，不会使你的配置失效',
        )
        v_layout.addWidget(self.force_update_opt)

        self.git_card = GitInstallCard(ctx)
        self.git_card.install_btn.setDisabled(True)
        self.git_card.finished.connect(self._on_git_updated)
        v_layout.addWidget(self.git_card)

        self.code_card = CodeInstallCard(ctx)
        self.code_card.finished.connect(self.on_code_updated)
        self.code_card.finished.connect(self._show_dialog_after_code_updated)
        v_layout.addWidget(self.code_card)

        self.custom_git_branch_lineedit = LineEdit()
        self.custom_git_branch_lineedit.setPlaceholderText(gt('自定义分支'))
        self.custom_git_branch_lineedit.editingFinished.connect(self._on_custom_branch_edited)
        self.code_card.git_branch_opt.currentIndexChanged.connect(
            lambda: self.custom_git_branch_lineedit.setText(self.code_card.git_branch_opt.currentData())
        )
        self.custom_git_branch_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.EDIT,
            title='自定义分支',
            extra_btn=self.custom_git_branch_lineedit,
            password_hash='9eccbf284f363f3a5f416e879aa9bcb2c8d8445997f97740270fccc98d360a33'
        )
        v_layout.addWidget(self.custom_git_branch_opt)

        self.log_table = TableWidget()
        self.log_table.setMinimumHeight(self.page_size * 42)

        self.log_table.setBorderVisible(True)
        self.log_table.setBorderRadius(8)

        self.log_table.setWordWrap(True)
        self.log_table.setColumnCount(5)
        self.log_table.setColumnWidth(0, 50)
        self.log_table.setColumnWidth(1, 100)
        self.log_table.setColumnWidth(2, 150)
        self.log_table.setColumnWidth(3, 200)
        self.log_table.setColumnWidth(4, 440)
        self.log_table.verticalHeader().hide()
        self.log_table.setHorizontalHeaderLabels([
            gt('回滚'),
            gt('ID'),
            gt('作者'),
            gt('时间'),
            gt('内容')
        ])

        v_layout.addWidget(self.log_table)

        self.pager = PipsPager()
        self.pager.setPageNumber(1)
        self.pager.setVisibleNumber(5)
        self.pager.currentIndexChanged.connect(self.on_page_changed)
        self.pager.setItemAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(self.pager)

        VerticalScrollInterface.__init__(
            self,
            object_name='code_interface',
            parent=parent, content_widget=content_widget,
            nav_text_cn='代码同步', nav_icon=FluentIcon.SYNC
        )
        self.ctx: OneDragonEnvContext = ctx

        self.fetch_total_runner = FetchTotalRunner(ctx.git_service.fetch_total_commit)
        self.fetch_total_runner.finished.connect(self.update_total)
        self.fetch_page_runner = FetchPageRunner(self.fetch_page)
        self.fetch_page_runner.finished.connect(self.update_page)

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.force_update_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('force_update'))
        self.custom_git_branch_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('custom_git_branch'))
        self.custom_git_branch_lineedit.setText(self.ctx.env_config.git_branch)
        self.start_fetch_total()
        self.git_card.check_and_update_display()
        self.code_card.check_and_update_display()

    def start_fetch_total(self) -> None:
        """
        开始获取总数
        :return:
        """
        if self.fetch_total_runner.isRunning():
            return
        self.fetch_total_runner.start()

    def update_total(self, total: int) -> None:
        """
        更新总数
        :param total:
        :return:
        """
        self.pager.setPageNumber(total // self.page_size + 1)
        if self.page_num == -1:  # 还没有加载过任何分页
            self.page_num = 0
            self.start_fetch_page()

    def start_fetch_page(self) -> None:
        """
        开始获取分页内容
        :return:
        """
        if self.fetch_page_runner.isRunning():
            return
        self.fetch_page_runner.start()

    def fetch_page(self) -> List[GitLog]:
        """
        获取分页数据
        :return:
        """
        return self.ctx.git_service.fetch_page_commit(self.page_num, self.page_size)

    def update_page(self, log_list: List[GitLog]) -> None:
        """
        更新分页内容
        :param log_list:
        :return:
        """
        page_size = len(log_list)
        self.log_table.setRowCount(page_size)

        for i in range(page_size):
            reset_btn = ToolButton(FluentIcon.LEFT_ARROW, parent=None)
            reset_btn.setFixedSize(32, 32)
            reset_btn.setProperty('commit', log_list[i].commit_id)
            reset_btn.clicked.connect(self.on_reset_commit_clicked)
            self.log_table.setCellWidget(i, 0, reset_btn)
            self.log_table.setItem(i, 1, QTableWidgetItem(log_list[i].commit_id))
            self.log_table.setItem(i, 2, QTableWidgetItem(log_list[i].author))
            self.log_table.setItem(i, 3, QTableWidgetItem(log_list[i].commit_time))
            self.log_table.setItem(i, 4, QTableWidgetItem(log_list[i].commit_message))

    def on_page_changed(self, page: int) -> None:
        """
        翻页
        :param page:
        :return:
        """
        if page == self.page_num:
            return
        self.page_num = page
        self.start_fetch_page()

    def _on_git_updated(self, success: bool) -> None:
        """
        Git选择后更新显示
        :param success: 是否成功
        :return:
        """
        if not success:
            return
        self.git_card.check_and_update_display()
        self.code_card.check_and_update_display()

    def on_code_updated(self, success: bool) -> None:
        """
        代码同步后更新显示
        :param success: 是否成功
        :return:
        """
        if not success:
            return

        self.pager.setCurrentIndex(0)
        self.page_num = -1
        self.start_fetch_total()

    def on_reset_commit_clicked(self) -> None:
        """
        回滚到特定的commit
        """
        btn = self.sender()
        commit_id = btn.property('commit')
        success = self.ctx.git_service.reset_to_commit(commit_id)
        if success:
            self.code_card.updated = True
            self.code_card.check_and_update_display()
            self.page_num = -1
            self.start_fetch_total()

    def _on_custom_branch_edited(self) -> None:
        text = self.custom_git_branch_lineedit.text()
        self.ctx.env_config.git_branch = text if text else self.code_card.git_branch_opt.currentData()
        self.code_card.check_and_update_display()

    def _show_dialog_after_code_updated(self, success: bool) -> None:
        """显示代码更新后的对话框"""
        if not success:
            return
        dialog = Dialog(gt('更新完成'), gt('代码已更新，重启以应用更改'), self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText(gt('立即重启'))
        dialog.cancelButton.setText(gt('稍后重启'))
        if dialog.exec():
            start_one_dragon(restart=True)
