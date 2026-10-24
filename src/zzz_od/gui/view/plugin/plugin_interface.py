"""插件一级界面。

包含两个二级页面：插件管理（本机已安装的插件）与插件商店（市场上可订阅的
插件）。两个页面共用一套订阅与详情逻辑，见 `plugin_operation_mixin`。
"""

from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext


class PluginInterface(PivotNavigatorInterface):
    """插件一级界面，包含插件管理与插件商店两个二级页面。"""

    def __init__(self, ctx: ZContext, parent=None) -> None:
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(
            self,
            object_name='plugin_interface',
            nav_text_cn='插件',
            nav_icon=FluentIcon.ZIP_FOLDER,
            parent=parent,
        )

    def create_sub_interface(self) -> None:
        """创建插件管理页与插件商店页。"""
        from zzz_od.gui.view.plugin.plugin_manage_interface import (
            PluginManageInterface,
        )
        from zzz_od.gui.view.plugin.plugin_store_interface import (
            PluginStoreInterface,
        )

        self.manage_interface: PluginManageInterface = PluginManageInterface(
            self.ctx,
            parent=self,
        )
        self.add_sub_interface(self.manage_interface)

        self.store_interface: PluginStoreInterface = PluginStoreInterface(
            self.ctx,
            parent=self,
        )
        self.add_sub_interface(self.store_interface)

    def shutdown(self) -> None:
        """程序退出前收尾，等页面里的后台线程结束。"""
        self.manage_interface.close_plugin_operation()
        self.store_interface.close_plugin_operation()
