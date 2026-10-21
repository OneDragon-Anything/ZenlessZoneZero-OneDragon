from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from packaging import version

from one_dragon.base.web.common_downloader import (
    CommonDownloaderParam,
    ResourceDownloadProgress,
)
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.envs.git_service import GitSyncStatus, WorkingDirectorySnapshot
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext


class RecoveryRepairChannel(StrEnum):
    """恢复重装使用的版本通道。"""

    STABLE = 'stable'
    BETA = 'beta'


class RecoveryRepairStage(StrEnum):
    """恢复重装的阶段。"""

    CHECKING_ASSET = 'checking_asset'
    DOWNLOADING = 'downloading'
    VERIFYING = 'verifying'
    CHECKING_WORKSPACE = 'checking_workspace'
    WAITING_FORCE_CONFIRM = 'waiting_force_confirm'
    SYNCING_CODE = 'syncing_code'
    COMMITTING = 'committing'
    APPLYING = 'applying'
    CANCELLING = 'cancelling'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


@dataclass(frozen=True, slots=True)
class RecoveryRepairEvent:
    """恢复重装状态变化。"""

    stage: RecoveryRepairStage
    progress: float = 0.0
    source_id: str = ''
    message: str = ''
    error: str = ''
    tag: str = ''


RecoveryEventCallback = Callable[[RecoveryRepairEvent], None]


@dataclass
class _CheckoutCommitState:
    """记录检出前最后确认过的工作区状态。"""

    snapshot: WorkingDirectorySnapshot
    force: bool | None = None
    error: Exception | None = None


class RecoveryRepairService:
    """不依赖 Qt 的恢复模式一键重装流程。"""

    def __init__(
        self,
        ctx: OneDragonEnvContext,
        event_callback: RecoveryEventCallback | None = None,
        restart_callback: Callable[[], None] | None = None,
    ) -> None:
        """创建恢复重装服务。"""
        self.ctx: OneDragonEnvContext = ctx
        self._event_callback: RecoveryEventCallback | None = event_callback
        self._restart_callback: Callable[[], None] | None = restart_callback
        self._worker: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._commit_started: bool = False
        self._force_decision: bool | None = None
        self._force_decision_event = threading.Event()
        self._progress_signal: dict[str, str | None] | None = None
        self._state_lock = threading.Lock()
        self._target: str = ''
        self._tag: str = ''
        self._checkout_state: _CheckoutCommitState | None = None

    def set_event_callback(self, callback: RecoveryEventCallback | None) -> None:
        """设置状态回调。"""
        self._event_callback = callback

    def start(self, target: str, force: bool = False) -> bool:
        """按版本通道或兼容的固定 tag 开始恢复重装。"""
        with self._state_lock:
            if self.is_active():
                return False
            if not target:
                self._emit(RecoveryRepairEvent(
                    RecoveryRepairStage.FAILED,
                    message='未选择版本通道',
                    error='未选择版本通道',
                ))
                return False
            self._target = target
            self._tag = ''
            self._cancel_event.clear()
            self._commit_started = False
            self._force_decision = force
            self._force_decision_event.clear()
            self._worker = threading.Thread(
                target=self._run,
                name='recovery-repair',
                daemon=True,
            )
            self._worker.start()
            return True

    def cancel(self) -> None:
        """在写入工作区前请求协作式取消。"""
        with self._state_lock:
            if not self.is_active():
                return
            if self._commit_started:
                can_cancel = False
            else:
                can_cancel = True
                self._cancel_event.set()
                if self._progress_signal is not None:
                    self._progress_signal['signal'] = 'cancel'
        if not can_cancel:
            self._emit(RecoveryRepairEvent(
                RecoveryRepairStage.COMMITTING,
                tag=self._tag,
                message='正在完成代码与启动器替换，当前阶段不能取消',
            ))
            return
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.CANCELLING,
            tag=self._tag,
            message='正在取消',
        ))

    def respond_force_confirmation(self, approved: bool) -> None:
        """回应工作区覆盖确认。"""
        self._force_decision = approved
        self._force_decision_event.set()

    def is_active(self) -> bool:
        """返回重装线程是否仍在运行。"""
        return self._worker is not None and self._worker.is_alive()

    def _run(self) -> None:
        """按选版本、下载校验、检出代码、替换启动器的顺序执行重装。"""
        try:
            initial_snapshot = self._get_workspace_snapshot()
            force = self._ensure_workspace_confirmation(
                initial_snapshot,
                preapproved=self._force_decision is True,
            )
            if force is None:
                self._emit_cancelled()
                return

            self._tag, urls = self._select_repair_target()
            staging_dir = self._download_and_validate_launcher(urls)
            self._checkout_selected_tag(initial_snapshot, force)
            self._apply_launcher(staging_dir)
            self._emit(RecoveryRepairEvent(
                RecoveryRepairStage.SUCCEEDED,
                progress=1.0,
                tag=self._tag,
                message='重装完成',
            ))
            if self._restart_callback is not None:
                self._restart_callback()
        except _RecoveryCancelled:
            self._emit_cancelled()
        except FileNotFoundError as error:
            self._emit_failure(str(error))
        except Exception as error:
            log.error('恢复模式一键重装失败', exc_info=True)
            self._emit_failure(str(error))
        finally:
            self._progress_signal = None
            self._worker = None

    def _select_repair_target(self) -> tuple[str, dict[str, str]]:
        """选择可下载的版本，并返回标签和下载地址。"""
        self._check_cancelled()
        candidates = self._get_candidate_tags()
        tag, urls = self._select_available_tag(candidates)
        self._check_cancelled()
        return tag, urls

    def _download_and_validate_launcher(
        self,
        urls: dict[str, str],
    ) -> Path:
        """下载并校验暂存启动器，返回暂存目录。"""
        staging_dir = self.ctx.update_service.get_launcher_staging_dir(
            'runtime', self._tag,
        )
        param = self.ctx.update_service.get_launcher_download_param(
            'runtime',
            self._tag,
            staging=True,
            download_urls=urls,
        )
        self._download(param)
        self._check_cancelled()
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.VERIFYING,
            progress=0.55,
            tag=self._tag,
            message='正在校验启动器安装包',
        ))
        self.ctx.update_service.validate_staged_launcher('runtime', staging_dir)
        self._check_cancelled()
        return staging_dir

    def _checkout_selected_tag(
        self,
        initial_snapshot: WorkingDirectorySnapshot,
        force: bool,
    ) -> None:
        """检出选定版本；真正写入前再次确认工作区没有变化。"""
        self._checkout_state = _CheckoutCommitState(initial_snapshot)
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.SYNCING_CODE,
            progress=0.6,
            tag=self._tag,
            message=f'正在同步代码 {self._tag}',
        ))
        status, message = self.ctx.git_service.fetch_tag_code(
            self._tag,
            progress_callback=self._on_git_progress,
            force=force,
            before_checkout=self._before_checkout,
        )
        if self._checkout_state.error is not None:
            raise self._checkout_state.error
        if status is GitSyncStatus.LOCAL_CHANGES:
            raise _RecoveryCancelled
        if status not in (GitSyncStatus.SUCCESS, GitSyncStatus.UP_TO_DATE):
            raise RuntimeError(message)
        if not self._commit_started:
            self._check_cancelled()

    def _before_checkout(self) -> bool | None:
        """返回是否强制检出；返回 None 表示取消，异常先暂存给外层抛出。"""
        state = self._checkout_state
        if self._commit_started:
            return state.force
        while True:
            try:
                self._check_cancelled()
                current_snapshot = self._get_workspace_snapshot()
                if current_snapshot != state.snapshot:
                    decision = self._ensure_workspace_confirmation(current_snapshot)
                    if decision is None:
                        return None
                    state.snapshot = current_snapshot
                    continue
                checkout_force = bool(current_snapshot)
            except Exception as error:
                state.error = error
                return None
            with self._state_lock:
                if self._cancel_event.is_set():
                    return None
                state.force = checkout_force
                self._commit_started = True
            self._emit(RecoveryRepairEvent(
                RecoveryRepairStage.COMMITTING,
                progress=0.8,
                tag=self._tag,
                message='正在切换代码版本并替换启动器，请勿关闭',
            ))
            return checkout_force

    def _apply_launcher(self, staging_dir: Path) -> None:
        """用已校验的暂存目录替换当前启动器。"""
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.APPLYING,
            progress=0.9,
            tag=self._tag,
            message='正在替换启动器',
        ))
        self.ctx.update_service.apply_staged_launcher_update(
            'runtime',
            staging_dir,
        )

    def _emit_cancelled(self) -> None:
        """发送已取消事件。"""
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.CANCELLED,
            tag=self._tag,
            message='已取消',
        ))

    def _get_candidate_tags(self) -> list[str]:
        """按通道返回从新到旧的候选标签。"""
        if self._target not in (
            RecoveryRepairChannel.STABLE.value,
            RecoveryRepairChannel.BETA.value,
        ):
            return [self._target]

        tags = self.ctx.git_service.get_version_tags_list()
        stable_tags: list[str] = []
        beta_tags: list[str] = []
        for tag in tags:
            try:
                prerelease = version.parse(tag).is_prerelease
            except version.InvalidVersion:
                continue
            if prerelease:
                beta_tags.append(tag)
            else:
                stable_tags.append(tag)

        if self._target == RecoveryRepairChannel.BETA.value:
            candidates = beta_tags + stable_tags
            channel_name = '测试版'
        else:
            candidates = stable_tags
            channel_name = '正式版'
        if not candidates:
            raise FileNotFoundError(f'没有可用的{channel_name}标签')
        return candidates

    def _select_available_tag(
        self,
        candidates: list[str],
    ) -> tuple[str, dict[str, str]]:
        """顺序检查附件，明确不存在时尝试下一标签。"""
        for tag in candidates:
            self._check_cancelled()
            self._tag = tag
            self._emit(RecoveryRepairEvent(
                RecoveryRepairStage.CHECKING_ASSET,
                progress=0.05,
                tag=tag,
                message=f'正在检查 {tag} 的启动器安装包',
            ))
            try:
                urls = self.ctx.update_service.check_launcher_asset('runtime', tag)
            except FileNotFoundError:
                log.info(f'{tag} 没有集成启动器安装包，尝试下一版本')
                continue
            return tag, urls

        channel_name = (
            '测试版'
            if self._target == RecoveryRepairChannel.BETA.value
            else '正式版'
        )
        raise FileNotFoundError(f'没有可下载的{channel_name}集成启动器安装包')

    def _download(self, param: CommonDownloaderParam) -> None:
        """下载并解压启动器；用户取消时抛出取消异常。"""
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.DOWNLOADING,
            progress=0.1,
            tag=self._tag,
            message='正在下载启动器',
        ))
        env_config = self.ctx.env_config
        downloader = ZipDownloader(param)
        self._progress_signal = {'signal': None}
        success = downloader.download(
            source_order=env_config.get_resource_source_order(),
            proxy_url=env_config.personal_proxy if env_config.is_personal_proxy else None,
            ghproxy_url=env_config.gh_proxy_url if env_config.is_gh_proxy else None,
            skip_if_existed=False,
            progress_signal=self._progress_signal,
            status_callback=self._on_download_progress,
            on_source_success=env_config.mark_resource_source_success,
            on_source_failure=env_config.mark_resource_source_failure,
            fallback_on_slow=env_config.is_resource_source_auto,
        )
        if self._cancel_event.is_set() or self._progress_signal.get('signal') == 'cancel':
            raise _RecoveryCancelled
        if not success:
            raise RuntimeError('启动器下载或解压失败')

    def _get_workspace_snapshot(self) -> WorkingDirectorySnapshot:
        """返回当前工作区快照；无法检查时视为重装失败。"""
        snapshot = self.ctx.git_service.get_uncommitted_changes_snapshot()
        if snapshot is None:
            raise RuntimeError('无法检查代码工作区')
        return snapshot

    def _ensure_workspace_confirmation(
        self,
        snapshot: WorkingDirectorySnapshot,
        preapproved: bool = False,
    ) -> bool | None:
        """确认是否覆盖未提交改动；取消时返回 None。"""
        if not snapshot:
            return False
        if preapproved:
            return True
        self._force_decision = None
        self._force_decision_event.clear()
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.WAITING_FORCE_CONFIRM,
            tag=self._tag,
            message='代码工作区有未提交改动，等待确认',
        ))
        while not self._force_decision_event.wait(0.1):
            if self._cancel_event.is_set():
                raise _RecoveryCancelled
        return True if self._force_decision else None

    def _check_cancelled(self) -> None:
        """已请求取消时中断当前步骤。"""
        if self._cancel_event.is_set():
            raise _RecoveryCancelled

    def _on_download_progress(self, progress: ResourceDownloadProgress) -> None:
        """把下载进度转换成恢复页事件。"""
        if self._cancel_event.is_set():
            return
        stage = RecoveryRepairStage.DOWNLOADING
        if progress.phase == 'extracting':
            stage = RecoveryRepairStage.VERIFYING
        self._emit(RecoveryRepairEvent(
            stage,
            progress=0.1 + progress.progress * 0.4,
            source_id=progress.source_id,
            message=progress.message,
            tag=self._tag,
        ))

    def _on_git_progress(self, progress: float, message: str) -> None:
        """把代码同步进度转换成恢复页事件。"""
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.SYNCING_CODE,
            progress=0.6 + progress * 0.25,
            message=message,
            tag=self._tag,
        ))

    def _emit_failure(self, message: str) -> None:
        """发送失败事件。"""
        self._emit(RecoveryRepairEvent(
            RecoveryRepairStage.FAILED,
            tag=self._tag,
            message=message,
            error=message,
        ))

    def _emit(self, event: RecoveryRepairEvent) -> None:
        """把状态事件交给外部回调。"""
        callback = self._event_callback
        if callback is not None:
            callback(event)


class _RecoveryCancelled(Exception):
    """恢复流程被用户取消。"""
