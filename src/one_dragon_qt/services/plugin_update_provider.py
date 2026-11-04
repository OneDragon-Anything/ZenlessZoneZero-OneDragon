from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from one_dragon.base.operation.application.plugin_info import PluginInfo
from one_dragon.base.operation.application.plugin_market import MarketPlugin
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.download_queue_service import ResourceDownloadSpec
from one_dragon_qt.view.plugin.plugin_operation_mixin import PluginOperationMixin

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class PluginUpdateProvider(PluginOperationMixin, QObject):
    """为统一资源更新弹窗提供已订阅插件的更新项。

    复用插件页面的版本判断与安装逻辑，只是没有自己的页面：
    提示框和 InfoBar 都挂在主窗口上。
    """

    def __init__(
        self,
        ctx: OneDragonContext,
        window: QWidget,
        parent: QObject | None = None,
    ) -> None:
        QObject.__init__(self, parent)
        self._window: QWidget = window
        self.init_plugin_operation(ctx)
        self._pending: list[tuple[MarketPlugin, PluginInfo]] = []

    def refresh_cards(self) -> None:
        """没有卡片可刷新。"""

    def set_controls_enabled(self, enabled: bool) -> None:
        """没有控件可切换。"""

    def _as_widget(self) -> QWidget:
        """插件安装结果的界面回调没有自己的页面，统一返回主窗口。"""
        return self._window

    def check_update(self) -> bool:
        """读取插件市场，判断是否有已订阅的插件可更新。在后台线程调用。"""
        if not self.ctx.env_config.plugin_update_notify:
            self._pending = []
            return False
        subscribed = [
            plugin_info
            for plugin_info in self.ctx.factory_manager.third_party_plugins
            if self.is_subscribed(plugin_info)
        ]
        if not subscribed:
            self._pending = []
            return False
        snapshot = self.market_service.load()
        self._market_snapshot = snapshot
        pending: list[tuple[MarketPlugin, PluginInfo]] = []
        for plugin_info in subscribed:
            if self.subscription_config.is_update_muted(
                self.subscription_registry_id(plugin_info)
            ):
                continue
            entry = self.find_market_entry(plugin_info)
            if entry is None or not self.pending_update_version(plugin_info, entry):
                continue
            pending.append((entry, plugin_info))
        self._pending = pending
        return bool(pending)

    def build_specs(self) -> list[ResourceDownloadSpec]:
        """为待更新的插件构造下载规格，正在运行的插件先跳过。"""
        specs: list[ResourceDownloadSpec] = []
        for entry, plugin_info in self._pending:
            package_dir = self.get_plugin_package_dir(plugin_info)
            if package_dir is not None and self.is_plugin_running(package_dir):
                continue
            spec, error = self.build_plugin_spec(
                entry,
                True,
                gt('更新'),
                plugin_info.version or '',
                package_dir,
            )
            if spec is None:
                log.warning(f'插件 {entry.name} 无法更新: {error}')
                continue
            spec.note = gt('第三方插件更新，未经官方审查')
            specs.append(spec)
        return specs
