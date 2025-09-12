import time

import cv2
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from qfluentwidgets import FluentIcon, PushButton, SpinBox, DoubleSpinBox

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum
from one_dragon.utils import cv2_utils, cal_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.click_image_label import ClickImageLabel
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.image_viewer_widget import ImageViewerWidget
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiLineSettingCard, MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.devtools.large_map_recorder import large_map_recorder_utils
from zzz_od.application.devtools.large_map_recorder.large_map_recorder_wrapper import LargeMapSnapshot, MiniMapSnapshot
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolEntry, WorldPatrolArea, \
    WorldPatrolLargeMapIcon, WorldPatrolLargeMap
from zzz_od.application.world_patrol.world_patrol_service import WorldPatrolService
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.devtools.icon_editor_dialog import IconEditorDialog
from zzz_od.application.world_patrol.mini_map_wrapper import MiniMapWrapper


class LargeMapRecorderInterface(VerticalScrollInterface):

    screenshot_requested = Signal()
    cal_pos_requested = Signal()
    overlap_requested = Signal()
    merge_requested = Signal()

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.world_patrol_service: WorldPatrolService = WorldPatrolService(ctx)

        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='world_patrol_large_map_recorder_interface',
            nav_text_cn='大地图录制',
            parent=parent,
        )

        self.screenshot_requested.connect(self.on_screenshot_btn_clicked)
        self.cal_pos_requested.connect(self.on_cal_pos_btn_clicked)
        self.overlap_requested.connect(self.on_overlap_btn_clicked)
        self.merge_requested.connect(self.on_merge_btn_clicked)

        self.chosen_entry: WorldPatrolEntry | None = None
        self.chosen_area: WorldPatrolArea | None = None
        self.chosen_large_map: WorldPatrolLargeMap | None = None

        self.last_large_map: LargeMapSnapshot | None = None
        self.large_map: LargeMapSnapshot | None = None

        self.mini_map_1: MiniMapWrapper | None = None
        self.mini_map_2: MiniMapWrapper | None = None
        self.mini_map: MiniMapSnapshot | None = None

        self.last_pos: Point | None = None  # 记录上次的角色坐标
        self.current_pos: Point | None = None  # 记录的当前角色所在的坐标
        self.mini_map_pos_mr: MatchResult | None = None  # 计算的小地图在大地图上的坐标
        self.overlap_mode: int = 1  # 0=不重叠显示 1=填充

        # 图标编辑器相关
        self.icon_editor_dialog: IconEditorDialog | None = None
        self.highlighted_icon_index: int = -1  # 当前高亮的图标索引

        # 图标匹配阈值
        self.current_icon_threshold: float = 0.7

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

        self.area_opt = MultiPushSettingCard(
            icon=FluentIcon.GLOBE,
            title='区域',
            btn_list=[
                self.entry_combo_box,
                self.area_combo_box,
            ]
        )
        control_layout.addWidget(self.area_opt)

        self.load_btn = PushButton(text='加载')
        self.load_btn.clicked.connect(self.on_load_btn_clicked)
        self.save_btn = PushButton(text='保存')
        self.save_btn.clicked.connect(self.on_save_btn_clicked)
        self.delete_btn = PushButton(text='删除')
        self.delete_btn.clicked.connect(self.on_delete_btn_clicked)
        self.cancel_btn = PushButton(text='取消')
        self.cancel_btn.clicked.connect(self.on_cancel_btn_clicked)

        self.screenshot_btn = PushButton(text='截图(1)')
        self.screenshot_btn.clicked.connect(self.on_screenshot_btn_clicked)
        self.cal_pos_btn = PushButton(text='定位(2)')
        self.cal_pos_btn.clicked.connect(self.on_cal_pos_btn_clicked)
        self.overlap_btn = PushButton(text='重叠(3)')
        self.overlap_btn.clicked.connect(self.on_overlap_btn_clicked)
        self.merge_btn = PushButton(text='合并(4)')
        self.merge_btn.clicked.connect(self.on_merge_btn_clicked)
        self.back_btn = PushButton(text='回退')
        self.back_btn.clicked.connect(self.on_back_btn_clicked)
        self.edit_icons_btn = PushButton(text='编辑图标')
        self.edit_icons_btn.clicked.connect(self.on_edit_icons_btn_clicked)
        self.save_row = MultiLineSettingCard(
            icon=FluentIcon.SAVE, title='',
            line_list=[
                [
                    self.load_btn,
                    self.save_btn,
                    self.delete_btn,
                    self.cancel_btn,
                ],
                [
                    self.screenshot_btn,
                    self.cal_pos_btn,
                    self.overlap_btn,
                    self.merge_btn,
                    self.back_btn,
                ],
                [
                    self.edit_icons_btn,
                ]
            ]
        )
        control_layout.addWidget(self.save_row)

        self.icon_opt = SwitchSettingCard(
            icon=FluentIcon.INFO,
            title='使用图标计算坐标',
        )
        control_layout.addWidget(self.icon_opt)

        self.icon_threshold_input = DoubleSpinBox()
        self.icon_threshold_input.setMinimumWidth(140)
        self.icon_threshold_input.setMinimum(0.1)
        self.icon_threshold_input.setMaximum(1.0)
        self.icon_threshold_input.setSingleStep(0.1)
        self.icon_threshold_input.setDecimals(1)
        self.icon_threshold_input.setValue(0.7)
        self.icon_threshold_save_btn = PushButton(text=gt('应用'))
        self.icon_threshold_save_btn.clicked.connect(self._on_icon_threshold_save_clicked)
        self.icon_threshold_opt = MultiPushSettingCard(
            icon=FluentIcon.SEARCH,
            title='图标匹配阈值',
            content='调整图标识别的匹配阈值，默认0.7',
            btn_list=[self.icon_threshold_input, self.icon_threshold_save_btn]
        )
        control_layout.addWidget(self.icon_threshold_opt)

        self.scale_input = SpinBox()
        self.scale_input.setValue(40)
        self.scale_input.setMinimumWidth(140)
        self.scale_save_btn = PushButton(text=gt('应用'))
        self.scale_save_btn.clicked.connect(self._on_scale_save_clicked)
        self.scale_opt = MultiPushSettingCard(icon=FluentIcon.MOVE, title='缩放', content='调整大地图的，只有第一次需要',
                                              btn_list=[self.scale_input, self.scale_save_btn])
        control_layout.addWidget(self.scale_opt)

        self.h_move_input = SpinBox()
        self.h_move_input.setMinimumWidth(140)
        self.h_move_input.setMinimum(-9999)
        self.h_move_input.setMaximum(9999)
        self.h_btn = PushButton(text=gt('横移'))
        self.h_btn.clicked.connect(self._on_h_move_clicked)

        self.v_move_input = SpinBox()
        self.v_move_input.setMinimumWidth(140)
        self.v_move_input.setMinimum(-9999)
        self.v_move_input.setMaximum(9999)
        self.v_btn = PushButton(text=gt('纵移'))
        self.v_btn.clicked.connect(self._on_v_move_clicked)

        self.pos_label = QLabel()

        self.pos_display_opt = MultiPushSettingCard(
            icon=FluentIcon.GLOBE,
            title='角色坐标',
            content='点击大地图可更新坐标',
            btn_list=[
                self.pos_label,
                self.h_move_input,
                self.h_btn,
                self.v_move_input,
                self.v_btn,
            ]
        )
        control_layout.addWidget(self.pos_display_opt)

        self.log_card = LogDisplayCard()
        control_layout.addWidget(self.log_card)

        control_layout.addStretch(1)
        return control_widget

    def _init_mini_map_display_panel(self) -> QWidget:
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(12)

        self.mm_viewer_1 = ClickImageLabel()
        display_layout.addWidget(self.mm_viewer_1)
        self.mm_viewer_2 = ClickImageLabel()
        display_layout.addWidget(self.mm_viewer_2)
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
        chosen = self.chosen_large_map is not None
        has_large_map = self.large_map is not None

        if chosen:
            self.load_btn.setText(gt('重置'))
        else:
            self.load_btn.setText(gt('加载'))
        self.save_btn.setDisabled(not chosen)
        self.delete_btn.setDisabled(not chosen)
        self.cancel_btn.setDisabled(not chosen)
        self.edit_icons_btn.setDisabled(not has_large_map)

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)
        self.log_card.stop()

    def on_entry_changed(self, idx: int) -> None:
        self.chosen_entry = self.entry_combo_box.itemData(idx)
        self.update_area_opt()

    def on_area_changed(self, idx: int) -> None:
        self.chosen_area = self.area_combo_box.itemData(idx)

    def on_load_btn_clicked(self) -> None:
        self._load_chosen_large_map()

        if self.chosen_large_map.road_mask is None:
            self.large_map = None
            log.info('未有地图数据 新建')
        else:
            self.large_map = LargeMapSnapshot(
                world_patrol_large_map=self.chosen_large_map,
                pos_after_merge=Point(self.chosen_large_map.road_mask.shape[1] // 2, self.chosen_large_map.road_mask.shape[0] // 2)
            )
            log.info('加载成功')
            self.current_pos = self.large_map.pos_after_merge

        self._update_large_map_display()
        self._update_pos_display()
        self._update_btn_display()

    def on_save_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return

        area_id = self.chosen_large_map.area_full_id

        icon_list: list[WorldPatrolLargeMapIcon] = [
            WorldPatrolLargeMapIcon(
                icon_name=icon.icon_name,
                template_id=icon.template_id,
                lm_pos=[icon.lm_pos.x, icon.lm_pos.y],
                tp_pos=[icon.tp_pos.x, icon.tp_pos.y],
            )
            for icon in self.large_map.icon_list
        ]

        new_large_map = WorldPatrolLargeMap(
            area_id,
            self.large_map.road_mask.copy(),
            icon_list,
        )

        saved = self.world_patrol_service.save_world_patrol_large_map(
            self.chosen_area,
            new_large_map,
        )

        if saved:  # 保存成功的话，更改原来的值
            self._load_chosen_large_map()

    def on_delete_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return

        self.world_patrol_service.delete_world_patrol_large_map(self.chosen_area)
        self.chosen_large_map = None
        self.large_map = None
        self._update_btn_display()
        self._update_large_map_display()

    def on_cancel_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return
        self.chosen_large_map = None
        self.large_map = None
        self._update_btn_display()
        self._update_large_map_display()

    def _on_key_press(self, event: ContextEventItem) -> None:
        key: str = event.data
        if key == '1':
            self.screenshot_requested.emit()
        elif key == '2':
            self.cal_pos_requested.emit()
        elif key == '3':
            self.overlap_requested.emit()
        elif key == '4':
            self.merge_requested.emit()

    def on_screenshot_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return

        log.info('[截图] 计算小地图道路 开始')
        _, screen = self.ctx.controller.screenshot()
        self.mini_map_1 = self.ctx.world_patrol_service.cut_mini_map(screen)
        snapshot_1 = large_map_recorder_utils.create_mini_map_snapshot(self.ctx, self.mini_map_1, self.current_icon_threshold)

        self.ctx.controller.turn_by_angle_diff(180)
        time.sleep(2)
        _, screen = self.ctx.controller.screenshot()
        self.mini_map_2 = self.ctx.world_patrol_service.cut_mini_map(screen)
        snapshot_2 = large_map_recorder_utils.create_mini_map_snapshot(self.ctx, self.mini_map_2, self.current_icon_threshold)

        self.mini_map = large_map_recorder_utils.merge_mini_map(snapshot_1, snapshot_2)

        self._update_mini_map_display()
        log.info('[截图] 计算小地图道路 完成')

    def _update_mini_map_display(self) -> None:
        self.mm_viewer_1.set_image(self.mini_map_1.rgb)
        self.mm_viewer_2.set_image(self.mini_map_2.rgb)
        self.mm_road_viewer.set_image(large_map_recorder_utils.get_mini_map_display(self.ctx, self.mini_map))

    def on_cal_pos_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return

        if self.large_map is None or self.mini_map is None:
            log.info('[计算坐标] 当前未有地图 跳过')
            return

        log.info('[计算坐标] 开始')

        if self.current_pos is None:
            log.error('[计算坐标] 未有上次坐标 请选点击选择一个坐标')
            return

        self.mini_map_pos_mr = large_map_recorder_utils.cal_pos(
            self.ctx,
            self.large_map,
            self.mini_map,
            self.current_pos,
            use_icon=self.icon_opt.btn.checked
        )
        self._update_large_map_display()

        log.info(f'[计算坐标] 完成 当前坐标: {self.mini_map_pos_mr.center}')

    def on_overlap_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return

        log.info('[重叠] 更改重叠显示方式')
        self.overlap_mode = (self.overlap_mode + 1) % 2
        self._update_large_map_display()

    def on_merge_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return

        if self.mini_map is None:
            return

        log.info('[合并到大地图] 开始')

        self.last_large_map = self.large_map
        self.large_map = large_map_recorder_utils.merge_large_map(
            self.large_map,
            self.mini_map,
            self.mini_map_pos_mr
        )
        self.last_pos = self.current_pos
        self.current_pos = self.large_map.pos_after_merge

        self.mini_map_pos_mr = None
        self._update_large_map_display()
        self._update_pos_display()
        log.info('[合并到大地图] 完成')

    def on_back_btn_clicked(self) -> None:
        if self.chosen_large_map is None:
            return

        log.info('[回退] 恢复上一步大地图 只能恢复一次')
        self.large_map = self.last_large_map
        self.current_pos = self.last_pos
        self._update_large_map_display()
        self._update_pos_display()

    def on_edit_icons_btn_clicked(self) -> None:
        """打开图标编辑器"""
        if self.large_map is None or not self.large_map.icon_list:
            log.info('没有可编辑的图标')
            return

        # 如果对话框已存在，则显示并激活
        if self.icon_editor_dialog is not None:
            self.icon_editor_dialog.show()
            self.icon_editor_dialog.activateWindow()
            return

        # 创建新的图标编辑器对话框
        self.icon_editor_dialog = IconEditorDialog(self.large_map.icon_list, self)
        self.icon_editor_dialog.icon_selected.connect(self._on_icon_selected)
        self.icon_editor_dialog.icons_saved.connect(self._on_icons_saved)
        self.icon_editor_dialog.finished.connect(self._on_icon_editor_closed)

        self.icon_editor_dialog.show()

    def _on_icon_selected(self, icon_index: int):
        """处理图标选择事件"""
        self.highlighted_icon_index = icon_index
        self._update_large_map_display()

    def _on_icons_saved(self, icon_list: list[WorldPatrolLargeMapIcon]):
        """处理图标保存事件"""
        if self.large_map is not None:
            self.large_map.icon_list = icon_list
            self._update_large_map_display()
            log.info('图标列表已更新')

    def _on_icon_editor_closed(self):
        """处理图标编辑器关闭事件"""
        self.icon_editor_dialog = None
        self.highlighted_icon_index = -1
        self._update_large_map_display()

    def get_current_calculated_pos(self):
        """获取当前计算的坐标，供图标编辑器使用"""
        if self.mini_map_pos_mr is not None:
            # 如果有小地图匹配结果，返回其中心点坐标
            return self.mini_map_pos_mr.center
        elif self.current_pos is not None:
            # 如果有当前位置，返回当前位置
            return self.current_pos
        else:
            # 没有可用坐标
            return None

    def _update_large_map_display(self) -> None:
        to_display = large_map_recorder_utils.get_large_map_display(self.ctx, self.large_map)
        if self.large_map is None:
            pass
        elif self.overlap_mode == 0:
            pass
        elif self.mini_map_pos_mr is not None:
            mini_map = large_map_recorder_utils.get_mini_map_display(self.ctx, self.mini_map)
            cv2_utils.source_overlap_template(
                to_display, mini_map,
                self.mini_map_pos_mr.x, self.mini_map_pos_mr.y,
                template_mask=large_map_recorder_utils.get_mini_map_circle_mask(self.mini_map.road_mask.shape[0]),
            )
        elif self.current_pos is not None:
            cv2.circle(to_display, self.current_pos.tuple(), 2, [0, 0, 255], -1)
        else:
            pass

        # 高亮选中的图标
        if (self.large_map is not None and
            0 <= self.highlighted_icon_index < len(self.large_map.icon_list)):
            icon = self.large_map.icon_list[self.highlighted_icon_index]
            # 现在保存的已经是中心点坐标，直接使用
            cv2.circle(to_display, (icon.lm_pos.x, icon.lm_pos.y), 15, [0, 0, 255], 3)

        self.lm_viewer.set_image(to_display)

    def on_large_map_clicked(self, x: int, y: int) -> None:
        clicked_point = Point(x, y)

        # 检查是否点击了图标
        if self.large_map is not None and self.large_map.icon_list:
            for i, icon in enumerate(self.large_map.icon_list):
                # 检查点击位置是否在图标附近（20像素范围内）
                if cal_utils.distance_between(clicked_point, icon.lm_pos) <= 20:
                    self.highlighted_icon_index = i
                    # 如果图标编辑器打开，则在编辑器中高亮对应行
                    if self.icon_editor_dialog is not None:
                        self.icon_editor_dialog.highlight_icon(i)
                    self._update_large_map_display()
                    log.info(f'[图标] 选中图标 {icon.template_id} 位置 ({icon.lm_pos.x}, {icon.lm_pos.y})')
                    return

        # 如果没有点击图标，则更新角色位置
        self.current_pos = clicked_point
        self.mini_map_pos_mr = None
        self.highlighted_icon_index = -1  # 清除图标高亮
        log.info('[位置] 更新为点击位置')
        self._update_large_map_display()
        self._update_pos_display()

    def _update_pos_display(self) -> None:
        if self.current_pos is None:
            return
        self.pos_label.setText(str(self.current_pos))

    def _on_h_move_clicked(self):
        try:
            dx = self.h_move_input.value()

            if self.mini_map_pos_mr is not None:
                self.mini_map_pos_mr.add_offset(Point(dx, 0))
            elif self.current_pos is not None:
                self.current_pos += Point(dx, 0)

            self._update_large_map_display()
            self._update_pos_display()
        except Exception:
            pass

    def _on_v_move_clicked(self):
        try:
            dy = self.v_move_input.value()

            if self.mini_map_pos_mr is not None:
                self.mini_map_pos_mr.add_offset(Point(0, dy))
            elif self.current_pos is not None:
                self.current_pos += Point(0, dy)

            self._update_large_map_display()
            self._update_pos_display()
        except Exception:
            pass

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

    def _on_scale_save_clicked(self):
        if self.large_map is None:
            return

        f = self.scale_input.value() / 100.0
        self.large_map.road_mask = cv2.resize(self.large_map.road_mask, (0, 0), fx=f, fy=f)
        self.large_map = large_map_recorder_utils._expand_edges_if_needed(self.large_map, (210, 210))

        self._update_large_map_display()

    def _on_icon_threshold_save_clicked(self):
        """保存图标匹配阈值"""
        self.current_icon_threshold = self.icon_threshold_input.value()
        log.info(f'图标匹配阈值已更新为: {self.current_icon_threshold}')
