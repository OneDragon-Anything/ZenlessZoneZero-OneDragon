import os
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QWidget, QFileDialog, QTableWidgetItem, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QKeyEvent
from qfluentwidgets import (FluentIcon, PushButton, ToolButton, CheckBox, LineEdit, BodyLabel,
                            TableWidget, SimpleCardWidget, SingleDirectionScrollArea, ScrollArea)
from typing import Optional, Any

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.base.screen.template_info import get_template_root_dir_path, get_template_sub_dir_path, TemplateInfo, \
    TemplateShapeEnum
from one_dragon.utils import os_utils, cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.mixins.history_mixin import HistoryMixin
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.zoomable_image_label import ZoomableClickImageLabel
from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard, MultiLineSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class ScreenInfoWorker(QObject):

    signal = Signal()


class DevtoolsScreenManageInterface(VerticalScrollInterface, HistoryMixin):

    def __init__(self, ctx: OneDragonContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='devtools_screen_manage_interface',
            parent=parent,
            nav_text_cn='画面管理'
        )
        self._init_history()  # 初始化历史记录功能

        self.ctx: OneDragonContext = ctx

        self.chosen_screen: Optional[ScreenInfo] = None
        self.last_screen_dir: Optional[str] = None  # 上一次选择的图片路径

        self._whole_update = ScreenInfoWorker()
        self._whole_update.signal.connect(self._update_display_by_screen)

        self._image_update = ScreenInfoWorker()
        self._image_update.signal.connect(self._update_image_display)

        self._area_table_update = ScreenInfoWorker()
        self._area_table_update.signal.connect(self._update_area_table_display)

        self._existed_yml_update = ScreenInfoWorker()
        self._existed_yml_update.signal.connect(self._update_existed_yml_options)

    def get_content_widget(self) -> QWidget:
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        left_panel = self._init_left_part()
        right_panel = self._init_right_part()

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

        return main_widget

    def _init_left_part(self) -> QWidget:
        scroll_area = SingleDirectionScrollArea()

        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(12, 0, 0, 0)
        control_layout.setSpacing(12)

        btn_row = Row(spacing=6, margins=(0, 0, 0, 0))
        control_layout.addWidget(btn_row)

        self.existed_yml_btn = EditableComboBox()
        self.existed_yml_btn.setPlaceholderText(gt('选择已有'))
        self.existed_yml_btn.currentTextChanged.connect(self._on_choose_existed_yml)
        self._update_existed_yml_options()
        btn_row.add_widget(self.existed_yml_btn)

        self.create_btn = PushButton(text=gt('新建'))
        self.create_btn.clicked.connect(self._on_create_clicked)
        btn_row.add_widget(self.create_btn)

        self.save_btn = PushButton(text=gt('保存'))
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_row.add_widget(self.save_btn)

        self.delete_btn = ToolButton(FluentIcon.DELETE)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row.add_widget(self.delete_btn)

        self.cancel_btn = PushButton(text=gt('取消'))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.add_widget(self.cancel_btn)

        btn_row.add_stretch(1)

        img_btn_row = Row(spacing=6, margins=(0, 0, 0, 0))
        control_layout.addWidget(img_btn_row)

        self.pc_alt_opt = CheckBox(text=gt('PC 点击需 Alt'))
        self.pc_alt_opt.stateChanged.connect(self._on_pc_alt_changed)
        img_btn_row.add_widget(self.pc_alt_opt)

        img_btn_row.add_stretch(1)

        self.choose_image_btn = PushButton(text=gt('选择图片'))
        self.choose_image_btn.clicked.connect(self.choose_existed_image)
        img_btn_row.add_widget(self.choose_image_btn)

        self.choose_template_btn = PushButton(text=gt('导入模板区域'))
        self.choose_template_btn.clicked.connect(self.choose_existed_template)
        img_btn_row.add_widget(self.choose_template_btn)

        self.screen_id_label = BodyLabel(text=gt('ID'))
        self.screen_id_edit = LineEdit()
        self.screen_id_edit.setMinimumWidth(200)
        self.screen_id_edit.editingFinished.connect(self._on_screen_id_changed)

        self.screen_name_label = BodyLabel(text=gt('名称'))
        self.screen_name_edit = LineEdit()
        self.screen_name_edit.setMinimumWidth(200)
        self.screen_name_edit.editingFinished.connect(self._on_screen_name_changed)

        self.screen_info_opt = MultiLineSettingCard(icon=FluentIcon.HOME, title=gt('画面信息'), line_list=[
            [self.screen_id_label, self.screen_id_edit],
            [self.screen_name_label, self.screen_name_edit]
        ])
        control_layout.addWidget(self.screen_info_opt)

        self.table_widget = self._init_area_table_widget()
        control_layout.addWidget(self.table_widget, stretch=1)

        scroll_area.setWidget(control_widget)
        scroll_area.setWidgetResizable(True)

        return scroll_area

    def _init_area_table_widget(self) -> QWidget:
        """
        创建区域表格控件
        """
        widget = SimpleCardWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 创建横向滚动区域
        scroll_area = ScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.area_table = TableWidget()
        self.area_table.cellChanged.connect(self._on_area_table_cell_changed)
        self.area_table.setMinimumWidth(990)
        self.area_table.setBorderVisible(True)
        self.area_table.setBorderRadius(8)
        self.area_table.setWordWrap(True)
        self.area_table.setColumnCount(10)
        self.area_table.verticalHeader().hide()
        self.area_table.setHorizontalHeaderLabels([
            gt('操作'),
            gt('区域名称'),
            gt('位置'),
            gt('文本'),
            gt('阈值'),
            gt('模板'),
            gt('阈值'),
            gt('颜色范围'),
            gt('唯一标识'),
            gt('前往画面')
        ])
        self.area_table.setColumnWidth(0, 40)  # 操作
        self.area_table.setColumnWidth(2, 200)  # 位置
        self.area_table.setColumnWidth(4, 70)  # 文本阈值
        self.area_table.setColumnWidth(6, 70)  # 模板阈值
        # table的行被选中时 触发
        self.area_table_row_selected: int = -1  # 选中的行
        self.area_table.cellClicked.connect(self.on_area_table_cell_clicked)

        # 将表格放入滚动区域
        scroll_area.setWidget(self.area_table)
        layout.addWidget(scroll_area)

        return widget

    def _update_existed_yml_options(self) -> None:
        """
        更新已有的yml选项
        :return:
        """
        self.existed_yml_btn.set_items([
            ConfigItem(i.screen_name)
            for i in self.ctx.screen_loader.screen_info_list
        ])

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

        self.image_click_pos_opt = MultiPushSettingCard(icon=FluentIcon.MOVE, title='鼠标点击坐标',
                                                        content='图片左上角为(0, 0)',
                                                        btn_list=[self.x_pos_label, self.y_pos_label])
        layout.addWidget(self.image_click_pos_opt)

        # 使用Mixin创建历史记录UI
        history_ui = self._create_history_ui()
        layout.addWidget(history_ui)

        self.image_label = ZoomableClickImageLabel()
        self.image_label.left_clicked_with_pos.connect(self._on_image_left_clicked)
        self.image_label.rect_selected.connect(self._on_image_rect_selected)
        layout.addWidget(self.image_label, 1)

        return widget



    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self._update_display_by_screen()

    def _update_display_by_screen(self) -> None:
        """
        根据画面图片，统一更新界面的显示
        :return:
        """
        chosen = self.chosen_screen is not None

        self.existed_yml_btn.setDisabled(chosen)
        self.create_btn.setDisabled(chosen)
        self.save_btn.setDisabled(not chosen)
        self.delete_btn.setDisabled(not chosen)
        self.cancel_btn.setDisabled(not chosen)

        self.choose_image_btn.setDisabled(not chosen)
        self.screen_id_edit.setDisabled(not chosen)
        self.screen_name_edit.setDisabled(not chosen)
        self.pc_alt_opt.setDisabled(not chosen)

        if not chosen:  # 清除一些值
            self.screen_id_edit.setText('')
            self.screen_name_edit.setText('')
            self.pc_alt_opt.setChecked(False)
        else:
            self.screen_id_edit.setText(self.chosen_screen.screen_id)
            self.screen_name_edit.setText(self.chosen_screen.screen_name)
            self.pc_alt_opt.setChecked(self.chosen_screen.pc_alt)

        self._update_image_display()
        self._update_area_table_display()

    def _update_area_table_display(self):
        """
        更新区域表格的显示
        :return:
        """
        self.area_table.blockSignals(True)
        area_list = [] if self.chosen_screen is None else self.chosen_screen.area_list
        area_cnt = len(area_list)
        self.area_table.setRowCount(area_cnt + 1)

        for idx in range(area_cnt):
            area_item = area_list[idx]
            del_btn = ToolButton(FluentIcon.DELETE, parent=None)
            del_btn.setFixedSize(32, 32)
            del_btn.clicked.connect(self._on_row_delete_clicked)

            id_check = CheckBox()
            id_check.setChecked(area_item.id_mark)
            id_check.setProperty('area_name', area_item.area_name)
            id_check.stateChanged.connect(self.on_area_id_check_changed)

            self.area_table.setCellWidget(idx, 0, del_btn)
            self.area_table.setItem(idx, 1, QTableWidgetItem(area_item.area_name))
            self.area_table.setItem(idx, 2, QTableWidgetItem(str(area_item.pc_rect)))
            self.area_table.setItem(idx, 3, QTableWidgetItem(area_item.text))
            self.area_table.setItem(idx, 4, QTableWidgetItem(str(area_item.lcs_percent)))
            self.area_table.setItem(idx, 5, QTableWidgetItem(area_item.template_id_display_text))
            self.area_table.setItem(idx, 6, QTableWidgetItem(str(area_item.template_match_threshold)))
            self.area_table.setItem(idx, 7, QTableWidgetItem(str(area_item.color_range_display_text)))
            self.area_table.setCellWidget(idx, 8, id_check)
            self.area_table.setItem(idx, 9, QTableWidgetItem(area_item.goto_list_display_text))


        add_btn = ToolButton(FluentIcon.ADD, parent=None)
        add_btn.setFixedSize(32, 32)
        add_btn.clicked.connect(self._on_area_add_clicked)
        self.area_table.setCellWidget(area_cnt, 0, add_btn)
        self.area_table.setItem(area_cnt, 1, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 2, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 3, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 4, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 5, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 6, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 7, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 8, QTableWidgetItem(''))
        self.area_table.setItem(area_cnt, 9, QTableWidgetItem(''))

        self.area_table.blockSignals(False)

    def _update_image_display(self):
        """
        更新图片显示
        :return:
        """
        image_to_show = None if self.chosen_screen is None else self.chosen_screen.get_image_to_show(self.area_table_row_selected)
        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            # 当图像尺寸相同时保留缩放和位置状态，这样绘制框时不会重置用户的视图状态
            preserve_state = (self.image_label.original_pixmap is not None and
                            image_to_show.shape[:2] == (self.image_label.original_pixmap.height(),
                                                        self.image_label.original_pixmap.width()))
            self.image_label.setImage(image, preserve_state)
        else:
            self.image_label.setImage(None)

    def _on_choose_existed_yml(self, screen_name: str):
        """
        选择了已有的yml
        :param screen_name:
        :return:
        """
        for screen_info in self.ctx.screen_loader.screen_info_list:
            if screen_info.screen_name == screen_name:
                self.chosen_screen = ScreenInfo(screen_id=screen_info.screen_id)
                # 清除撤回记录
                self._clear_history()
                self._update_history_buttons()
                self._whole_update.signal.emit()
                break

    def _on_create_clicked(self):
        """
        创建一个新的
        :return:
        """
        if self.chosen_screen is not None:
            return

        self.chosen_screen = ScreenInfo(create_new=True)
        # 清除撤回记录
        self._clear_history()
        self._whole_update.signal.emit()

    def _on_save_clicked(self) -> None:
        """
        保存
        :return:
        """
        if self.chosen_screen is None:
            return

        self.chosen_screen.save()
        self.ctx.screen_loader.load_all()
        self._existed_yml_update.signal.emit()

    def _on_delete_clicked(self) -> None:
        """
        删除
        :return:
        """
        if self.chosen_screen is None:
            return
        self.chosen_screen.delete()
        self.chosen_screen = None
        self._whole_update.signal.emit()
        self._existed_yml_update.signal.emit()

    def _on_cancel_clicked(self) -> None:
        """
        取消编辑
        :return:
        """
        self.chosen_screen = None
        self.existed_yml_btn.setCurrentIndex(-1)
        self.area_table_row_selected = -1
        self.x_pos_label.setText('')
        self.y_pos_label.setText('')
        # 清除撤回记录
        self._clear_history()
        self._whole_update.signal.emit()

    def choose_existed_image(self) -> None:
        """
        选择已有的环图片
        :return:
        """
        default_dir = os_utils.get_path_under_work_dir('.debug', 'images')
        if self.last_screen_dir is not None:
            default_dir = self.last_screen_dir
        elif self.chosen_screen is not None:
            screen_dir = os_utils.get_path_under_work_dir('.debug', 'devtools', 'screen', self.chosen_screen.screen_id)
            if os.path.exists(screen_dir):
                default_dir = screen_dir

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
        if self.chosen_screen is None:
            return

        self.chosen_screen.screen_image = cv2_utils.read_image(image_file_path)
        self._image_update.signal.emit()

    def choose_existed_template(self) -> None:
        if self.chosen_screen is None:
            return

        template_root_dir = get_template_root_dir_path()
        template_sub_dir = get_template_sub_dir_path(self.chosen_screen.screen_id)

        if os.path.exists(template_sub_dir):
            default_dir = template_sub_dir
        else:
            default_dir = template_root_dir

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            gt('选择模板配置文件'),
            dir=default_dir,
            filter="YML (*.yml)",
        )
        if file_path is not None and file_path.endswith('.yml'):
            fix_file_path = os.path.normpath(file_path)
            log.info('选择路径 %s', fix_file_path)
            self._on_template_chosen(fix_file_path)

    def _on_template_chosen(self, template_file_path: str) -> None:
        """
        选择模板后 导入模板对应的区域
        :param template_file_path: 模板文件路径
        :return:
        """
        if self.chosen_screen is None:
            return

        directory, filename = os.path.split(template_file_path)
        template_id = os.path.basename(directory)
        sub_dir = os.path.basename(os.path.dirname(directory))

        template_info = TemplateInfo(sub_dir=sub_dir, template_id=template_id)
        template_info.update_template_shape(TemplateShapeEnum.RECTANGLE.value.value)

        area = ScreenArea()
        area.area_name = template_info.template_name
        if len(template_info.point_list) >= 2:
            p1 = template_info.point_list[0]
            p2 = template_info.point_list[1]
            # 需要取稍微比模板大一点的范围
            area.pc_rect = Rect(max(0, p1.x - 10), max(0, p1.y - 10),
                                min(self.ctx.project_config.screen_standard_width, p2.x + 10),
                                min(self.ctx.project_config.screen_standard_height, p2.y + 10))
        area.template_sub_dir = sub_dir
        area.template_id = template_id

        self.chosen_screen.area_list.append(area)
        self._area_table_update.signal.emit()

    def _on_screen_id_changed(self) -> None:
        if self.chosen_screen is None:
            return

        self.chosen_screen.screen_id = self.screen_id_edit.text()

    def _on_screen_name_changed(self) -> None:
        if self.chosen_screen is None:
            return

        self.chosen_screen.screen_name = self.screen_name_edit.text()

    def _on_pc_alt_changed(self, checked: bool) -> None:
        if self.chosen_screen is None:
            return

        self.chosen_screen.pc_alt = self.pc_alt_opt.isChecked()

    def _on_area_add_clicked(self) -> None:
        """
        新增一个区域
        :return:
        """
        if self.chosen_screen is None:
            return

        self.chosen_screen.area_list.append(ScreenArea())
        self._area_table_update.signal.emit()

    def _on_row_delete_clicked(self):
        """
        删除一行
        :return:
        """
        if self.chosen_screen is None:
            return

        button_idx = self.sender()
        if button_idx is not None:
            row_idx = self.area_table.indexAt(button_idx.pos()).row()
            self.chosen_screen.remove_area_by_idx(row_idx)
            self.area_table.removeRow(row_idx)
            self._image_update.signal.emit()

    def _on_area_table_cell_changed(self, row: int, column: int) -> None:
        """
        表格内容改变
        :param row:
        :param column:
        :return:
        """
        if self.chosen_screen is None:
            return
        if row < 0 or row >= len(self.chosen_screen.area_list):
            return
        area_item = self.chosen_screen.area_list[row]
        text = self.area_table.item(row, column).text().strip()

        # 列映射：列索引 -> (属性名, 处理函数)
        column_handlers = {
            1: ('area_name', lambda x: x),
            2: ('pc_rect', self._parse_rect_from_text),
            3: ('text', lambda x: x),
            4: ('lcs_percent', lambda x: float(x) if len(x) > 0 else 0.5),
            5: ('template', lambda x: x),
            6: ('template_match_threshold', lambda x: float(x) if len(x) > 0 else 0.7),
            7: ('color_range', self._parse_color_range_from_text),
            9: ('goto_list', lambda x: x.split(','))
        }

        if column not in column_handlers:
            return

        attr_name, handler = column_handlers[column]

        # 记录修改前的状态
        if attr_name == 'template':
            old_value = f"{area_item.template_sub_dir}.{area_item.template_id}" if area_item.template_sub_dir else area_item.template_id
        elif attr_name == 'pc_rect':
            old_value = Rect(area_item.pc_rect.x1, area_item.pc_rect.y1, area_item.pc_rect.x2, area_item.pc_rect.y2)
        elif attr_name == 'goto_list':
            old_value = area_item.goto_list.copy() if area_item.goto_list else []
        else:
            old_value = getattr(area_item, attr_name)

        # 应用新值
        try:
            new_value = handler(text)
            if attr_name == 'template':
                if len(text) == 0:
                    area_item.template_sub_dir = ''
                    area_item.template_id = ''
                else:
                    template_list = text.split('.')
                    if len(template_list) > 1:
                        area_item.template_sub_dir = template_list[0]
                        area_item.template_id = template_list[1]
                    else:
                        area_item.template_sub_dir = ''
                        area_item.template_id = template_list[0]
            elif attr_name == 'pc_rect':
                area_item.pc_rect = new_value
                self._image_update.signal.emit()
            else:
                setattr(area_item, attr_name, new_value)
        except:
            # 如果解析失败，不进行修改
            return

        # 添加到撤回历史记录
        table_change = {
            'type': 'table_edit',
            'row_index': row,
            'change_type': attr_name,
            'old_value': old_value,
            'new_value': text
        }
        self._add_history_record(table_change)

    def _parse_rect_from_text(self, text: str) -> Rect:
        """解析文本为矩形对象"""
        num_list = [int(i) for i in text[1:-1].split(',')]
        while len(num_list) < 4:
            num_list.append(0)
        return Rect(num_list[0], num_list[1], num_list[2], num_list[3])

    def _parse_color_range_from_text(self, text: str):
        """解析颜色范围文本"""
        try:
            import json
            arr = json.loads(text)
            if isinstance(arr, list):
                return arr
        except Exception:
            pass
        return None

    def _on_image_left_clicked(self, x: int, y: int) -> None:
        """
        图片上左键单击后显示坐标
        :param x: 点击的x坐标
        :param y: 点击的y坐标
        :return:
        """
        if self.chosen_screen is None or self.chosen_screen.screen_image is None:
            return

        self.x_pos_label.setText(str(x))
        self.y_pos_label.setText(str(y))

    def _on_image_rect_selected(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """
        在图片上选择一个区域后的回调
        :param x1:
        :param y1:
        :param x2:
        :param y2:
        :return:
        """
        if self.chosen_screen is None or self.area_table_row_selected is None:
            return
        if self.area_table_row_selected < 0 or self.area_table_row_selected >= len(self.chosen_screen.area_list):
            return

        area_item = self.chosen_screen.area_list[self.area_table_row_selected]

        # 记录撤回信息
        rect_change = {
            'row_index': self.area_table_row_selected,
            'old_rect': Rect(area_item.pc_rect.x1, area_item.pc_rect.y1, area_item.pc_rect.x2, area_item.pc_rect.y2),
            'new_rect': Rect(x1, y1, x2, y2)
        }

        # 添加到历史记录
        self._add_history_record(rect_change)

        self.area_table.blockSignals(True)
        self.area_table.item(self.area_table_row_selected, 2).setText(f'({x1}, {y1}, {x2}, {y2})')
        self.area_table.blockSignals(False)

        area_item.pc_rect = Rect(x1, y1, x2, y2)
        self._image_update.signal.emit()

        # 更新撤回按钮
        self._update_history_buttons()

    def on_area_id_check_changed(self):
        if self.chosen_screen is None:
            return
        btn: CheckBox = self.sender()
        if btn is not None:
            row_idx = self.area_table.indexAt(btn.pos()).row()
            if row_idx < 0 or row_idx >= len(self.chosen_screen.area_list):
                return
            self.chosen_screen.area_list[row_idx].id_mark = btn.isChecked()

    def on_area_table_cell_clicked(self, row: int, column: int):
        if self.area_table_row_selected == row:
            self.area_table_row_selected = None
        else:
            self.area_table_row_selected = row
        self._update_image_display()

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
        处理画面管理特定的键盘快捷键
        """
        # 这里可以添加特定的键盘快捷键处理
        return False

    def _has_valid_context(self) -> bool:
        """
        检查是否有有效的上下文（选中的屏幕）
        """
        return self.chosen_screen is not None

    def _apply_undo(self, change_record: dict[str, Any]) -> None:
        """
        应用撤销操作
        """
        if self.chosen_screen is None:
            return

        if change_record.get('type') == 'table_edit':
            # 处理表格编辑的撤回
            row_index = change_record['row_index']
            change_type = change_record['change_type']
            old_value = change_record['old_value']

            # 检查行索引是否仍然有效
            if row_index < 0 or row_index >= len(self.chosen_screen.area_list):
                return

            area_item = self.chosen_screen.area_list[row_index]

            # 根据修改类型恢复原值
            if change_type == 'template':
                if '.' in old_value:
                    template_list = old_value.split('.')
                    area_item.template_sub_dir = template_list[0]
                    area_item.template_id = template_list[1]
                else:
                    area_item.template_sub_dir = ''
                    area_item.template_id = old_value
            else:
                setattr(area_item, change_type, old_value)

            # 如果是坐标修改，需要更新图像显示
            if change_type == 'pc_rect':
                self._image_update.signal.emit()

            # 更新表格显示
            self._update_area_table_display()

        else:
            # 处理拖框操作的撤回
            row_index = change_record['row_index']
            old_rect = change_record['old_rect']

            # 检查行索引是否仍然有效
            if row_index < 0 or row_index >= len(self.chosen_screen.area_list):
                return

            # 恢复旧的矩形
            area_item = self.chosen_screen.area_list[row_index]
            area_item.pc_rect = old_rect

            # 更新表格显示
            self.area_table.blockSignals(True)
            self.area_table.item(row_index, 2).setText(f'({old_rect.x1}, {old_rect.y1}, {old_rect.x2}, {old_rect.y2})')
            self.area_table.blockSignals(False)

            # 更新图像显示
            self._image_update.signal.emit()

    def _apply_redo(self, change_record: dict[str, Any]) -> None:
        """
        应用重做操作
        """
        if self.chosen_screen is None:
            return

        if change_record.get('type') == 'table_edit':
            # 处理表格编辑的恢复
            row_index = change_record['row_index']
            change_type = change_record['change_type']
            new_value = change_record['new_value']

            # 检查行索引是否仍然有效
            if row_index < 0 or row_index >= len(self.chosen_screen.area_list):
                return

            area_item = self.chosen_screen.area_list[row_index]

            # 根据修改类型恢复新值
            if change_type == 'template':
                if len(new_value) == 0:
                    area_item.template_sub_dir = ''
                    area_item.template_id = ''
                else:
                    template_list = new_value.split('.')
                    if len(template_list) > 1:
                        area_item.template_sub_dir = template_list[0]
                        area_item.template_id = template_list[1]
                    else:
                        area_item.template_sub_dir = ''
                        area_item.template_id = template_list[0]
            elif change_type == 'pc_rect':
                rect_value = self._parse_rect_from_text(new_value)
                area_item.pc_rect = rect_value
                self._image_update.signal.emit()
            else:
                if change_type == 'lcs_percent' or change_type == 'template_match_threshold':
                    setattr(area_item, change_type, float(new_value) if len(new_value) > 0 else (0.5 if change_type == 'lcs_percent' else 0.7))
                elif change_type == 'goto_list':
                    setattr(area_item, change_type, new_value.split(','))
                else:
                    setattr(area_item, change_type, new_value)

            # 更新表格显示
            self._area_table_update.signal.emit()

        else:
            # 处理拖框操作的恢复
            row_index = change_record['row_index']
            new_rect = change_record['new_rect']

            # 检查行索引是否仍然有效
            if row_index < 0 or row_index >= len(self.chosen_screen.area_list):
                return

            # 恢复新的矩形
            area_item = self.chosen_screen.area_list[row_index]
            area_item.pc_rect = new_rect

            # 更新表格显示
            self.area_table.blockSignals(True)
            self.area_table.item(row_index, 2).setText(f'({new_rect.x1}, {new_rect.y1}, {new_rect.x2}, {new_rect.y2})')
            self.area_table.blockSignals(False)

            # 更新图像显示
            self._image_update.signal.emit()
