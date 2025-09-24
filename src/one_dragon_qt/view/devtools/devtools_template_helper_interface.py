import os
import cv2
from PySide6.QtWidgets import QWidget, QSizePolicy, QFileDialog, QTableWidgetItem, QMessageBox, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from qfluentwidgets import (FluentIcon, InfoBarIcon, PushButton, ToolButton, CaptionLabel, LineEdit,
                            SingleDirectionScrollArea, TableWidget, TeachingTip, TeachingTipTailPosition)
from typing import Optional, Any

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.screen.template_info import TemplateInfo, TemplateShapeEnum
from one_dragon.utils import os_utils, cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.mixins.history_mixin import HistoryMixin
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.fixed_size_image_label import FixedSizeImageLabel
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.zoomable_image_label import ZoomableClickImageLabel


class DevtoolsTemplateHelperInterface(VerticalScrollInterface, HistoryMixin):

    def __init__(self, ctx: OneDragonContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='devtools_template_helper_interface',
            parent=parent,
            content_widget=None,
            nav_text_cn='模板管理'
        )
        self._init_history()  # 初始化历史记录功能

        self.ctx: OneDragonContext = ctx
        self.chosen_template: Optional[TemplateInfo] = None
        self.last_screen_dir: Optional[str] = None  # 上一次选择的图片路径


    def get_content_widget(self) -> QWidget:
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        left_panel = self._init_left_part()
        mid_panel = self._init_mid_part()
        right_panel = self._init_right_part()

        main_layout.addWidget(left_panel)
        main_layout.addWidget(mid_panel)
        main_layout.addWidget(right_panel, 1)

        return main_widget

    def _init_left_part(self) -> QWidget:
        scroll_area = SingleDirectionScrollArea()

        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(12, 0, 12, 0)
        control_layout.setSpacing(6)

        btn_row = Row(spacing=6, margins=(0, 0, 0, 0))
        control_layout.addWidget(btn_row)

        self.existed_yml_btn = EditableComboBox()
        self.existed_yml_btn.setPlaceholderText(gt('选择已有'))
        self.existed_yml_btn.currentIndexChanged.connect(self._on_choose_existed_yml)
        btn_row.add_widget(self.existed_yml_btn, stretch=1)

        self.create_btn = PushButton(text=gt('新建'))
        self.create_btn.clicked.connect(self._on_create_clicked)
        btn_row.add_widget(self.create_btn)

        self.copy_btn = PushButton(text=gt('复制'))
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        btn_row.add_widget(self.copy_btn)

        self.delete_btn = ToolButton(FluentIcon.DELETE)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row.add_widget(self.delete_btn)

        self.cancel_btn = PushButton(text=gt('取消'))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.add_widget(self.cancel_btn)

        save_row = Row(spacing=6, margins=(0, 0, 0, 0))
        control_layout.addWidget(save_row)

        save_row.add_stretch(1)

        self.choose_image_btn = PushButton(text=gt('选择图片'))
        self.choose_image_btn.clicked.connect(self.choose_existed_image)
        save_row.add_widget(self.choose_image_btn)

        self.save_config_btn = PushButton(text=gt('保存配置'))
        self.save_config_btn.clicked.connect(self._on_save_config_clicked)
        save_row.add_widget(self.save_config_btn)

        self.save_raw_btn = PushButton(text=gt('保存模板'))
        self.save_raw_btn.clicked.connect(self._on_save_raw_clicked)
        save_row.add_widget(self.save_raw_btn)

        self.save_mask_btn = PushButton(text=gt('保存掩码'))
        self.save_mask_btn.clicked.connect(self._on_save_mask_clicked)
        save_row.add_widget(self.save_mask_btn)

        self.template_sub_dir_opt = TextSettingCard(icon=FluentIcon.HOME, title='画面')
        self.template_sub_dir_opt.line_edit.setFixedWidth(240)
        self.template_sub_dir_opt.value_changed.connect(self._on_template_sub_dir_changed)
        control_layout.addWidget(self.template_sub_dir_opt)

        self.template_id_opt = TextSettingCard(icon=FluentIcon.HOME, title='模板ID')
        self.template_id_opt.line_edit.setFixedWidth(240)
        self.template_id_opt.value_changed.connect(self._on_template_id_changed)
        control_layout.addWidget(self.template_id_opt)

        self.template_name_opt = TextSettingCard(icon=FluentIcon.HOME, title='模板名称')
        self.template_name_opt.line_edit.setFixedWidth(240)
        self.template_name_opt.value_changed.connect(self._on_template_name_changed)
        control_layout.addWidget(self.template_name_opt)

        self.h_move_input = LineEdit()
        self.h_move_input.setPlaceholderText(gt('横'))
        self.h_move_input.setClearButtonEnabled(True)
        self.h_move_input.setFixedWidth(90)

        self.v_move_input = LineEdit()
        self.v_move_input.setPlaceholderText(gt('纵'))
        self.v_move_input.setClearButtonEnabled(True)
        self.v_move_input.setFixedWidth(90)

        self.move_btn = PushButton(text=gt('移动'))
        self.move_btn.clicked.connect(self._on_move_clicked)

        self.move_opt = MultiPushSettingCard(icon=FluentIcon.MOVE, title='微调',
                                             btn_list=[self.h_move_input, self.v_move_input, self.move_btn])
        control_layout.addWidget(self.move_opt)

        self.template_shape_opt = ComboBox()
        shape_items = [shape.value for shape in TemplateShapeEnum]
        self.template_shape_opt.set_items(shape_items)
        self.template_shape_opt.currentIndexChanged.connect(self._on_template_shape_changed)

        self.shape_help_btn = ToolButton(FluentIcon.HELP)
        self.shape_help_btn.setToolTip('点击查看形状使用说明')
        self.shape_help_btn.clicked.connect(self._show_template_shape_help)

        self.template_shape_help_opt = MultiPushSettingCard(
            icon=FluentIcon.FIT_PAGE,
            title='形状',
            btn_list=[self.template_shape_opt, self.shape_help_btn]
        )

        control_layout.addWidget(self.template_shape_help_opt)

        self.auto_mask_opt = SwitchSettingCard(icon=FluentIcon.HOME, title='自动生成掩码')
        self.auto_mask_opt.value_changed.connect(self._on_auto_mask_changed)
        control_layout.addWidget(self.auto_mask_opt)

        self.point_table = TableWidget()
        self.point_table.setBorderVisible(True)
        self.point_table.setBorderRadius(8)
        self.point_table.setWordWrap(True)
        self.point_table.setColumnCount(2)
        self.point_table.setColumnWidth(0, 40)  # 操作
        # 设置最后一列占用剩余空间
        self.point_table.horizontalHeader().setStretchLastSection(True)
        self.point_table.verticalHeader().hide()
        self.point_table.setHorizontalHeaderLabels([
            gt('操作'),
            gt('点位'),
        ])
        self.point_table.cellChanged.connect(self._on_point_table_cell_changed)
        self.point_table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        control_layout.addWidget(self.point_table)

        control_layout.addStretch(1)

        scroll_area.setWidget(control_widget)
        scroll_area.setWidgetResizable(True)

        return scroll_area

    def _init_mid_part(self) -> QWidget:
        scroll_area = SingleDirectionScrollArea()

        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 12, 0)
        control_layout.setSpacing(2)

        raw_label = CaptionLabel(text=gt('模板原图'))
        control_layout.addWidget(raw_label)

        self.template_raw_label = FixedSizeImageLabel(140)
        control_layout.addWidget(self.template_raw_label)

        mask_label = CaptionLabel(text=gt('模板掩码'))
        control_layout.addWidget(mask_label)

        self.template_mask_label = FixedSizeImageLabel(140)
        control_layout.addWidget(self.template_mask_label)

        merge_label = CaptionLabel(text=gt('模板抠图'))
        control_layout.addWidget(merge_label)

        self.template_merge_label = FixedSizeImageLabel(140)
        control_layout.addWidget(self.template_merge_label)

        reversed_label = CaptionLabel(text=gt('反向抠图'))
        control_layout.addWidget(reversed_label)

        self.template_reversed_label = FixedSizeImageLabel(140)
        control_layout.addWidget(self.template_reversed_label)

        control_layout.addStretch(1)

        scroll_area.setWidget(control_widget)
        scroll_area.setWidgetResizable(True)

        return scroll_area

    def _init_right_part(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.x_pos_label = LineEdit()
        self.x_pos_label.setReadOnly(True)
        self.x_pos_label.setPlaceholderText(gt('横'))

        self.y_pos_label = LineEdit()
        self.y_pos_label.setReadOnly(True)
        self.y_pos_label.setPlaceholderText(gt('纵'))

        self.clear_points_btn = PushButton(text=gt('清除点位'))
        self.clear_points_btn.clicked.connect(self._on_clear_points_clicked)

        self.image_click_pos_opt = MultiPushSettingCard(icon=FluentIcon.MOVE, title='鼠标点击坐标',
                                                        content='图片左上角为(0, 0)',
                                                        btn_list=[self.x_pos_label, self.y_pos_label, self.clear_points_btn])
        layout.addWidget(self.image_click_pos_opt)

        # 使用Mixin创建历史记录UI
        history_ui = self._create_history_ui()
        layout.addWidget(history_ui)

        self.image_label = ZoomableClickImageLabel()
        self.image_label.left_clicked_with_pos.connect(self._on_image_left_clicked)
        self.image_label.right_clicked_with_pos.connect(self._on_image_right_clicked)
        self.image_label.rect_selected.connect(self._on_image_rect_selected)
        layout.addWidget(self.image_label, stretch=1)

        return widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self._update_whole_display()
        # 设置焦点以便键盘快捷键能正常工作
        self.setFocus()

    def _update_whole_display(self) -> None:
        """
        根据画面图片，统一更新界面的显示
        :return:
        """
        chosen = self.chosen_template is not None

        self.existed_yml_btn.setDisabled(chosen)
        self.create_btn.setDisabled(chosen)
        self.copy_btn.setDisabled(not chosen)
        self.delete_btn.setDisabled(not chosen)
        self.cancel_btn.setDisabled(not chosen)

        self.choose_image_btn.setDisabled(not chosen)
        self.save_config_btn.setDisabled(not chosen)
        self.save_raw_btn.setDisabled(not chosen)
        self.save_mask_btn.setDisabled(not chosen)
        self.clear_points_btn.setDisabled(not chosen)

        self.h_move_input.setDisabled(not chosen)
        self.v_move_input.setDisabled(not chosen)
        self.move_btn.setDisabled(not chosen)
        self.move_opt.setDisabled(not chosen)

        self.template_sub_dir_opt.setDisabled(not chosen)
        self.template_id_opt.setDisabled(not chosen)
        self.template_name_opt.setDisabled(not chosen)
        self.template_shape_help_opt.setDisabled(not chosen)
        self.auto_mask_opt.setDisabled(not chosen)

        if not chosen:  # 清除一些值
            self.template_sub_dir_opt.setValue('')
            self.template_id_opt.setValue('')
            self.template_name_opt.setValue('')
            self.template_shape_opt.setCurrentIndex(-1)
            self.auto_mask_opt.setValue(True)
            self.x_pos_label.setText('')
            self.y_pos_label.setText('')
            self._clear_history()
        else:
            self.template_sub_dir_opt.setValue(self.chosen_template.sub_dir)
            self.template_id_opt.setValue(self.chosen_template.template_id)
            self.template_name_opt.setValue(self.chosen_template.template_name)
            self.template_shape_opt.init_with_value(self.chosen_template.template_shape)
            self.auto_mask_opt.setValue(self.chosen_template.auto_mask)

        self._update_existed_yml_options()
        self._update_all_image_display()
        self._update_point_table_display()

    def _update_existed_yml_options(self) -> None:
        """
        更新已有的yml选项
        :return:
        """
        template_info_list: list[TemplateInfo] = self.ctx.template_loader.get_all_template_info_from_disk(need_raw=False, need_config=True)
        config_list: list[ConfigItem] = [
            ConfigItem(label=template_info.template_name, value=template_info)
            for template_info in template_info_list
        ]
        self.existed_yml_btn.set_items(config_list, self.chosen_template)

    def _update_point_table_display(self):
        """
        更新区域表格的显示
        :return:
        """
        self.point_table.blockSignals(True)
        point_list: list[Point] = [] if self.chosen_template is None else self.chosen_template.point_list
        point_cnt = len(point_list)
        self.point_table.setRowCount(point_cnt)

        # 如果没有数据行，隐藏表格；否则显示表格
        if point_cnt == 0:
            self.point_table.hide()
        else:
            self.point_table.show()

            for idx in range(point_cnt):
                point_item = point_list[idx]
                del_btn = ToolButton(FluentIcon.DELETE, parent=None)
                del_btn.setFixedSize(32, 32)
                del_btn.clicked.connect(self._on_row_delete_clicked)

                self.point_table.setCellWidget(idx, 0, del_btn)
                self.point_table.setItem(idx, 1, QTableWidgetItem('%d, %d' % (point_item.x, point_item.y)))

            # 根据行数调整表格高度
            row_height = self.point_table.rowHeight(0) if self.point_table.rowCount() > 0 else 32
            header_height = self.point_table.horizontalHeader().height()
            total_height = header_height + point_cnt * row_height + 4  # 4像素的边距
            self.point_table.setFixedHeight(total_height)

        self.point_table.blockSignals(False)

    def _show_template_shape_help(self) -> None:
        """
        显示模板形状帮助的TeachingTip
        :return:
        """
        if self.chosen_template is None:
            TeachingTip.create(
                target=self.template_shape_opt,
                icon=InfoBarIcon.WARNING,
                title='温馨提示',
                content="请先选择或创建模板",
                isClosable=True,
                tailPosition=TeachingTipTailPosition.RIGHT,
                duration=3000,
                parent=self
            )
            return

        help_text = ""
        shape = self.chosen_template.template_shape

        if shape == TemplateShapeEnum.RECTANGLE.value.value:
            help_text = "矩形模板：左键拖拽选择矩形区域，或单击两个对角点"
        elif shape == TemplateShapeEnum.CIRCLE.value.value:
            help_text = "圆形模板：左键拖拽选择外接矩形，或单击圆心和边界点"
        elif shape == TemplateShapeEnum.QUADRILATERAL.value.value:
            help_text = "四边形模板：左键拖拽选择矩形区域，或依次单击四个顶点"
        elif shape == TemplateShapeEnum.POLYGON.value.value:
            help_text = "多边形模板：左键单击添加顶点，或拖拽添加矩形顶点"
        elif shape == TemplateShapeEnum.MULTI_RECT.value.value:
            help_text = "多矩形模板：左键拖拽添加矩形区域，或单击添加点位"
        else:
            help_text = "左键单击添加点位，右键显示颜色信息"

        help_text += "\n\n快捷键：Ctrl+左键拖拽移动图片，滚轮缩放\nCtrl+Z撤销，Ctrl+Shift+Z恢复，Del清除"

        TeachingTip.create(
            target=self.template_shape_opt,
            icon=InfoBarIcon.SUCCESS,
            title='形状使用说明',
            content=help_text,
            isClosable=True,
            tailPosition=TeachingTipTailPosition.RIGHT,
            duration=-1,  # 不自动消失
            parent=self
        )

    def _update_all_image_display(self) -> None:
        """
        更新所有图片的显示
        :return:
        """
        self._update_screen_image_display()
        self._update_template_raw_display()
        self._update_template_mask_display()
        self._update_template_merge_display()
        self._update_template_reversed_merge_display()

    def _update_screen_image_display(self):
        """
        更新游戏画面图片的显示
        :return:
        """
        image_to_show = self.chosen_template.get_screen_image_to_display() if self.chosen_template is not None else None

        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.image_label.setImage(image, preserve_state=True)
        else:
            self.image_label.setImage(None)

    def _update_template_raw_display(self) -> None:
        """
        更新模板原图的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_raw_to_display() if self.chosen_template is not None else None
        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_raw_label.setImage(image)
        else:
            self.template_raw_label.setImage(None)

    def _update_template_mask_display(self) -> None:
        """
        更新模板掩码的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_mask_to_display() if self.chosen_template is not None else None

        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_mask_label.setImage(image)
        else:
            self.template_mask_label.setImage(None)

    def _update_template_merge_display(self) -> None:
        """
        更新模板抠图的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_merge_to_display() if self.chosen_template is not None else None

        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_merge_label.setImage(image)
        else:
            self.template_merge_label.setImage(None)

    def _update_template_reversed_merge_display(self) -> None:
        """
        更新反向抠图的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_reversed_merge_to_display() if self.chosen_template is not None else None

        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_reversed_label.setImage(image)
        else:
            self.template_reversed_label.setImage(None)

    def _on_choose_existed_yml(self, idx: int):
        """
        选择了已有的yml
        :param idx:
        :return:
        """
        self.chosen_template: TemplateInfo = self.existed_yml_btn.items[idx].userData
        self._update_whole_display()

    def _on_create_clicked(self):
        """
        创建一个新的
        :return:
        """
        if self.chosen_template is not None:
            return

        self.chosen_template = TemplateInfo('', '')
        self._update_whole_display()

    def _on_copy_clicked(self):
        """
        复制一个
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.copy_new()
        self._update_whole_display()

    def _on_save_config_clicked(self) -> None:
        """
        保存配置
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.save_config()
        self._update_existed_yml_options()

    def _on_save_raw_clicked(self) -> None:
        """
        保存配置
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.save_raw()
        self._update_existed_yml_options()

    def _on_save_mask_clicked(self) -> None:
        """
        保存掩码
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.save_mask()
        self._update_existed_yml_options()

    def _on_clear_points_clicked(self) -> None:
        """
        清除所有点位
        :return:
        """
        if self.chosen_template is None:
            return

        if len(self.chosen_template.point_list) > 0:
            self._add_history_record({'type': 'clear_points', 'old_points': [Point(p.x, p.y) for p in self.chosen_template.point_list]})
            self.chosen_template.point_list.clear()
            self.chosen_template.point_updated = True
            self._update_point_table_display()
            self._update_all_image_display()

    def _on_delete_clicked(self) -> None:
        """
        删除
        :return:
        """
        if self.chosen_template is None:
            return
        self.chosen_template.delete()
        self.chosen_template = None
        self._update_whole_display()

    def _on_cancel_clicked(self) -> None:
        """
        取消编辑
        :return:
        """
        if self.chosen_template is None:
            return
        self.chosen_template = None
        self.existed_yml_btn.setCurrentIndex(-1)
        self._update_whole_display()

    def choose_existed_image(self) -> None:
        """
        选择已有的环图片
        :return:
        """
        if self.last_screen_dir is not None:
            default_dir = self.last_screen_dir
        else:
            default_dir = os_utils.get_path_under_work_dir('.debug', 'images')

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            gt('选择图片'),
            dir=default_dir,
            filter="PNG (*.png)",
        )
        if file_path is not None and file_path.endswith('.png'):
            fix_file_path = os.path.normpath(file_path)
            log.info('选择路径 %s', fix_file_path)
            self.last_screen_dir = os.path.dirname(fix_file_path)
            self._on_image_chosen(fix_file_path)

    def _on_image_chosen(self, image_file_path: str) -> None:
        """
        选择图片之后的回调
        :param image_file_path:
        :return:
        """
        if self.chosen_template is None:
            return

        self.chosen_template.screen_image = cv2_utils.read_image(image_file_path)
        self.chosen_template.point_updated = True
        self._update_all_image_display()

    def _on_template_sub_dir_changed(self, value: str) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.sub_dir = value

    def _on_template_id_changed(self, value: str) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.template_id = value

    def _on_template_name_changed(self, value: str) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.template_name = value

    def _on_template_shape_changed(self, idx: int) -> None:
        if self.chosen_template is None or idx < 0:
            return

        value = self.template_shape_opt.currentData()
        if value is not None:
            self.chosen_template.update_template_shape(value)
            self._update_point_table_display()
            self._update_all_image_display()

    def _on_auto_mask_changed(self, value: bool) -> None:
        if self.chosen_template is None:
            return

        self.chosen_template.auto_mask = value
        self._update_all_image_display()

    def _on_row_delete_clicked(self):
        """
        删除一行
        :return:
        """
        if self.chosen_template is None:
            return

        button_idx = self.sender()
        if button_idx is not None:
            row_idx = self.point_table.indexAt(button_idx.pos()).row()
            if 0 <= row_idx < len(self.chosen_template.point_list):
                removed_point = self.chosen_template.point_list[row_idx]
                self._add_history_record({
                    'type': 'remove_point',
                    'removed_index': row_idx,
                    'removed_point': Point(removed_point.x, removed_point.y),
                    'old_points': [Point(p.x, p.y) for p in self.chosen_template.point_list]
                })
                self.chosen_template.remove_point_by_idx(row_idx)
                self.point_table.removeRow(row_idx)
                self._update_all_image_display()

    def _on_point_table_cell_changed(self, row: int, column: int) -> None:
        """
        表格内容改变
        :param row:
        :param column:
        :return:
        """
        if self.chosen_template is None:
            return
        if row < 0 or row >= len(self.chosen_template.point_list):
            return
        text = self.point_table.item(row, column).text().strip()
        if column == 1:
            num_list = [int(i) for i in text.split(',')]
            if len(num_list) >= 2:
                old_point = Point(self.chosen_template.point_list[row].x, self.chosen_template.point_list[row].y)
                new_point = Point(num_list[0], num_list[1])
                self._add_history_record({
                    'type': 'table_edit',
                    'row_index': row,
                    'old_point': old_point,
                    'new_point': new_point,
                    'old_points': [Point(p.x, p.y) for p in self.chosen_template.point_list]
                })
                self.chosen_template.point_list[row] = new_point
                self.chosen_template.point_updated = True
                self._update_all_image_display()

    def _on_image_left_clicked(self, x1: int, y1: int) -> None:
        """
        图片上点击后显示坐标
        :return:
        """
        if self.chosen_template is None or self.chosen_template.screen_image is None:
            return

        # 显示坐标
        self.x_pos_label.setText(str(x1))
        self.y_pos_label.setText(str(y1))

        new_point = Point(x1, y1)
        self._add_history_record({
            'type': 'add_point',
            'new_point': new_point,
            'old_points': [Point(p.x, p.y) for p in self.chosen_template.point_list]
        })
        self.chosen_template.add_point(new_point)

        self._update_point_table_display()
        self._update_all_image_display()

    def _on_image_rect_selected(self, left: int, top: int, right: int, bottom: int) -> None:
        """
        图片上矩形选择后的处理
        :param left: 左上角x坐标
        :param top: 左上角y坐标
        :param right: 右下角x坐标
        :param bottom: 右下角y坐标
        :return:
        """
        if self.chosen_template is None or self.chosen_template.screen_image is None:
            return

        old_points = [Point(p.x, p.y) for p in self.chosen_template.point_list]
        self._add_history_record({
            'type': 'rect_selected',
            'rect_area': (left, top, right, bottom),
            'old_points': old_points
        })

        # 根据模板形状处理矩形选择
        if self.chosen_template.template_shape == TemplateShapeEnum.RECTANGLE.value.value:
            # 矩形模板：使用矩形的左上角和右下角
            self.chosen_template.point_list = [Point(left, top), Point(right, bottom)]
            self.chosen_template.point_updated = True
        elif self.chosen_template.template_shape == TemplateShapeEnum.CIRCLE.value.value:
            # 圆形模板：使用矩形的中心点和边界计算半径
            center_x = (left + right) // 2
            center_y = (top + bottom) // 2
            radius = max(abs(right - left), abs(bottom - top)) // 2
            self.chosen_template.point_list = [Point(center_x, center_y), Point(center_x + radius, center_y)]
            self.chosen_template.point_updated = True
        elif self.chosen_template.template_shape == TemplateShapeEnum.QUADRILATERAL.value.value:
            # 四边形模板：使用矩形的四个角点
            self.chosen_template.point_list = [
                Point(left, top),      # 左上角
                Point(right, top),     # 右上角
                Point(right, bottom),  # 右下角
                Point(left, bottom)    # 左下角
            ]
            self.chosen_template.point_updated = True
        elif self.chosen_template.template_shape == TemplateShapeEnum.MULTI_RECT.value.value:
            # 多矩形模板：添加矩形的左上角和右下角作为新的矩形
            self.chosen_template.point_list.extend([Point(left, top), Point(right, bottom)])
            self.chosen_template.point_updated = True
        elif self.chosen_template.template_shape == TemplateShapeEnum.POLYGON.value.value:
            # 多边形模板：添加矩形的四个角点
            self.chosen_template.point_list.extend([
                Point(left, top),      # 左上角
                Point(right, top),     # 右上角
                Point(right, bottom),  # 右下角
                Point(left, bottom)    # 左下角
            ])
            self.chosen_template.point_updated = True

        self._update_point_table_display()
        self._update_all_image_display()

    def _on_move_clicked(self) -> None:
        """
        同时移动所有点位的横纵坐标
        """
        if self.chosen_template is None:
            return

        try:
            h_text = self.h_move_input.text().strip()
            v_text = self.v_move_input.text().strip()

            dx = int(h_text) if h_text else 0
            dy = int(v_text) if v_text else 0

            if dx != 0 or dy != 0:
                old_points = [Point(p.x, p.y) for p in self.chosen_template.point_list]
                self._add_history_record({
                    'type': 'move_points',
                    'dx': dx,
                    'dy': dy,
                    'old_points': old_points
                })
                self.chosen_template.update_all_points(dx, dy)
                self._update_point_table_display()
                self._update_all_image_display()
        except Exception:
            pass

    def _on_image_right_clicked(self, x: int, y: int) -> None:
        """
        右键点击图片时，弹窗显示点击位置的 HSV 颜色
        """
        if self.chosen_template is None or self.chosen_template.screen_image is None:
            QMessageBox.warning(self, "错误", "未选择图片")
            return

        # 获取 RGB 颜色值
        rgb_color = self.chosen_template.screen_image[y, x]

        # 将 RGB 转换为 HSV
        hsv_color = cv2.cvtColor(rgb_color.reshape(1, 1, 3), cv2.COLOR_RGB2HSV)[0, 0]

        message = (f"点击位置: ({x}, {y})\n"
                   f"RGB: ({rgb_color[0]}, {rgb_color[1]}, {rgb_color[2]})\n"
                   f"HSV: ({hsv_color[0]}, {hsv_color[1]}, {hsv_color[2]})")

        QMessageBox.information(self, "像素颜色信息", message)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        处理键盘快捷键
        """
        # 使用Mixin处理历史记录快捷键
        if self.history_key_press_event(event):
            return

        super().keyPressEvent(event)

    def _handle_specific_keys(self, event: QKeyEvent) -> bool:
        """
        处理模板助手特定的键盘快捷键
        """
        if self.chosen_template is None:
            return False

        # Delete 或 Backspace 清除所有点位
        if event.key() in [Qt.Key.Key_Delete, Qt.Key.Key_Backspace]:
            if len(self.chosen_template.point_list) > 0:
                self._add_history_record({'type': 'clear_points', 'old_points': [Point(p.x, p.y) for p in self.chosen_template.point_list]})
                self.chosen_template.point_list.clear()
                self.chosen_template.point_updated = True
                self._update_point_table_display()
                self._update_all_image_display()
            event.accept()
            return True

        return False

    # HistoryMixin 抽象方法实现
    def _has_valid_context(self) -> bool:
        """检查是否有有效的操作上下文"""
        return self.chosen_template is not None

    def _apply_undo(self, change_record: dict[str, Any]) -> None:
        """应用撤回操作"""
        if self.chosen_template is None:
            return

        # 恢复到记录的旧状态
        self.chosen_template.point_list = [Point(p.x, p.y) for p in change_record['old_points']]
        self.chosen_template.point_updated = True
        self._update_point_table_display()
        self._update_all_image_display()

    def _apply_redo(self, change_record: dict[str, Any]) -> None:
        """应用恢复操作"""
        if self.chosen_template is None:
            return

        change_type = change_record['type']

        if change_type == 'add_point':
            self.chosen_template.add_point(change_record['new_point'])
        elif change_type == 'remove_point':
            idx = change_record['removed_index']
            if 0 <= idx < len(self.chosen_template.point_list):
                self.chosen_template.remove_point_by_idx(idx)
        elif change_type == 'clear_points':
            self.chosen_template.point_list.clear()
        elif change_type == 'table_edit':
            row_idx = change_record['row_index']
            if 0 <= row_idx < len(self.chosen_template.point_list):
                self.chosen_template.point_list[row_idx] = change_record['new_point']
        elif change_type == 'rect_selected':
            left, top, right, bottom = change_record['rect_area']
            # 根据模板形状处理矩形选择
            if self.chosen_template.template_shape == TemplateShapeEnum.RECTANGLE.value.value:
                self.chosen_template.point_list = [Point(left, top), Point(right, bottom)]
            elif self.chosen_template.template_shape == TemplateShapeEnum.CIRCLE.value.value:
                center_x = (left + right) // 2
                center_y = (top + bottom) // 2
                radius = max(abs(right - left), abs(bottom - top)) // 2
                self.chosen_template.point_list = [Point(center_x, center_y), Point(center_x + radius, center_y)]
            elif self.chosen_template.template_shape == TemplateShapeEnum.QUADRILATERAL.value.value:
                self.chosen_template.point_list = [
                    Point(left, top), Point(right, top), Point(right, bottom), Point(left, bottom)
                ]
            elif self.chosen_template.template_shape == TemplateShapeEnum.MULTI_RECT.value.value:
                self.chosen_template.point_list.extend([Point(left, top), Point(right, bottom)])
            elif self.chosen_template.template_shape == TemplateShapeEnum.POLYGON.value.value:
                self.chosen_template.point_list.extend([
                    Point(left, top), Point(right, top), Point(right, bottom), Point(left, bottom)
                ])
        elif change_type == 'move_points':
            dx = change_record['dx']
            dy = change_record['dy']
            self.chosen_template.update_all_points(dx, dy)

        self.chosen_template.point_updated = True
        self._update_point_table_display()
        self._update_all_image_display()
