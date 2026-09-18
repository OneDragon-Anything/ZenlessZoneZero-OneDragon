from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal

from one_dragon.base.web.common_downloader import (
    CommonDownloader,
    ResourceDownloadProgress,
)
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext


class ResourceDownloadTaskState(StrEnum):
    """下载队列任务状态。"""

    WAITING = 'waiting'
    DOWNLOADING = 'downloading'
    EXTRACTING = 'extracting'
    APPLYING = 'applying'
    CANCELLING = 'cancelling'
    CANCELLED = 'cancelled'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


@dataclass(slots=True)
class ResourceDownloadSpec:
    """可加入下载队列的一项资源。"""

    resource_id: str
    resource_type: str
    title: str
    current_version: str
    target_version: str
    downloader_factory: Callable[[], CommonDownloader]
    note: str = ''
    source_order: list[str] | None = None
    before_download: Callable[[], None] | None = None
    after_download: Callable[[bool], None] | None = None

    @property
    def task_key(self) -> str:
        """返回队列去重键。"""
        return f'{self.resource_id}:{self.target_version}'


@dataclass(slots=True)
class ResourceDownloadTask:
    """下载队列中的任务及运行状态。"""

    spec: ResourceDownloadSpec
    state: ResourceDownloadTaskState = ResourceDownloadTaskState.WAITING
    queued_at: float = field(default_factory=time.time)
    progress: ResourceDownloadProgress = field(default_factory=ResourceDownloadProgress)
    error_message: str = ''
    progress_signal: dict[str, str | None] = field(default_factory=lambda: {'signal': None})

    @property
    def task_key(self) -> str:
        """返回任务去重键。"""
        return self.spec.task_key


class DownloadTaskWorker(QThread):
    """执行单个下载任务的工作线程。"""

    progress_changed = Signal(object)
    task_finished = Signal(bool, bool, str)

    def __init__(self, ctx: OneDragonEnvContext, task: ResourceDownloadTask) -> None:
        """创建任务线程。

        Args:
            ctx: 环境上下文。
            task: 要执行的下载任务。
        """
        super().__init__()
        self.ctx: OneDragonEnvContext = ctx
        self.task: ResourceDownloadTask = task

    def run(self) -> None:
        """执行下载并上报最终结果。"""
        success = False
        error_message = ''
        try:
            if self.task.spec.before_download is not None:
                self.task.spec.before_download()
            env_config = self.ctx.env_config
            downloader = self.task.spec.downloader_factory()
            success = downloader.download(
                source_order=self.task.spec.source_order or env_config.get_resource_source_order(),
                proxy_url=env_config.personal_proxy if env_config.is_personal_proxy else None,
                ghproxy_url=env_config.gh_proxy_url if env_config.is_gh_proxy else None,
                skip_if_existed=False,
                progress_signal=self.task.progress_signal,
                status_callback=self.progress_changed.emit,
                on_source_success=env_config.mark_resource_source_success,
                on_source_failure=env_config.mark_resource_source_failure,
                fallback_on_slow=env_config.is_resource_source_auto,
            )
        except Exception as exc:
            error_message = str(exc)
            log.error('下载队列任务失败', exc_info=True)
        finally:
            if self.task.spec.after_download is not None:
                try:
                    if success:
                        self.progress_changed.emit(
                            ResourceDownloadProgress(
                                phase='applying',
                                progress=1,
                                message='正在应用更新',
                            )
                        )
                    self.task.spec.after_download(success)
                except Exception as exc:
                    success = False
                    error_message = str(exc)
                    log.error('下载任务后处理失败', exc_info=True)

        cancelled = self.task.progress_signal.get('signal') == 'cancel'
        self.task_finished.emit(success, cancelled, error_message)

    def cancel(self) -> None:
        """请求取消当前下载。"""
        self.task.progress_signal['signal'] = 'cancel'


class DownloadQueueService(QObject):
    """进程内单线程资源下载队列。"""

    task_added = Signal(object)
    task_updated = Signal(object)
    task_removed = Signal(str)
    queue_updated = Signal()

    def __init__(self, ctx: OneDragonEnvContext, parent: QObject | None = None) -> None:
        """创建下载队列。

        Args:
            ctx: 环境上下文。
            parent: Qt 父对象。
        """
        super().__init__(parent)
        self.ctx: OneDragonEnvContext = ctx
        self.tasks: list[ResourceDownloadTask] = []
        self._worker: DownloadTaskWorker | None = None
        self._current_task: ResourceDownloadTask | None = None
        self._worker_result: tuple[bool, bool, str] | None = None

    def enqueue(self, spec: ResourceDownloadSpec, priority: bool = False) -> ResourceDownloadTask:
        """添加任务，重复任务直接返回已有实例。

        Args:
            spec: 资源规格。
            priority: 是否插入当前任务之后。

        Returns:
            新建或已有的任务。
        """
        existing = self.get_task(spec.task_key)
        if existing is not None:
            return existing

        task = ResourceDownloadTask(spec=spec)
        if priority and self._current_task in self.tasks:
            current_index = self.tasks.index(self._current_task)
            self.tasks.insert(current_index + 1, task)
        else:
            self.tasks.append(task)
        self.task_added.emit(task)
        self.queue_updated.emit()
        self._start_next()
        return task

    def get_task(self, task_key: str) -> ResourceDownloadTask | None:
        """按去重键查找任务。"""
        return next((task for task in self.tasks if task.task_key == task_key), None)

    def cancel(self, task_key: str) -> None:
        """取消运行任务或移除等待任务。"""
        task = self.get_task(task_key)
        if task is None:
            return
        if task.state == ResourceDownloadTaskState.WAITING:
            task.state = ResourceDownloadTaskState.CANCELLED
            task.progress = ResourceDownloadProgress(phase='cancelled', message='已取消')
            self.task_updated.emit(task)
            self.queue_updated.emit()
            return
        if task is self._current_task and self._worker is not None:
            task.state = ResourceDownloadTaskState.CANCELLING
            task.progress = ResourceDownloadProgress(
                source_id=task.progress.source_id,
                phase='cancelling',
                downloaded_bytes=task.progress.downloaded_bytes,
                total_bytes=task.progress.total_bytes,
                bytes_per_second=task.progress.bytes_per_second,
                progress=task.progress.progress,
                message='正在取消',
            )
            self._worker.cancel()
            self.task_updated.emit(task)
            self.queue_updated.emit()

    def cancel_all(self) -> None:
        """取消所有等待或运行任务。"""
        for task in list(self.tasks):
            if task.state in (
                ResourceDownloadTaskState.WAITING,
                ResourceDownloadTaskState.DOWNLOADING,
                ResourceDownloadTaskState.EXTRACTING,
                ResourceDownloadTaskState.APPLYING,
            ):
                self.cancel(task.task_key)

    def retry(self, task_key: str) -> None:
        """重新排队一个失败或已取消任务。"""
        task = self.get_task(task_key)
        if task is None or task.state not in (
            ResourceDownloadTaskState.FAILED,
            ResourceDownloadTaskState.CANCELLED,
        ):
            return
        task.state = ResourceDownloadTaskState.WAITING
        task.progress = ResourceDownloadProgress()
        task.error_message = ''
        task.progress_signal = {'signal': None}
        if task in self.tasks:
            self.tasks.remove(task)
        insert_index = (
            self.tasks.index(self._current_task) + 1
            if self._current_task in self.tasks
            else 0
        )
        self.tasks.insert(insert_index, task)
        self.task_updated.emit(task)
        self.queue_updated.emit()
        self._start_next()

    def remove(self, task_key: str) -> None:
        """移除非运行状态任务。"""
        task = self.get_task(task_key)
        if task is None or task is self._current_task:
            return
        self.tasks.remove(task)
        self.task_removed.emit(task_key)
        self.queue_updated.emit()

    def clear_finished(self) -> None:
        """清除成功和已取消任务。"""
        removable = [
            task for task in self.tasks
            if task is not self._current_task
            and task.state in (
                ResourceDownloadTaskState.SUCCEEDED,
                ResourceDownloadTaskState.CANCELLED,
            )
        ]
        for task in removable:
            self.tasks.remove(task)
            self.task_removed.emit(task.task_key)
        if removable:
            self.queue_updated.emit()

    def has_active_tasks(self) -> bool:
        """返回是否存在等待或运行任务。"""
        return any(
            task.state in (
                ResourceDownloadTaskState.WAITING,
                ResourceDownloadTaskState.DOWNLOADING,
                ResourceDownloadTaskState.EXTRACTING,
                ResourceDownloadTaskState.APPLYING,
                ResourceDownloadTaskState.CANCELLING,
            )
            for task in self.tasks
        )

    def active_count(self) -> int:
        """返回等待和运行任务数量。"""
        return sum(
            task.state in (
                ResourceDownloadTaskState.WAITING,
                ResourceDownloadTaskState.DOWNLOADING,
                ResourceDownloadTaskState.EXTRACTING,
                ResourceDownloadTaskState.APPLYING,
                ResourceDownloadTaskState.CANCELLING,
            )
            for task in self.tasks
        )

    def failed_count(self) -> int:
        """返回失败任务数量。"""
        return sum(task.state == ResourceDownloadTaskState.FAILED for task in self.tasks)

    def _start_next(self) -> None:
        """没有运行任务时启动下一项。"""
        if self._worker is not None and self._worker.isRunning():
            return
        task = next(
            (item for item in self.tasks if item.state == ResourceDownloadTaskState.WAITING),
            None,
        )
        if task is None:
            self._worker = None
            self._current_task = None
            self.queue_updated.emit()
            return

        self._current_task = task
        task.state = ResourceDownloadTaskState.DOWNLOADING
        task.progress_signal = {'signal': None}
        self.task_updated.emit(task)
        self.queue_updated.emit()

        worker = DownloadTaskWorker(self.ctx, task)
        worker.progress_changed.connect(
            lambda progress, bound_task=task: self._on_progress_changed(bound_task, progress)
        )
        worker.task_finished.connect(self._store_worker_result)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._worker_result = None
        worker.start()

    def _on_progress_changed(
        self,
        task: ResourceDownloadTask,
        progress: ResourceDownloadProgress,
    ) -> None:
        """保存指定任务的进度。"""
        if task is not self._current_task:
            return
        task.progress = progress
        if progress.phase == 'extracting':
            task.state = ResourceDownloadTaskState.EXTRACTING
        elif progress.phase == 'applying':
            task.state = ResourceDownloadTaskState.APPLYING
        elif task.state != ResourceDownloadTaskState.CANCELLING:
            task.state = ResourceDownloadTaskState.DOWNLOADING
        self.task_updated.emit(task)

    def _store_worker_result(self, success: bool, cancelled: bool, error_message: str) -> None:
        """保存工作线程结果，等线程真正结束后再启动下一项。"""
        self._worker_result = (success, cancelled, error_message)

    def _on_worker_finished(self) -> None:
        """收口当前任务并启动下一项。"""
        task = self._current_task
        if task is None:
            return
        success, cancelled, error_message = self._worker_result or (
            False,
            task.progress_signal.get('signal') == 'cancel',
            '下载线程异常结束',
        )
        task.error_message = error_message
        if success:
            task.state = ResourceDownloadTaskState.SUCCEEDED
            task.progress = ResourceDownloadProgress(phase='succeeded', progress=1, message='下载完成')
        elif cancelled:
            task.state = ResourceDownloadTaskState.CANCELLED
            task.progress = ResourceDownloadProgress(phase='cancelled', message='已取消')
        else:
            task.state = ResourceDownloadTaskState.FAILED
            message = error_message or task.progress.message or '下载失败'
            task.progress = ResourceDownloadProgress(
                source_id=task.progress.source_id,
                phase='failed',
                downloaded_bytes=task.progress.downloaded_bytes,
                total_bytes=task.progress.total_bytes,
                progress=task.progress.progress,
                message=message,
            )
        self.task_updated.emit(task)
        self.queue_updated.emit()
        self._worker = None
        self._current_task = None
        self._worker_result = None
        self._start_next()
