from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                               QListWidgetItem, QMessageBox, QInputDialog)
from qfluentwidgets import FluentIcon, PushButton, BodyLabel

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.world_patrol.world_patrol_route_list import (
    WorldPatrolRouteList, RouteListType
)
from zzz_od.application.world_patrol.world_patrol_service import (
    WorldPatrolService, WorldPatrolEntry, WorldPatrolArea
)
from zzz_od.context.zzz_context import ZContext


class WorldPatrolRouteListInterface(VerticalScrollInterface):
    """世界巡逻路线列表编辑界面"""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.world_patrol_service: WorldPatrolService = ctx.world_patrol_service

        # 数据
        self.chosen_entry: WorldPatrolEntry | None = None
        self.chosen_area: WorldPatrolArea | None = None
        self.current_route_list: WorldPatrolRouteList | None = None
        self.available_routes: list = []  # 当前区域可用的路线

        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='world_patrol_route_list_interface',
            nav_text_cn='路线列表',
            parent=parent,
        )

    def get_content_widget(self):
        # 主容器A，水平布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._init_control_panel())
        main_layout.addWidget(self._init_list_panel(), stretch=1)

        return main_widget

    def _init_control_panel(self) -> QWidget:
        """初始化控制面板"""
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        # 路线列表管理
        self.route_list_combo = EditableComboBox()
        self.route_list_combo.currentIndexChanged.connect(self.on_route_list_changed)

        self.list_type_combo = ComboBox()
        self.list_type_combo.set_items([
            ConfigItem('白名单', RouteListType.WHITELIST),
            ConfigItem('黑名单', RouteListType.BLACKLIST),
        ])
        self.list_type_combo.currentIndexChanged.connect(self.on_list_type_changed)
        list_card = MultiPushSettingCard(
            icon=FluentIcon.FOLDER,
            title='名单选择',
            btn_list=[self.route_list_combo, self.list_type_combo],
        )
        control_layout.addWidget(list_card)

        self.new_list_btn = PushButton(text='新建')
        self.new_list_btn.clicked.connect(self.on_new_list_clicked)
        self.save_list_btn = PushButton(text='保存')
        self.save_list_btn.clicked.connect(self.on_save_list_clicked)
        self.delete_list_btn = PushButton(text='删除')
        self.delete_list_btn.clicked.connect(self.on_delete_list_clicked)
        self.cancel_btn = PushButton(text='取消')
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)

        list_mgmt_card = MultiPushSettingCard(
            icon=FluentIcon.SAVE,
            title='编辑',
            btn_list=[self.new_list_btn, self.save_list_btn, self.delete_list_btn, self.cancel_btn],
        )
        control_layout.addWidget(list_mgmt_card)

        # 区域选择
        self.entry_combo_box = EditableComboBox()
        self.entry_combo_box.currentIndexChanged.connect(self.on_entry_changed)
        self.area_combo_box = EditableComboBox()
        self.area_combo_box.currentIndexChanged.connect(self.on_area_changed)

        area_card = MultiPushSettingCard(
            icon=FluentIcon.GLOBE,
            title='区域选择',
            btn_list=[self.entry_combo_box, self.area_combo_box]
        )
        control_layout.addWidget(area_card)

        # 路线操作
        self.add_area_btn = PushButton(text='添加整个区域')
        self.add_area_btn.clicked.connect(self.on_add_area_clicked)
        self.add_route_btn = PushButton(text='添加单条路线')
        self.add_route_btn.clicked.connect(self.on_add_route_clicked)

        route_ops_card = MultiPushSettingCard(
            icon=FluentIcon.ADD,
            title='添加路线',
            btn_list=[self.add_area_btn, self.add_route_btn]
        )
        control_layout.addWidget(route_ops_card)

        # 顺序调整
        self.move_up_btn = PushButton(text='上移')
        self.move_up_btn.clicked.connect(self.on_move_up_clicked)
        self.move_down_btn = PushButton(text='下移')
        self.move_down_btn.clicked.connect(self.on_move_down_clicked)
        self.remove_btn = PushButton(text='移除')
        self.remove_btn.clicked.connect(self.on_remove_clicked)

        order_card = MultiPushSettingCard(
            icon=FluentIcon.UP,
            title='顺序调整',
            btn_list=[self.move_up_btn, self.move_down_btn, self.remove_btn]
        )
        control_layout.addWidget(order_card)

        control_layout.addStretch()
        return control_widget

    def _init_list_panel(self) -> QWidget:
        """初始化列表面板"""
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(12)

        # 标题
        title_label = BodyLabel('路线列表')
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        list_layout.addWidget(title_label)

        # 路线列表
        self.route_list_widget = QListWidget()
        self.route_list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        list_layout.addWidget(self.route_list_widget)

        # 可用路线列表
        available_label = BodyLabel('当前区域可用路线')
        available_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        list_layout.addWidget(available_label)

        self.source_route_list_widget = QListWidget()
        self.source_route_list_widget.itemSelectionChanged.connect(self.on_source_selection_changed)
        list_layout.addWidget(self.source_route_list_widget)

        return list_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.world_patrol_service.load_data()
        self._update_route_list_combo()

        self.entry_combo_box.set_items(
            [ConfigItem(entry.entry_name, entry) for entry in self.world_patrol_service.entry_list],
            self.chosen_entry
        )
        self.update_area_opt()

    def update_area_opt(self) -> None:
        if self.chosen_entry is not None:
            area_list = [ConfigItem(area.full_name, area) for area in self.world_patrol_service.get_area_list_by_entry(self.chosen_entry)]
        else:
            area_list = []
        self.area_combo_box.set_items(area_list, self.chosen_area)

    def _update_route_list_combo(self):
        """更新路线列表下拉框"""
        route_lists = self.world_patrol_service.get_world_patrol_route_lists()
        list_items = []
        for route_list in route_lists:
            display_name = f"{route_list.name} ({route_list.list_type})"
            list_items.append(ConfigItem(display_name, route_list))

        # 添加空选项
        self.route_list_combo.set_items(list_items, self.current_route_list)

    def _update_btn_display(self):
        """更新按钮状态"""
        has_list = self.current_route_list is not None
        has_area = self.chosen_area is not None
        has_source_selection = len(self.source_route_list_widget.selectedItems())
        has_selection = len(self.route_list_widget.selectedItems()) > 0

        self.new_list_btn.setDisabled(has_list)
        self.save_list_btn.setDisabled(not has_list)
        self.delete_list_btn.setDisabled(not has_list)
        self.cancel_btn.setDisabled(not has_list)
        self.add_route_btn.setDisabled(not (has_list and has_area and has_source_selection))
        self.add_area_btn.setDisabled(not (has_list and has_area))
        self.move_up_btn.setDisabled(not (has_list and has_selection))
        self.move_down_btn.setDisabled(not (has_list and has_selection))
        self.remove_btn.setDisabled(not (has_list and has_selection))

    def _update_route_list_display(self):
        """更新路线列表显示"""
        self.route_list_widget.clear()
        if self.current_route_list is None:
            return

        route_list = self.ctx.world_patrol_service.get_world_patrol_routes()
        id_2_route = {route.full_id: route for route in route_list}

        for route_full_id in self.current_route_list.route_items:
            route = id_2_route.get(route_full_id)
            display_text = f"{route.tp_area.full_name} {route.idx}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, route_full_id)
            self.route_list_widget.addItem(item)

    def _update_available_routes(self):
        """更新可用路线列表"""
        self.source_route_list_widget.clear()
        self.available_routes = []

        if self.chosen_area is None:
            return

        # 获取当前区域的所有路线
        routes = self.world_patrol_service.get_world_patrol_routes_by_area(self.chosen_area)
        self.available_routes = routes

        for route in routes:
            display_text = f"{route.idx:02d}. {route.tp_name} ({len(route.op_list)}步)"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, route)
            self.source_route_list_widget.addItem(item)

    # 事件处理方法
    def on_route_list_changed(self, idx: int):
        """路线列表选择变化"""
        self.current_route_list = self.route_list_combo.itemData(idx)
        if self.current_route_list is not None:
            # 更新列表类型显示
            if self.current_route_list.list_type == RouteListType.WHITELIST:
                self.list_type_combo.setCurrentIndex(0)
            else:
                self.list_type_combo.setCurrentIndex(1)

        self._update_route_list_display()
        self._update_btn_display()

    def on_list_type_changed(self, idx: int):
        """列表类型变化"""
        if self.current_route_list is None:
            return
        self.current_route_list.list_type = self.list_type_combo.currentData()

    def on_entry_changed(self, idx: int) -> None:
        self.chosen_entry = self.entry_combo_box.itemData(idx)
        self.update_area_opt()

    def on_area_changed(self, idx: int):
        """区域选择变化"""
        self.chosen_area = self.area_combo_box.itemData(idx)
        self._update_available_routes()
        self._update_btn_display()

    def on_new_list_clicked(self):
        """新建列表按钮点击"""
        name, ok = QInputDialog.getText(self, '新建路线列表', '请输入列表名称:')
        if ok and name.strip():
            self.current_route_list = WorldPatrolRouteList(
                name=name.strip(),
                list_type=RouteListType.WHITELIST
            )
            self._update_route_list_combo()
            # 选择新建的列表
            for i in range(self.route_list_combo.count()):
                if self.route_list_combo.itemData(i) == self.current_route_list:
                    self.route_list_combo.setCurrentIndex(i)
                    break
            self._update_route_list_display()
            self._update_btn_display()
            log.info(f'新建路线列表: {name}')

    def on_save_list_clicked(self):
        """保存列表按钮点击"""
        if self.current_route_list is None:
            return

        success = self.world_patrol_service.save_world_patrol_route_list(self.current_route_list)
        if success:
            self._update_route_list_combo()
            log.info(f'保存路线列表成功: {self.current_route_list.name}')
        else:
            QMessageBox.warning(self, '错误', '保存路线列表失败')

    def on_delete_list_clicked(self):
        """删除列表按钮点击"""
        if self.current_route_list is None:
            return

        success = self.world_patrol_service.delete_world_patrol_route_list(self.current_route_list)
        if success:
            self.current_route_list = None
            self._update_route_list_combo()
            self._update_route_list_display()
            self._update_btn_display()
            log.info('删除路线列表成功')
        else:
            QMessageBox.warning(self, '错误', '删除路线列表失败')

    def on_cancel_clicked(self) -> None:
        if self.current_route_list is None:
            return
        self.current_route_list = None
        self._update_route_list_display()
        self._update_btn_display()

    def on_add_route_clicked(self):
        """添加单条路线按钮点击"""
        if self.current_route_list is None or self.chosen_area is None:
            return

        # 显示可用路线选择对话框
        if not self.available_routes:
            QMessageBox.information(self, '提示', '当前区域没有可用路线')
            return

        selected_route = self.source_route_list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
        self.current_route_list.add_route(selected_route.full_id)
        self._update_route_list_display()
        log.info(f'添加路线: {selected_route.full_id}')

    def on_add_area_clicked(self):
        """添加整个区域按钮点击"""
        if self.current_route_list is None or self.chosen_area is None:
            return

        if not self.available_routes:
            QMessageBox.information(self, '提示', '当前区域没有可用路线')
            return

        route_indices = [route.idx for route in self.available_routes]
        for route in self.available_routes:
            self.current_route_list.add_route(route.full_id)
        self._update_route_list_display()
        log.info(f'添加整个区域: {self.chosen_area.full_name} ({len(route_indices)}条路线)')

    def on_move_up_clicked(self):
        """上移按钮点击"""
        if self.current_route_list is None:
            return

        current_row = self.route_list_widget.currentRow()
        if current_row > 0:
            self.current_route_list.move_route(current_row, current_row - 1)
            self._update_route_list_display()
            self.route_list_widget.setCurrentRow(current_row - 1)

    def on_move_down_clicked(self):
        """下移按钮点击"""
        if self.current_route_list is None:
            return

        current_row = self.route_list_widget.currentRow()
        if current_row < len(self.current_route_list.route_items) - 1:
            self.current_route_list.move_route(current_row, current_row + 1)
            self._update_route_list_display()
            self.route_list_widget.setCurrentRow(current_row + 1)

    def on_remove_clicked(self):
        """移除按钮点击"""
        if self.current_route_list is None:
            return

        current_row = self.route_list_widget.currentRow()
        if 0 <= current_row < len(self.current_route_list.route_items):
            removed_item = self.current_route_list.route_items.pop(current_row)
            self._update_route_list_display()
            log.info(f'移除路线: {removed_item}')

    def on_selection_changed(self):
        """选择变化"""
        self._update_btn_display()

    def on_source_selection_changed(self):
        self._update_btn_display()
