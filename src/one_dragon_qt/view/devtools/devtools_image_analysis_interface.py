from functools import partial

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, QFileDialog, QApplication
from qfluentwidgets import (
    ComboBox, CheckBox, SpinBox, DoubleSpinBox, PushButton, ToolButton, PlainTextEdit, LineEdit,
    FluentIcon, SubtitleLabel, BodyLabel, InfoBar, InfoBarPosition, MessageBoxBase, Dialog,
    ListWidget, SimpleCardWidget, SingleDirectionScrollArea
)

from one_dragon.base.cv_process.cv_step import CvStep
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.logic.image_analysis_logic import ImageAnalysisLogic
from one_dragon_qt.widgets.color_channel_dialog import ColorChannelDialog
from one_dragon_qt.widgets.color_tip import ColorTip
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.zoomable_image_label import ZoomableClickImageLabel


class PipelineNameDialog(MessageBoxBase):
    """ Custom message box for entering pipeline name """

    def __init__(self, title: str, default_text: str = '', parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        self.name_edit = LineEdit(self)

        self.yesButton.setText(gt('确定'))
        self.cancelButton.setText(gt('取消'))

        self.name_edit.setText(default_text)
        self.name_edit.setPlaceholderText(gt('请输入流水线名称'))
        self.name_edit.setClearButtonEnabled(True)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.name_edit)

        self.widget.setMinimumWidth(360)


class DevtoolsImageAnalysisInterface(VerticalScrollInterface):
    _CREATE_NEW_PIPELINE_TEXT = '[ 新建流水线... ]'

    def __init__(self, ctx: OneDragonContext, parent=None):
        self.ctx: OneDragonContext = ctx
        self.logic = ImageAnalysisLogic(ctx)
        self.param_layout: QVBoxLayout = None
        self.param_widgets = []  # 用于存储动态创建的参数控件，用于统一删除
        self.param_widget_map = {}  # 用于通过参数名快速查找控件 {param_name: input_widget}

        VerticalScrollInterface.__init__(
            self,
            content_widget=self._init_content_widget(),
            object_name='devtools_image_analysis_interface',
            parent=parent,
            nav_text_cn='图像分析'
        )

        self._init_signal_connections()

        self._update_pipeline_combo()
        self._update_ui_status()

    def _init_signal_connections(self):
        """
        初始化信号和槽的连接
        """
        self.open_btn.clicked.connect(self._on_open_image)
        self.image_label.right_clicked_with_pos.connect(self._on_image_right_clicked)
        self.image_label.rect_selected.connect(self._on_image_rect_selected)
        self.del_btn.clicked.connect(self._on_delete_step)
        self.copy_btn.clicked.connect(self._on_copy_code_clicked)
        self.up_btn.clicked.connect(self._on_move_step_up)
        self.down_btn.clicked.connect(self._on_move_step_down)
        self.add_step_combo.currentIndexChanged.connect(self._on_add_step_by_combo)
        self.run_btn.clicked.connect(self._on_run_pipeline)
        self.toggle_view_btn.clicked.connect(self._on_toggle_view)
        self.color_channel_btn.clicked.connect(self._on_color_channel_clicked)
        self.pipeline_list_widget.currentItemChanged.connect(self._on_pipeline_selection_changed)

        # 流水线管理
        self.pipeline_combo.currentIndexChanged.connect(self._on_pipeline_combo_changed)
        self.save_pipeline_btn.clicked.connect(self._on_save_pipeline)
        self.save_as_pipeline_btn.clicked.connect(self._on_save_as_pipeline)
        self.rename_pipeline_btn.clicked.connect(self._on_rename_pipeline)
        self.delete_pipeline_btn.clicked.connect(self._on_delete_pipeline_btn_clicked)

    def _init_content_widget(self) -> QWidget:
        """
        初始化主内容控件 (容器A)
        """
        # 主容器A，水平布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # 左侧控制面板B
        control_panel_b = self._init_control_panel()

        # 右侧显示面板C
        display_panel_c = self._init_display_panel()

        main_layout.addWidget(control_panel_b)
        main_layout.addWidget(display_panel_c, stretch=1)

        return main_widget

    def _init_control_panel(self) -> QWidget:
        """
        初始化左侧的控制面板 (容器B)，垂直布局
        """
        # 容器B，垂直布局
        scroll_area = SingleDirectionScrollArea()

        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 16, 0)
        control_layout.setSpacing(12)

        # B1: 顶部操作按钮
        op_buttons_widget = self._init_op_buttons()

        # B2: 流水线列表
        pipeline_widget = self._init_pipeline_list_widget()

        # B3: 参数区域
        param_widget = self._init_step_param_widget()

        # B4: 文字结果
        result_widget = self._init_result_widget()

        control_layout.addWidget(op_buttons_widget)
        control_layout.addWidget(pipeline_widget)
        control_layout.addWidget(param_widget)
        control_layout.addWidget(result_widget)

        scroll_area.setWidget(control_widget)
        scroll_area.setWidgetResizable(True)

        return scroll_area

    def _init_display_panel(self) -> QWidget:
        """
        初始化右侧的显示面板 (容器C)，垂直布局
        """
        # 容器C，垂直布局
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(12)

        # C1: 图像显示区域
        self.image_label = ZoomableClickImageLabel()

        display_layout.addWidget(self.image_label, stretch=1)

        return display_widget

    def _init_op_buttons(self) -> QWidget:
        """
        创建顶部的操作按钮 (B1)
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        self.open_btn = PushButton(text=gt('打开图片'), icon=FluentIcon.DOCUMENT)
        layout.addWidget(self.open_btn)
        self.toggle_view_btn = PushButton(text=gt('切换视图'))
        layout.addWidget(self.toggle_view_btn)
        self.run_btn = PushButton(text=gt('执行'), icon=FluentIcon.PLAY_SOLID)
        layout.addWidget(self.run_btn)
        self.color_channel_btn = PushButton(text=gt('色彩通道'), icon=FluentIcon.INFO)
        layout.addWidget(self.color_channel_btn)
        layout.addStretch(1)
        return widget

    def _init_pipeline_list_widget(self) -> QWidget:
        """
        创建流水线步骤列表控件 (B2)
        """
        widget = SimpleCardWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 流水线管理面板
        pipeline_manage_widget = self._init_pipeline_manage_widget()
        layout.addWidget(pipeline_manage_widget)

        # 流水线步骤列表
        self.pipeline_list_widget = ListWidget()
        layout.addWidget(self.pipeline_list_widget)

        # 步骤管理按钮
        step_manage_widget = self._init_step_manage_widget()
        layout.addWidget(step_manage_widget)

        return widget

    def _init_pipeline_manage_widget(self) -> QWidget:
        """
        创建流水线管理面板
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.pipeline_combo = ComboBox()
        self.pipeline_combo.setPlaceholderText(gt('选择或新建流水线'))
        layout.addWidget(self.pipeline_combo, 1)

        self.save_pipeline_btn = PushButton(gt('保存'))
        layout.addWidget(self.save_pipeline_btn)

        self.save_as_pipeline_btn = PushButton(gt('另存为'))
        layout.addWidget(self.save_as_pipeline_btn)

        self.rename_pipeline_btn = PushButton(gt('重命名'))
        layout.addWidget(self.rename_pipeline_btn)

        self.delete_pipeline_btn = PushButton(gt('删除'))
        layout.addWidget(self.delete_pipeline_btn)

        return widget

    def _init_step_manage_widget(self) -> QWidget:
        """
        创建步骤管理面板
        """
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.add_step_combo = ComboBox()
        self.add_step_combo.setPlaceholderText(gt('添加步骤'))
        self.add_step_combo.addItems(self.logic.get_available_step_names())
        self.add_step_combo.setCurrentIndex(-1)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.add_step_combo)
        self.del_btn = PushButton(gt('删除步骤'))
        btn_layout.addWidget(self.del_btn)
        self.copy_btn = PushButton(gt('复制方法'))
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addSpacing(20)
        self.up_btn = ToolButton(FluentIcon.UP)
        btn_layout.addWidget(self.up_btn)
        self.down_btn = ToolButton(FluentIcon.DOWN)
        btn_layout.addWidget(self.down_btn)
        btn_layout.addStretch(1)
        return btn_widget

    def _init_step_param_widget(self) -> QWidget:
        """
        创建单个步骤的参数设置控件 (B3)
        """
        widget = SimpleCardWidget()
        self.param_layout = QVBoxLayout(widget)
        self.param_layout.setContentsMargins(12, 8, 12, 8)
        self.param_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.param_title_label = SubtitleLabel(gt('参数设置'))
        self.param_layout.addWidget(self.param_title_label)

        return widget

    def _init_result_widget(self) -> QWidget:
        """
        创建结果文本框 (B4)
        """
        self.result_text = PlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setObjectName('result_text')
        self.result_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.result_text.setFixedHeight(150)
        return self.result_text

    def _update_param_display(self):
        """
        根据当前选中的步骤，更新参数显示区域
        """
        self._clear_param_widgets()

        current_row = self.pipeline_list_widget.currentRow()
        if current_row < 0 or current_row >= len(self.logic.pipeline.steps):
            self.param_title_label.setText(gt('参数设置'))
            return

        step = self.logic.pipeline.steps[current_row]
        self.param_title_label.setText(f"{step.name} - {gt('参数设置')}")

        description = step.get_description()
        if description:
            desc_label = BodyLabel(description)
            desc_label.setWordWrap(True)
            self.param_layout.addWidget(desc_label)
            self.param_widgets.append(desc_label)

        param_defs = step.get_params()
        for param_name, definition in param_defs.items():
            self._create_param_widget(step, param_name, definition)

        # 首次加载时，触发一次所有根参数的更新，确保子控件被正确初始化
        for param_name, definition in param_defs.items():
            if 'parent' not in definition:
                self._refresh_dependent_widgets(step, param_name)

    def _clear_param_widgets(self):
        """
        清除所有动态生成的参数控件
        """
        for widget in self.param_widgets:
            self.param_layout.removeWidget(widget)
            widget.deleteLater()
        self.param_widgets.clear()
        self.param_widget_map.clear()

    def _create_param_row(self, label_text: str, input_widget: QWidget) -> QWidget:
        """
        创建一个参数行，包含一个标签和一个输入控件
        :param label_text: 标签文本
        :param input_widget: 输入控件
        :return:
        """
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        label_widget = BodyLabel(label_text)
        row_layout.addWidget(label_widget)
        row_layout.addStretch(1)
        row_layout.addWidget(input_widget)
        return row_widget

    def _create_param_widget(self, step: CvStep, param_name: str, definition: dict):
        """
        为单个参数创建输入控件
        """
        param_type = definition['type']
        label_text = definition.get('label', param_name)
        tooltip_text = definition.get('tooltip', None)

        def _set_tooltip(widget: QWidget):
            if tooltip_text:
                widget.setToolTip(tooltip_text)

        input_widget = None

        if param_type == 'tuple_int':
            # 元组参数比较特殊，因为它创建了多个行，所以单独处理
            component_labels = ['R', 'G', 'B'] if 'rgb' in param_name else ['H', 'S', 'V']
            current_value = step.params.get(param_name, definition.get('default', (0, 0, 0)))

            if not isinstance(current_value, (list, tuple)):
                current_value = definition.get('default', (0, 0, 0))
                step.params[param_name] = current_value

            for i in range(len(current_value)):
                sub_label_text = f"{label_text} {component_labels[i]}"
                spin_box = SpinBox()
                spin_box.setFixedWidth(160)
                param_range = definition.get('range', [(0, 255), (0, 255), (0, 255)])
                min_val, max_val = param_range[i] if isinstance(param_range[0], tuple) else param_range
                spin_box.setRange(min_val, max_val)
                spin_box.setValue(current_value[i])
                spin_box.valueChanged.connect(partial(self._on_tuple_param_changed, step, param_name, i))

                tuple_row = self._create_param_row(sub_label_text, spin_box)
                _set_tooltip(tuple_row)
                self.param_layout.addWidget(tuple_row)
                self.param_widgets.append(tuple_row)
            return  # 直接返回，不走下面的通用逻辑

        elif param_type == 'int':
            spin_box = SpinBox()
            spin_box.setFixedWidth(160)
            min_val, max_val = definition.get('range', (0, 9999))
            spin_box.setRange(min_val, max_val)
            spin_box.setValue(step.params.get(param_name, definition.get('default', 0)))
            spin_box.valueChanged.connect(partial(self._on_param_value_changed, step, param_name))
            input_widget = spin_box
        elif param_type == 'bool':
            check_box = CheckBox()
            check_box.setChecked(step.params.get(param_name, definition.get('default', False)))
            check_box.stateChanged.connect(partial(self._on_param_value_changed, step, param_name))
            input_widget = check_box
        elif param_type == 'enum':
            combo_box = ComboBox()
            combo_box.addItems(definition.get('options', []))
            combo_box.setCurrentText(step.params.get(param_name, definition.get('default', '')))
            combo_box.currentTextChanged.connect(partial(self._on_param_value_changed, step, param_name))
            input_widget = combo_box
        elif param_type == 'float':
            spin_box = DoubleSpinBox()
            spin_box.setFixedWidth(160)
            min_val, max_val = definition.get('range', (0.0, 1.0))
            spin_box.setRange(min_val, max_val)
            spin_box.setValue(step.params.get(param_name, definition.get('default', 0.0)))
            spin_box.setSingleStep(0.1)
            spin_box.valueChanged.connect(partial(self._on_param_value_changed, step, param_name))
            input_widget = spin_box
        elif param_type == 'enum_template':
            combo_box = ComboBox()
            template_infos = self.logic.get_template_info_list()
            if not template_infos:
                combo_box.setPlaceholderText(gt('无可用模板'))
                combo_box.setEnabled(False)
            else:
                template_names = [f"{t.sub_dir}/{t.template_id}" for t in template_infos]
                combo_box.addItems(template_names)
                combo_box.setCurrentText(step.params.get(param_name, definition.get('default', '')))
            combo_box.currentTextChanged.connect(partial(self._on_param_value_changed, step, param_name))
            input_widget = combo_box
        elif param_type == 'enum_screen_name':
            combo_box = ComboBox()
            screen_names = self.logic.get_screen_names()
            combo_box.addItems(screen_names)
            combo_box.setCurrentText(step.params.get(param_name, definition.get('default', '')))
            combo_box.currentTextChanged.connect(partial(self._on_param_value_changed, step, param_name))
            input_widget = combo_box
        elif param_type == 'enum_area_name':
            combo_box = ComboBox()
            # 初始为空，由 _refresh_dependent_widgets 填充
            combo_box.setCurrentText(step.params.get(param_name, definition.get('default', '')))
            combo_box.currentTextChanged.connect(partial(self._on_param_value_changed, step, param_name))
            input_widget = combo_box

        if input_widget:
            row = self._create_param_row(label_text, input_widget)
            _set_tooltip(row)
            self.param_layout.addWidget(row)
            self.param_widgets.append(row)
            self.param_widget_map[param_name] = input_widget

    def _on_param_value_changed(self, step: CvStep, param_name: str, value):
        """
        当一个参数值发生变化时，更新模型并触发依赖刷新
        """
        # 对于 CheckBox，信号传递的是 Qt.CheckState 枚举，需要转换为 bool
        if isinstance(value, Qt.CheckState):
            value = (value == Qt.CheckState.Checked)

        # 如果值没有实际变化，则不进行任何操作，防止不必要的刷新和信号循环
        if step.params.get(param_name) == value:
            return

        step.params[param_name] = value
        self._refresh_dependent_widgets(step, param_name)

    def _refresh_dependent_widgets(self, step: CvStep, changed_param_name: str):
        """
        刷新所有依赖于某个参数的控件
        """
        param_defs = step.get_params()

        for child_param_name, definition in param_defs.items():
            if definition.get('parent') == changed_param_name:
                child_input_widget = self.param_widget_map.get(child_param_name)
                if not child_input_widget or not isinstance(child_input_widget, ComboBox):
                    continue

                parent_value = step.params.get(changed_param_name)

                new_options = []
                child_param_type = definition.get('type')

                if child_param_type == 'enum_area_name':
                    new_options = self.logic.get_area_names_by_screen(parent_value) if parent_value else []

                child_input_widget.blockSignals(True)
                # 优先从数据模型中恢复值，而不是从UI状态中恢复
                current_child_value = step.params.get(child_param_name)
                child_input_widget.clear()
                child_input_widget.addItems(new_options)

                if current_child_value and current_child_value in new_options:
                    child_input_widget.setCurrentText(current_child_value)
                else:
                    # 如果之前保存的值在新选项中不存在，则清空模型和UI
                    if current_child_value is not None:
                        step.params[child_param_name] = ''
                    child_input_widget.setCurrentIndex(-1)

                child_input_widget.blockSignals(False)

    def _on_tuple_param_changed(self, step: CvStep, param_name: str, index: int, value: int):
        """
        当元组参数值发生变化时 (特殊处理)
        """
        current_tuple = list(step.params.get(param_name, ()))
        if index < len(current_tuple):
            current_tuple[index] = value
            step.params[param_name] = tuple(current_tuple)

    def _on_simple_param_changed(self, step: CvStep, param_name: str, value):
        """
        当简单的参数值发生变化时
        """
        step.params[param_name] = value

    def _update_pipeline_list(self):
        """
        刷新流水线列表显示
        """
        self.pipeline_list_widget.clear()
        for step in self.logic.pipeline.steps:
            self.pipeline_list_widget.addItem(step.name)

    def _on_add_step_by_combo(self, index: int):
        """
        通过下拉框选择后添加步骤
        """
        if index < 0:
            return

        step_name = self.add_step_combo.itemText(index)
        if not step_name:
            return

        # 添加后重置，方便再次添加
        self.add_step_combo.setCurrentIndex(-1)

        self.logic.add_step(step_name)
        self._update_pipeline_list()
        self.pipeline_list_widget.setCurrentRow(len(self.logic.pipeline.steps) - 1)

    def _on_delete_step(self):
        """
        删除当前选中的步骤
        """
        current_row = self.pipeline_list_widget.currentRow()
        if current_row < 0:
            return

        self.logic.remove_step(current_row)
        self._update_pipeline_list()

        # 更新参数显示，如果列表空了就清空
        if len(self.logic.pipeline.steps) == 0:
            self._update_param_display()
        else:
            # 选中被删除项的前一项，或第一项
            new_row = max(0, current_row - 1)
            self.pipeline_list_widget.setCurrentRow(new_row)

    def _on_copy_code_clicked(self):
        """
        复制流水线代码到剪贴板
        """
        code = self.logic.get_pipeline_code()
        clipboard = QApplication.clipboard()
        clipboard.setText(code)
        InfoBar.success(
            title=gt('成功'),
            content=gt('已将方法代码复制到剪贴板'),
            duration=3000,
            parent=self,
            position=InfoBarPosition.TOP
        )

    def _on_move_step_up(self):
        """
        上移一个步骤
        """
        row = self.pipeline_list_widget.currentRow()
        if row > 0:
            self.logic.move_step_up(row)
            self._update_pipeline_list()
            self.pipeline_list_widget.setCurrentRow(row - 1)

    def _on_move_step_down(self):
        """
        下移一个步骤
        """
        row = self.pipeline_list_widget.currentRow()
        if 0 <= row < self.pipeline_list_widget.count() - 1:
            self.logic.move_step_down(row)
            self._update_pipeline_list()
            self.pipeline_list_widget.setCurrentRow(row + 1)

    def _on_pipeline_selection_changed(self):
        """
        当流水线中的步骤选择变化时，更新参数面板
        """
        self._update_param_display()

    def _on_run_pipeline(self):
        """
        执行流水线
        """
        if self.logic.context is None:
            InfoBar.error(
                title=gt('错误'),
                content=gt('请先打开一张图片'),
                duration=3000,
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        if self.logic.active_pipeline_name is None:
            InfoBar.error(
                title=gt('错误'),
                content=gt('请先选择一个流水线'),
                duration=3000,
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        display_image, results = self.logic.execute_pipeline()
        self._display_image(display_image)

        # 格式化显示结果，包括性能数据
        result_lines = []
        if self.logic.context.analysis_results:
            result_lines.extend(self.logic.context.analysis_results)
            result_lines.append("\n" + "="*20 + "\n")

        if self.logic.context.step_execution_times:
            result_lines.append(f"--- {gt('性能分析')} ---")
            for step_name, t in self.logic.context.step_execution_times:
                result_lines.append(f"[{step_name}] - {t:.2f} ms")
            result_lines.append("-" * 20)
            result_lines.append(f"{gt('总耗时')}: {self.logic.context.total_execution_time:.2f} ms")

        self.result_text.setPlainText('\n'.join(result_lines))
        self._update_toggle_button_text()

    def _on_toggle_view(self):
        """
        切换显示原图/处理后
        """
        self.logic.toggle_display()
        self._display_image(self.logic.get_display_image())
        self._update_toggle_button_text()

    def _update_toggle_button_text(self):
        """
        更新切换视图按钮的文本
        """
        self.toggle_view_btn.setText(self.logic.get_current_view_name())

    def _on_open_image(self):
        """
        响应打开图片按钮
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, gt('打开图片文件'), '', 'Image Files (*.png *.jpg *.bmp)'
        )

        if not file_path:
            return

        if self.logic.load_image(file_path):
            self._display_image(self.logic.get_display_image())
            self._update_toggle_button_text()

    def _display_image(self, image_np: np.ndarray):
        """
        在UI上显示图像
        :param image_np: np格式的图像
        """
        if image_np is None:
            return

        # 根据维度判断图像类型并提取基本尺寸信息
        ndim = image_np.ndim
        if ndim not in (2, 3):
            return

        height, width = image_np.shape[0], image_np.shape[1]

        # 创建连续内存的 uint8 视图
        arr = np.ascontiguousarray(image_np.astype(np.uint8, copy=False))

        if ndim == 2:  # 灰度
            q_image = QImage(arr.data, width, height, int(arr.strides[0]), QImage.Format.Format_Grayscale8).copy()
        elif ndim == 3:  # 彩色
            channel = image_np.shape[2]
            if channel == 3:
                q_image = QImage(arr.data, width, height, int(arr.strides[0]), QImage.Format.Format_RGB888).copy()
            elif channel == 4:
                q_image = QImage(arr.data, width, height, int(arr.strides[0]), QImage.Format.Format_RGBA8888).copy()
            else:
                return

        pixmap = QPixmap.fromImage(q_image)
        self.image_label.setPixmap(pixmap, preserve_state=True)

    def _on_image_right_clicked(self, x: int, y: int):
        """
        响应图片右键点击
        """
        if self.logic.context is None:
            return

        color_info = self.logic.get_color_info_at(x, y)
        if color_info is None:
            return

        # 准备颜色信息列表
        color_infos = []

        # 当前图像信息
        if color_info.get('display_rgb') and color_info.get('display_hsv'):
            color_infos.append({
                'pos': color_info.get('pos'),
                'rgb': color_info.get('display_rgb'),
                'hsv': color_info.get('display_hsv'),
                'title': gt('当前图像')
            })

        # 原始图像信息
        if color_info.get('source_rgb') and color_info.get('source_hsv'):
            color_infos.append({
                'pos': color_info.get('source_pos'),
                'rgb': color_info.get('source_rgb'),
                'hsv': color_info.get('source_hsv'),
                'title': gt('原始图像')
            })

        # 显示颜色提示框
        if color_infos:
            ColorTip.show_color_tip(self.image_label, color_infos, self)

    def _on_image_rect_selected(self, left: int, top: int, right: int, bottom: int):
        """
        响应框选
        """
        if self.logic.context is None:
            return
        # 轻量反馈：仅提示选择区域坐标，避免误用再次坐标转换
        InfoBar.success(
            title=gt('已选择区域'),
            content=f"({left}, {top}) - ({right}, {bottom})",
            duration=2000,
            parent=self,
            position=InfoBarPosition.TOP
        )

    def _on_color_channel_clicked(self):
        """
        响应色彩通道按钮点击
        """
        if self.logic.context is None:
            InfoBar.error(
                title=gt('错误'),
                content=gt('请先打开一张图片'),
                duration=3000,
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        # 获取当前显示的图像
        display_image = self.logic.get_display_image()
        if display_image is None:
            InfoBar.error(
                title=gt('错误'),
                content=gt('没有可用的图像进行分析'),
                duration=3000,
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        # 显示色彩通道弹窗
        dialog = ColorChannelDialog(display_image, self.window())
        dialog.exec()

    def _update_pipeline_combo(self):
        """
        刷新流水线选择框
        """
        self.pipeline_combo.blockSignals(True)
        current_text = self.pipeline_combo.currentText()
        self.pipeline_combo.clear()

        pipelines = self.logic.get_pipeline_names()
        all_items = [self._CREATE_NEW_PIPELINE_TEXT] + pipelines
        self.pipeline_combo.addItems(all_items)

        if current_text in all_items:
            self.pipeline_combo.setCurrentText(current_text)
        else:
            self.pipeline_combo.setCurrentIndex(0)
        self.pipeline_combo.blockSignals(False)

    def _update_ui_status(self):
        """
        根据当前状态更新UI控件的启用/禁用
        """
        is_new = self.logic.active_pipeline_name is None
        self.run_btn.setEnabled(not is_new)
        self.save_pipeline_btn.setEnabled(not is_new)
        self.rename_pipeline_btn.setEnabled(not is_new)
        self.delete_pipeline_btn.setEnabled(not is_new)
        self.save_as_pipeline_btn.setEnabled(True)  # 另存为总是可用

    def _on_pipeline_combo_changed(self, index: int):
        """
        当流水线选择变化时
        """
        if index < 0:
            return

        pipeline_name = self.pipeline_combo.itemText(index)
        if pipeline_name == self._CREATE_NEW_PIPELINE_TEXT:
            self.logic.active_pipeline_name = None
            self.logic.pipeline.steps.clear()
        else:
            if not self.logic.load_pipeline(pipeline_name):
                InfoBar.error(gt('失败'), f"{gt('流水线')} {pipeline_name} {gt('加载失败')}", parent=self)
                return

        self._update_pipeline_list()
        self._update_param_display()
        self._update_ui_status()

    def _on_save_pipeline(self):
        """
        保存当前流水线
        """
        if self.logic.save_pipeline(self.logic.active_pipeline_name):
            InfoBar.success(gt('成功'), f"{gt('流水线')} {self.logic.active_pipeline_name} {gt('已保存')}", parent=self)
        else:
            InfoBar.error(gt('失败'), gt('流水线保存失败'), parent=self)

    def _on_save_as_pipeline(self):
        """
        另存为流水线
        """
        dialog = PipelineNameDialog(gt('另存为'), parent=self.window())
        if dialog.exec():
            text = dialog.name_edit.text()
            if text:
                if self.logic.save_pipeline(text):
                    self._update_pipeline_combo()
                    self.pipeline_combo.setCurrentText(text)
                    self._update_ui_status()
                    InfoBar.success(gt('成功'), f"{gt('流水线已另存为')} {text}", parent=self)
                else:
                    InfoBar.error(gt('失败'), gt('另存为失败'), parent=self)

    def _on_rename_pipeline(self):
        """
        重命名流水线
        """
        old_name = self.logic.active_pipeline_name
        if not old_name:
            return

        dialog = PipelineNameDialog(gt('重命名'), default_text=old_name, parent=self.window())
        if dialog.exec():
            new_name = dialog.name_edit.text()
            if new_name and new_name != old_name:
                self.logic.rename_pipeline(old_name, new_name)
                self._update_pipeline_combo()
                self.pipeline_combo.setCurrentText(new_name)
                InfoBar.success(gt('成功'), f"{gt('流水线已重命名为')} {new_name}", parent=self)

    def _on_delete_pipeline_btn_clicked(self):
        """
        删除当前选中的流水线
        """
        name_to_delete = self.logic.active_pipeline_name
        if not name_to_delete:
            return

        dialog = Dialog(gt('确认删除'), f"{gt('您确定要删除流水线')} `{name_to_delete}` ?\n{gt('此操作无法撤销。')}", self.window())
        if not dialog.exec():
            return

        self.logic.delete_pipeline(name_to_delete)
        self._update_pipeline_combo()
        self.logic.pipeline.steps.clear()
        self._update_pipeline_list()
        self._update_param_display()
        self._update_ui_status()
        InfoBar.success(gt('成功'), f"{gt('流水线')} {name_to_delete} {gt('已删除')}", parent=self)
