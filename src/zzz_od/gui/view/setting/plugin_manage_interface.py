"""插件管理界面

提供插件的查看、安装、卸载等管理功能。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.plugin_card import PluginCard, PluginInfo
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class PluginManageInterface(VerticalScrollInterface):
    """插件管理界面

    提供已安装插件的查看和管理功能。
    """

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        VerticalScrollInterface.__init__(
            self,
            object_name="plugin_manage_interface",
            content_widget=None,
            parent=parent,
            nav_text_cn="插件管理",
        )

        self.ctx: ZContext = ctx
        self._plugin_cards: list[PluginCard | HelpCard] = []
        self.installed_group: SettingCardGroup | None = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        # 帮助说明
        content_widget.add_widget(self._create_help_group())

        # 已安装插件
        self.installed_group = SettingCardGroup(gt("已安装插件"))
        content_widget.add_widget(self.installed_group)

        # 刷新按钮
        self.refresh_card = PushSettingCard(
            icon=FluentIcon.SYNC,
            title=gt("刷新插件"),
            text=gt("刷新"),
            content=gt("重新扫描插件目录并刷新应用注册"),
        )
        self.refresh_card.clicked.connect(self._on_refresh_clicked)
        self.installed_group.addSettingCard(self.refresh_card)

        content_widget.add_stretch(1)

        return content_widget

    def _create_help_group(self) -> SettingCardGroup:
        """创建帮助说明组"""
        group = SettingCardGroup(gt("使用说明"))

        help_card = HelpCard(
            title="插件安装方式",
            content="将插件文件夹放入 plugins 目录后点击刷新即可加载",
        )
        group.addSettingCard(help_card)

        plugins_path = self._get_plugins_dir()
        path_card = HelpCard(
            title="插件目录",
            content=str(plugins_path) if plugins_path else "未找到插件目录",
        )
        group.addSettingCard(path_card)

        return group

    def _get_plugins_dir(self) -> Path | None:
        """获取插件目录路径"""
        try:
            plugin_dirs = self.ctx.get_application_plugin_dirs()
            for d in plugin_dirs:
                p = Path(d)
                if p.name == "plugins" and p.exists():
                    return p
        except Exception as e:
            log.debug(f"获取插件目录失败: {e}")
        return None

    def _scan_installed_plugins(self) -> list[PluginInfo]:
        """扫描已安装的插件"""
        plugins: list[PluginInfo] = []
        plugins_dir = self._get_plugins_dir()

        if not plugins_dir or not plugins_dir.exists():
            return plugins

        # 扫描 plugins 目录下的子目录
        for plugin_path in plugins_dir.iterdir():
            if not plugin_path.is_dir():
                continue
            if plugin_path.name.startswith("."):
                continue

            # 检查是否有 *_factory.py 文件
            factory_files = list(plugin_path.glob("*_factory.py"))
            if not factory_files:
                continue

            # 尝试读取插件信息
            plugin_info = self._read_plugin_info(plugin_path)
            if plugin_info:
                plugins.append(plugin_info)

        return plugins

    def _read_plugin_info(self, plugin_path: Path) -> PluginInfo | None:
        """读取插件信息"""
        plugin_id = plugin_path.name

        # 尝试从 const 文件读取信息
        const_file = plugin_path / f"{plugin_id}_const.py"
        name = plugin_id
        version = "1.0.0"
        description = ""

        if const_file.exists():
            try:
                content = const_file.read_text(encoding="utf-8")
                # 简单解析
                for line in content.splitlines():
                    if "APP_NAME" in line and "=" in line:
                        # APP_NAME = '示例插件'
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip("'\"")
                            if val:
                                name = val
            except Exception as e:
                log.debug(f"读取插件 const 文件失败: {e}")

        return PluginInfo(
            plugin_id=plugin_id,
            name=name,
            version=version,
            description=description,
            installed=True,
            local_path=plugin_path,
        )

    def _refresh_plugin_list(self) -> None:
        """刷新插件列表显示"""
        # 检查 installed_group 是否存在
        if self.installed_group is None:
            return

        # 扫描已安装插件
        plugins = self._scan_installed_plugins()

        # 获取当前显示的插件 ID
        current_plugin_ids: set[str] = set()
        for card in self._plugin_cards:
            if isinstance(card, PluginCard):
                current_plugin_ids.add(card.plugin_info.plugin_id)
        new_plugin_ids = {p.plugin_id for p in plugins}

        # 如果插件列表没有变化且已有卡片，不刷新 UI
        if current_plugin_ids == new_plugin_ids and self._plugin_cards:
            return

        # 清除旧的插件卡片
        for card in self._plugin_cards:
            try:
                card.setParent(None)
                card.deleteLater()
            except Exception:
                pass
        self._plugin_cards.clear()

        if not plugins:
            # 显示无插件提示
            empty_card = HelpCard(
                title="暂无插件",
                content="plugins 目录下没有找到任何插件",
            )
            self.installed_group.addSettingCard(empty_card)
            empty_card.show()
            self._plugin_cards.append(empty_card)
        else:
            for plugin_info in plugins:
                card = PluginCard(self.ctx, plugin_info)
                card.operation_finished.connect(self._on_plugin_operation_finished)
                card.state_changed.connect(self._on_plugin_state_changed)
                self.installed_group.addSettingCard(card)
                card.show()
                self._plugin_cards.append(card)

        # 强制更新布局
        self.installed_group.adjustSize()
        self.installed_group.updateGeometry()

    def _on_refresh_clicked(self) -> None:
        """刷新按钮点击"""
        log.info("刷新插件列表...")

        # 刷新应用注册
        try:
            self.ctx.plugin_manager.refresh_applications()
            log.info("应用注册刷新完成")
        except Exception as e:
            log.error(f"刷新应用注册失败: {e}")

        # 刷新显示
        self._refresh_plugin_list()

    def _on_plugin_operation_finished(self, success: bool, msg: str) -> None:
        """插件操作完成"""
        if success:
            log.info(msg)
        else:
            log.warning(msg)

    def _on_plugin_state_changed(self) -> None:
        """插件状态变化后刷新"""
        self._on_refresh_clicked()

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        # 只在第一次显示时刷新，后续不自动刷新
        if not self._plugin_cards:
            self._refresh_plugin_list()

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
