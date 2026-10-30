"""插件订阅、更新、卸载与详情页的共用能力。

插件管理页与插件商店页面对的是同一批插件和同一份订阅记录，只是展示角度不同：
管理页看本机已安装的，商店页看市场上可安装的。两个页面都需要「订阅 / 更新 /
取消订阅 / 打开详情」，这部分逻辑放在这里，页面本身只管布局与卡片刷新。
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TypeVar

from packaging import version
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

from one_dragon.base.config.plugin_subscription_config import (
    PluginSubscriptionConfig,
    get_plugin_subscription_config,
)
from one_dragon.base.operation.application.plugin_import_service import (
    ImportResult,
    PluginImportService,
)
from one_dragon.base.operation.application.plugin_info import PluginInfo
from one_dragon.base.operation.application.plugin_market import (
    MarketPlugin,
    MarketSnapshot,
    PluginMarketService,
    get_plugin_market_service,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.web.common_downloader import (
    GITHUB_SOURCE_ID,
    CommonDownloader,
    CommonDownloaderParam,
)
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.download_queue_service import (
    DownloadQueueService,
    ResourceDownloadSpec,
    ResourceDownloadTaskState,
)
from one_dragon_qt.services.plugin_cover_service import (
    PluginCoverService,
    get_plugin_cover_service,
)
from one_dragon_qt.view.plugin.plugin_detail_dialog import (
    ACTION_IGNORE,
    ACTION_SUBSCRIBE,
    ACTION_UNINSTALL,
    ACTION_UNSUBSCRIBE,
    ACTION_UPDATE,
    PluginDetailData,
    PluginDetailDialog,
)
from one_dragon_qt.widgets.plugin_card import (
    BADGE_INSTALLED,
    BADGE_NONE,
    BADGE_SUBSCRIBED,
    BADGE_UPDATE,
    CARD_HEIGHT,
    CARD_WIDTH,
    PluginCard,
    PluginCardGrid,
    PluginPager,
)

_T = TypeVar("_T")

_active_runner: PluginImportRunner | None = None
"""当前正在执行的插件写任务。

导入、订阅、更新、取消订阅都会改动 plugins 目录，两个插件页面共用同一个占位，
避免两个页面同时操作同一个插件目录。
"""

_active_runner_lock: threading.Lock = threading.Lock()
_plugin_write_lock: threading.Lock = threading.Lock()
"""导入、更新、卸载共用的写锁。下载队列安装插件时也要拿到它。"""


def _claim_task_slot(runner: PluginImportRunner) -> bool:
    """占用插件写操作的唯一名额，已被占用时返回 False。"""
    global _active_runner
    if not _plugin_write_lock.acquire(blocking=False):
        return False
    with _active_runner_lock:
        if _active_runner is not None:
            _plugin_write_lock.release()
            return False
        _active_runner = runner
        return True


def _release_task_slot(runner: PluginImportRunner) -> None:
    """释放插件写操作名额。"""
    global _active_runner
    released = False
    with _active_runner_lock:
        if _active_runner is runner:
            _active_runner = None
            released = True
    if released:
        _plugin_write_lock.release()


class PluginImportRunner(QThread):
    """在后台线程执行插件导入或卸载任务。"""

    task_finished = Signal(object)
    task_failed = Signal(str)

    def __init__(
        self,
        task: Callable[[], object],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._task: Callable[[], object] = task

    def run(self) -> None:
        """执行任务并把结果或异常发回界面线程。"""
        try:
            result = self._task()
        except Exception as e:
            log.error(f"插件操作异常: {e}", exc_info=True)
            self.task_failed.emit(str(e))
            return
        self.task_finished.emit(result)


class MarketLoadRunner(QObject):
    """在后台守护线程读取插件市场数据。

    用 Python 守护线程而不是 QThread：网络卡住时程序退出不必等它结束，
    线程随进程一起退出；QThread 在运行中被销毁会让 Qt 直接中止进程。
    """

    load_finished = Signal(object)

    def __init__(
        self,
        service: PluginMarketService,
        force: bool,
    ) -> None:
        super().__init__()
        self._service: PluginMarketService = service
        self._force: bool = force
        self._thread: threading.Thread = threading.Thread(
            target=self._run,
            name='plugin-market-load',
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def is_running(self) -> bool:
        return self._thread.is_alive()

    def wait(self, timeout_seconds: float) -> None:
        self._thread.join(timeout_seconds)

    def _run(self) -> None:
        self.load_finished.emit(self._service.load(force=self._force))


class PluginOperationMixin:
    """插件页面共用的订阅与详情逻辑。

    子类需要实现 `refresh_cards()` 与 `set_controls_enabled(enabled)`，
    并调用 `init_plugin_operation()` 完成初始化。
    """

    ctx: OneDragonContext
    plugin_import_service: PluginImportService
    market_service: PluginMarketService
    subscription_config: PluginSubscriptionConfig
    cover_service: PluginCoverService

    def init_plugin_operation(
        self,
        ctx: OneDragonContext,
    ) -> None:
        """初始化共用状态，由页面构造函数调用。"""
        self.ctx = ctx
        self.plugin_import_service = PluginImportService(ctx)
        self.market_service = get_plugin_market_service()
        self.subscription_config = get_plugin_subscription_config()
        self.cover_service = get_plugin_cover_service()
        self._cards_by_key: dict[str, PluginCard] = {}
        self._cover_urls: dict[str, str] = {}
        self._market_snapshot: MarketSnapshot | None = None
        self._market_runner: MarketLoadRunner | None = None
        self._import_busy: bool = False

    # ------------------------------------------------------------------
    # 由子类实现
    # ------------------------------------------------------------------

    def refresh_cards(self) -> None:
        """重新生成页面卡片。"""
        raise NotImplementedError

    def set_controls_enabled(self, enabled: bool) -> None:
        """操作进行中时禁用页面上的按钮。"""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 市场数据
    # ------------------------------------------------------------------

    def load_market(self, force: bool = False) -> None:
        """读取市场数据，结果通过 market_loaded 回调交给页面。"""
        if self._market_runner is not None and self._market_runner.is_running():
            return
        if force:
            # 手动刷新时给之前下载失败的封面一次重试机会
            self.cover_service.clear_failed()
        self.on_market_loading()
        runner = MarketLoadRunner(self.market_service, force)
        # 信号在后台线程发出，显式排队回到 GUI 线程
        runner.load_finished.connect(
            self._on_market_loaded,
            Qt.ConnectionType.QueuedConnection,
        )
        runner.load_finished.connect(
            lambda _snapshot: self._cleanup_market_runner(runner),
            Qt.ConnectionType.QueuedConnection,
        )
        self._market_runner = runner
        runner.start()

    def on_market_loading(self) -> None:
        """市场数据开始读取，页面可更新提示文案。"""

    def on_market_loaded(self, snapshot: MarketSnapshot) -> None:
        """市场数据读取完成，页面可刷新卡片。"""

    def _on_market_loaded(self, snapshot: MarketSnapshot) -> None:
        self._market_snapshot = snapshot
        self.on_market_loaded(snapshot)
        self.refresh_cards()

    def _cleanup_market_runner(self, runner: MarketLoadRunner) -> None:
        if self._market_runner is runner:
            self._market_runner = None

    def wait_for_market_load(self) -> None:
        """等待市场线程结束，让读取结果有机会在界面关闭前处理完。

        最多等 MARKET_WAIT_SECONDS 秒：下载卡住时也要能退出程序。市场线程是
        守护线程，超时后放着不管，会随进程一起结束。
        """
        runner = self._market_runner
        if runner is None or not runner.is_running():
            return
        deadline = time.monotonic() + self.MARKET_WAIT_SECONDS
        while runner.is_running() and time.monotonic() < deadline:
            runner.wait(0.05)
            QApplication.processEvents()

    @property
    def market_snapshot(self) -> MarketSnapshot | None:
        return self._market_snapshot

    def _as_widget(self) -> QWidget:
        return self  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # 市场匹配与版本判断
    # ------------------------------------------------------------------

    def installed_market_map(self) -> dict[str, PluginInfo]:
        """市场条目 id → 已安装插件。"""
        result: dict[str, PluginInfo] = {}
        for plugin_info in self.ctx.factory_manager.third_party_plugins:
            entry = self.find_market_entry(plugin_info)
            if entry is not None:
                result[entry.plugin_id] = plugin_info
        return result

    def is_subscribed(self, plugin_info: PluginInfo) -> bool:
        """是否从网页源订阅。

        订阅记录只在商店安装或更新成功后写入。没有记录，或记录来源是本地，
        都只算安装。旧记录没有 source 字段，当时只有商店安装会写记录，按订阅处理。
        """
        package_dir = self.get_plugin_package_dir(plugin_info)
        dir_name = package_dir.name if package_dir is not None else ''
        registry_id = self.subscription_config.find_registry_id(plugin_info.app_id, dir_name)
        if not registry_id:
            return False
        record = self.subscription_config.get_record(registry_id)
        if record is None:
            return False
        return str(record.get('source') or 'market') == 'market'

    def find_market_entry(self, plugin_info: PluginInfo) -> MarketPlugin | None:
        """查找某个已安装插件对应的市场条目。"""
        snapshot = self._market_snapshot
        if snapshot is None:
            return None

        package_dir = self.get_plugin_package_dir(plugin_info)
        dir_name = package_dir.name if package_dir is not None else ''
        registry_id = self.subscription_config.find_registry_id(plugin_info.app_id, dir_name)
        if registry_id:
            found = snapshot.get(registry_id)
            if found is not None:
                return found

        homepage = (plugin_info.homepage or '').strip().rstrip('/').casefold()
        if not homepage:
            return None
        for entry in snapshot.plugins:
            repo = (entry.repo or '').strip().rstrip('/').casefold()
            if repo and repo == homepage:
                return entry
        return None

    def pending_update_version(
        self,
        plugin_info: PluginInfo,
        entry: MarketPlugin | None,
    ) -> str:
        """返回可更新到的版本号，无需更新时返回空字符串。"""
        if entry is None or not entry.latest_version:
            return ''
        installed = plugin_info.version or ''
        if not installed:
            return ''
        if not self._is_newer(entry.latest_version, installed):
            return ''
        ignored = str(
            (self.subscription_config.get_record(entry.plugin_id) or {}).get('ignored_version') or ''
        )
        if ignored and ignored == entry.latest_version:
            return ''
        return entry.latest_version

    @staticmethod
    def _is_newer(new_ver: str | None, old_ver: str | None) -> bool:
        """新版本是否高于旧版本。"""
        if not new_ver or not old_ver:
            return False
        try:
            return version.parse(new_ver) > version.parse(old_ver)
        except version.InvalidVersion:
            return False

    @staticmethod
    def initial_of(text: str) -> str:
        value = (text or '').strip()
        return value[0].upper() if value else '?'

    # ------------------------------------------------------------------
    # 详情页
    # ------------------------------------------------------------------

    def open_market_detail(self, entry: MarketPlugin) -> None:
        """打开市场条目的详情页。"""
        plugin_info = self.installed_market_map().get(entry.plugin_id)
        actions: list[tuple[str, str]] = []
        status_text = ''
        status_kind = ''
        subscribed = plugin_info is not None and self.is_subscribed(plugin_info)
        if subscribed and plugin_info is not None:
            update_version = self.pending_update_version(plugin_info, entry)
            status_text = gt('已订阅 · v{version}').format(version=plugin_info.version or '-')
            status_kind = BADGE_SUBSCRIBED
            if update_version:
                status_kind = BADGE_UPDATE
                status_text += gt('，可更新到 v{version}').format(version=update_version)
                actions.append((ACTION_UPDATE, gt('更新到 v{version}').format(version=update_version)))
                actions.append((ACTION_IGNORE, gt('跳过此版本')))
            actions.append((ACTION_UNSUBSCRIBE, gt('取消订阅')))
        elif plugin_info is not None:
            status_text = gt('已安装 · 未从商店订阅')
            status_kind = BADGE_INSTALLED
            actions.append((ACTION_UNINSTALL, gt('卸载')))
        else:
            actions.append((ACTION_SUBSCRIBE, gt('订阅')))

        meta_parts = []
        if entry.latest_version:
            meta_parts.append(f'v{entry.latest_version}')
        if entry.author_name:
            meta_parts.append(entry.author_name)

        data = PluginDetailData(
            title=entry.name,
            initial=entry.initial,
            meta_text=' · '.join(meta_parts),
            tags=entry.tags,
            summary=entry.summary,
            readme_html=entry.readme_html,
            changelog_html=entry.latest.changelog_html if entry.latest is not None else '',
            changelog_version=entry.latest_version,
            status_text=status_text,
            status_kind=status_kind,
            warning_text=(
                gt('插件仓库长期无法访问，可能已停止维护') if entry.stale else ''
            ),
            homepage=entry.repo,
            actions=actions,
        )
        self._show_detail(data, partial(self._on_detail_action, entry, plugin_info))

    def open_installed_detail(self, plugin_info: PluginInfo) -> None:
        """打开本机已安装插件的详情页。"""
        entry = self.find_market_entry(plugin_info)
        actions: list[tuple[str, str]] = []
        subscribed = self.is_subscribed(plugin_info)
        if subscribed:
            status_text = gt('已订阅')
            status_kind = BADGE_SUBSCRIBED
            update_version = self.pending_update_version(plugin_info, entry)
            if entry is not None and update_version:
                status_kind = BADGE_UPDATE
                status_text += gt('，可更新到 v{version}').format(version=update_version)
                actions.append((ACTION_UPDATE, gt('更新到 v{version}').format(version=update_version)))
                actions.append((ACTION_IGNORE, gt('跳过此版本')))
            actions.append((ACTION_UNSUBSCRIBE, gt('取消订阅')))
            if entry is None:
                status_text = gt('已订阅 · 商店暂无此插件')
        else:
            status_text = (
                gt('已安装 · 本地插件')
                if entry is None else gt('已安装 · 未从商店订阅')
            )
            status_kind = BADGE_INSTALLED
            actions.append((ACTION_UNINSTALL, gt('卸载')))

        meta_parts = []
        if plugin_info.version:
            meta_parts.append(f'v{plugin_info.version}')
        if plugin_info.author:
            meta_parts.append(plugin_info.author)

        data = PluginDetailData(
            title=plugin_info.app_name,
            initial=self.initial_of(plugin_info.app_name),
            meta_text=' · '.join(meta_parts),
            tags=[],
            summary=plugin_info.description,
            readme_html=entry.readme_html if entry is not None else '',
            changelog_html=(
                entry.latest.changelog_html
                if entry is not None and entry.latest is not None else ''
            ),
            changelog_version=entry.latest_version if entry is not None else '',
            status_text=status_text,
            status_kind=status_kind,
            homepage=plugin_info.homepage,
            actions=actions,
        )
        self._show_detail(data, partial(self._on_detail_action, entry, plugin_info))

    def _show_detail(
        self,
        data: PluginDetailData,
        action_handler: Callable[[str], None],
    ) -> None:
        """以弹窗形式展示插件详情。"""
        detail = PluginDetailDialog(data, parent=self._as_widget().window())
        detail.action_triggered.connect(action_handler)
        detail.exec()

    def _on_detail_action(
        self,
        entry: MarketPlugin | None,
        plugin_info: PluginInfo | None,
        action: str,
    ) -> None:
        if action == ACTION_SUBSCRIBE and entry is not None:
            self.subscribe(entry)
        elif action in (ACTION_UNSUBSCRIBE, ACTION_UNINSTALL) and plugin_info is not None:
            self.unsubscribe(
                plugin_info,
                entry.plugin_id if entry is not None else None,
                subscribed=action == ACTION_UNSUBSCRIBE,
            )
        elif action == ACTION_UPDATE and entry is not None and plugin_info is not None:
            self.update_plugin(entry, plugin_info)
        elif action == ACTION_IGNORE and entry is not None:
            self._ignore_version(entry, plugin_info)
            self.refresh_cards()
            InfoBar.success(
                title=gt('已跳过'),
                content=gt('已跳过版本 v{version}').format(version=entry.latest_version),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2500,
                parent=self._as_widget(),
            )
        # 弹窗在动作发出时已经关闭，这里不再操作界面

    # ------------------------------------------------------------------
    # 订阅 / 更新 / 取消订阅
    # ------------------------------------------------------------------

    def subscribe(self, entry: MarketPlugin) -> None:
        """订阅一个市场条目：把插件包放进统一下载队列，下完再安装。"""
        self._enqueue_plugin_download(
            entry,
            overwrite=False,
            action_name=gt('订阅'),
            current_version='',
        )

    def update_plugin(self, entry: MarketPlugin, plugin_info: PluginInfo) -> None:
        """把已安装插件更新到市场最新版本，下载走统一队列。"""
        action_name = gt('更新')
        package_dir = self.get_plugin_package_dir(plugin_info)
        if package_dir is not None and self.is_plugin_running(package_dir):
            self._show_error(
                gt('无法{action}').format(action=action_name),
                gt('插件正在运行，请先停止后再{action}').format(action=action_name),
            )
            return
        self._enqueue_plugin_download(
            entry,
            overwrite=True,
            action_name=action_name,
            current_version=plugin_info.version or '',
            package_dir=package_dir,
        )

    def _enqueue_plugin_download(
        self,
        entry: MarketPlugin,
        overwrite: bool,
        action_name: str,
        current_version: str,
        package_dir: Path | None = None,
    ) -> None:
        """把插件包加入下载队列。已在队列中的同一版本不重复添加。

        Args:
            entry: 市场条目。
            overwrite: 是否覆盖已安装的同名插件。
            action_name: 操作名称，用于提示文案。
            current_version: 当前已安装的版本号，未安装时为空。
            package_dir: 被覆盖的插件目录，安装前用它确认插件没有在运行。
        """
        if self._import_busy:
            return
        release = entry.latest
        if release is None or not release.download_url:
            self._show_error(
                gt('无法{action}').format(action=action_name),
                gt('该插件没有可下载的版本'),
            )
            return
        if not release.sha256:
            self._show_error(
                gt('无法{action}').format(action=action_name),
                gt('该插件没有提供校验值，无法确认安装包未被篡改'),
            )
            return

        queue = self._download_queue()
        if queue is None:
            self._show_error(gt('无法{action}').format(action=action_name), gt('下载队列不可用'))
            return

        archive_name = self._plugin_archive_name(entry)
        save_dir = os_utils.get_path_under_work_dir('config', 'temp', 'plugin_downloads')
        source_id = self._plugin_download_source(release.download_url)
        spec = ResourceDownloadSpec(
            resource_id=f'plugin:{entry.plugin_id}',
            resource_type='plugin',
            title=entry.name,
            current_version=current_version,
            target_version=entry.latest_version or archive_name,
            downloader_factory=lambda: CommonDownloader(
                CommonDownloaderParam(
                    save_file_path=save_dir,
                    save_file_name=archive_name,
                    download_urls={source_id: release.download_url},
                )
            ),
            source_order=[source_id],
            note=action_name,
            after_download=lambda success: self._install_queued_plugin(
                entry,
                overwrite,
                action_name,
                Path(save_dir) / archive_name,
                success,
                package_dir,
            ),
        )
        active_states = {
            ResourceDownloadTaskState.WAITING,
            ResourceDownloadTaskState.DOWNLOADING,
            ResourceDownloadTaskState.EXTRACTING,
            ResourceDownloadTaskState.APPLYING,
            ResourceDownloadTaskState.CANCELLING,
        }
        existing = queue.get_task(spec.task_key)
        if existing is not None and existing.state in active_states:
            self._show_download_queued_tip(entry.name)
            return
        if existing is not None:
            queue.remove(existing.task_key)
        queue.enqueue(spec)
        self._show_download_queued_tip(entry.name)

    def _download_queue(self) -> DownloadQueueService | None:
        """主窗口上的统一下载队列。"""
        window = self._as_widget().window()
        queue = getattr(window, 'download_queue', None)
        if isinstance(queue, DownloadQueueService):
            return queue
        return None

    def _show_download_queued_tip(self, title: str) -> None:
        """提示用户到标题栏的下载队列看进度。"""
        window = self._as_widget().window()
        show_tip = getattr(window, 'show_download_queue_added_tip', None)
        if callable(show_tip):
            show_tip(title)

    @staticmethod
    def _plugin_download_source(download_url: str) -> str:
        """GitHub 地址走统一源的代理规则，其他地址按直链下载。"""
        lowered = download_url.casefold()
        if 'github.com/' in lowered or 'githubusercontent.com' in lowered:
            return GITHUB_SOURCE_ID
        return 'direct'

    @staticmethod
    def _plugin_archive_name(entry: MarketPlugin) -> str:
        """插件包在临时目录中的文件名。"""
        raw = f'{entry.plugin_id}-{entry.latest_version or "latest"}.zip'
        return ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in raw)

    def _install_queued_plugin(
        self,
        entry: MarketPlugin,
        overwrite: bool,
        action_name: str,
        archive: Path,
        success: bool,
        package_dir: Path | None = None,
    ) -> None:
        """下载队列完成后校验并安装。此方法在下载线程中调用。

        Args:
            entry: 市场条目。
            overwrite: 是否覆盖已安装的同名插件。
            action_name: 操作名称，用于提示文案。
            archive: 下载好的插件包。
            success: 下载是否成功。
            package_dir: 被覆盖的插件目录，安装前用它确认插件没有在运行。
        """
        if not success:
            archive.unlink(missing_ok=True)
            return
        try:
            if not archive.is_file() or archive.stat().st_size == 0:
                raise RuntimeError('下载插件包失败')
            release = entry.latest
            # 插件代码会被直接加载运行，没有校验值时不安装
            if release is None or not release.sha256:
                raise RuntimeError('插件包缺少校验值，无法确认未被篡改')
            digest = self._sha256_of(archive)
            if digest.casefold() != release.sha256.casefold():
                raise RuntimeError('插件包校验失败，文件可能已损坏')
            if not _plugin_write_lock.acquire(timeout=120):
                raise RuntimeError('有插件操作正在进行，请稍后再试')
            try:
                # 下载期间插件可能已被启动，覆盖前在写锁内再确认一次
                if package_dir is not None and self.is_plugin_running(package_dir):
                    raise RuntimeError(f'插件正在运行，请先停止后再{action_name}')
                result = self.plugin_import_service.import_plugin(archive, overwrite=overwrite)
            finally:
                _plugin_write_lock.release()
            if not result.success:
                raise RuntimeError(result.message or '导入插件失败')
        finally:
            archive.unlink(missing_ok=True)

        widget = self._as_widget()
        QTimer.singleShot(
            0,
            widget,
            lambda imported=result: self._handle_subscription_results(
                [imported],
                entry,
                action_name,
            ),
        )

    @staticmethod
    def _sha256_of(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def _handle_subscription_results(
        self,
        results: list[ImportResult],
        entry: MarketPlugin,
        action_name: str,
    ) -> None:
        success_results = [result for result in results if result.success]
        if not success_results:
            messages = [result.message for result in results if result.message]
            self._show_error(
                gt('{action}失败').format(action=action_name),
                '\n'.join(messages) or gt('未知错误'),
            )
            return

        self.ctx.refresh_application_registration()
        for result in success_results:
            package_dir = self._find_package_dir_of_result(result)
            app_id = self._find_app_id_by_package(package_dir)
            self.subscription_config.upsert_record(
                registry_id=entry.plugin_id,
                app_id=app_id,
                plugin_dir_name=package_dir.name if package_dir is not None else '',
                installed_version=result.new_version or entry.latest_version,
            )

        self.refresh_cards()
        InfoBar.success(
            title=gt('{action}成功').format(action=action_name),
            content=gt('{name} 已{action}').format(name=entry.name, action=action_name),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self._as_widget(),
        )

    def _find_package_dir_of_result(self, result: ImportResult) -> Path | None:
        if result.plugin_dir is None:
            return None
        plugins_root = self.plugin_import_service.plugins_dir.resolve(strict=False)
        plugin_dir = result.plugin_dir.resolve(strict=False)
        if not plugin_dir.is_relative_to(plugins_root) or plugin_dir == plugins_root:
            return None
        return plugins_root / plugin_dir.relative_to(plugins_root).parts[0]

    def _find_app_id_by_package(self, package_dir: Path | None) -> str:
        if package_dir is None:
            return ''
        for plugin_info in self.ctx.factory_manager.third_party_plugins:
            current = self.get_plugin_package_dir(plugin_info)
            if current is not None and current.resolve(strict=False) == package_dir.resolve(strict=False):
                return plugin_info.app_id
        return ''

    def unsubscribe(
        self,
        plugin_info: PluginInfo,
        registry_id: str | None = None,
        subscribed: bool | None = None,
    ) -> None:
        """删除插件目录。订阅来的插件文案用取消订阅，本地安装用卸载。"""
        if self._import_busy:
            return

        if subscribed is None:
            subscribed = self.is_subscribed(plugin_info)
        title = gt('取消订阅') if subscribed else gt('卸载')
        message = (
            gt('确定要取消订阅 "{name}" 吗？插件文件会被删除。')
            if subscribed else gt('确定要卸载 "{name}" 吗？插件文件会被删除。')
        )
        msg_box = MessageBox(title, message.format(name=plugin_info.app_name), self._as_widget().window())
        msg_box.yesButton.setText(title)
        msg_box.cancelButton.setText(gt('保留'))

        if not msg_box.exec():
            return

        failure_title = gt('取消失败') if subscribed else gt('卸载失败')
        plugin_package_dir = self.get_plugin_package_dir(plugin_info)
        if plugin_package_dir is None:
            self._show_error(
                failure_title,
                gt('无法定位插件目录，只能删除 plugins 目录下的插件'),
            )
            return

        if self.is_plugin_running(plugin_package_dir):
            self._show_error(
                failure_title,
                gt('插件正在运行，请先停止后再{action}').format(action=title),
            )
            return

        self._start_plugin_task(
            lambda: self.plugin_import_service.delete_plugin(plugin_package_dir),
            partial(self._finish_unsubscribe, plugin_info, registry_id, subscribed),
        )

    def _finish_unsubscribe(
        self,
        plugin_info: PluginInfo,
        registry_id: str | None,
        subscribed: bool,
        result: ImportResult,
    ) -> None:
        self._finish_plugin_task()
        if not result.success:
            self._show_error(
                gt('取消失败') if subscribed else gt('卸载失败'),
                result.message,
            )
            return

        if registry_id:
            self.subscription_config.remove_record(registry_id)
        else:
            package_dir = self.get_plugin_package_dir(plugin_info)
            dir_name = package_dir.name if package_dir is not None else ''
            found = self.subscription_config.find_registry_id(plugin_info.app_id, dir_name)
            if found:
                self.subscription_config.remove_record(found)

        self.ctx.refresh_application_registration()
        self.refresh_cards()
        InfoBar.success(
            title=gt('已取消订阅') if subscribed else gt('已卸载'),
            content=gt('{name} 已移除').format(name=plugin_info.app_name),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self._as_widget(),
        )

    # ------------------------------------------------------------------
    # 后台任务
    # ------------------------------------------------------------------

    def _start_plugin_task(
        self,
        task: Callable[[], _T],
        on_finished: Callable[[_T], None],
    ) -> None:
        """在后台线程执行一次插件操作。

        入口处的忙碌检查由各操作自己负责；这里只保证全局同时只有一个写任务，
        因为任务链（预览完接着导入）需要在 busy 尚未复位的回调里直接续跑。
        """
        runner = PluginImportRunner(task, self._as_widget())
        if not _claim_task_slot(runner):
            runner.deleteLater()
            # 任务链的后续段走到这里时 busy 还是上一段留下的 True，必须复位，
            # 否则页面按钮会一直禁用
            self._finish_plugin_task()
            self._show_error(
                gt('有插件操作正在进行'),
                gt('请等上一个插件操作完成后再试'),
            )
            return

        # 结果回调先释放占位，再交给业务处理：业务处理里可能马上要启动下一段任务
        runner.task_finished.connect(
            lambda result: self._on_plugin_task_finished(runner, result, on_finished)
        )
        runner.task_failed.connect(
            lambda message: self._on_plugin_task_failed(runner, message)
        )
        runner.finished.connect(runner.deleteLater)
        self._set_plugin_busy(True)
        runner.start()

    def _ignore_version(self, entry: MarketPlugin, plugin_info: PluginInfo | None) -> None:
        """忽略某个市场版本。

        没有订阅记录时先补一条：手动放进 plugins 目录或早版本安装的插件也可能
        没有记录，否则写忽略版本会静默失败，界面却提示已跳过。
        """
        if self.subscription_config.get_record(entry.plugin_id) is None and plugin_info is not None:
            package_dir = self.get_plugin_package_dir(plugin_info)
            self.subscription_config.upsert_record(
                registry_id=entry.plugin_id,
                app_id=plugin_info.app_id,
                plugin_dir_name=package_dir.name if package_dir is not None else '',
                installed_version=plugin_info.version or '',
                source='local',
            )
        self.subscription_config.set_ignored_version(entry.plugin_id, entry.latest_version)

    def _release_plugin_runner(self, runner: PluginImportRunner) -> None:
        """释放任务占位，允许紧接着启动下一段任务。"""
        _release_task_slot(runner)

    def _on_plugin_task_finished(
        self,
        runner: PluginImportRunner,
        result: _T,
        on_finished: Callable[[_T], None],
    ) -> None:
        self._release_plugin_runner(runner)
        on_finished(result)

    def _wait_for_plugin_task(self) -> None:
        """等待当前插件任务结束，避免界面销毁时线程仍在运行。"""
        runner = _active_runner
        if runner is None or not runner.isRunning():
            return

        while runner.isRunning():
            runner.wait(50)
            QApplication.processEvents()

    def _on_plugin_task_failed(self, runner: PluginImportRunner, message: str) -> None:
        self._release_plugin_runner(runner)
        self._finish_plugin_task()
        self._show_error(gt('操作失败'), message)

    def _set_plugin_busy(self, busy: bool) -> None:
        self._import_busy = busy
        self.set_controls_enabled(not busy)

    def _finish_plugin_task(self) -> None:
        self._set_plugin_busy(False)

    def close_plugin_operation(self) -> None:
        """界面关闭前收尾，等后台线程结束。"""
        self._wait_for_plugin_task()
        self.wait_for_market_load()

    # ------------------------------------------------------------------
    # 公共工具
    # ------------------------------------------------------------------

    def get_plugin_package_dir(self, plugin_info: PluginInfo) -> Path | None:
        """获取插件所属的顶层插件目录。"""
        if plugin_info.plugin_dir is None:
            return None

        plugins_root = self.plugin_import_service.plugins_dir.resolve(strict=False)
        plugin_dir = plugin_info.plugin_dir.resolve(strict=False)
        if plugin_dir == plugins_root or not plugin_dir.is_relative_to(plugins_root):
            return None

        relative_path = plugin_dir.relative_to(plugins_root)
        return plugins_root / relative_path.parts[0]

    def is_plugin_running(self, plugin_package_dir: Path) -> bool:
        """判断插件包中是否有应用正在运行。"""
        run_context = self.ctx.run_context
        # 停止请求会先把状态改为 STOP，但应用线程退出前 current_app_id 仍有效。
        if run_context.current_app_id is None:
            return False

        current_plugin = self.ctx.factory_manager.get_plugin_info(
            run_context.current_app_id
        )
        if current_plugin is None or not current_plugin.is_third_party:
            return False

        current_package_dir = self.get_plugin_package_dir(current_plugin)
        if current_package_dir is None:
            return False
        return current_package_dir.resolve(strict=False) == plugin_package_dir.resolve(
            strict=False
        )

    def _show_error(self, title: str, content: str) -> None:
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self._as_widget(),
        )

    @staticmethod
    def make_card(
        title: str,
        meta_text: str,
        seed: str,
        cover: QPixmap | None = None,
        badge_text: str = '',
        badge_kind: str = BADGE_NONE,
        on_click: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> PluginCard:
        """统一创建卡片，避免两个页面各写一份参数。"""
        card = PluginCard(
            title=title,
            meta_text=meta_text,
            seed=seed,
            badge_text=badge_text,
            badge_kind=badge_kind,
            cover=cover,
            on_click=on_click,
            parent=parent,
        )
        card.key = seed
        return card

    def cover_for(
        self,
        plugin_id: str,
        cover_url: str,
        plugin_info: PluginInfo | None = None,
    ) -> QPixmap | None:
        """取插件封面。

        已安装插件优先用包里自带的图；没有再退到市场发布的封面地址。
        两者都没有时返回 None，界面用默认封面顶上。

        Args:
            plugin_id: 市场条目标识。
            cover_url: 市场条目里的封面地址。
            plugin_info: 已安装插件的元数据，可为空。

        Returns:
            封面位图；不可用时返回 None。
        """
        if plugin_info is not None:
            pixmap = self.cover_service.installed_cover(plugin_info)
            if pixmap is not None:
                return pixmap
        return self.cover_service.market_cover(plugin_id, cover_url)

    def connect_cover_signal(self) -> None:
        """在界面基类初始化完成后连接封面信号。

        连接必须在 QWidget 初始化之后进行，并固定为 QueuedConnection：
        封面下载在后台线程完成，回调要回到 GUI 线程改控件。
        """
        self.cover_service.cover_ready.connect(
            self._on_cover_ready,
            Qt.ConnectionType.QueuedConnection,
        )

    def _on_cover_ready(self, plugin_id: str) -> None:
        self.on_cover_ready(plugin_id)

    def on_cover_ready(self, plugin_id: str) -> None:
        """某张远程封面下载完成，把卡片上的默认封面换成真图。"""
        card = self._cards_by_key.get(plugin_id)
        if card is None:
            return
        pixmap = self.cover_service.market_cover(
            plugin_id, self._cover_urls.get(plugin_id, '')
        )
        if pixmap is not None:
            card.set_cover(pixmap)

    def reset_card_registry(self) -> None:
        """卡片重建前清空卡片与封面回填用的索引。"""
        self._cards_by_key.clear()
        self._cover_urls.clear()
        self._all_cards = []
        self._filtered_cards = []

    def remember_card(self, card: PluginCard, plugin_id: str, cover_url: str = '') -> None:
        """登记卡片与封面地址，供远程封面下载完成后回填。"""
        self._cards_by_key[plugin_id] = card
        if cover_url:
            self._cover_urls[plugin_id] = cover_url

    # ------------------------------------------------------------------
    # 分页
    # ------------------------------------------------------------------

    PAGE_ROWS = 3
    """每页显示几行卡片，列数由可用宽度决定。"""

    CARD_SPACING = 12
    """卡片之间的间距，与 PluginCardGrid 保持一致。"""

    MARKET_WAIT_SECONDS = 10.0
    """关闭界面时等待市场线程的上限，超时后不再阻塞退出。"""

    def init_paging(self, grid: PluginCardGrid, pager: PluginPager) -> None:
        """接管卡片网格的分页。"""
        self._card_grid: PluginCardGrid = grid
        self._pager: PluginPager = pager
        self._all_cards: list[PluginCard] = []
        self._filtered_cards: list[PluginCard] = []
        self._fixed_cards: list[PluginCard] = []
        self._keyword: str = ''
        self._page_index: int = 0
        self._page_size: int = self.PAGE_ROWS
        pager.page_changed.connect(self._on_page_index_changed)
        grid.resized.connect(self._on_grid_resized)

    def _on_grid_resized(self) -> None:
        """网格宽度变化后按新宽度重算每页数量。"""
        if self._calc_page_size() != self._page_size:
            self.update_paging()

    def set_cards(self, cards: list[PluginCard]) -> None:
        """用一批新卡片替换当前列表，保留当前搜索词。"""
        self._all_cards = list(cards)
        self._page_index = 0
        self.set_card_filter(self._keyword)

    def set_fixed_cards(self, cards: list[PluginCard]) -> None:
        """设置不参与分页的固定卡片，例如单独一行展示的推荐插件。"""
        self._fixed_cards = list(cards)
        self._apply_fixed_visibility()

    def _apply_fixed_visibility(self) -> None:
        """按当前搜索词控制固定卡片的可见性。"""
        text = self._keyword.casefold()
        for card in self._fixed_cards:
            card.setVisible(not text or text in card.title.casefold())

    def set_card_filter(self, keyword: str) -> None:
        """按关键字过滤卡片并回到第一页。"""
        self._keyword = (keyword or '').strip()
        text = self._keyword.casefold()
        if not text:
            self._filtered_cards = list(self._all_cards)
        else:
            self._filtered_cards = [
                card for card in self._all_cards if text in card.title.casefold()
            ]
        self._page_index = 0
        self._apply_fixed_visibility()
        self.update_paging()

    def update_paging(self) -> None:
        """按当前可用宽度重算每页数量并刷新显示。"""
        if not hasattr(self, '_pager'):
            return

        self._page_size = self._calc_page_size()
        page_count = max(1, (len(self._filtered_cards) + self._page_size - 1) // self._page_size)
        self._page_index = max(0, min(self._page_index, page_count - 1))

        self._pager.set_page_count(page_count)
        self._pager.set_current_page(self._page_index)

        start = self._page_index * self._page_size
        self._card_grid.apply_visible(self._filtered_cards[start:start + self._page_size])

    def _calc_page_size(self) -> int:
        """按网格宽度算出一页能放几张卡片。"""
        width = self._card_grid.width()
        if width <= 0:
            width = self._as_widget().width()
        step = CARD_WIDTH + self.CARD_SPACING
        columns = max(1, (width + self.CARD_SPACING) // step)
        rows = max(1, self._as_widget().height() // (CARD_HEIGHT + self.CARD_SPACING))
        return columns * min(self.PAGE_ROWS, rows)

    def _on_page_index_changed(self, index: int) -> None:
        self._page_index = max(0, index)
        self.update_paging()
