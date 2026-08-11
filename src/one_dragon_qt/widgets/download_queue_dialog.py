from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    IndeterminateProgressBar,
    MessageBoxBase,
    ProgressBar,
    PushButton,
    SimpleCardWidget,
    StrongBodyLabel,
    SubtitleLabel,
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


def format_byte_size(size: int) -> str:
    """将字节数格式化为适合界面展示的文本。"""
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f'{value:.1f} {unit}'
        value /= 1024
    return f'{value:.1f} GB'


class DownloadQueueItemWidget(SimpleCardWidget):
    """下载队列中的单项状态卡片。"""

    def __init__(
        self,
        service: DownloadQueueService,
        task: ResourceDownloadTask,
        parent: QWidget | None = None,
    ) -> None:
        """创建任务卡片。"""
        SimpleCardWidget.__init__(self, parent)
        self.service: DownloadQueueService = service
        self.task: ResourceDownloadTask = task

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self.title_label = StrongBodyLabel(task.spec.title)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.title_label.setToolTip(task.spec.title)
        layout.addWidget(self.title_label)

        self.version_label = ElidedCaptionLabel(self._version_text())
        self.version_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.version_label)

        progress_row = QHBoxLayout()
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.indeterminate_bar = IndeterminateProgressBar()
        self.indeterminate_bar.setVisible(False)
        self.action_button = PushButton('')
        self.action_button.clicked.connect(self._on_action_clicked)
        progress_row.addWidget(self.progress_bar, stretch=1)
        progress_row.addWidget(self.indeterminate_bar, stretch=1)
        progress_row.addWidget(self.action_button)
        layout.addLayout(progress_row)

        self.detail_label = CaptionLabel('')
        self.detail_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.detail_label)
        self.refresh(task)

    def _version_text(self) -> str:
        """返回版本变化文本。"""
        current = self.task.spec.current_version or gt('未安装')
        target = self.task.spec.target_version or gt('最新版本')
        return f'{current} → {target}'

    def refresh(self, task: ResourceDownloadTask) -> None:
        """刷新任务状态。"""
        self.task = task
        version_text = self._version_text()
        self.version_label.setText(version_text)
        indeterminate = task.state in (
            ResourceDownloadTaskState.EXTRACTING,
            ResourceDownloadTaskState.APPLYING,
        ) or (
            task.state == ResourceDownloadTaskState.DOWNLOADING
            and task.progress.downloaded_bytes > 0
            and task.progress.total_bytes == 0
        )
        self.indeterminate_bar.setVisible(indeterminate)
        self.progress_bar.setVisible(not indeterminate)
        self.progress_bar.setValue(int(task.progress.progress * 100))
        self.detail_label.setText(self._detail_text())

        action_text = {
            ResourceDownloadTaskState.WAITING: '取消',
            ResourceDownloadTaskState.DOWNLOADING: '取消',
            ResourceDownloadTaskState.EXTRACTING: '取消',
            ResourceDownloadTaskState.APPLYING: '取消',
            ResourceDownloadTaskState.CANCELLING: '取消中',
            ResourceDownloadTaskState.CANCELLED: '移除',
            ResourceDownloadTaskState.SUCCEEDED: '移除',
            ResourceDownloadTaskState.FAILED: '重试',
        }[task.state]
        self.action_button.setText(gt(action_text))
        self.action_button.setEnabled(task.state != ResourceDownloadTaskState.CANCELLING)

    def _detail_text(self) -> str:
        """生成下载详情文本。"""
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
        state_text = {
            ResourceDownloadTaskState.WAITING: '等待中',
            ResourceDownloadTaskState.DOWNLOADING: '下载中',
            ResourceDownloadTaskState.EXTRACTING: '正在解压',
            ResourceDownloadTaskState.APPLYING: '正在应用更新',
            ResourceDownloadTaskState.CANCELLING: '正在取消',
            ResourceDownloadTaskState.CANCELLED: '已取消',
            ResourceDownloadTaskState.SUCCEEDED: '已完成',
            ResourceDownloadTaskState.FAILED: '失败',
        }[self.task.state]
        if self.task.state == ResourceDownloadTaskState.FAILED and progress.message:
            state_text = progress.message
        elif (
            self.task.state == ResourceDownloadTaskState.DOWNLOADING
            and progress.phase == 'connecting'
        ):
            state_text = '正在连接'
        parts.append(gt(state_text))
        return ' · '.join(parts)

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

        self.yesButton.setText(gt('关闭'))
        self.cancelButton.hide()

        self.title_label = SubtitleLabel(gt('下载队列'))
        self.summary_label = CaptionLabel('')
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.summary_label)

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
        self.items_layout.setSpacing(8)
        self.empty_label = BodyLabel(gt('暂无下载任务'))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.items_layout.addWidget(self.empty_label, stretch=1)
        self.items_layout.addStretch(0)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setMinimumHeight(260)
        self.viewLayout.addWidget(self.scroll_area)

        self.widget.setMinimumWidth(620)
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

    def refresh_all(self) -> None:
        """根据服务状态重建缺失的任务行。"""
        for task in self.service.tasks:
            self._on_task_added(task)
            self._on_task_updated(task)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """刷新队列摘要和空状态。"""
        active = self.service.active_count()
        failed = self.service.failed_count()
        waiting = sum(
            task.state == ResourceDownloadTaskState.WAITING
            for task in self.service.tasks
        )
        running = active - waiting
        self.summary_label.setText(
            f'{gt("等待")} {waiting} · {gt("运行")} {running} · {gt("失败")} {failed}'
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
        self.refresh_summary()

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
        self.refresh_summary()
