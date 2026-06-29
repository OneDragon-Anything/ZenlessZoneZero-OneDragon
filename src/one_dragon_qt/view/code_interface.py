from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QTableWidgetItem
from qfluentwidgets import (
    Dialog,
    FluentIcon,
    PipsPager,
    TableWidget,
    ToolButton,
)

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.git_service import GitLog
from one_dragon.utils.app_utils import start_one_dragon
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.install_card.code_install_card import CodeInstallCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class FetchTotalRunner(QThread):

    finished = Signal(int)

    def __init__(self, method: Callable[[], int]):
        super().__init__()
        self.method: Callable[[], int] = method

    def run(self) -> None:
        self.finished.emit(self.method())


class FetchPageRunner(QThread):

    finished = Signal(list)

    def __init__(self, method: Callable[[], list[GitLog]]):
        super().__init__()
        self.method: Callable[[], list[GitLog]] = method

    def run(self) -> None:
        self.finished.emit(self.method())


class CodeInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        self.page_num: int = -1
        self.page_size: int = 10

        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='code_interface',
            parent=parent,
            nav_text_cn='代码同步', nav_icon=FluentIcon.SYNC
        )
        self.ctx: OneDragonEnvContext = ctx

        self.fetch_total_runner = FetchTotalRunner(ctx.git_service.fetch_total_commit)
        self.fetch_total_runner.finished.connect(self.update_total)
        self.fetch_page_runner = FetchPageRunner(self.fetch_page)
        self.fetch_page_runner.finished.connect(self.update_page)

    def get_content_widget(self) -> Column:
        content_widget = Column()

        self.code_card = CodeInstallCard(self.ctx)
        self.code_card.finished.connect(self.on_code_updated)
        self.code_card.finished.connect(self._show_dialog_after_code_updated)
        content_widget.add_widget(self.code_card, alignment=Qt.AlignmentFlag(0))

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
        # 设置最后一列占用剩余空间
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.verticalHeader().hide()
        self.log_table.setHorizontalHeaderLabels([
            gt('回滚'),
            gt('ID'),
            gt('作者'),
            gt('时间'),
            gt('内容')
        ])
        content_widget.add_widget(self.log_table, stretch=1, alignment=Qt.AlignmentFlag(0))

        self.pager = PipsPager()
        self.pager.setPageNumber(1)
        self.pager.setVisibleNumber(5)
        self.pager.currentIndexChanged.connect(self.on_page_changed)
        self.pager.setItemAlignment(Qt.AlignmentFlag.AlignCenter)
        content_widget.add_widget(self.pager, alignment=Qt.AlignmentFlag.AlignHCenter)

        return content_widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.start_fetch_total()
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
        self.pager.setPageNumber((total + self.page_size - 1) // self.page_size)
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

    def fetch_page(self) -> list[GitLog]:
        """
        获取分页数据
        :return:
        """
        return self.ctx.git_service.fetch_page_commit(self.page_num, self.page_size)

    def update_page(self, log_list: list[GitLog]) -> None:
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

            author_item = QTableWidgetItem(log_list[i].author)
            author_item.setFlags(author_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 2, author_item)

            time_item = QTableWidgetItem(log_list[i].commit_time)
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 3, time_item)

            content_item = QTableWidgetItem(log_list[i].commit_message)
            content_item.setFlags(content_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 4, content_item)

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
        success, msg = self.ctx.git_service.reset_to_commit(commit_id)
        if success:
            self.code_card.updated = True
            self.code_card.check_and_update_display()
            self.page_num = -1
            self.start_fetch_total()
        elif msg:
            dialog = Dialog(gt('回滚失败'), msg, self)
            dialog.setTitleBarVisible(False)
            dialog.cancelButton.hide()
            dialog.exec()

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
