from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, FluentIconBase

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon_qt.services.download_queue_service import DownloadQueueService
from one_dragon_qt.view.resource_management_interface import (
    ResourceManagementInterface,
)
from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface


class ResourceManagerInterface(PivotNavigatorInterface):
    """资源管理一级界面，包含资源和插件两个二级页面。"""

    def __init__(
        self,
        ctx: OneDragonContext,
        download_queue: DownloadQueueService,
        nav_text_cn: str = '资源管理',
        nav_icon: FluentIconBase | QIcon | str = FluentIcon.SYNC,
        parent: QWidget | None = None,
    ) -> None:
        self.ctx: OneDragonContext = ctx
        self.download_queue: DownloadQueueService = download_queue
        PivotNavigatorInterface.__init__(
            self,
            object_name='resource_manager_interface',
            nav_text_cn=nav_text_cn,
            nav_icon=nav_icon,
            parent=parent,
        )

    def create_sub_interface(self) -> None:
        """创建资源管理下的二级页面。"""
        from zzz_od.gui.view.setting.setting_plugin_interface import (
            SettingPluginInterface,
        )

        self.add_sub_interface(
            ResourceManagementInterface(self.ctx, self.download_queue, parent=self)
        )
        self.add_sub_interface(SettingPluginInterface(self.ctx, parent=self))
