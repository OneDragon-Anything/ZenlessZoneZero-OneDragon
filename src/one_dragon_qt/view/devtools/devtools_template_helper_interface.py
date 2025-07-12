import os
import cv2
from PySide6.QtWidgets import QWidget, QFileDialog, QTableWidgetItem, QMessageBox
from qfluentwidgets import FluentIcon, PushButton, TableWidget, ToolButton, ImageLabel, CaptionLabel, LineEdit
from typing import List, Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.screen.template_info import TemplateInfo, TemplateShapeEnum
from one_dragon.utils import os_utils, cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.click_image_label import ImageScaleEnum, ClickImageLabel
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class DevtoolsTemplateHelperInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='devtools_template_helper_interface',
            parent=parent,
            content_widget=None,
            nav_text_cn='模板管理'
        )

        self.ctx: OneDragonContext = ctx
        self.chosen_template: Optional[TemplateInfo] = None
        self.last_screen_dir: Optional[str] = None  # 上一次选择的图片路径

    def get_content_widget(self) -> QWidget:
        content_widget = Row()

        content_widget.add_widget(self._init_left_part())
        content_widget.add_widget(self._init_mid_part())
        content_widget.add_widget(self._init_right_part())

        return content_widget

    def _init_left_part(self) -> QWidget:
        widget = Column()

        btn_row = Row()
        widget.add_widget(btn_row)

        self.existed_yml_btn = EditableComboBox()
        self.existed_yml_btn.setPlaceholderText(gt('选择已有'))
        self.existed_yml_btn.currentIndexChanged.connect(self._on_choose_existed_yml)
        btn_row.add_widget(self.existed_yml_btn)

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

        btn_row.add_stretch(1)

        save_row = Row()
        widget.add_widget(save_row)

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

        save_row.add_stretch(1)

        self.h_move_input = LineEdit()
        self.h_btn = PushButton(text=gt('移动'))
        self.h_btn.clicked.connect(self._on_h_move_clicked)
        self.h_move_opt = MultiPushSettingCard(icon=FluentIcon.MOVE, title='横移',
                                               btn_list=[self.h_move_input, self.h_btn])
        widget.add_widget(self.h_move_opt)

        self.v_move_input = LineEdit()
        self.v_btn = PushButton(text=gt('移动'))
        self.v_btn.clicked.connect(self._on_v_move_clicked)
        self.v_move_opt = MultiPushSettingCard(icon=FluentIcon.MOVE, title='纵移',
                                               btn_list=[self.v_move_input, self.v_btn])
        widget.add_widget(self.v_move_opt)

        self.template_sub_dir_opt = TextSettingCard(icon=FluentIcon.HOME, title='画面')
        self.template_sub_dir_opt.line_edit.setFixedWidth(240)
        self.template_sub_dir_opt.value_changed.connect(self._on_template_sub_dir_changed)
        widget.add_widget(self.template_sub_dir_opt)

        self.template_id_opt = TextSettingCard(icon=FluentIcon.HOME, title='模板ID')
        self.template_id_opt.line_edit.setFixedWidth(240)
        self.template_id_opt.value_changed.connect(self._on_template_id_changed)
        widget.add_widget(self.template_id_opt)

        self.template_name_opt = TextSettingCard(icon=FluentIcon.HOME, title='模板名称')
        self.template_name_opt.line_edit.setFixedWidth(240)
        self.template_name_opt.value_changed.connect(self._on_template_name_changed)
        widget.add_widget(self.template_name_opt)

        self.template_shape_opt = ComboBoxSettingCard(icon=FluentIcon.FIT_PAGE, title='形状', options_enum=TemplateShapeEnum)
        self.template_shape_opt.value_changed.connect(self._on_template_shape_changed)
        widget.add_widget(self.template_shape_opt)

        self.auto_mask_opt = SwitchSettingCard(icon=FluentIcon.HOME, title='自动生成掩码')
        self.auto_mask_opt.value_changed.connect(self._on_auto_mask_changed)
        widget.add_widget(self.auto_mask_opt)

        self.point_table = TableWidget()
        self.point_table.setMinimumWidth(300)
        self.point_table.setMinimumHeight(220)
        self.point_table.setBorderVisible(True)
        self.point_table.setBorderRadius(8)
        self.point_table.setWordWrap(True)
        self.point_table.setColumnCount(2)
        self.point_table.verticalHeader().hide()
        self.point_table.setHorizontalHeaderLabels([
            gt('操作'),
            gt('点位'),
        ])
        self.point_table.setColumnWidth(0, 40)  # 操作
        self.point_table.setColumnWidth(1, 200)  # 位置
        self.point_table.cellChanged.connect(self._on_point_table_cell_changed)
        widget.add_widget(self.point_table)

        widget.add_stretch(1)
        return widget

    def _init_mid_part(self) -> QWidget:
        widget = Column()

        raw_label = CaptionLabel(text=gt('模板原图'))
        widget.add_widget(raw_label)

        self.template_raw_label = ImageLabel()
        widget.add_widget(self.template_raw_label)

        mask_label = CaptionLabel(text=gt('模板掩码'))
        widget.add_widget(mask_label)

        self.template_mask_label = ImageLabel()
        widget.add_widget(self.template_mask_label)

        merge_label = CaptionLabel(text=gt('模板抠图'))
        widget.add_widget(merge_label)

        self.template_merge_label = ImageLabel()
        widget.add_widget(self.template_merge_label)

        reversed_label = CaptionLabel(text=gt('反向抠图'))
        widget.add_widget(reversed_label)

        self.template_reversed_label = ImageLabel()
        widget.add_widget(self.template_reversed_label)

        widget.add_stretch(1)

        return widget

    def _init_right_part(self) -> QWidget:
        widget = Column()

        self.image_display_size_opt = ComboBoxSettingCard(
            icon=FluentIcon.ZOOM_IN, title='图片显示大小',
            options_enum=ImageScaleEnum
        )
        self.image_display_size_opt.setValue(0.5)
        self.image_display_size_opt.setFixedWidth(240)
        self.image_display_size_opt.value_changed.connect(self._update_screen_image_display)
        widget.add_widget(self.image_display_size_opt)

        self.image_click_pos_opt = TextSettingCard(icon=FluentIcon.MOVE, title='鼠标选择区域')
        self.image_click_pos_opt.setFixedWidth(240)
        widget.add_widget(self.image_click_pos_opt)

        self.image_label = ClickImageLabel()
        self.image_label.clicked_with_pos.connect(self._on_image_clicked)
        self.image_label.right_clicked_with_pos.connect(self._on_image_right_clicked)
        widget.add_widget(self.image_label)

        widget.add_stretch(1)

        return widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self._update_whole_display()

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

        self.h_move_input.setDisabled(not chosen)
        self.h_btn.setDisabled(not chosen)
        self.h_move_opt.setDisabled(not chosen)
        self.v_move_input.setDisabled(not chosen)
        self.v_btn.setDisabled(not chosen)
        self.v_move_opt.setDisabled(not chosen)

        self.template_sub_dir_opt.setDisabled(not chosen)
        self.template_id_opt.setDisabled(not chosen)
        self.template_name_opt.setDisabled(not chosen)
        self.template_shape_opt.setDisabled(not chosen)
        self.auto_mask_opt.setDisabled(not chosen)

        if not chosen:  # 清除一些值
            self.template_sub_dir_opt.setValue('')
            self.template_id_opt.setValue('')
            self.template_name_opt.setValue('')
            self.template_shape_opt.setValue('')
            self.auto_mask_opt.setValue(True)
        else:
            self.template_sub_dir_opt.setValue(self.chosen_template.sub_dir)
            self.template_id_opt.setValue(self.chosen_template.template_id)
            self.template_name_opt.setValue(self.chosen_template.template_name)
            self.template_shape_opt.setValue(self.chosen_template.template_shape)
            self.auto_mask_opt.setValue(self.chosen_template.auto_mask)

        self._update_existed_yml_options()
        self._update_all_image_display()
        self._update_point_table_display()

    def _update_existed_yml_options(self) -> None:
        """
        更新已有的yml选项
        :return:
        """
        template_info_list: List[TemplateInfo] = self.ctx.template_loader.get_all_template_info_from_disk(need_raw=False, need_config=True)
        config_list: List[ConfigItem] = [
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
        point_list: List[Point] = [] if self.chosen_template is None else self.chosen_template.point_list
        point_cnt = len(point_list)
        self.point_table.setRowCount(point_cnt + 1)

        for idx in range(point_cnt):
            point_item = point_list[idx]
            del_btn = ToolButton(FluentIcon.DELETE, parent=None)
            del_btn.clicked.connect(self._on_row_delete_clicked)

            self.point_table.setCellWidget(idx, 0, del_btn)
            self.point_table.setItem(idx, 1, QTableWidgetItem('%d, %d' % (point_item.x, point_item.y)))

        self.point_table.blockSignals(False)

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

    def _update_template_raw_display(self) -> None:
        """
        更新模板原图的显示
        :return:
        """
        image_to_show = self.chosen_template.get_template_raw_to_display() if self.chosen_template is not None else None
        if image_to_show is not None:
            image = Cv2Image(image_to_show)
            self.template_raw_label.setImage(image)
            self.template_raw_label.setFixedSize(image.width(), image.height())
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
            self.template_mask_label.setFixedSize(image.width(), image.height())
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
            self.template_merge_label.setFixedSize(image.width(), image.height())
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
            self.template_reversed_label.setFixedSize(image.width(), image.height())
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

    def _on_template_shape_changed(self, idx: int, value: str) -> None:
        if self.chosen_template is None:
            return

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
            self.chosen_template.point_list[row] = Point(num_list[0], num_list[1])
            self.chosen_template.point_updated = True
            self._update_all_image_display()

    def _on_image_clicked(self, x1: int, y1: int) -> None:
        """
        图片上拖拽区域后 显示坐标
        :return:
        """
        if self.chosen_template is None or self.chosen_template.screen_image is None:
            return
        display_width = self.image_label.width()
        display_height = self.image_label.height()

        image_height, image_width, _ = self.chosen_template.screen_image.shape

        real_x = int(x1 * image_width / display_width)
        real_y = int(y1 * image_height / display_height)

        self.chosen_template.add_point(Point(real_x, real_y))

        self._update_point_table_display()
        self._update_all_image_display()

    def _on_h_move_clicked(self) -> None:
        """
        所有点为的横坐标改变
        """
        if self.chosen_template is None:
            return

        input_text = self.h_move_input.text()
        try:
            dx = int(input_text)
            self.chosen_template.update_all_points(dx, 0)
            self._update_point_table_display()
            self._update_all_image_display()
        except Exception:
            pass

    def _on_v_move_clicked(self) -> None:
        """
        所有点为的纵坐标改变
        """
        if self.chosen_template is None:
            return

        input_text = self.v_move_input.text()
        try:
            dy = int(input_text)
            self.chosen_template.update_all_points(0, dy)
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

        display_width = self.image_label.width()
        display_height = self.image_label.height()

        image_height, image_width, _ = self.chosen_template.screen_image.shape

        # 将显示坐标转换为原始图像坐标
        real_x = int(x * image_width / display_width)
        real_y = int(y * image_height / display_height)

        if not (0 <= real_y < image_height and 0 <= real_x < image_width):
            QMessageBox.warning(self, "错误", f"点击位置 ({real_x}, {real_y}) 超出图像范围")
            return

        # 获取 RGB 颜色值
        rgb_color = self.chosen_template.screen_image[real_y, real_x]

        # 将 RGB 转换为 HSV
        hsv_color = cv2.cvtColor(rgb_color.reshape(1, 1, 3), cv2.COLOR_RGB2HSV)[0, 0]

        message = (f"点击位置: ({real_x}, {real_y})\n"
                   f"RGB: ({rgb_color[0]}, {rgb_color[1]}, {rgb_color[2]})\n"
                   f"HSV: ({hsv_color[0]}, {hsv_color[1]}, {hsv_color[2]})")

        QMessageBox.information(self, "像素颜色信息", message)
