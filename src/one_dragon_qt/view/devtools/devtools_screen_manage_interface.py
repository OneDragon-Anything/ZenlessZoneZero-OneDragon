import ast
import os
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    FluentIcon,
    InfoBarIcon,
    LineEdit,
    PushButton,
    ScrollArea,
    SimpleCardWidget,
    SingleDirectionScrollArea,
    TableWidget,
    ToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.base.screen.template_info import (
    TemplateInfo,
    TemplateShapeEnum,
    get_template_root_dir_path,
    get_template_sub_dir_path,
)
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.mixins.history_mixin import HistoryMixin
from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiLineSettingCard,
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.zoomable_image_label import ZoomableClickImageLabel


class ScreenInfoWorker(QObject):

    signal = Signal()


@dataclass
class ColumnMeta:
    """表格列元数据"""
    display_name: str
    attr_name: str | None = None
    parser: Callable[[str], Any] | None = None
    width: int | None = None  # None = 自动宽度
    formatter: Callable[[Any], str] | None = None  # 属性值 → 显示文本，None = str()


def _parse_rect(text: str) -> Rect:
    """解析矩形，校验为 (x1, y1, x2, y2) 结构。"""
    stripped = text.strip().strip('()[]')
    parts = [p.strip() for p in stripped.split(',')]
    if len(parts) != 4:
        raise ValueError(f'需要 4 个坐标值，实际: {len(parts)} 个')
    return Rect(*(int(p) for p in parts))


def _parse_color_range(text: str) -> list[list[int]] | None:
    """解析颜色范围，校验为 [[r,g,b],[r,g,b]] 结构。"""
    if not text.strip():
        return None
    val = ast.literal_eval(text)
    if (isinstance(val, list) and len(val) == 2
            and all(isinstance(v, list) and len(v) == 3 for v in val)):
        return val
    raise ValueError(f'需要 [[r,g,b],[r,g,b]]，实际: {val}')


AREA_TYPE_LABEL_MAP: dict[str, str] = {
    ScreenArea.AREA_TYPE_CLICK: '点击',
    ScreenArea.AREA_TYPE_OCR: 'OCR',
    ScreenArea.AREA_TYPE_TEMPLATE: '模板',
    ScreenArea.AREA_TYPE_COLOR: '颜色',
}
AREA_TYPE_ITEMS: list[ConfigItem] = [
    ConfigItem(label, area_type)
    for area_type, label in AREA_TYPE_LABEL_MAP.items()
]


def _parse_area_type(text: str) -> str:
    """解析区域类型。"""
    stripped = text.strip()
    for area_type, label in AREA_TYPE_LABEL_MAP.items():
        if stripped in (area_type, label):
            return area_type
    raise ValueError(f'未知区域类型: {text}')


def _format_area_type(area_type: str) -> str:
    """格式化区域类型。"""
    return AREA_TYPE_LABEL_MAP.get(area_type, area_type)


def _format_color_range(color_range: list[list[int]] | None) -> str:
    """格式化颜色范围。"""
    return '' if color_range is None else str(color_range)


class DevtoolsScreenManageInterface(VerticalScrollInterface, HistoryMixin):

    AREA_COLUMNS: list[ColumnMeta] = [
        ColumnMeta('操作', width=40),
        ColumnMeta('标识', width=40),
        ColumnMeta('类型', 'area_type', _parse_area_type, 90, _format_area_type),
        ColumnMeta('区域名称', 'area_name', lambda x: x),
        ColumnMeta('位置', 'pc_rect', _parse_rect, 170),
        ColumnMeta('前往画面', 'goto_list', lambda x: [i.strip() for i in x.split(',') if i.strip()],
                   formatter=lambda v: ','.join(v) if v else ''),
        ColumnMeta('手柄键', 'gamepad_key', lambda x: x.strip() or None, 120,
                   formatter=lambda v: '' if v is None else str(v)),
    ]

    AREA_FIELD_2_COLUMN: dict[str, int] = {col.display_name: idx for idx, col in enumerate(AREA_COLUMNS)}
    AREA_PARAM_PARSERS: dict[str, Callable[[str], Any]] = {
        'area_type': _parse_area_type,
        'area_name': lambda x: x,
        'pc_rect': _parse_rect,
        'text': lambda x: x,
        'lcs_percent': lambda x: float(x) if x else 0.5,
        'template_sub_dir': lambda x: x,
        'template_id': lambda x: x,
        'template_match_threshold': lambda x: float(x) if x else 0.7,
        'color_range': _parse_color_range,
        'color_match_threshold': lambda x: float(x) if x else 0.1,
        'goto_list': lambda x: [i.strip() for i in x.split(',') if i.strip()],
        'gamepad_key': lambda x: x.strip() or None,
    }

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

        self.chosen_screen: ScreenInfo | None = None
        self.last_screen_dir: str | None = None  # 上一次选择的图片路径
        self.area_param_rows: dict[str, QWidget] = {}
        self.area_param_inputs: dict[str, LineEdit] = {}
        self._updating_area_param: bool = False

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
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        self.merge_opt = PushSettingCard(
            icon=FluentIcon.SETTING,
            title='更新合并配置文件',
            content='手动更改yml文件后 需要触发更新生效',
            text='更新',
        )
        self.merge_opt.clicked.connect(self._on_merge_clicked)
        control_layout.addWidget(self.merge_opt)

        btn_row = Row(spacing=6, margins=Margins(0, 0, 0, 0))
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

        self.delete_btn = ToolButton(FluentIcon.DELETE, parent=None)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row.add_widget(self.delete_btn)

        self.cancel_btn = PushButton(text=gt('取消'))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.add_widget(self.cancel_btn)

        btn_row.add_stretch(1)

        img_btn_row = Row(spacing=6, margins=Margins(0, 0, 0, 0))
        control_layout.addWidget(img_btn_row)

        self.pc_alt_opt = CheckBox(text=gt('PC 点击需 Alt'))
        self.pc_alt_opt.stateChanged.connect(self._on_pc_alt_changed)
        img_btn_row.add_widget(self.pc_alt_opt)

        img_btn_row.add_stretch(1)

        self.choose_image_btn = PushButton(text=gt('选择图片'))
        self.choose_image_btn.clicked.connect(self.choose_existed_image)
        img_btn_row.add_widget(self.choose_image_btn)

        self.screenshot_btn = PushButton(text=gt('截图'))
        self.screenshot_btn.clicked.connect(self._on_screenshot_clicked)
        img_btn_row.add_widget(self.screenshot_btn)

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

        self.screen_info_opt = MultiLineSettingCard(
            icon=FluentIcon.HOME,
            title=gt('画面信息'),
            line_list=[
                [self.screen_id_label, self.screen_id_edit],
                [self.screen_name_label, self.screen_name_edit]
            ]
        )
        control_layout.addWidget(self.screen_info_opt)

        self._control_layout = control_layout
        self.table_widget = self._init_area_table_widget()
        control_layout.addWidget(self.table_widget, stretch=1)

        self.popup_table_btn = PushButton(text=gt('弹出表格'))
        self.popup_table_btn.clicked.connect(self._on_popup_table)
        control_layout.addWidget(self.popup_table_btn)

        self._popup_win: QDialog | None = None

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
        self.area_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area_table.setBorderVisible(True)
        self.area_table.setBorderRadius(8)
        self.area_table.setWordWrap(True)
        self.area_table.setColumnCount(len(self.AREA_COLUMNS))
        self.area_table.verticalHeader().hide()
        self.area_table.setHorizontalHeaderLabels([gt(col.display_name) for col in self.AREA_COLUMNS])
        for idx, col in enumerate(self.AREA_COLUMNS):
            if col.width is not None:
                self.area_table.setColumnWidth(idx, col.width)

        # 让表格宽度始终等于所有列宽之和
        self._sync_table_width()
        self.area_table.horizontalHeader().sectionResized.connect(self._on_table_column_resized)

        # table的行被选中时 触发
        self.area_table_row_selected: int | None = -1  # 选中的行
        self.area_table.cellClicked.connect(self.on_area_table_cell_clicked)

        # 将表格放入滚动区域
        scroll_area.setWidget(self.area_table)
        layout.addWidget(scroll_area)
        layout.addWidget(self._init_area_param_widget())

        return widget

    def _init_area_param_widget(self) -> QWidget:
        """创建区域类型参数控件。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 0, 12, 12)
        layout.setSpacing(6)

        title_label = BodyLabel(text=gt('区域参数'))
        layout.addWidget(title_label)

        param_meta_list = [
            ('text', 'OCR文本'),
            ('lcs_percent', 'OCR阈值'),
            ('template_sub_dir', '模板目录'),
            ('template_id', '模板ID'),
            ('template_match_threshold', '模板阈值'),
            ('color_range', '颜色范围'),
            ('color_match_threshold', '颜色阈值'),
        ]

        for attr_name, label_text in param_meta_list:
            row = Row(spacing=8, margins=Margins(0, 0, 0, 0))
            label = BodyLabel(text=gt(label_text))
            label.setFixedWidth(72)
            editor = LineEdit()
            editor.editingFinished.connect(lambda attr=attr_name: self._on_area_param_changed(attr))
            row.add_widget(label)
            row.add_widget(editor, stretch=1)
            layout.addWidget(row)
            self.area_param_rows[attr_name] = row
            self.area_param_inputs[attr_name] = editor

        return widget

    def _sync_table_width(self) -> None:
        """同步表格宽度为所有列宽之和。"""
        total = sum(
            self.area_table.columnWidth(c)
            for c in range(self.area_table.columnCount())
        )
        self.area_table.setFixedWidth(total + 2)

    def _on_table_column_resized(self, _index: int, _old: int, _new: int) -> None:
        """列宽变化时同步表格整体宽度。"""
        self._sync_table_width()

    def _on_popup_table(self) -> None:
        """弹出区域表格到独立窗口。"""
        if self._popup_win is not None:
            self._popup_win.activateWindow()
            return

        self._popup_win = QDialog(self)
        self._popup_win.setWindowTitle(gt('区域表格编辑'))
        self._popup_win.setWindowFlags(
            self._popup_win.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
        )
        self._popup_win.setMinimumSize(1200, 600)
        self._popup_win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._popup_win.destroyed.connect(self._on_popup_closed)

        popup_layout = QVBoxLayout(self._popup_win)
        popup_layout.setContentsMargins(4, 4, 4, 4)

        # 将表格卡片移到弹出窗口
        self.table_widget.setParent(self._popup_win)
        popup_layout.addWidget(self.table_widget)
        self.table_widget.show()
        self.popup_table_btn.hide()

        # 占位拉伸，把其他控件挤到顶部
        self._control_layout.addStretch(1)

        self._popup_win.show()

    def _on_popup_closed(self) -> None:
        """弹出窗口关闭后，将表格放回原位。"""
        # 移除占位拉伸（layout 最后一个 item）
        last = self._control_layout.count() - 1
        spacer = self._control_layout.itemAt(last)
        if spacer is not None and spacer.widget() is None:
            self._control_layout.removeItem(spacer)

        # 插到弹出按钮前面
        btn_idx = self._control_layout.indexOf(self.popup_table_btn)
        self._control_layout.insertWidget(btn_idx, self.table_widget, stretch=1)
        self.table_widget.show()
        self.popup_table_btn.show()
        self._popup_win = None

    def _update_existed_yml_options(self) -> None:
        """更新已有的yml选项。"""
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
        self.image_label.image_pasted.connect(self._on_image_pasted)
        layout.addWidget(self.image_label, 1)

        return widget

    def on_interface_shown(self) -> None:
        """子界面显示时 进行初始化。"""
        VerticalScrollInterface.on_interface_shown(self)
        self._update_display_by_screen()

    def _update_display_by_screen(self) -> None:
        """根据画面图片，统一更新界面的显示。"""
        chosen = self.chosen_screen is not None

        self.merge_opt.setDisabled(chosen)

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
        """更新区域表格的显示。"""
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
            id_check.setFixedSize(32, 32)
            id_check.setStyleSheet(id_check.styleSheet() + 'CheckBox { margin-left: 8px; }')

            self.area_table.setCellWidget(idx, 0, del_btn)
            self.area_table.setCellWidget(idx, 1, id_check)

            for col_idx, col in enumerate(self.AREA_COLUMNS):
                if col.attr_name is None:
                    continue
                if col.attr_name == 'area_type':
                    area_type_combo = ComboBox()
                    area_type_combo.set_items(AREA_TYPE_ITEMS, area_item.area_type)
                    area_type_combo.setProperty('row_idx', idx)
                    area_type_combo.currentIndexChanged.connect(self._on_area_type_changed)
                    self.area_table.setCellWidget(idx, col_idx, area_type_combo)
                    continue
                val = getattr(area_item, col.attr_name)
                text = col.formatter(val) if col.formatter else str(val)
                self.area_table.setItem(idx, col_idx, QTableWidgetItem(text))

        # 最后一行 只保留一个新增按钮
        add_btn = ToolButton(FluentIcon.ADD, parent=None)
        add_btn.setFixedSize(32, 32)
        add_btn.clicked.connect(self._on_area_add_clicked)
        self.area_table.setCellWidget(area_cnt, 0, add_btn)
        for col_idx in range(1, len(self.AREA_COLUMNS)):
            self.area_table.removeCellWidget(area_cnt, col_idx)
            self.area_table.setItem(area_cnt, col_idx, QTableWidgetItem(''))

        self.area_table.blockSignals(False)
        self._update_area_param_display()

    def _update_image_display(self):
        """更新图片显示。"""
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
        """选择了已有的yml。"""
        self.chosen_screen = None
        # 搜索时 输入了一半时候会找到对应的画面
        with suppress(Exception):
            self.chosen_screen = self.ctx.screen_loader.get_screen(screen_name, copy=True)
        if self.chosen_screen is None:
            return
        # 清除撤回记录
        self._clear_history()
        self._update_history_buttons()
        self._whole_update.signal.emit()

    def _on_create_clicked(self):
        """创建一个新的。"""
        if self.chosen_screen is not None:
            return

        self.chosen_screen = ScreenInfo({})
        # 清除撤回记录
        self._clear_history()
        self._whole_update.signal.emit()

    def _on_save_clicked(self) -> None:
        """保存。"""
        if self.chosen_screen is None:
            return

        self.ctx.screen_loader.save_screen(self.chosen_screen)
        self._existed_yml_update.signal.emit()

    def _on_delete_clicked(self) -> None:
        """删除。"""
        if self.chosen_screen is None:
            return
        self.ctx.screen_loader.delete_screen(self.chosen_screen.screen_id)
        self.chosen_screen = None
        self._whole_update.signal.emit()
        self._existed_yml_update.signal.emit()

    def _on_cancel_clicked(self) -> None:
        """取消编辑。"""
        self.chosen_screen = None
        self.existed_yml_btn.blockSignals(True)
        self.existed_yml_btn.setCurrentIndex(-1)
        self.existed_yml_btn.blockSignals(False)
        self.area_table_row_selected = -1
        self.x_pos_label.setText('')
        self.y_pos_label.setText('')
        # 清除撤回记录
        self._clear_history()
        self._whole_update.signal.emit()

    def choose_existed_image(self) -> None:
        """选择已有的环图片。"""
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
        """选择图片之后的回调。"""
        if self.chosen_screen is None:
            return

        self.chosen_screen.screen_image = cv2_utils.read_image(image_file_path)
        self._image_update.signal.emit()

    def _on_screenshot_clicked(self) -> None:
        """
        截图按钮点击
        :return:
        """
        _, screen = self.ctx.controller.screenshot()
        if screen is None:
            return

        if self.chosen_screen is None:
            # 没有选中画面时，自动创建一个新的
            self.chosen_screen = ScreenInfo({})
            # 清除撤回记录
            self._clear_history()
            self._whole_update.signal.emit()

        self.chosen_screen.screen_image = screen
        self._image_update.signal.emit()

    def _on_image_pasted(self, image_data) -> None:
        """通过拖放或粘贴加载图片后的回调，等同于“选择图片”。

        Args:
            image_data: 文件路径 (str) 或 numpy 数组 (RGB 格式)
        """
        if self.chosen_screen is None:
            return

        if isinstance(image_data, str):
            # 文件路径，使用 read_image 读取
            self.chosen_screen.screen_image = cv2_utils.read_image(image_data)
        else:
            # numpy 数组，直接使用
            self.chosen_screen.screen_image = image_data
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
        """选择模板后 导入模板对应的区域。

        Args:
            template_file_path: 模板文件路径
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
        area.area_type = ScreenArea.AREA_TYPE_TEMPLATE

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
        """新增一个区域。"""
        if self.chosen_screen is None:
            return

        self.chosen_screen.area_list.append(ScreenArea())
        self._area_table_update.signal.emit()

    def _get_selected_area(self) -> ScreenArea | None:
        """获取当前选中的区域。"""
        if self.chosen_screen is None:
            return None
        if self.area_table_row_selected is None:
            return None
        if self.area_table_row_selected < 0 or self.area_table_row_selected >= len(self.chosen_screen.area_list):
            return None
        return self.chosen_screen.area_list[self.area_table_row_selected]

    def _on_area_type_changed(self, _index: int) -> None:
        """区域类型变化。"""
        if self.chosen_screen is None:
            return
        combo: ComboBox = self.sender()
        if combo is None:
            return

        row_idx = combo.property('row_idx')
        if row_idx is None or row_idx < 0 or row_idx >= len(self.chosen_screen.area_list):
            return

        area_item = self.chosen_screen.area_list[row_idx]
        new_value = combo.currentData()
        if new_value is None or new_value == area_item.area_type:
            return

        old_value = area_item.area_type
        area_item.area_type = new_value
        self.area_table_row_selected = row_idx

        table_change = {
            'type': 'table_edit',
            'row_index': row_idx,
            'change_type': 'area_type',
            'old_value': old_value,
            'new_value': new_value,
        }
        self._add_history_record(table_change)
        self._update_area_param_display()

    def _update_area_param_display(self) -> None:
        """根据选中区域类型更新参数编辑区。"""
        if not self.area_param_inputs:
            return

        area_item = self._get_selected_area()
        visible_map = {
            'text': area_item is not None and area_item.is_text_area,
            'lcs_percent': area_item is not None and area_item.is_text_area,
            'template_sub_dir': area_item is not None and area_item.is_template_area,
            'template_id': area_item is not None and area_item.is_template_area,
            'template_match_threshold': area_item is not None and area_item.is_template_area,
            'color_range': area_item is not None and (area_item.is_text_area or area_item.is_color_area),
            'color_match_threshold': area_item is not None and area_item.is_color_area,
        }

        self._updating_area_param = True
        for attr_name, row in self.area_param_rows.items():
            row.setVisible(visible_map.get(attr_name, False))
            editor = self.area_param_inputs[attr_name]
            if area_item is None:
                editor.setText('')
                continue
            value = getattr(area_item, attr_name)
            if attr_name == 'color_range':
                text = _format_color_range(value)
            else:
                text = '' if value is None else str(value)
            editor.setText(text)
        self._updating_area_param = False

    def _on_area_param_changed(self, attr_name: str) -> None:
        """区域参数变化。"""
        if self._updating_area_param:
            return

        area_item = self._get_selected_area()
        if area_item is None:
            return

        editor = self.area_param_inputs[attr_name]
        text = editor.text().strip()
        parser = self._get_attr_parser(attr_name)
        old_value = getattr(area_item, attr_name)

        try:
            new_value = parser(text) if parser is not None else text
        except Exception as e:
            log.error('解析失败', exc_info=True)
            self.show_info_bar(
                '解析失败',
                f'{attr_name}: {e}',
                icon=InfoBarIcon.ERROR,
                duration=5000,
            )
            self._update_area_param_display()
            return

        if new_value == old_value:
            return

        setattr(area_item, attr_name, new_value)
        table_change = {
            'type': 'table_edit',
            'row_index': self.area_table_row_selected,
            'change_type': attr_name,
            'old_value': old_value,
            'new_value': text,
        }
        self._add_history_record(table_change)

    def _on_row_delete_clicked(self):
        """删除一行。"""
        if self.chosen_screen is None:
            return

        button_idx = self.sender()
        if button_idx is not None:
            row_idx = self.area_table.indexAt(button_idx.pos()).row()
            self.chosen_screen.remove_area_by_idx(row_idx)
            self.area_table.removeRow(row_idx)
            self._image_update.signal.emit()

    def _get_attr_parser(self, attr_name: str) -> Callable[[str], Any] | None:
        """获取字段解析器。"""
        return self.AREA_PARAM_PARSERS.get(attr_name)

    def _on_area_table_cell_changed(self, row: int, column: int) -> None:
        """表格内容改变。"""
        if self.chosen_screen is None:
            return
        if row < 0 or row >= len(self.chosen_screen.area_list):
            return
        item = self.area_table.item(row, column)
        if item is None:
            return
        area_item = self.chosen_screen.area_list[row]
        text = item.text().strip()

        # 直接从 AREA_COLUMNS 获取属性名和解析器
        if column >= len(self.AREA_COLUMNS):
            return
        col_meta = self.AREA_COLUMNS[column]
        if col_meta.attr_name is None:
            return
        attr_name = col_meta.attr_name
        handler = self._get_attr_parser(attr_name)

        # 记录修改前的状态
        old_value = getattr(area_item, attr_name)

        # 应用新值
        try:
            new_value = handler(text) if handler is not None else text
            setattr(area_item, attr_name, new_value)
            if attr_name == 'pc_rect':
                self._image_update.signal.emit()
        except Exception as e:
            # 如果解析失败，不进行修改
            log.error('解析失败', exc_info=True)
            self.show_info_bar(
                '解析失败',
                f'{col_meta.display_name}: {e}',
                icon=InfoBarIcon.ERROR,
                duration=5000,
            )
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

    def _on_image_left_clicked(self, x: int, y: int) -> None:
        """图片上左键单击后显示坐标。

        Args:
            x: 点击的x坐标
            y: 点击的y坐标
        """
        if self.chosen_screen is None or self.chosen_screen.screen_image is None:
            return

        self.x_pos_label.setText(str(x))
        self.y_pos_label.setText(str(y))

    def _on_image_rect_selected(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """在图片上选择一个区域后的回调。"""
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
        self.area_table.item(self.area_table_row_selected, self.AREA_FIELD_2_COLUMN['位置']).setText(f'({x1}, {y1}, {x2}, {y2})')
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
        self._update_area_param_display()

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
            setattr(area_item, change_type, old_value)

            # 如果是坐标修改，需要更新图像显示
            if change_type == 'pc_rect':
                self._image_update.signal.emit()

            # 更新表格显示
            self._update_area_table_display()
            self._update_area_param_display()

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
            self.area_table.item(row_index, self.AREA_FIELD_2_COLUMN['位置']).setText(f'({old_rect.x1}, {old_rect.y1}, {old_rect.x2}, {old_rect.y2})')
            self.area_table.blockSignals(False)

            # 更新图像显示
            self._image_update.signal.emit()
            self._update_area_param_display()

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

            # 将文本恢复为正确类型
            parser = self._get_attr_parser(change_type)
            parsed = parser(new_value) if parser else new_value
            setattr(area_item, change_type, parsed)

            if change_type == 'pc_rect':
                self._image_update.signal.emit()

            # 更新表格显示
            self._area_table_update.signal.emit()
            self._update_area_param_display()

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
            self.area_table.item(row_index, self.AREA_FIELD_2_COLUMN['位置']).setText(f'({new_rect.x1}, {new_rect.y1}, {new_rect.x2}, {new_rect.y2})')
            self.area_table.blockSignals(False)

            # 更新图像显示
            self._image_update.signal.emit()
            self._update_area_param_display()

    def _on_merge_clicked(self) -> None:
        self.ctx.screen_loader.reload(from_separated_files=True)
        self.ctx.screen_loader.save(reload_after_save=False)
        self._existed_yml_update.signal.emit()
