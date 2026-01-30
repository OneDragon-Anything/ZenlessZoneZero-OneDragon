"""插件卡片组件

用于显示单个插件的信息和操作按钮。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, QThread
from qfluentwidgets import FluentIcon, PrimaryPushButton, PushButton

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class PluginInfo:
    """插件信息数据类"""

    def __init__(
        self,
        plugin_id: str,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        authors: list[str] | None = None,
        tags: list[str] | None = None,
        installed: bool = False,
        local_path: Path | None = None,
    ):
        self.plugin_id = plugin_id
        self.name = name
        self.version = version
        self.description = description
        self.authors = authors or []
        self.tags = tags or []
        self.installed = installed
        self.local_path = local_path


class PluginOperationRunner(QThread):
    """插件操作运行线程"""

    finished = Signal(bool, str)

    def __init__(self, operation: str, plugin_info: PluginInfo, ctx: OneDragonContext):
        super().__init__()
        self.operation = operation
        self.plugin_info = plugin_info
        self.ctx = ctx

    def run(self):
        try:
            if self.operation == "install":
                success, msg = self._install_plugin()
            elif self.operation == "uninstall":
                success, msg = self._uninstall_plugin()
            elif self.operation == "update":
                success, msg = self._update_plugin()
            else:
                success, msg = False, f"未知操作: {self.operation}"
        except Exception as e:
            log.error(f"插件操作失败: {e}")
            success, msg = False, str(e)

        self.finished.emit(success, msg)

    def _install_plugin(self) -> tuple[bool, str]:
        """安装插件"""
        # TODO: 实现从远程仓库下载安装插件
        return False, "暂不支持在线安装，请手动下载插件到 plugins 目录"

    def _uninstall_plugin(self) -> tuple[bool, str]:
        """卸载插件"""
        if self.plugin_info.local_path and self.plugin_info.local_path.exists():
            import shutil

            try:
                shutil.rmtree(self.plugin_info.local_path)
                return True, "卸载成功"
            except Exception as e:
                return False, f"卸载失败: {e}"
        return False, "插件路径不存在"

    def _update_plugin(self) -> tuple[bool, str]:
        """更新插件"""
        # TODO: 实现插件更新逻辑
        return False, "暂不支持在线更新"


class PluginCard(SettingCardBase):
    """插件卡片

    显示单个插件的信息，包括名称、版本、描述、作者，
    以及卸载按钮。
    """

    operation_finished = Signal(bool, str)
    state_changed = Signal()

    def __init__(
        self,
        ctx: OneDragonContext,
        plugin_info: PluginInfo,
        parent=None,
    ):
        self.ctx = ctx
        self.plugin_info = plugin_info

        # 构建内容文本
        content_parts = []
        if plugin_info.description:
            content_parts.append(plugin_info.description)
        if plugin_info.authors:
            content_parts.append(f"作者: {', '.join(plugin_info.authors)}")
        if plugin_info.tags:
            content_parts.append(f"标签: {', '.join(plugin_info.tags)}")

        content = " | ".join(content_parts) if content_parts else "已安装"

        SettingCardBase.__init__(
            self,
            icon=FluentIcon.LIBRARY,
            title=f"{plugin_info.name} v{plugin_info.version}",
            content=content,
            parent=parent,
        )

        self._init_buttons()
        self._runner: PluginOperationRunner | None = None

    def _init_buttons(self) -> None:
        """初始化按钮"""
        # 卸载按钮
        self.uninstall_btn = PushButton(gt("卸载"), self)
        self.uninstall_btn.clicked.connect(self._on_uninstall_clicked)
        self.hBoxLayout.addWidget(self.uninstall_btn)
        self.hBoxLayout.addSpacing(16)

    def _on_uninstall_clicked(self) -> None:
        """卸载按钮点击"""
        self._run_operation("uninstall")

    def _run_operation(self, operation: str) -> None:
        """运行插件操作"""
        if self._runner and self._runner.isRunning():
            log.warning("操作正在进行中...")
            return

        self.uninstall_btn.setEnabled(False)
        self._runner = PluginOperationRunner(operation, self.plugin_info, self.ctx)
        self._runner.finished.connect(self._on_operation_finished)
        self._runner.start()

    def _on_operation_finished(self, success: bool, msg: str) -> None:
        """操作完成回调"""
        self.uninstall_btn.setEnabled(True)
        self.operation_finished.emit(success, msg)
        if success:
            self.state_changed.emit()
