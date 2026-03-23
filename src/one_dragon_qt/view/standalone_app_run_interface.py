from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QListWidgetItem, QWidget
from qfluentwidgets import (
    FluentIcon,
    FluentIconBase,
    MessageBoxBase,
    PrimaryPushButton,
    SubtitleLabel,
    getFont,
)

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.view.app_run_interface import SplitAppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.multi_select_list import MultiSelectListWidget
from one_dragon_qt.widgets.selectable_app_list import SelectableAppList


class StandaloneRunInterface(SplitAppRunInterface):
    """独立应用运行界面基类

    左侧为用户手动添加的应用卡片列表，
    右侧为标准的运行/停止/日志控件。
    选中某个应用后，点击"开始"即运行该应用。

    子类可覆盖 get_setting_dialog_map() 以提供设置弹窗。
    """

    def __init__(self, ctx: OneDragonContext,
                 object_name: str = 'standalone_run_interface',
                 nav_text_cn: str = '运行',
                 nav_icon: FluentIconBase | QIcon | str = FluentIcon.PLAY,
                 parent: QWidget | None = None):
        self.ctx: OneDragonContext = ctx

        SplitAppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id='',
            object_name=object_name,
            nav_text_cn=nav_text_cn,
            nav_icon=nav_icon,
            parent=parent,
            left_stretch=1,
            right_stretch=1,
        )

    def get_left_widget(self) -> QWidget:
        left = Column(spacing=4)

        self.app_list_widget = SelectableAppList()
        self.app_list_widget.app_selected.connect(self._on_app_selected)
        self.app_list_widget.app_removed.connect(self._on_app_removed)
        self.app_list_widget.app_setting_clicked.connect(self._on_app_setting_clicked)
        self.app_list_widget.app_order_changed.connect(self._on_app_order_changed)
        left.add_widget(self.app_list_widget, alignment=Qt.AlignmentFlag(0))

        self.add_app_btn = PrimaryPushButton(
            text=gt('添加应用'), icon=FluentIcon.ADD
        )
        self.add_app_btn.clicked.connect(self._on_add_app_clicked)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 16, 0)
        btn_layout.addWidget(self.add_app_btn)
        left.add_widget(btn_container, alignment=Qt.AlignmentFlag(0))

        left.add_stretch(1)
        return left

    def on_interface_shown(self) -> None:
        SplitAppRunInterface.on_interface_shown(self)
        self._refresh_app_list()

    # ── 应用列表管理 ──

    def _get_all_apps(self) -> dict[str, str]:
        """获取所有已注册的默认组应用 {app_id: app_name}"""
        result: dict[str, str] = {}
        for app_id in self.ctx.run_context.default_group_apps:
            name = self.ctx.run_context.get_application_name(app_id)
            result[app_id] = name or app_id
        return result

    def _refresh_app_list(self) -> None:
        """刷新应用列表"""
        all_apps = self._get_all_apps()
        config = self.ctx.standalone_app_config

        valid_ids = [aid for aid in config.app_list if aid in all_apps]

        app_list = [(aid, all_apps[aid]) for aid in valid_ids]
        self.app_list_widget.set_app_list(app_list)
        self._update_setting_btn_visibility()

        active_id = config.active_app_id
        if active_id and active_id in valid_ids:
            target = active_id
        elif valid_ids:
            target = valid_ids[0]
        else:
            target = None

        if target:
            self.app_list_widget.select_app(target)
        self.app_id = target or ''
        self.ctx.standalone_app_config.active_app_id = target or ''

    # ── 事件处理 ──

    def _on_app_selected(self, app_id: str) -> None:
        self.app_id = app_id
        self.ctx.standalone_app_config.active_app_id = app_id

    def _on_app_removed(self, app_id: str) -> None:
        self.ctx.standalone_app_config.app_list = self.app_list_widget.app_ids
        selected = self.app_list_widget.selected_app_id
        self.app_id = selected or ''
        self.ctx.standalone_app_config.active_app_id = selected or ''

    def _on_app_order_changed(self, app_ids: list[str]) -> None:
        self.ctx.standalone_app_config.app_list = app_ids

    def _on_add_app_clicked(self) -> None:
        all_apps = self._get_all_apps()
        existing_ids = set(self.app_list_widget.app_ids)
        available = {aid: name for aid, name in all_apps.items() if aid not in existing_ids}

        if not available:
            return

        dialog = AddAppDialog(available, self.window())
        if dialog.exec():
            selected_ids = dialog.get_selected_ids()
            for app_id in selected_ids:
                self.app_list_widget.add_app(app_id, all_apps[app_id])
            self._update_setting_btn_visibility()
            self.ctx.standalone_app_config.app_list = self.app_list_widget.app_ids

            if not self.app_list_widget.selected_app_id and selected_ids:
                self.app_list_widget.select_app(selected_ids[0])
                self.app_id = selected_ids[0]
                self.ctx.standalone_app_config.active_app_id = selected_ids[0]

    def _on_app_setting_clicked(self, app_id: str) -> None:
        dialog_fn = self.get_setting_dialog_map().get(app_id)
        if dialog_fn is None:
            return
        target = self._find_setting_btn(app_id) or self.add_app_btn
        dialog_fn(
            parent=self,
            group_id=application_const.DEFAULT_GROUP_ID,
            target=target,
        )

    def _find_setting_btn(self, app_id: str) -> QWidget | None:
        """找到对应 app_id 的卡片上的设置按钮"""
        for card in self.app_list_widget._cards:
            if card.app_id == app_id:
                return card.setting_btn
        return None

    def _update_setting_btn_visibility(self) -> None:
        """根据 get_setting_dialog_map 的注册信息，显示或隐藏卡片的设置按钮"""
        settable = set(self.get_setting_dialog_map())
        for card in self.app_list_widget._cards:
            card.setting_btn.setVisible(card.app_id in settable)

    def get_setting_dialog_map(self) -> dict[str, Callable]:
        """返回 app_id -> 设置弹窗回调 的映射，由子类实现"""
        return {}


class AddAppDialog(MessageBoxBase):
    """添加应用对话框"""

    def __init__(self, available_apps: dict[str, str], parent: QWidget):
        super().__init__(parent=parent)

        self.titleLabel = SubtitleLabel(gt('添加应用'))
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)

        self._app_ids = list(available_apps.keys())

        self._list_widget = MultiSelectListWidget()
        self._list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._list_widget.setViewportMargins(0, 0, 16, 0)
        self._list_widget.setMinimumHeight(400)
        self._list_widget.setMinimumWidth(480)
        item_font = getFont(16)
        for _, app_name in available_apps.items():
            item = QListWidgetItem(gt(app_name))
            item.setSizeHint(QSize(0, 36))
            item.setFont(item_font)
            self._list_widget.addItem(item)

        self.viewLayout.addWidget(self._list_widget)

        self.yesButton.setText(gt('确定'))
        self.cancelButton.setText(gt('取消'))

    def get_selected_ids(self) -> list[str]:
        selected_rows = {idx.row() for idx in self._list_widget.selectedIndexes()}
        return [self._app_ids[i] for i in sorted(selected_rows)]
