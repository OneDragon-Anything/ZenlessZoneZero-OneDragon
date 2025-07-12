import os
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget, QFileDialog, QTableWidgetItem
from qfluentwidgets import FluentIcon, PushButton, TableWidget, ToolButton, CheckBox
from typing import Optional

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
from one_dragon_qt.widgets.click_image_label import ImageScaleEnum, ClickImageLabel
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.check_box_setting_card import CheckBoxSettingCard
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class ScreenInfoWorker(QObject):

    signal = Signal()


class DevtoolsScreenManageInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='devtools_screen_manage_interface',
            parent=parent,
            nav_text_cn='画面管理'
        )
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
        content_widget = Row()
        content_widget.add_widget(self._init_left_part())
        content_widget.add_widget(self._init_right_part())
        return content_widget

    def _init_left_part(self) -> QWidget:
        widget = Column()

        btn_row = Row()
        widget.add_widget(btn_row)

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

        img_btn_row = Row()
        widget.add_widget(img_btn_row)

        self.choose_image_btn = PushButton(text=gt('选择图片'))
        self.choose_image_btn.clicked.connect(self.choose_existed_image)
        img_btn_row.add_widget(self.choose_image_btn)

        self.choose_template_btn = PushButton(text=gt('导入模板区域'))
        self.choose_template_btn.clicked.connect(self.choose_existed_template)
        img_btn_row.add_widget(self.choose_template_btn)

        self.screen_id_opt = TextSettingCard(icon=FluentIcon.HOME, title='画面ID')
        self.screen_id_opt.value_changed.connect(self._on_screen_id_changed)
        widget.add_widget(self.screen_id_opt)

        self.screen_name_opt = TextSettingCard(icon=FluentIcon.HOME, title='画面名称')
        self.screen_name_opt.value_changed.connect(self._on_screen_name_changed)
        widget.add_widget(self.screen_name_opt)

        self.pc_alt_opt = CheckBoxSettingCard(icon=FluentIcon.MOVE, title='PC点击需alt')
        self.pc_alt_opt.value_changed.connect(self._on_pc_alt_changed)
        widget.add_widget(self.pc_alt_opt)

        self.area_table = TableWidget()
        self.area_table.cellChanged.connect(self._on_area_table_cell_changed)
        self.area_table.setMinimumWidth(980)
        self.area_table.setMinimumHeight(420)
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
        widget.add_widget(self.area_table)

        widget.add_stretch(1)
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
        widget = Column()

        self.image_display_size_opt = ComboBoxSettingCard(
            icon=FluentIcon.ZOOM_IN, title='图片显示大小',
            options_enum=ImageScaleEnum
        )
        self.image_display_size_opt.setValue(0.5)
        self.image_display_size_opt.value_changed.connect(self._update_image_display)
        widget.add_widget(self.image_display_size_opt)

        self.image_click_pos_opt = TextSettingCard(icon=FluentIcon.MOVE, title='鼠标选择区域')
        widget.add_widget(self.image_click_pos_opt)

        self.image_label = ClickImageLabel()
        self.image_label.drag_released.connect(self._on_image_drag_released)
        widget.add_widget(self.image_label)

        widget.add_stretch(1)

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
        self.screen_id_opt.setDisabled(not chosen)
        self.screen_name_opt.setDisabled(not chosen)
        self.pc_alt_opt.setDisabled(not chosen)

        if not chosen:  # 清除一些值
            self.screen_id_opt.setValue('')
            self.screen_name_opt.setValue('')
            self.pc_alt_opt.setValue(False)
        else:
            self.screen_id_opt.setValue(self.chosen_screen.screen_id)
            self.screen_name_opt.setValue(self.chosen_screen.screen_name)
            self.pc_alt_opt.setValue(self.chosen_screen.pc_alt)

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
            self.image_label.setImage(image)
            size_value: float = self.image_display_size_opt.getValue()
            if size_value is None:
                display_width = image.width()
                display_height = image.height()
            else:
                display_width = int(image.width() * size_value)
                display_height = int(image.height() * size_value)
            self.image_label.setFixedSize(display_width, display_height)
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

    def _on_screen_id_changed(self, value: str) -> None:
        if self.chosen_screen is None:
            return

        self.chosen_screen.screen_id = value

    def _on_screen_name_changed(self, value: str) -> None:
        if self.chosen_screen is None:
            return

        self.chosen_screen.screen_name = value

    def _on_pc_alt_changed(self, value: bool) -> None:
        if self.chosen_screen is None:
            return

        self.chosen_screen.pc_alt = value

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
        if column == 1:
            area_item.area_name = text
        elif column == 2:
            num_list = [int(i) for i in text[1:-1].split(',')]
            while len(num_list) < 4:
                num_list.append(0)
            area_item.pc_rect = Rect(num_list[0], num_list[1], num_list[2], num_list[3])
            self._image_update.signal.emit()
        elif column == 3:
            area_item.text = text
        elif column == 4:
            area_item.lcs_percent = float(text) if len(text) > 0 else 0.5
        elif column == 5:
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
        elif column == 6:
            area_item.template_match_threshold = float(text) if len(text) > 0 else 0.7
        elif column == 7:
            try:
                import json
                arr = json.loads(text)
                if isinstance(arr, list):
                    area_item.color_range = arr
            except Exception:
                area_item.color_range = None
        elif column == 9:
            area_item.goto_list = text.split(',')

    def _on_image_drag_released(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """
        图片上拖拽区域后 显示坐标
        :return:
        """
        if self.chosen_screen is None or self.chosen_screen.screen_image is None:
            return

        display_width = self.image_label.width()
        display_height = self.image_label.height()

        image_width = self.chosen_screen.screen_image.shape[1]
        image_height = self.chosen_screen.screen_image.shape[0]

        real_x1 = int(x1 * image_width / display_width)
        real_y1 = int(y1 * image_height / display_height)
        real_x2 = int(x2 * image_width / display_width)
        real_y2 = int(y2 * image_height / display_height)

        self.image_click_pos_opt.setValue(f'({real_x1}, {real_y1}, {real_x2}, {real_y2})')

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
