import cv2
from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSpinBox
from cv2.typing import MatLike
from qfluentwidgets import FluentIcon, PushButton

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum, OneDragonContext
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.click_image_label import ClickImageLabel
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.image_viewer_widget import ImageViewerWidget
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.devtools.large_map_recorder import large_map_recorder_utils
from zzz_od.application.devtools.large_map_recorder.large_map_recorder_wrapper import LargeMapSnapshot, MiniMapSnapshot
from zzz_od.application.world_patrol.operation.world_patrol_run_route import WorldPatrolRunRoute
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolEntry, WorldPatrolArea, \
    WorldPatrolLargeMapIcon, WorldPatrolLargeMap
from zzz_od.application.world_patrol.world_patrol_route import WorldPatrolRoute
from zzz_od.application.world_patrol.world_patrol_service import WorldPatrolService
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.world_patrol.route_operation_editor_dialog import RouteOperationEditorDialog


class DebugRouteRunner(QThread):

    def __init__(self, ctx: OneDragonContext):
        super().__init__()
        self.ctx: OneDragonContext = ctx
        self.op: WorldPatrolRunRoute | None = None

    def run(self):
        """
        运行 最后发送结束信号
        :return:
        """
        try:
            self.ctx.run_context.start_running()
            self.op.execute()
        except Exception as e:
            log.error('调试异常', exc_info=True)
        finally:
            self.ctx.run_context.stop_running()


class WorldPatrolRouteRecorderInterface(VerticalScrollInterface):

    screenshot_requested = Signal()

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.world_patrol_service: WorldPatrolService = WorldPatrolService(ctx)

        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='world_patrol_route_recorder_interface',
            nav_text_cn='锄地路线录制',
            parent=parent,
        )
        self.debug_runner = DebugRouteRunner(self.ctx)

        self.screenshot_requested.connect(self.on_screenshot_btn_clicked)

        self.chosen_entry: WorldPatrolEntry | None = None
        self.chosen_area: WorldPatrolArea | None = None
        self.chosen_large_map: WorldPatrolLargeMap | None = None
        self.chosen_tp_icon: WorldPatrolLargeMapIcon | None = None

        # 路线相关
        self.chosen_route: WorldPatrolRoute | None = None
        self.existing_routes: list[WorldPatrolRoute] = []

        self.large_map: LargeMapSnapshot | None = None

        self.mini_map: MiniMapSnapshot | None = None

        self.current_pos: Point | None = None  # 记录的当前角色所在的坐标
        self.mini_map_pos_mr: MatchResult | None = None  # 计算的小地图在大地图上的坐标
        self.overlap_mode: int = 1  # 0=不重叠显示 1=填充

    def get_content_widget(self) -> QWidget:
        # 主容器A，水平布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._init_control_panel())
        main_layout.addWidget(self._init_mini_map_display_panel())
        main_layout.addWidget(self._init_large_map_display_panel(), stretch=1)

        return main_widget

    def _init_control_panel(self) -> QWidget:
        # 容器B，垂直布局
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        self.entry_combo_box = EditableComboBox()
        self.entry_combo_box.currentIndexChanged.connect(self.on_entry_changed)
        self.area_combo_box = EditableComboBox()
        self.area_combo_box.currentIndexChanged.connect(self.on_area_changed)
        self.route_combo_box = EditableComboBox()
        self.route_combo_box.currentIndexChanged.connect(self.on_route_changed)

        self.route_row = MultiPushSettingCard(
            icon=FluentIcon.GLOBE,
            title='路线',
            btn_list=[
                self.entry_combo_box,
                self.area_combo_box,
                self.route_combo_box,
            ]
        )
        control_layout.addWidget(self.route_row)

        self.new_route_btn = PushButton(text='新增')
        self.new_route_btn.clicked.connect(self.on_new_route_btn_clicked)
        self.save_route_btn = PushButton(text='保存')
        self.save_route_btn.clicked.connect(self.on_save_route_btn_clicked)
        self.delete_route_btn = PushButton(text='删除')
        self.delete_route_btn.clicked.connect(self.on_delete_route_btn_clicked)
        self.cancel_route_btn = PushButton(text='取消')
        self.cancel_route_btn.clicked.connect(self.on_cancel_route_btn_clicked)
        self.edit_operations_btn = PushButton(text='编辑操作')
        self.edit_operations_btn.clicked.connect(self.on_edit_operations_btn_clicked)
        self.rout_opt_row = MultiPushSettingCard(
            icon=FluentIcon.SAVE, title='编辑',
            btn_list=[
                self.new_route_btn,
                self.save_route_btn,
                self.delete_route_btn,
                self.cancel_route_btn,
                self.edit_operations_btn,
            ]
        )
        control_layout.addWidget(self.rout_opt_row)

        self.tp_combo_box = EditableComboBox()
        self.tp_combo_box.currentIndexChanged.connect(self.on_tp_changed)
        self.tp_opt = MultiPushSettingCard(
            icon=FluentIcon.PLAY,
            title='传送点',
            content='选择路线起始传送点',
            btn_list=[self.tp_combo_box]
        )
        control_layout.addWidget(self.tp_opt)

        self.screenshot_btn = PushButton(text='截图(1)')
        self.screenshot_btn.clicked.connect(self.on_screenshot_btn_clicked)
        self.add_move_btn = PushButton(text='添加移动(4)')
        self.add_move_btn.clicked.connect(self.on_add_move_btn_clicked)
        self.undo_move_btn = PushButton(text='回退(5)')
        self.undo_move_btn.clicked.connect(self.on_undo_move_btn_clicked)
        self.pos_opt_row = MultiPushSettingCard(
            icon=FluentIcon.ROBOT, title='操作',
            btn_list=[
                self.screenshot_btn,
                self.add_move_btn,
                self.undo_move_btn,
            ]
        )
        control_layout.addWidget(self.pos_opt_row)

        self.debug_start_input = QSpinBox()
        self.debug_start_input.setMinimum(0)
        self.debug_start_input.setValue(0)
        self.debug_start_input.setMinimumWidth(80)
        self.debug_route_btn = PushButton(text='调试')
        self.debug_route_btn.clicked.connect(self.on_debug_route_btn_clicked)
        self.debug_row = MultiPushSettingCard(
            icon=FluentIcon.ROBOT, title='调试',
            content='可选择从第几步开始, 0代表需要传送，1代表已完成第1步',
            btn_list=[
                self.debug_start_input,
                self.debug_route_btn,
            ]
        )
        control_layout.addWidget(self.debug_row)

        self.auto_add_click_pos_opt = SwitchSettingCard(
            icon=FluentIcon.ROBOT,
            title='点击后自动追加移动',
        )
        self.auto_add_click_pos_opt.setValue(True)
        control_layout.addWidget(self.auto_add_click_pos_opt)

        self.pos_label = QLabel()

        self.log_card = LogDisplayCard()
        control_layout.addWidget(self.log_card)

        control_layout.addStretch(1)
        return control_widget

    def _init_mini_map_display_panel(self) -> QWidget:
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(12)

        self.mm_road_viewer = ClickImageLabel()
        display_layout.addWidget(self.mm_road_viewer)

        return display_widget

    def _init_large_map_display_panel(self) -> QWidget:
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(12)

        self.lm_viewer = ImageViewerWidget()
        self.lm_viewer.point_clicked.connect(self.on_large_map_clicked)
        display_layout.addWidget(self.lm_viewer)

        return display_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.world_patrol_service.load_data()

        self.entry_combo_box.set_items(
            [ConfigItem(entry.entry_name, entry) for entry in self.world_patrol_service.entry_list],
            self.chosen_entry
        )
        self.update_area_opt()

        self._update_btn_display()

        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)
        self.log_card.start()

    def update_area_opt(self) -> None:
        if self.chosen_entry is not None:
            area_list = [ConfigItem(area.full_name, area) for area in self.world_patrol_service.get_area_list_by_entry(self.chosen_entry)]
        else:
            area_list = []
        self.area_combo_box.set_items(area_list, self.chosen_area)

    def _update_btn_display(self) -> None:
        has_area = self.chosen_area is not None
        has_large_map = self.large_map is not None
        has_route = self.chosen_route is not None
        has_tp_point = self.chosen_tp_icon is not None

        self.new_route_btn.setDisabled(not (has_area and has_tp_point))
        self.save_route_btn.setDisabled(not has_route)
        self.delete_route_btn.setDisabled(not has_route)
        self.cancel_route_btn.setDisabled(not has_route)
        self.edit_operations_btn.setDisabled(not has_route)
        self.debug_route_btn.setDisabled(not has_route)
        self.screenshot_btn.setDisabled(not has_large_map)
        self.add_move_btn.setDisabled(not has_route)
        self.undo_move_btn.setDisabled(not (has_route and len(self.chosen_route.op_list) > 0 if has_route else True))

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)
        self.log_card.stop()

    def on_entry_changed(self, idx: int) -> None:
        self.chosen_entry = self.entry_combo_box.itemData(idx)
        self.update_area_opt()

    def on_area_changed(self, idx: int) -> None:
        self.chosen_area = self.area_combo_box.itemData(idx)
        if self.chosen_area is not None:
            self._auto_load_large_map()
        self._update_btn_display()

    def _auto_load_large_map(self) -> None:
        """自动加载选中区域的大地图"""
        self._load_chosen_large_map()

        if self.chosen_large_map.road_mask is None:
            self.large_map = None
            log.info('未有地图数据')
        else:
            # 使用原图大小显示，不进行缩放
            self.large_map = LargeMapSnapshot(
                world_patrol_large_map=self.chosen_large_map,
                pos_after_merge=Point(self.chosen_large_map.road_mask.shape[1] // 2, self.chosen_large_map.road_mask.shape[0] // 2)
            )
            log.info(f'自动加载地图成功: {self.chosen_area.full_name}')

        # 更新传送点列表和路线列表
        self._update_tp_list()
        self._update_route_list()
        self._update_large_map_display()

    def _update_tp_list(self) -> None:
        """更新传送点列表"""
        tp_list = []
        if self.chosen_large_map is not None:
            # 筛选出传送点图标 (template_id = map_icon_01)
            for icon in self.chosen_large_map.icon_list:
                if icon.template_id == 'map_icon_01':
                    display_name = icon.icon_name if icon.icon_name else f'传送点({icon.lm_pos.x}, {icon.lm_pos.y})'
                    tp_list.append(ConfigItem(display_name, icon))

        self.tp_combo_box.set_items(tp_list, self.chosen_tp_icon)

    def on_tp_changed(self, idx: int) -> None:
        """传送点选择变化"""
        self.chosen_tp_icon = self.tp_combo_box.itemData(idx)
        if self.chosen_route is not None:
            self.chosen_route.tp_name = self.chosen_tp_icon.icon_name
        self._update_btn_display()

    def _update_route_list(self) -> None:
        """更新路线列表"""
        route_list = []
        if self.chosen_area is not None:
            self.existing_routes = self.world_patrol_service.get_world_patrol_routes_by_area(self.chosen_area)
            for route in self.existing_routes:
                display_name = f'{route.idx:02d} - {route.tp_name} ({len(route.op_list)}步)'
                route_list.append(ConfigItem(display_name, route))

        self.route_combo_box.set_items(route_list, None)

    def on_route_changed(self, idx: int) -> None:
        """路线选择变化"""
        selected_route = self.route_combo_box.itemData(idx)
        if selected_route is not None:
            self.chosen_route = selected_route
            # 同步传送点选择
            for i in range(self.tp_combo_box.count()):
                tp_icon = self.tp_combo_box.itemData(i)
                if tp_icon and tp_icon.icon_name == selected_route.tp_name:
                    self.tp_combo_box.setCurrentIndex(i)
                    self.chosen_tp_icon = tp_icon
                    break
            self.current_pos = self.world_patrol_service.get_route_last_pos(self.chosen_route)
            log.info(f'加载路线: {selected_route.tp_name} ({len(selected_route.op_list)}步)')
            self._update_large_map_display()
        self._update_btn_display()

    def on_new_route_btn_clicked(self) -> None:
        """新增路线按钮点击"""
        if self.chosen_area is None:
            log.error('请先选择区域')
            return

        if self.chosen_tp_icon is None:
            log.error('请先选择传送点')
            return

        # 获取下一个可用的idx
        next_idx = self.world_patrol_service.get_next_route_idx(self.chosen_area)

        # 创建新的路线，使用选中的传送点名称
        tp_name = self.chosen_tp_icon.icon_name
        self.chosen_route = WorldPatrolRoute(
            tp_area=self.chosen_area,
            tp_name=tp_name,
            idx=next_idx,
        )
        log.info(f'新建路线: {self.chosen_area.full_name} - 传送点: {tp_name} (idx: {next_idx})')

        # 重置路线选择
        self.route_combo_box.setCurrentIndex(0)
        self._update_large_map_display()
        self._update_btn_display()

    def on_save_route_btn_clicked(self) -> None:
        """保存路线按钮点击"""
        if self.chosen_route is None:
            log.error('没有可保存的路线')
            return

        success = self.world_patrol_service.save_world_patrol_route(self.chosen_route)
        if success:
            log.info(f'路线保存成功: {self.chosen_route.tp_name}')
            # 刷新路线列表
            self._update_route_list()
        else:
            log.error('路线保存失败')

    def on_delete_route_btn_clicked(self) -> None:
        """删除路线按钮点击"""
        if self.chosen_route is None:
            log.error('没有可删除的路线')
            return

        if self.chosen_route.idx == 0:
            log.error('无法删除未保存的路线')
            return

        success = self.world_patrol_service.delete_world_patrol_route(self.chosen_route)
        if success:
            # 清除当前路线
            self.chosen_route = None

            # 刷新路线列表
            self._update_route_list()
            self.route_combo_box.setCurrentIndex(0)

            # 更新显示
            self._update_large_map_display()
            self._update_btn_display()

    def on_cancel_route_btn_clicked(self) -> None:
        """取消路线编辑按钮点击"""
        if self.chosen_route is None:
            log.info('没有正在编辑的路线')
            return

        log.info(f'取消编辑路线: {self.chosen_route.tp_name}')

        # 清除当前路线
        self.chosen_route = None

        # 重置路线选择
        self.route_combo_box.setCurrentIndex(-1)

        # 清除计算结果
        self.mini_map_pos_mr = None

        # 更新显示
        self._update_large_map_display()
        self._update_btn_display()

    def on_undo_move_btn_clicked(self) -> None:
        """回退移动操作按钮点击"""
        if self.chosen_route is None:
            log.error('没有正在编辑的路线')
            return

        if not self.chosen_route.op_list:
            log.info('路线中没有可回退的操作')
            return

        # 删除最后一个操作
        removed_op = self.chosen_route.op_list.pop()

        if removed_op.op_type == 'move' and len(removed_op.data) >= 2:
            log.info(f'回退移动操作: ({removed_op.data[0]}, {removed_op.data[1]}), 剩余操作数: {len(self.chosen_route.op_list)}')
        else:
            log.info(f'回退操作: {removed_op.op_type}, 剩余操作数: {len(self.chosen_route.op_list)}')

        # 更新显示
        self._update_large_map_display()
        self._update_btn_display()

    def _get_route_large_map_display(self) -> MatLike | None:
        """获取带路线可视化的大地图显示"""
        if self.large_map is None:
            return None

        # 复制原始地图显示逻辑
        to_display = cv2.cvtColor(self.large_map.road_mask, cv2.COLOR_GRAY2RGB)

        # 绘制地图图标
        for icon in self.large_map.icon_list:
            template = self.ctx.template_loader.get_template('map', icon.template_id)
            if template is None:
                continue

            # 将中心点坐标转换为左上角坐标进行渲染
            left_top_x = icon.lm_pos.x - template.raw.shape[1] // 2
            left_top_y = icon.lm_pos.y - template.raw.shape[0] // 2

            # 定义目标图像中的感兴趣区域 (ROI)
            y_start, y_end = left_top_y, left_top_y + template.raw.shape[0]
            x_start, x_end = left_top_x, left_top_x + template.raw.shape[1]

            # 边界检查
            if (y_start >= 0 and y_end <= to_display.shape[0] and
                x_start >= 0 and x_end <= to_display.shape[1]):
                roi = to_display[y_start:y_end, x_start:x_end]
                mask_condition = template.mask > 0
                roi[mask_condition] = template.raw[mask_condition]

        # 绘制路线可视化
        if self.chosen_route is not None:
            # 绘制传送点（起始点）
            if self.chosen_tp_icon is not None:
                tp_pos = (self.chosen_tp_icon.lm_pos.x, self.chosen_tp_icon.lm_pos.y)
                cv2.circle(to_display, tp_pos, 20, [255, 255, 0], 4)  # 黄色圆圈
                cv2.circle(to_display, tp_pos, 15, [0, 255, 255], 2)  # 青色内圈

            # 绘制移动路径点和连线
            move_points = []

            # 添加传送点作为起始点
            if self.chosen_tp_icon is not None:
                move_points.append((self.chosen_tp_icon.lm_pos.x, self.chosen_tp_icon.lm_pos.y))

            # 添加所有移动操作点
            for op in self.chosen_route.op_list:
                if op.op_type == 'move' and len(op.data) >= 2:
                    try:
                        x = int(op.data[0])
                        y = int(op.data[1])
                        move_points.append((x, y))
                    except (ValueError, IndexError):
                        continue

            # 绘制路径点
            for i, point in enumerate(move_points):
                if i == 0:
                    # 起始点（传送点）已经在上面绘制了
                    continue
                else:
                    # 移动点用绿色圆圈
                    cv2.circle(to_display, point, 8, [0, 255, 0], 2)
                    # 绘制序号
                    cv2.putText(to_display, str(i), (point[0]-5, point[1]-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, [255, 0, 0], 2)

            # 绘制连线
            for i in range(len(move_points) - 1):
                cv2.line(to_display, move_points[i], move_points[i + 1], [0, 255, 0], 2)

        return to_display

    def _on_key_press(self, event: ContextEventItem) -> None:
        key: str = event.data
        if key == '1':
            self.screenshot_requested.emit()
        elif key == '4':
            self.on_add_move_btn_clicked()
        elif key == '5':
            self.on_undo_move_btn_clicked()

    def on_screenshot_btn_clicked(self) -> None:
        if self.chosen_route is None:
            return
        if self.large_map is None:
            log.error('[截图] 请先选择区域加载地图')
            return

        log.info('[截图] 开始')
        _, screen = self.ctx.controller.screenshot()
        mini_map_wrapper = self.ctx.world_patrol_service.cut_mini_map(screen)
        self.mini_map = large_map_recorder_utils.create_mini_map_snapshot(self.ctx, mini_map_wrapper, 0.7)

        self._update_mini_map_display()
        log.info('[截图] 完成')

        self.mini_map_pos_mr = large_map_recorder_utils.cal_pos(
            self.ctx,
            self.large_map,
            self.mini_map,
            self.current_pos,
            use_icon=True
        )
        if self.mini_map_pos_mr is not None:
            log.info(f'[计算坐标] 当前坐标: {self.mini_map_pos_mr.center}')
            self.chosen_route.add_move_operation(self.mini_map_pos_mr.center)
            self._update_large_map_display()
        else:
            log.info(f'[计算坐标] 当前计算坐标失败')

        self._update_btn_display()

    def _update_mini_map_display(self) -> None:
        if self.mini_map is not None:
            self.mm_road_viewer.set_image(large_map_recorder_utils.get_mini_map_display(self.ctx, self.mini_map))

    def on_overlap_btn_clicked(self) -> None:
        """重叠按钮点击"""
        if self.chosen_large_map is None:
            return

        log.info('[重叠] 更改重叠显示方式')
        self.overlap_mode = (self.overlap_mode + 1) % 2
        self._update_large_map_display()

    def on_add_move_btn_clicked(self) -> None:
        """添加移动操作到路线"""
        if self.chosen_route is None:
            log.error('请先新建路线')
            return

        if self.mini_map_pos_mr is not None:
            pos = self.mini_map_pos_mr.center
        else:
            pos = self.current_pos
        self.chosen_route.add_move_operation(pos)

        log.info(f'[添加移动] 坐标: ({pos.x}, {pos.y}), 当前路线操作数: {len(self.chosen_route.op_list)}')

        # 清除当前计算结果，准备下一次操作
        self.mini_map_pos_mr = None
        self._update_large_map_display()
        self._update_btn_display()

    def _update_large_map_display(self) -> None:
        # 使用自定义的路线可视化显示
        to_display = self._get_route_large_map_display()

        if to_display is None:
            return

        self.lm_viewer.set_image(to_display)

    def on_large_map_clicked(self, x: int, y: int) -> None:
        clicked_point = Point(x, y)

        # 更新角色位置
        self.current_pos = clicked_point
        self.mini_map_pos_mr = None
        if self.auto_add_click_pos_opt.btn.checked:
            self.on_add_move_btn_clicked()
        log.info('[位置] 更新为点击位置')
        self._update_large_map_display()

    def _load_chosen_large_map(self) -> None:
        """
        加载大地图 要复制出来 防止在这里修改会影响到内存的值
        Returns:
            None
        """
        if self.chosen_area is None:
            return
        chosen_large_map = self.world_patrol_service.get_large_map_by_area_full_id(self.chosen_area.full_id)
        if chosen_large_map is None:
            self.chosen_large_map = WorldPatrolLargeMap(
                self.chosen_area.full_id,
                None,
                [],
            )
        else:
            self.chosen_large_map = WorldPatrolLargeMap(
                chosen_large_map.area_full_id,
                None if chosen_large_map.road_mask is None else chosen_large_map.road_mask.copy(),
                [] + chosen_large_map.icon_list
            )

    def on_debug_route_btn_clicked(self) -> None:
        if self.chosen_route is None:
            return
        self.ctx.world_patrol_service.load_data()
        if self.debug_runner.op is not None:
            self.debug_runner.op

        self.debug_runner.op = WorldPatrolRunRoute(self.ctx, self.chosen_route,
                                                   start_idx=self.debug_start_input.value())
        self.debug_runner.start()

    def on_edit_operations_btn_clicked(self) -> None:
        """编辑操作按钮点击"""
        if self.chosen_route is None:
            log.error('请先选择路线')
            return

        # 创建编辑对话框
        dialog = RouteOperationEditorDialog(self.chosen_route.op_list, self)
        dialog.operations_updated.connect(self._on_operations_updated)
        dialog.exec()

    def _on_operations_updated(self, updated_op_list: list) -> None:
        """操作列表更新后的处理"""
        if self.chosen_route is None:
            return

        # 更新路线的操作列表
        self.chosen_route.op_list = updated_op_list

        # 更新大地图显示
        self._update_large_map_display()

        # 更新按钮状态
        self._update_btn_display()

        log.info(f'路线操作已更新，当前操作数: {len(self.chosen_route.op_list)}')
