from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QWidget

from one_dragon.base.operation.context_download_request_event import (
    ContextDownloadRequestEvent,
)
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.envs.update_service import LauncherType
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.download_queue_service import (
    DownloadQueueService,
    ResourceDownloadSpec,
    ResourceDownloadTask,
    ResourceDownloadTaskState,
)
from one_dragon_qt.widgets.resource_download_dialog import ResourceUpdateDialog

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


@dataclass(frozen=True, slots=True)
class _ResourceCheck:
    """框架内部的一项资源检查及下载规格构造方法。"""

    check_id: str
    check_update: Callable[[], bool]
    build_specs: Callable[[], list[ResourceDownloadSpec]]


class _ResourceUpdateCheckRunner(QThread):
    """在后台执行单个资源提供器的更新检查。"""

    checked = Signal(str, bool)

    def __init__(
        self,
        resource_check: _ResourceCheck,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.resource_check: _ResourceCheck = resource_check

    def run(self) -> None:
        """执行检查；检查异常按无更新处理，确保聚合流程可以结束。"""
        need_update = False
        try:
            need_update = self.resource_check.check_update()
        except Exception:
            log.error(
                f'资源更新检查失败: {self.resource_check.check_id}',
                exc_info=True,
            )
        self.checked.emit(self.resource_check.check_id, need_update)


class ResourceUpdateCoordinator(QObject):
    """聚合通用和项目资源更新，并统一接入下载队列。"""

    def __init__(
        self,
        ctx: OneDragonContext,
        queue: DownloadQueueService,
        window: QWidget,
        show_queue_added_tip: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctx: OneDragonContext = ctx
        self.queue: DownloadQueueService = queue
        self.window: QWidget = window
        self._show_queue_added_tip: Callable[[str], None] = show_queue_added_tip
        self._resource_checks: dict[str, _ResourceCheck] = {}
        self._check_runners: dict[str, _ResourceUpdateCheckRunner] = {}
        self._pending_updates: dict[str, bool] = {}
        self._checks_complete: dict[str, bool] = {}
        self._pending_ocr_request: ContextDownloadRequestEvent | None = None
        self._welcome_dialog_closed: bool = False
        self._suppressed_update_keys: set[str] = set()
        self._update_dialog_scheduled: bool = False
        self._update_dialog_open: bool = False
        self._ocr_waiting: bool = False
        self._last_check_time: float = 0
        self._check_interval: float = 300
        self._checks_started: bool = False

        self._register_check(
            _ResourceCheck(
                check_id='launcher',
                check_update=self.ctx.update_service.is_launcher_update_available,
                build_specs=self._build_launcher_specs,
            )
        )
        self._register_check(
            _ResourceCheck(
                check_id='project_models',
                check_update=self.ctx.model_config.needs_model_download,
                build_specs=self._build_model_specs,
            )
        )

    def _register_check(self, resource_check: _ResourceCheck) -> None:
        """注册框架内部资源检查项。"""
        if resource_check.check_id in self._resource_checks:
            raise ValueError(f'资源更新检查重复注册: {resource_check.check_id}')
        self._resource_checks[resource_check.check_id] = resource_check
        self._pending_updates[resource_check.check_id] = False
        self._checks_complete[resource_check.check_id] = False
        runner = _ResourceUpdateCheckRunner(resource_check, self)
        runner.checked.connect(self._on_check_completed)
        self._check_runners[resource_check.check_id] = runner

    def check_updates(self, force: bool = False) -> None:
        """每次启动只检查一次；启动检查完成后，后续非强制调用不再检查。"""
        if self._checks_started and not force:
            return
        current_time = time.time()
        if not force and current_time - self._last_check_time <= self._check_interval:
            return
        if any(runner.isRunning() for runner in self._check_runners.values()):
            return

        self._checks_started = True
        self._last_check_time = current_time
        for check_id, runner in self._check_runners.items():
            self._checks_complete[check_id] = False
            runner.start()

    def on_welcome_dialog_closed(self) -> None:
        """首次欢迎弹窗结束后，才允许展示资源更新弹窗。"""
        self._welcome_dialog_closed = True
        if not self._checks_started:
            self.check_updates(force=True)
        self._schedule_update_dialog()

    def add_context_download_request(
        self,
        event: ContextDownloadRequestEvent,
    ) -> None:
        """把 OCR 初始化下载请求并入当前资源更新批次。"""
        if self._pending_ocr_request is not None:
            self._pending_ocr_request.respond(confirmed=False)
        self._pending_ocr_request = event
        if not self._checks_started:
            self.check_updates(force=True)
        self._schedule_update_dialog()

    def _on_check_completed(self, check_id: str, need_update: bool) -> None:
        """记录单项检查结果，并在全部完成后安排一次弹窗。"""
        if check_id not in self._resource_checks:
            return
        self._pending_updates[check_id] = need_update
        self._checks_complete[check_id] = True
        self._schedule_update_dialog()

    def _schedule_update_dialog(self) -> None:
        """等待检查和欢迎弹窗结束后，聚合展示全部可下载项。"""
        has_pending_update = any(self._pending_updates.values())
        if (
            not self._welcome_dialog_closed
            or not self._checks_started
            or not all(self._checks_complete.values())
            or not (has_pending_update or self._pending_ocr_request is not None)
            or self._ocr_waiting
            or self._update_dialog_scheduled
            or self._update_dialog_open
        ):
            return
        self._update_dialog_scheduled = True
        QTimer.singleShot(0, self._show_update_dialog)

    def _show_update_dialog(self) -> None:
        """展示聚合资源列表，确认后加入统一下载队列。"""
        self._update_dialog_scheduled = False
        if self._update_dialog_open:
            return
        self._update_dialog_open = True
        included_ocr_request = self._pending_ocr_request
        specs = self._build_pending_specs(included_ocr_request)
        if not specs:
            self._update_dialog_open = False
            self._reset_pending_updates()
            return

        self._suppressed_update_keys.update(
            spec.task_key
            for spec in specs
            if spec.resource_type != 'ocr'
        )

        selected_specs: list[ResourceDownloadSpec]
        remember_choice = False
        if self.ctx.env_config.resource_download_no_confirm:
            selected_specs = specs
        else:
            dialog = ResourceUpdateDialog(
                self.ctx,
                self.queue,
                specs,
                title='发现可下载资源',
                show_remember=included_ocr_request is not None,
                parent=self.window,
            )
            if not dialog.exec():
                if included_ocr_request is not None:
                    self._respond_ocr_request(
                        included_ocr_request,
                        False,
                        False,
                    )
                self._update_dialog_open = False
                self._reset_pending_updates()
                return
            selected_specs = dialog.selected_specs()
            remember_choice = dialog.remember_choice

        self._enqueue_selected_specs(
            selected_specs,
            included_ocr_request,
            remember_choice,
        )
        self._update_dialog_open = False
        self._reset_pending_updates()
        self._schedule_update_dialog()

    def _build_pending_specs(
        self,
        ocr_request: ContextDownloadRequestEvent | None,
    ) -> list[ResourceDownloadSpec]:
        """构造当前批次的通用与项目资源下载规格。"""
        specs: list[ResourceDownloadSpec] = []
        if ocr_request is not None:
            target_version = ocr_request.note or self.ctx.model_config.ocr
            specs.append(
                ResourceDownloadSpec(
                    resource_id='ocr',
                    resource_type='ocr',
                    title=ocr_request.title,
                    current_version='',
                    target_version=target_version,
                    downloader_factory=lambda: self.ctx.ocr,
                    note='首次使用需要下载',
                )
            )

        for check_id, resource_check in self._resource_checks.items():
            if not self._pending_updates[check_id]:
                continue
            try:
                resource_specs = resource_check.build_specs()
            except Exception:
                log.error(
                    f'构造资源下载项失败: {check_id}',
                    exc_info=True,
                )
                resource_specs = []
            if not resource_specs:
                self._pending_updates[check_id] = False
            specs.extend(
                spec
                for spec in resource_specs
                if spec.task_key not in self._suppressed_update_keys
            )
        return specs

    def _enqueue_selected_specs(
        self,
        specs: list[ResourceDownloadSpec],
        ocr_request: ContextDownloadRequestEvent | None,
        remember: bool,
    ) -> None:
        """将选中项加入队列，并等待 OCR 任务回传后端。"""
        selected_keys = {spec.task_key for spec in specs}
        ocr_task: ResourceDownloadTask | None = None
        for spec in specs:
            existing = self.queue.get_task(spec.task_key)
            if existing is not None and existing.state in (
                ResourceDownloadTaskState.FAILED,
                ResourceDownloadTaskState.CANCELLED,
            ):
                self.queue.retry(existing.task_key)
                task = existing
            elif existing is not None:
                task = existing
            else:
                task = self.queue.enqueue(
                    spec,
                    priority=spec.resource_type == 'ocr',
                )
            if spec.resource_type == 'ocr':
                ocr_task = task

        if ocr_request is not None:
            if not any(key.startswith('ocr:') for key in selected_keys):
                self._respond_ocr_request(ocr_request, False, False)
            elif ocr_task is not None:
                self._wait_for_ocr_task(ocr_request, ocr_task, remember)
        if specs:
            self._show_queue_added_tip(f'{len(specs)} {gt("项资源")}')

    def _wait_for_ocr_task(
        self,
        request: ContextDownloadRequestEvent,
        task: ResourceDownloadTask,
        remember: bool,
    ) -> None:
        """OCR 队列任务结束后唤醒等待初始化的后端线程。"""
        terminal_states = (
            ResourceDownloadTaskState.SUCCEEDED,
            ResourceDownloadTaskState.FAILED,
            ResourceDownloadTaskState.CANCELLED,
        )
        self._ocr_waiting = True
        if task.state in terminal_states:
            self._respond_ocr_request(
                request,
                task.state == ResourceDownloadTaskState.SUCCEEDED,
                remember,
            )
            return

        def _on_task_updated(updated: ResourceDownloadTask) -> None:
            if updated.task_key != task.task_key or updated.state not in terminal_states:
                return
            _disconnect()
            self._respond_ocr_request(
                request,
                updated.state == ResourceDownloadTaskState.SUCCEEDED,
                remember,
            )

        def _on_task_removed(removed_key: str) -> None:
            if removed_key != task.task_key:
                return
            _disconnect()
            self._respond_ocr_request(request, False, remember)

        def _disconnect() -> None:
            with contextlib.suppress(RuntimeError):
                self.queue.task_updated.disconnect(_on_task_updated)
            with contextlib.suppress(RuntimeError):
                self.queue.task_removed.disconnect(_on_task_removed)

        self.queue.task_updated.connect(_on_task_updated)
        self.queue.task_removed.connect(_on_task_removed)

    def _reset_pending_updates(self) -> None:
        """弹窗已展示并处理完毕后清除本轮待更新标记，避免立即重复弹窗。"""
        for check_id in self._pending_updates:
            self._pending_updates[check_id] = False

    def _respond_ocr_request(
        self,
        request: ContextDownloadRequestEvent,
        confirmed: bool,
        remember: bool,
    ) -> None:
        """结束指定 OCR 下载确认请求，不影响后来到达的新请求。"""
        if self._pending_ocr_request is request:
            self._pending_ocr_request = None
        self._ocr_waiting = False
        request.respond(confirmed=confirmed, remember=remember)

    def _build_launcher_specs(self) -> list[ResourceDownloadSpec]:
        """构造当前已安装启动器的更新下载项。"""
        update_service = self.ctx.update_service
        launcher_type = update_service.detect_running_launcher_type() or 'launcher'
        current, stable, beta = update_service.get_launcher_version_info(launcher_type)
        target = update_service.get_launcher_target_version(current, stable, beta)
        if not target or current == target:
            return []
        launcher_param = update_service.get_launcher_download_param(
            launcher_type,
            target,
            staging=True,
        )
        staging_dir = update_service.get_launcher_staging_dir(
            launcher_type,
            target,
        )
        return [
            ResourceDownloadSpec(
                resource_id=f'launcher_{launcher_type}',
                resource_type='launcher',
                title='启动器',
                current_version=current,
                target_version=target,
                note='启动器更新',
                downloader_factory=lambda: ZipDownloader(launcher_param),
                after_download=lambda success: self._after_launcher_download(
                    launcher_type,
                    staging_dir,
                    success,
                ),
            )
        ]

    def _build_model_specs(self) -> list[ResourceDownloadSpec]:
        """按项目模型配置声明构造全部缺失或更新任务。"""
        specs: list[ResourceDownloadSpec] = []
        for update in self.ctx.model_config.get_model_update_params():
            definition = update.definition
            specs.append(
                ResourceDownloadSpec(
                    resource_id=definition.config_key,
                    resource_type='model',
                    title=f'{definition.display_name}模型',
                    current_version=(
                        ''
                        if update.current_files_missing
                        else update.current_model
                    ),
                    target_version=update.target_model,
                    note=(
                        '模型文件缺失'
                        if update.current_files_missing
                        else '推荐版本更新'
                    ),
                    downloader_factory=(
                        lambda selected=update.download_param: ZipDownloader(
                            selected
                        )
                    ),
                    after_download=(
                        lambda success,
                        config_key=definition.config_key,
                        target=update.target_model: self._after_model_download(
                            config_key,
                            target,
                            success,
                        )
                    ),
                )
            )
        return specs

    def _after_model_download(
        self,
        config_key: str,
        target: str,
        success: bool,
    ) -> None:
        """模型下载成功后再切换当前配置。"""
        if success:
            self.ctx.model_config.update(config_key, target)

    def _after_launcher_download(
        self,
        launcher_type: LauncherType,
        staging_dir: Path,
        success: bool,
    ) -> None:
        """下载成功后事务替换启动器，失败时保留当前版本。"""
        if success:
            self.ctx.update_service.apply_staged_launcher_update(
                launcher_type,
                staging_dir,
            )
