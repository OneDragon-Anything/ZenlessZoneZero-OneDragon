import cv2
import numpy as np
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox
from qfluentwidgets import (FluentIcon, PushButton, SpinBox, ComboBox,
                            BodyLabel)

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.image_viewer_widget import ImageViewerWidget
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class ImageStitchingInterface(VerticalScrollInterface):
    """图片拼接界面"""

    def __init__(self, ctx: OneDragonContext, parent=None):
        self.ctx: OneDragonContext = ctx
        
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='image_stitching_interface',
            nav_text_cn='图片拼接',
            parent=parent,
        )
        
        # 图像数据
        self.base_image: np.ndarray | None = None  # 底图
        self.second_image: np.ndarray | None = None  # 第二张图
        self.merged_image: np.ndarray | None = None  # 合并后的图像
        
        # 拼接参数
        self.stitch_direction: str = 'left'  # 拼接方向: left, right, top, bottom
        self.second_image_x: int = 0  # 第二张图的绝对X坐标
        self.second_image_y: int = 0  # 第二张图的绝对Y坐标
        self.overlap_width_ratio: float = 0.9  # 宽度重叠比例
        self.overlap_height_ratio: float = 0.9  # 高度重叠比例

        # 显示状态保持
        self.saved_scale_percent: int = 100  # 保存的缩放百分比
        self.should_preserve_scale: bool = False  # 是否应该保持缩放

    def get_content_widget(self) -> QWidget:
        """获取主要内容组件。

        创建并返回包含控制面板和图像显示面板的主要界面组件。

        Returns:
            QWidget: 配置好的主要内容组件
        """
        # 主容器，水平布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._init_control_panel())
        main_layout.addWidget(self._init_image_display_panel(), stretch=1)

        return main_widget

    def _init_control_panel(self) -> QWidget:
        """初始化控制面板。

        创建包含所有控制组件的面板，包括图像加载、拼接设置、匹配控制等。

        Returns:
            QWidget: 配置好的控制面板组件
        """
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        # 图像加载
        self.load_base_btn = PushButton(text='加载底图')
        self.load_base_btn.clicked.connect(self.on_load_base_clicked)
        
        self.load_second_btn = PushButton(text='加载第二张图')
        self.load_second_btn.clicked.connect(self.on_load_second_clicked)
        
        load_card = MultiPushSettingCard(
            icon=FluentIcon.FOLDER,
            title='图像加载',
            btn_list=[self.load_base_btn, self.load_second_btn]
        )
        control_layout.addWidget(load_card)

        # 拼接方向
        self.direction_combo = ComboBox()
        self.direction_combo.addItems(['左边', '右边', '上边', '下边'])
        self.direction_combo.currentTextChanged.connect(self.on_direction_changed)

        direction_card = MultiPushSettingCard(
            icon=FluentIcon.ALIGNMENT,
            title='拼接方向',
            content='第二张图相对于底图的位置',
            btn_list=[self.direction_combo]
        )
        control_layout.addWidget(direction_card)

        # 重叠比例
        self.overlap_width_input = SpinBox()
        self.overlap_width_input.setRange(0, 100)
        self.overlap_width_input.setValue(90)
        self.overlap_width_input.setSuffix('%')
        self.overlap_width_input.valueChanged.connect(self.on_overlap_changed)

        self.overlap_height_input = SpinBox()
        self.overlap_height_input.setRange(0, 100)
        self.overlap_height_input.setValue(90)
        self.overlap_height_input.setSuffix('%')
        self.overlap_height_input.valueChanged.connect(self.on_overlap_changed)

        overlap_card = MultiPushSettingCard(
            icon=FluentIcon.ZOOM,
            title='重叠比例',
            content='宽度和高度的重叠区域大小',
            btn_list=[
                BodyLabel('宽度:'), self.overlap_width_input,
                BodyLabel('高度:'), self.overlap_height_input
            ]
        )
        control_layout.addWidget(overlap_card)

        # 自动匹配
        self.auto_match_btn = PushButton(text='自动匹配')
        self.auto_match_btn.clicked.connect(self.on_auto_match_clicked)
        
        match_card = MultiPushSettingCard(
            icon=FluentIcon.SEARCH,
            title='图像匹配',
            btn_list=[self.auto_match_btn]
        )
        control_layout.addWidget(match_card)

        # 手动调整
        self.offset_x_input = SpinBox()
        self.offset_x_input.setRange(-999, 999)
        self.offset_x_input.setValue(0)

        self.offset_y_input = SpinBox()
        self.offset_y_input.setRange(-999, 999)
        self.offset_y_input.setValue(0)

        self.apply_x_offset_btn = PushButton(text='X偏移')
        self.apply_x_offset_btn.clicked.connect(self.on_apply_x_offset_clicked)

        self.apply_y_offset_btn = PushButton(text='Y偏移')
        self.apply_y_offset_btn.clicked.connect(self.on_apply_y_offset_clicked)

        offset_card = MultiPushSettingCard(
            icon=FluentIcon.MOVE,
            title='手动调整',
            content='微调第二张图的位置（累积偏移）',
            btn_list=[
                BodyLabel('ΔX:'), self.offset_x_input, self.apply_x_offset_btn,
                BodyLabel('ΔY:'), self.offset_y_input, self.apply_y_offset_btn
            ]
        )
        control_layout.addWidget(offset_card)

        # 合并操作
        self.merge_btn = PushButton(text='合并图像')
        self.merge_btn.clicked.connect(self.on_merge_clicked)

        self.save_btn = PushButton(text='保存结果')
        self.save_btn.clicked.connect(self.on_save_clicked)

        self.clear_btn = PushButton(text='清空图像')
        self.clear_btn.clicked.connect(self.on_clear_clicked)

        merge_card = MultiPushSettingCard(
            icon=FluentIcon.SAVE,
            title='合并操作',
            btn_list=[self.merge_btn, self.save_btn, self.clear_btn]
        )
        control_layout.addWidget(merge_card)

        control_layout.addStretch(1)
        return control_widget

    def _init_image_display_panel(self) -> QWidget:
        """初始化图像显示面板。

        创建用于显示图像的面板，包含图像查看器组件。

        Returns:
            QWidget: 配置好的图像显示面板
        """
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(12)

        # 图像显示器
        self.image_viewer = ImageViewerWidget()
        display_layout.addWidget(self.image_viewer)

        return display_widget

    def _ensure_rgb_format(self, image: np.ndarray) -> np.ndarray:
        """确保图像是RGB格式。

        将输入图像转换为RGB格式，支持灰度图和其他格式的自动转换。

        Args:
            image: 输入图像数组

        Returns:
            np.ndarray: RGB格式的图像数组，如果输入为None则返回None
        """
        if image is None:
            return None

        if image.ndim == 2:
            # 灰度图转RGB
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.ndim == 3:
            # 已经是3通道，直接返回
            return image
        else:
            # 其他格式，尝试转换
            return image

    def on_load_base_clicked(self):
        """处理加载底图按钮点击事件。

        打开文件对话框让用户选择底图文件，加载并显示图像。
        支持多种图像格式，自动转换为RGB格式。
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择底图', '',
            'Image Files (*.png *.jpg *.jpeg *.bmp *.tiff)'
        )

        if file_path:
            try:
                image = cv2_utils.read_image(file_path)
                if image is None:
                    raise ValueError("无法读取图像文件")

                # 确保是RGB格式
                self.base_image = self._ensure_rgb_format(image)

                log.info(f'加载底图成功: {file_path}, 形状: {self.base_image.shape}')
                self._update_display()
                self._update_button_states()

            except Exception as e:
                QMessageBox.warning(self, '错误', f'加载底图失败: {str(e)}')

    def on_load_second_clicked(self):
        """处理加载第二张图按钮点击事件。

        打开文件对话框让用户选择第二张图文件，加载并显示图像。
        支持多种图像格式，自动转换为RGB格式。
        加载后自动根据拼接方向进行初始拼接。
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择第二张图', '',
            'Image Files (*.png *.jpg *.jpeg *.bmp *.tiff)'
        )

        if file_path:
            try:
                image = cv2_utils.read_image(file_path)
                if image is None:
                    raise ValueError("无法读取图像文件")

                # 确保是RGB格式
                self.second_image = self._ensure_rgb_format(image)

                # 自动根据方向设置初始位置
                self.second_image_x, self.second_image_y = self._calculate_initial_position()

                # 启用缩放保持（从加载第二张图开始）
                self.should_preserve_scale = True

                log.info(f'加载第二张图成功: {file_path}, 形状: {self.second_image.shape}')
                log.info(f'自动拼接位置: ({self.second_image_x}, {self.second_image_y})')

                self._update_display()
                self._update_button_states()

            except Exception as e:
                QMessageBox.warning(self, '错误', f'加载第二张图失败: {str(e)}')

    def on_direction_changed(self, text: str):
        """处理拼接方向改变事件。

        当用户选择不同的拼接方向时，更新内部状态并记录日志。

        Args:
            text: 用户选择的方向文本（中文）
        """
        direction_map = {
            '左边': 'left',
            '右边': 'right',
            '上边': 'top',
            '下边': 'bottom'
        }
        self.stitch_direction = direction_map.get(text, 'left')
        log.info(f'拼接方向设置为: {text}')

    def on_overlap_changed(self):
        """处理重叠比例改变事件。

        当用户调整宽度或高度重叠比例时，更新内部状态并记录日志。
        重叠比例用于确定图像匹配时使用的区域大小。
        """
        self.overlap_width_ratio = self.overlap_width_input.value() / 100.0
        self.overlap_height_ratio = self.overlap_height_input.value() / 100.0
        log.info(f'重叠比例设置为: 宽度{self.overlap_width_input.value()}%, 高度{self.overlap_height_input.value()}%')

    def on_auto_match_clicked(self):
        """处理自动匹配按钮点击事件。

        执行图像自动匹配算法，计算第二张图相对于底图的最佳位置。
        匹配成功后会更新第二张图的绝对坐标并刷新显示。
        """
        if self.base_image is None or self.second_image is None:
            QMessageBox.warning(self, '错误', '请先加载两张图像')
            return

        try:
            # 执行图像匹配，基于当前位置进行微调
            match_offset_x, match_offset_y = self._perform_image_matching()

            # 应用匹配结果到绝对坐标
            self.second_image_x += match_offset_x
            self.second_image_y += match_offset_y

            # 启用缩放保持
            self.should_preserve_scale = True

            # 更新显示
            self._update_display()

            log.info(f'自动匹配完成，调整偏移: ({match_offset_x}, {match_offset_y})')
            log.info(f'第二张图新位置: ({self.second_image_x}, {self.second_image_y})')

        except Exception as e:
            QMessageBox.warning(self, '错误', f'自动匹配失败: {str(e)}')
            log.error(f'自动匹配失败: {str(e)}')

    def on_apply_x_offset_clicked(self):
        """处理X偏移按钮点击事件。

        将输入框中的X偏移量累积应用到第二张图的当前位置上。
        每次点击都会在当前位置基础上进行X方向偏移，实现累积效果。
        """
        if self.second_image is None:
            QMessageBox.warning(self, '错误', '请先加载第二张图')
            return

        # 获取当前输入的X偏移量
        delta_x = self.offset_x_input.value()

        # 累积应用到绝对坐标
        self.second_image_x += delta_x

        # 启用缩放保持
        self.should_preserve_scale = True

        # 更新显示
        self._update_display()
        log.info(f'应用X偏移: Δ{delta_x}, 新位置: ({self.second_image_x}, {self.second_image_y})')

    def on_apply_y_offset_clicked(self):
        """处理Y偏移按钮点击事件。

        将输入框中的Y偏移量累积应用到第二张图的当前位置上。
        每次点击都会在当前位置基础上进行Y方向偏移，实现累积效果。
        """
        if self.second_image is None:
            QMessageBox.warning(self, '错误', '请先加载第二张图')
            return

        # 获取当前输入的Y偏移量
        delta_y = self.offset_y_input.value()

        # 累积应用到绝对坐标
        self.second_image_y += delta_y

        # 启用缩放保持
        self.should_preserve_scale = True

        # 更新显示
        self._update_display()
        log.info(f'应用Y偏移: Δ{delta_y}, 新位置: ({self.second_image_x}, {self.second_image_y})')

    def on_merge_clicked(self):
        """处理合并图像按钮点击事件。

        将当前的底图和第二张图按照当前位置合并成一张新图像。
        合并后的图像会成为新的底图，第二张图会被清空。
        """
        if self.base_image is None or self.second_image is None:
            QMessageBox.warning(self, '错误', '请先加载两张图像')
            return

        try:
            # 执行图像合并
            self.merged_image = self._merge_images()

            # 将合并后的图像设为新的底图
            self.base_image = self.merged_image.copy()
            self.second_image = None

            # 重置第二张图的位置
            self.second_image_x = 0
            self.second_image_y = 0

            # 禁用缩放保持（新的底图）
            self.should_preserve_scale = False

            # 更新显示
            self._update_display()
            self._update_button_states()

            log.info('图像合并完成')

        except Exception as e:
            QMessageBox.warning(self, '错误', f'图像合并失败: {str(e)}')
            log.error(f'图像合并失败: {str(e)}')

    def on_save_clicked(self):
        """处理保存结果按钮点击事件。

        打开文件保存对话框，将当前的底图保存到用户指定的文件中。
        支持多种图像格式的保存。
        """
        if self.base_image is None:
            QMessageBox.warning(self, '错误', '没有可保存的图像')
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存图像', '',
            'PNG Files (*.png);;JPG Files (*.jpg);;All Files (*)'
        )

        if file_path:
            try:
                cv2_utils.save_image(self.base_image, file_path)
                log.info(f'图像保存成功: {file_path}')
                QMessageBox.information(self, '成功', '图像保存成功')

            except Exception as e:
                QMessageBox.warning(self, '错误', f'保存失败: {str(e)}')

    def on_clear_clicked(self):
        """处理清空图像按钮点击事件。

        清空所有已加载的图像（底图、第二张图、合并结果）并重置所有参数。
        操作前会显示确认对话框以防止误操作。
        """
        reply = QMessageBox.question(self, '确认清空',
                                   '确定要清空所有图像吗？',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.base_image = None
            self.second_image = None
            self.merged_image = None

            # 重置第二张图位置
            self.second_image_x = 0
            self.second_image_y = 0

            # 禁用缩放保持（清空状态）
            self.should_preserve_scale = False

            # 更新显示
            self._update_display()
            self._update_button_states()

            log.info('已清空所有图像')

    def _update_display(self):
        """更新图像显示。

        根据当前加载的图像状态更新显示内容。
        如果只有底图则显示底图，如果有两张图则显示重叠预览效果。
        保持当前的缩放比例和滚动位置。
        """
        if self.base_image is None:
            # 没有底图时显示空白图像
            empty_image = np.zeros((200, 200, 3), dtype=np.uint8)
            empty_image.fill(240)  # 浅灰色背景
            self.image_viewer.set_image(empty_image)
            self.should_preserve_scale = False
            return

        # 保存当前缩放状态（如果需要保持）
        if self.should_preserve_scale:
            self.saved_scale_percent = self.image_viewer.scale_spinbox.value()

        # 如果有第二张图，显示重叠效果
        if self.second_image is not None:
            display_image = self._create_overlay_image()
        else:
            display_image = self.base_image.copy()

        # 图像已经是RGB格式，直接显示
        self.image_viewer.set_image(display_image)

        # 强制恢复缩放状态（如果需要保持）
        if self.should_preserve_scale:
            # 使用QTimer延迟执行，确保图像已经完全加载
            from PySide6.QtCore import QTimer
            QTimer.singleShot(10, lambda: self._restore_scale_state())

    def _restore_scale_state(self):
        """恢复缩放状态。

        强制将图像查看器的缩放比例恢复到保存的状态。
        """
        if self.should_preserve_scale and hasattr(self.image_viewer, 'scale_spinbox'):
            current_scale = self.image_viewer.scale_spinbox.value()
            if current_scale != self.saved_scale_percent:
                self.image_viewer.scale_spinbox.setValue(self.saved_scale_percent)
                log.info(f'恢复缩放状态: {self.saved_scale_percent}% (当前: {current_scale}%)')

    def _update_button_states(self):
        """更新按钮状态。

        根据当前图像加载状态更新各个按钮的启用/禁用状态。
        确保用户只能在适当的时候执行相应操作。
        """
        has_base = self.base_image is not None
        has_second = self.second_image is not None
        has_both = has_base and has_second
        has_any = has_base or has_second

        self.auto_match_btn.setEnabled(has_both)
        self.apply_x_offset_btn.setEnabled(has_second)
        self.apply_y_offset_btn.setEnabled(has_second)
        self.merge_btn.setEnabled(has_both)
        self.save_btn.setEnabled(has_base)
        self.clear_btn.setEnabled(has_any)

    def _calculate_initial_position(self) -> tuple[int, int]:
        """计算第二张图的初始位置。

        根据当前选择的拼接方向，计算第二张图相对于底图的初始位置坐标。

        Returns:
            tuple[int, int]: 第二张图的初始X和Y坐标
        """
        if self.base_image is None or self.second_image is None:
            return 0, 0

        base_h, base_w = self.base_image.shape[:2]
        second_h, second_w = self.second_image.shape[:2]

        if self.stitch_direction == 'left':
            # 第二张图在左边
            x = -second_w
            y = 0
        elif self.stitch_direction == 'right':
            # 第二张图在右边
            x = base_w
            y = 0
        elif self.stitch_direction == 'top':
            # 第二张图在上边
            x = 0
            y = -second_h
        elif self.stitch_direction == 'bottom':
            # 第二张图在下边
            x = 0
            y = base_h
        else:
            x = 0
            y = 0

        return x, y

    def _perform_image_matching(self) -> tuple[int, int]:
        """执行图像匹配算法。

        使用模板匹配算法在两张图像的重叠区域中寻找最佳匹配位置。

        Returns:
            tuple[int, int]: 匹配得到的偏移量（相对于初始位置的调整）

        Raises:
            ValueError: 当无法提取匹配区域或匹配度过低时抛出异常
        """
        if self.base_image is None or self.second_image is None:
            return 0, 0

        # 根据拼接方向提取匹配区域
        base_region, second_region = self._extract_matching_regions()

        if base_region is None or second_region is None:
            raise ValueError("无法提取匹配区域")

        # 转换为灰度图进行匹配
        base_gray = cv2.cvtColor(base_region, cv2.COLOR_RGB2GRAY)
        second_gray = cv2.cvtColor(second_region, cv2.COLOR_RGB2GRAY)

        # 使用模板匹配
        result = cv2.matchTemplate(base_gray, second_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < 0.3:  # 匹配度阈值
            raise ValueError(f"匹配度过低: {max_val:.3f}")

        # 计算偏移量
        offset_x, offset_y = self._calculate_offset_from_match(max_loc)

        log.info(f'匹配成功，匹配度: {max_val:.3f}')
        return offset_x, offset_y

    def _extract_matching_regions(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        """提取用于匹配的图像区域。

        根据拼接方向和重叠比例，从底图和第二张图中提取相应的区域用于模板匹配。

        Returns:
            tuple[np.ndarray | None, np.ndarray | None]: 底图匹配区域和第二张图匹配区域
        """
        if self.base_image is None or self.second_image is None:
            return None, None

        base_h, base_w = self.base_image.shape[:2]
        second_h, second_w = self.second_image.shape[:2]

        if self.stitch_direction == 'left':
            # 第二张图在左边，取第二张图的右边部分和底图的左边部分
            overlap_w = max(1, int(min(base_w, second_w) * self.overlap_width_ratio))
            overlap_h = max(1, int(min(base_h, second_h) * self.overlap_height_ratio))

            # 计算垂直居中的起始位置
            base_start_y = max(0, (base_h - overlap_h) // 2)
            second_start_y = max(0, (second_h - overlap_h) // 2)

            base_region = self.base_image[base_start_y:base_start_y + overlap_h, :overlap_w]
            second_region = self.second_image[second_start_y:second_start_y + overlap_h, second_w - overlap_w:]

        elif self.stitch_direction == 'right':
            # 第二张图在右边，取第二张图的左边部分和底图的右边部分
            overlap_w = max(1, int(min(base_w, second_w) * self.overlap_width_ratio))
            overlap_h = max(1, int(min(base_h, second_h) * self.overlap_height_ratio))

            base_start_y = max(0, (base_h - overlap_h) // 2)
            second_start_y = max(0, (second_h - overlap_h) // 2)

            base_region = self.base_image[base_start_y:base_start_y + overlap_h, base_w - overlap_w:]
            second_region = self.second_image[second_start_y:second_start_y + overlap_h, :overlap_w]

        elif self.stitch_direction == 'top':
            # 第二张图在上边，取第二张图的下边部分和底图的上边部分
            overlap_w = max(1, int(min(base_w, second_w) * self.overlap_width_ratio))
            overlap_h = max(1, int(min(base_h, second_h) * self.overlap_height_ratio))

            base_start_x = max(0, (base_w - overlap_w) // 2)
            second_start_x = max(0, (second_w - overlap_w) // 2)

            base_region = self.base_image[:overlap_h, base_start_x:base_start_x + overlap_w]
            second_region = self.second_image[second_h - overlap_h:, second_start_x:second_start_x + overlap_w]

        elif self.stitch_direction == 'bottom':
            # 第二张图在下边，取第二张图的上边部分和底图的下边部分
            overlap_w = max(1, int(min(base_w, second_w) * self.overlap_width_ratio))
            overlap_h = max(1, int(min(base_h, second_h) * self.overlap_height_ratio))

            base_start_x = max(0, (base_w - overlap_w) // 2)
            second_start_x = max(0, (second_w - overlap_w) // 2)

            base_region = self.base_image[base_h - overlap_h:, base_start_x:base_start_x + overlap_w]
            second_region = self.second_image[:overlap_h, second_start_x:second_start_x + overlap_w]

        else:
            return None, None

        return base_region, second_region

    def _calculate_offset_from_match(self, match_loc: tuple[int, int]) -> tuple[int, int]:
        """根据模板匹配结果计算偏移量。

        将模板匹配得到的最佳匹配位置转换为第二张图相对于初始位置的偏移量。

        Args:
            match_loc: 模板匹配得到的最佳匹配位置坐标

        Returns:
            tuple[int, int]: 计算得到的X和Y方向偏移量
        """
        match_x, match_y = match_loc

        if self.stitch_direction in ['left', 'right']:
            # 水平拼接，主要关注垂直偏移
            offset_x = 0
            offset_y = match_y
        else:
            # 垂直拼接，主要关注水平偏移
            offset_x = match_x
            offset_y = 0

        return offset_x, offset_y

    def _create_overlay_image(self) -> np.ndarray:
        """创建重叠显示的图像。

        将底图和第二张图按照当前位置进行半透明重叠显示，用于预览拼接效果。

        Returns:
            np.ndarray: 重叠显示的图像数组
        """
        if self.base_image is None or self.second_image is None:
            return self.base_image

        base_h, base_w = self.base_image.shape[:2]
        second_h, second_w = self.second_image.shape[:2]

        # 使用绝对坐标
        second_x = self.second_image_x
        second_y = self.second_image_y

        # 计算合并后的画布大小
        min_x = min(0, second_x)
        min_y = min(0, second_y)
        max_x = max(base_w, second_x + second_w)
        max_y = max(base_h, second_y + second_h)

        canvas_w = max_x - min_x
        canvas_h = max_y - min_y

        # 创建画布
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

        # 放置底图
        base_start_x = -min_x
        base_start_y = -min_y
        canvas[base_start_y:base_start_y + base_h, base_start_x:base_start_x + base_w] = self.base_image

        # 放置第二张图（半透明）
        second_start_x = second_x - min_x
        second_start_y = second_y - min_y

        # 确保坐标在画布范围内
        if (second_start_x < canvas_w and second_start_y < canvas_h and
            second_start_x + second_w > 0 and second_start_y + second_h > 0):

            # 计算实际的重叠区域
            x1 = max(0, second_start_x)
            y1 = max(0, second_start_y)
            x2 = min(canvas_w, second_start_x + second_w)
            y2 = min(canvas_h, second_start_y + second_h)

            # 计算在第二张图中的对应区域
            src_x1 = x1 - second_start_x
            src_y1 = y1 - second_start_y
            src_x2 = src_x1 + (x2 - x1)
            src_y2 = src_y1 + (y2 - y1)

            # 半透明叠加
            alpha = 0.5
            canvas[y1:y2, x1:x2] = (
                canvas[y1:y2, x1:x2] * (1 - alpha) +
                self.second_image[src_y1:src_y2, src_x1:src_x2] * alpha
            ).astype(np.uint8)

        return canvas

    def _merge_images(self) -> np.ndarray:
        """智能合并两张图像。

        将底图和第二张图按照当前位置进行智能合并，生成新的图像。
        第二张图只会填充到底图的空白区域（黑色或接近黑色的区域），
        不会覆盖底图已有的有颜色内容。

        Returns:
            np.ndarray: 合并后的图像数组
        """
        if self.base_image is None or self.second_image is None:
            return self.base_image

        base_h, base_w = self.base_image.shape[:2]
        second_h, second_w = self.second_image.shape[:2]

        # 使用绝对坐标
        second_x = self.second_image_x
        second_y = self.second_image_y

        # 计算合并后的画布大小
        min_x = min(0, second_x)
        min_y = min(0, second_y)
        max_x = max(base_w, second_x + second_w)
        max_y = max(base_h, second_y + second_h)

        canvas_w = max_x - min_x
        canvas_h = max_y - min_y

        # 创建画布
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

        # 放置底图
        base_start_x = -min_x
        base_start_y = -min_y
        canvas[base_start_y:base_start_y + base_h, base_start_x:base_start_x + base_w] = self.base_image

        # 智能放置第二张图（只填充空白区域）
        second_start_x = second_x - min_x
        second_start_y = second_y - min_y

        if (second_start_x < canvas_w and second_start_y < canvas_h and
            second_start_x + second_w > 0 and second_start_y + second_h > 0):

            x1 = max(0, second_start_x)
            y1 = max(0, second_start_y)
            x2 = min(canvas_w, second_start_x + second_w)
            y2 = min(canvas_h, second_start_y + second_h)

            src_x1 = x1 - second_start_x
            src_y1 = y1 - second_start_y
            src_x2 = src_x1 + (x2 - x1)
            src_y2 = src_y1 + (y2 - y1)

            # 获取重叠区域
            canvas_region = canvas[y1:y2, x1:x2]
            second_region = self.second_image[src_y1:src_y2, src_x1:src_x2]

            # 创建掩码：底图中接近黑色的区域（RGB值都小于阈值）
            # 阈值设为30，可以捕获黑色和非常暗的区域
            threshold = 30
            base_is_dark = np.all(canvas_region <= threshold, axis=2)

            # 只在底图为暗色的地方放置第二张图
            for c in range(3):  # RGB三个通道
                canvas_region[:, :, c] = np.where(
                    base_is_dark,
                    second_region[:, :, c],  # 底图暗色区域用第二张图填充
                    canvas_region[:, :, c]   # 底图有颜色区域保持不变
                )

        return canvas
