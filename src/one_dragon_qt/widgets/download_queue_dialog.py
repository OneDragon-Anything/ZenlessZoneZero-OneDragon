from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    HorizontalSeparator,
    IndeterminateProgressBar,
    MessageBoxBase,
    ProgressBar,
    StrongBodyLabel,
    SubtitleLabel,
    ToolTipFilter,
    ToolTipPosition,
    TransparentToolButton,
)

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.download_queue_service import (
    DownloadQueueService,
    ResourceDownloadTask,
    ResourceDownloadTaskState,
)
from one_dragon_qt.widgets.fast_scroll_area import FastScrollArea


class ElidedCaptionLabel(CaptionLabel):
    """宽度不足时在右侧显示省略号的说明文字。"""

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        self._full_text: str = ''
        CaptionLabel.__init__(self, parent)
        self.setText(text)

    def setText(self, text: str) -> None:
        """保存完整文字并刷新省略显示。"""
        self._full_text = text
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """尺寸变化后重新计算可显示文字。"""
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        """按当前宽度生成省略文字。"""
        elided_text = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            max(0, self.width()),
        )
        CaptionLabel.setText(self, elided_text)

class DownloadQueueItemWidget(QWidget):
    """下载队列中的轻量任务行。"""

    def __init__(
        self,
        service: DownloadQueueService,
        task: ResourceDownloadTask,
        parent: QWidget | None = None,
    ) -> None:
        """创建任务行。"""
        QWidget.__init__(self, parent)
        self.service: DownloadQueueService = service
        self.task: ResourceDownloadTask = task
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(12)

        self.name_widget = QWidget(self)
        self.name_widget.setFixedWidth(292)
        name_layout = QVBoxLayout(self.name_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(3)
        self.title_label = StrongBodyLabel(task.spec.title)
        self.title_label.setToolTip(task.spec.title)
        self.version_label = ElidedCaptionLabel(self._version_text())
        self.version_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        name_layout.addWidget(self.title_label)
        name_layout.addWidget(self.version_label)

        self.status_widget = QWidget(self)
        status_layout = QVBoxLayout(self.status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(3)
        self.status_label = ElidedCaptionLabel('')
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        status_layout.addWidget(self.status_label)

        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(5)
        self.indeterminate_bar = IndeterminateProgressBar()
        self.indeterminate_bar.setFixedHeight(5)
        self.indeterminate_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.indeterminate_bar)

        self.action_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.action_button.setFixedSize(28, 28)
        self.action_button.installEventFilter(
            ToolTipFilter(
                self.action_button,
                showDelay=500,
                position=ToolTipPosition.TOP,
            )
        )
        self.action_button.clicked.connect(self._on_action_clicked)
        content_row.addWidget(self.name_widget)
        content_row.addWidget(self.status_widget, stretch=1)
        content_row.addWidget(
            self.action_button,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addLayout(content_row)

        self.separator_spacer = QWidget(self)
        self.separator_spacer.setFixedHeight(8)
        layout.addWidget(self.separator_spacer)
        self.separator = HorizontalSeparator(self)
        layout.addWidget(self.separator)
        self.refresh(task)

    def set_separator_visible(self, visible: bool) -> None:
        """显示或隐藏任务行底部的分隔线及其前置留白。"""
        self.separator_spacer.setVisible(visible)
        self.separator.setVisible(visible)

    def _version_text(self) -> str:
        """返回任务目标版本。"""
        return self.task.spec.target_version or gt('最新版本')

    def refresh(self, task: ResourceDownloadTask) -> None:
        """刷新任务状态。"""
        self.task = task
        active = task.state in (
            ResourceDownloadTaskState.DOWNLOADING,
            ResourceDownloadTaskState.EXTRACTING,
            ResourceDownloadTaskState.APPLYING,
            ResourceDownloadTaskState.CANCELLING,
        )
        indeterminate = task.state in (
            ResourceDownloadTaskState.EXTRACTING,
            ResourceDownloadTaskState.APPLYING,
        ) or (
            task.state == ResourceDownloadTaskState.DOWNLOADING
            and task.progress.total_bytes == 0
        )
        self.indeterminate_bar.setVisible(active and indeterminate)
        self.progress_bar.setVisible(active and not indeterminate)
        self.progress_bar.setValue(int(task.progress.progress * 100))
        self.version_label.setText(self._version_text())
        self.status_label.setText(self._status_text())

        action_icon, action_tooltip = {
            ResourceDownloadTaskState.WAITING: (FluentIcon.CLOSE, '取消'),
            ResourceDownloadTaskState.DOWNLOADING: (FluentIcon.CLOSE, '取消'),
            ResourceDownloadTaskState.EXTRACTING: (FluentIcon.CLOSE, '取消'),
            ResourceDownloadTaskState.APPLYING: (FluentIcon.CLOSE, '取消'),
            ResourceDownloadTaskState.CANCELLING: (FluentIcon.CLOSE, '取消中'),
            ResourceDownloadTaskState.CANCELLED: (FluentIcon.DELETE, '移除'),
            ResourceDownloadTaskState.SUCCEEDED: (FluentIcon.DELETE, '移除'),
            ResourceDownloadTaskState.FAILED: (FluentIcon.SYNC, '重试'),
        }[task.state]
        self.action_button.setIcon(action_icon)
        self.action_button.setToolTip(gt(action_tooltip))
        self.action_button.setEnabled(
            task.state != ResourceDownloadTaskState.CANCELLING
        )

    def _transfer_text(self) -> str:
        """生成传输信息文本。"""
        progress = self.task.progress
        parts: list[str] = []
        if progress.source_id:
            source = self.service.ctx.repo_config.get_resource_source(progress.source_id)
            parts.append(source.label if source is not None else progress.source_id.upper())
        if progress.downloaded_bytes:
            downloaded = format_byte_size(progress.downloaded_bytes)
            if progress.total_bytes:
                parts.append(f'{downloaded}/{format_byte_size(progress.total_bytes)}')
            else:
                parts.append(downloaded)
        if progress.bytes_per_second:
            parts.append(f'{format_byte_size(int(progress.bytes_per_second))}/s')
        return ' · '.join(parts)

    def _status_text(self) -> str:
        """生成中列的单一状态文本行。"""
        if self.task.state == ResourceDownloadTaskState.DOWNLOADING:
            transfer = self._transfer_text()
            if transfer:
                return transfer
            return gt('正在连接')
        return gt({
            ResourceDownloadTaskState.WAITING: '等待中',
            ResourceDownloadTaskState.EXTRACTING: '正在解压',
            ResourceDownloadTaskState.APPLYING: '正在应用更新',
            ResourceDownloadTaskState.CANCELLING: '正在取消',
            ResourceDownloadTaskState.CANCELLED: '已取消',
            ResourceDownloadTaskState.SUCCEEDED: '已完成',
            ResourceDownloadTaskState.FAILED: '失败',
        }[self.task.state])

    def _on_action_clicked(self) -> None:
        """执行当前状态对应的操作。"""
        if self.task.state in (
            ResourceDownloadTaskState.WAITING,
            ResourceDownloadTaskState.DOWNLOADING,
            ResourceDownloadTaskState.EXTRACTING,
            ResourceDownloadTaskState.APPLYING,
        ):
            self.service.cancel(self.task.task_key)
        elif self.task.state == ResourceDownloadTaskState.FAILED:
            self.service.retry(self.task.task_key)
        else:
            self.service.remove(self.task.task_key)


class DownloadQueueDialog(MessageBoxBase):
    """可关闭并重新打开的下载队列弹窗。"""

    def __init__(
        self,
        service: DownloadQueueService,
        parent: QWidget,
    ) -> None:
        """创建下载队列弹窗。"""
        super().__init__(parent)
        self.service: DownloadQueueService = service
        self.item_widgets: dict[str, DownloadQueueItemWidget] = {}
        self._task_states: dict[str, ResourceDownloadTaskState] = {}

        self.buttonGroup.hide()
        self.viewLayout.setSpacing(8)

        self.header_widget = QWidget(self)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        header_text_layout = QVBoxLayout()
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(8)
        self.title_label = SubtitleLabel(gt('下载队列'))
        header_text_layout.addWidget(self.title_label)

        self.summary_widget = QWidget(self.header_widget)
        summary_layout = QHBoxLayout(self.summary_widget)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(12)
        self.running_summary_label = CaptionLabel('')
        self.waiting_summary_label = CaptionLabel('')
        self.completed_summary_label = CaptionLabel('')
        self.failed_summary_label = CaptionLabel('')
        summary_layout.addWidget(self.running_summary_label)
        summary_layout.addWidget(self.waiting_summary_label)
        summary_layout.addWidget(self.completed_summary_label)
        summary_layout.addWidget(self.failed_summary_label)
        summary_layout.addStretch(1)
        header_text_layout.addWidget(self.summary_widget)

        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.close_button.setFixedSize(32, 32)
        self.close_button.setToolTip(gt('关闭'))
        self.close_button.installEventFilter(
            ToolTipFilter(
                self.close_button,
                showDelay=500,
                position=ToolTipPosition.BOTTOM,
            )
        )
        self.close_button.clicked.connect(self.reject)
        header_layout.addLayout(header_text_layout, stretch=1)
        header_layout.addWidget(
            self.close_button,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
        self.viewLayout.addWidget(self.header_widget)

        self.scroll_area = FastScrollArea()
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            'QScrollArea { background-color: transparent; border: none; }'
        )
        self.scroll_area.viewport().setStyleSheet('background-color: transparent;')
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet('background-color: transparent;')
        self.items_layout = QVBoxLayout(self.scroll_content)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(0)
        self.empty_label = BodyLabel(gt('暂无下载任务'))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.items_layout.addWidget(self.empty_label, stretch=1)
        self.items_layout.addStretch(0)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.viewLayout.addWidget(self.scroll_area, stretch=1)

        self.widget.setFixedSize(760, 480)
        self.service.task_added.connect(self._on_task_added)
        self.service.task_updated.connect(self._on_task_updated)
        self.service.task_removed.connect(self._on_task_removed)
        self.service.queue_updated.connect(self.refresh_summary)
        self.refresh_all()

    def show_queue(self) -> None:
        """显示并置顶下载队列。"""
        self.refresh_all()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self._scroll_to_running_task)

    def resizeEvent(self, e: QResizeEvent) -> None:
        """父窗口尺寸变化后保持活动任务可见。"""
        super().resizeEvent(e)
        if hasattr(self, 'scroll_area'):
            QTimer.singleShot(0, self._scroll_to_running_task)

    def refresh_all(self) -> None:
        """根据服务状态重建缺失的任务行。"""
        for task in self.service.tasks:
            self._on_task_added(task)
            self._on_task_updated(task)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """刷新队列状态摘要和空状态。"""
        running = sum(
            task.state in (
                ResourceDownloadTaskState.DOWNLOADING,
                ResourceDownloadTaskState.EXTRACTING,
                ResourceDownloadTaskState.APPLYING,
                ResourceDownloadTaskState.CANCELLING,
            )
            for task in self.service.tasks
        )
        waiting = sum(
            task.state == ResourceDownloadTaskState.WAITING
            for task in self.service.tasks
        )
        completed = sum(
            task.state == ResourceDownloadTaskState.SUCCEEDED
            for task in self.service.tasks
        )
        failed = self.service.failed_count()
        self.running_summary_label.setText(f'{gt("下载中")} {running}')
        self.running_summary_label.setVisible(running > 0)
        self.waiting_summary_label.setText(f'{gt("等待中")} {waiting}')
        self.waiting_summary_label.setVisible(waiting > 0)
        self.completed_summary_label.setText(f'{gt("已完成")} {completed}')
        self.completed_summary_label.setVisible(completed > 0)
        self.failed_summary_label.setText(f'{gt("失败")} {failed}')
        self.failed_summary_label.setVisible(failed > 0)
        self.summary_widget.setVisible(
            running > 0 or waiting > 0 or completed > 0 or failed > 0
        )
        self.empty_label.setVisible(len(self.service.tasks) == 0)

    def _on_task_added(self, task: ResourceDownloadTask) -> None:
        """为新任务增加状态行。"""
        if task.task_key in self.item_widgets:
            return
        widget = DownloadQueueItemWidget(self.service, task, self.scroll_content)
        self.items_layout.insertWidget(self.items_layout.count() - 1, widget)
        self.item_widgets[task.task_key] = widget
        self._task_states[task.task_key] = task.state
        self._refresh_item_separators()
        self.refresh_summary()

    def _refresh_item_separators(self) -> None:
        """仅显示相邻任务行之间的分隔线。"""
        item_widgets = list(self.item_widgets.values())
        for index, widget in enumerate(item_widgets):
            widget.set_separator_visible(index < len(item_widgets) - 1)

    def _on_task_updated(self, task: ResourceDownloadTask) -> None:
        """刷新已有任务行，并在后续任务开始下载时滚动到该卡片。"""
        widget = self.item_widgets.get(task.task_key)
        if widget is None:
            self._on_task_added(task)
            widget = self.item_widgets[task.task_key]
        previous_state = self._task_states.get(task.task_key)
        widget.refresh(task)
        self._task_states[task.task_key] = task.state
        if (
            self.isVisible()
            and task.state == ResourceDownloadTaskState.DOWNLOADING
            and previous_state != ResourceDownloadTaskState.DOWNLOADING
        ):
            QTimer.singleShot(
                0,
                lambda task_key=task.task_key: self._scroll_to_task(task_key),
            )
        self.refresh_summary()

    def _scroll_to_running_task(self) -> None:
        """打开队列时将当前运行任务滚动到可见区域。"""
        for task in self.service.tasks:
            if task.state in (
                ResourceDownloadTaskState.DOWNLOADING,
                ResourceDownloadTaskState.EXTRACTING,
                ResourceDownloadTaskState.APPLYING,
                ResourceDownloadTaskState.CANCELLING,
            ):
                self._scroll_to_task(task.task_key)
                return

    def _scroll_to_task(self, task_key: str) -> None:
        """将指定任务卡片滚动到可见区域。"""
        widget = self.item_widgets.get(task_key)
        if widget is not None:
            self.scroll_area.ensureWidgetVisible(widget, 0, 8)

    def _on_task_removed(self, task_key: str) -> None:
        """移除任务行。"""
        widget = self.item_widgets.pop(task_key, None)
        self._task_states.pop(task_key, None)
        if widget is not None:
            self.items_layout.removeWidget(widget)
            widget.deleteLater()
        self._refresh_item_separators()
        self.refresh_summary()

def format_byte_size(size: int) -> str:
    """将字节数格式化为适合界面展示的文本。"""
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f'{value:.1f} {unit}'
        value /= 1024
    return f'{value:.1f} GB'
