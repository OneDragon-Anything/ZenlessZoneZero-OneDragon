import os
from typing import Optional, Union

import numpy as np
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QMouseEvent, QPaintEvent, QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy
from qfluentwidgets import FluentIcon, PushButton, SpinBox, ComboBox, ToolButton, BodyLabel

from one_dragon.utils.i18_utils import gt


class ImageDisplayLabel(QLabel):
    """内部图片显示标签，支持绘制选择框."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_viewer = parent

    def paintEvent(self, event: QPaintEvent):
        QLabel.paintEvent(self, event)

        # 绘制选择矩形
        if (self.parent_viewer and
            self.parent_viewer.interaction_mode == "select" and
            self.parent_viewer.selection_start is not None and
            self.parent_viewer.selection_end is not None and
            self.parent_viewer.original_pixmap is not None):

            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0, 180), 2, Qt.PenStyle.DashLine))

            # 计算显示坐标
            display_start = self.parent_viewer.map_from_original_coords(self.parent_viewer.selection_start)
            display_end = self.parent_viewer.map_from_original_coords(self.parent_viewer.selection_end)

            if display_start is not None and display_end is not None:
                x1, y1 = display_start.x(), display_start.y()
                x2, y2 = display_end.x(), display_end.y()

                left = min(x1, x2)
                top = min(y1, y2)
                width = abs(x2 - x1)
                height = abs(y2 - y1)

                painter.drawRect(left, top, width, height)


class OptimizedImageDisplayLabel(QScrollArea):
    """优化的图片显示标签，支持点击、框选两种模式，带滚动条.

    支持从文件路径或OpenCV RGB格式图片数组加载图片，提供多种交互模式。
    所有选择区域坐标基于原始图片坐标系。
    """

    area_selected = Signal(int, int, int, int)  # x, y, width, height (原图坐标)
    point_clicked = Signal(int, int)  # x, y (原图坐标)

    def __init__(self, parent=None):
        """初始化图片显示标签.

        Args:
            parent: 父窗口组件
        """
        QScrollArea.__init__(self, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 创建内部的图片标签
        self.image_label = ImageDisplayLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWidget(self.image_label)

        # 设置滚动条策略
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 交互模式: "click", "select"
        self.interaction_mode = "click"

        # 框选相关
        self.selection_start: Optional[QPoint] = None  # 原图坐标系
        self.selection_end: Optional[QPoint] = None    # 原图坐标系
        self.selection_rect: Optional[QRect] = None    # 原图坐标系
        self.is_selecting = False

        # 原始图片和缩放比例
        self.original_pixmap: Optional[QPixmap] = None
        self.scale_factor = 1.0  # 当前缩放因子

        # 用于保持滚动位置的状态
        self.previous_image_size: Optional[QSize] = None
        self.saved_scroll_position: Optional[QPoint] = None
        self.saved_scale_factor: Optional[float] = None

    def set_image(self, image_source: Union[str, np.ndarray]):
        """设置要显示的图片.

        Args:
            image_source: 图片源，可以是文件路径字符串或OpenCV RGB格式的numpy数组
        """
        # 保存当前状态
        should_preserve_state = False
        if self.original_pixmap is not None:
            self.saved_scroll_position = QPoint(
                self.horizontalScrollBar().value(),
                self.verticalScrollBar().value()
            )
            self.saved_scale_factor = self.scale_factor

        # 清除之前的显示内容
        self.image_label.clear()
        old_pixmap = self.original_pixmap
        self.original_pixmap = None

        if isinstance(image_source, str):
            # 从文件路径加载图片
            if not os.path.exists(image_source):
                return  # 无效图片，不显示任何内容

            pixmap = QPixmap(image_source)
            if pixmap.isNull():
                return  # 无效图片，不显示任何内容
            self.original_pixmap = pixmap
        elif isinstance(image_source, np.ndarray):
            # 从OpenCV RGB格式数组加载图片
            pixmap = self._numpy_to_pixmap(image_source)
            if pixmap is None:
                return  # 无效图片，不显示任何内容
            self.original_pixmap = pixmap
        else:
            return  # 不支持的格式，不显示任何内容

        # 检查是否应该保持之前的状态
        if (old_pixmap is not None and
            self.original_pixmap.size() == old_pixmap.size() and
            self.saved_scale_factor is not None and
            self.saved_scroll_position is not None):
            should_preserve_state = True

        if should_preserve_state:
            # 保持之前的缩放比例和滚动位置
            self.scale_factor = self.saved_scale_factor
            self.update_display()
            # 延迟恢复滚动位置，确保图片已经显示
            self.horizontalScrollBar().setValue(self.saved_scroll_position.x())
            self.verticalScrollBar().setValue(self.saved_scroll_position.y())
        else:
            # 新图片或尺寸不同，使用适应窗口的方式显示
            self.fit_to_window()

        # 更新之前的图片尺寸记录
        self.previous_image_size = self.original_pixmap.size() if self.original_pixmap else None

    def _numpy_to_pixmap(self, image_array: np.ndarray) -> Optional[QPixmap]:
        """将OpenCV RGB格式的numpy数组转换为QPixmap.

        Args:
            image_array: OpenCV RGB格式的图片数组，形状为 (height, width, 3)

        Returns:
            转换后的QPixmap对象，转换失败时返回None
        """
        try:
            # 确保数据类型为uint8
            if image_array.dtype != np.uint8:
                image_array = image_array.astype(np.uint8)

            # 确保数据在内存中是连续的，这对于QImage从内存缓冲区创建很重要
            if not image_array.flags['C_CONTIGUOUS']:
                image_array = np.ascontiguousarray(image_array)

            if image_array.ndim == 3 and image_array.shape[2] == 3:  # 彩色RGB图
                height, width, _ = image_array.shape
                bytes_per_line = 3 * width
                q_format = QImage.Format.Format_RGB888
            elif image_array.ndim == 2:  # 灰度图
                height, width = image_array.shape
                bytes_per_line = width
                q_format = QImage.Format.Format_Grayscale8
            else:
                # 不支持的数组形状
                return None

            # 创建QImage
            q_image = QImage(image_array.data, width, height, bytes_per_line, q_format)

            # 创建QImage的深拷贝，以防原始numpy数组被回收导致图像数据丢失
            return QPixmap.fromImage(q_image.copy())
        except Exception:
            return None

    def set_scale_factor(self, factor: float):
        """设置缩放因子.

        Args:
            factor: 缩放因子，1.0表示原始大小
        """
        self.scale_factor = factor
        self.update_display()
        # 缩放改变时重新绘制选择区域
        self.update()

    def fit_to_window(self):
        """适应窗口大小.

        自动计算最佳缩放比例，使图片完整显示在可用区域内。
        """
        if self.original_pixmap is None:
            return

        # 获取可用显示区域大小
        available_size = self.size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            # 如果还没有有效尺寸，使用默认缩放
            self.scale_factor = 1.0
            self.update_display()
            return

        # 计算适应大小的缩放比例
        img_size = self.original_pixmap.size()
        scale_x = available_size.width() / img_size.width()
        scale_y = available_size.height() / img_size.height()
        self.scale_factor = min(scale_x, scale_y, 1.0)  # 不超过原始大小

        self.update_display()

    def update_display(self):
        """更新图片显示.

        根据当前缩放因子重新缩放并显示图片。
        """
        if self.original_pixmap is None:
            return

        # 计算缩放后的尺寸
        scaled_size = QSize(
            int(self.original_pixmap.width() * self.scale_factor),
            int(self.original_pixmap.height() * self.scale_factor)
        )

        # 缩放图片
        scaled_pixmap = self.original_pixmap.scaled(
            scaled_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size())

    def get_scale_percent(self) -> int:
        """获取当前缩放百分比.

        Returns:
            当前缩放百分比，100表示原始大小
        """
        return int(self.scale_factor * 100)

    def set_interaction_mode(self, mode: str):
        """设置交互模式.

        Args:
            mode: 交互模式 "click", "select"
        """
        self.interaction_mode = mode
        if mode != "select":
            self.clear_selection()

    def clear_selection(self):
        """清除选择区域.

        清除当前的选择区域并重新绘制界面。
        """
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.is_selecting = False
        self.image_label.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.image_label.pixmap() is not None:
            # 将事件坐标转换为图片标签坐标
            label_pos = self.image_label.mapFromParent(event.pos())

            if self.interaction_mode == "click":
                # 点击模式：只发送点击事件
                pos = self.map_to_original_coords(label_pos)
                if pos is not None:
                    self.point_clicked.emit(pos.x(), pos.y())

            elif self.interaction_mode == "select":
                # 框选模式：开始选择区域
                pos = self.map_to_original_coords(label_pos)
                if pos is not None:
                    self.point_clicked.emit(pos.x(), pos.y())  # 也发送点击事件
                    self.selection_start = pos
                    self.selection_end = pos
                    self.is_selecting = True
                    self.image_label.update()

        QScrollArea.mousePressEvent(self, event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.interaction_mode == "select" and self.is_selecting:
            # 框选模式：更新选择区域
            if self.image_label.pixmap() is not None:
                # 将事件坐标转换为图片标签坐标
                label_pos = self.image_label.mapFromParent(event.pos())
                pos = self.map_to_original_coords(label_pos)
                if pos is not None:
                    self.selection_end = pos
                    self.image_label.update()

        QScrollArea.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.interaction_mode == "select" and self.is_selecting:
                # 框选模式：完成选择
                self.is_selecting = False
                if self.selection_start is not None and self.selection_end is not None:
                    # 计算选择矩形（原图坐标系）
                    x1, y1 = self.selection_start.x(), self.selection_start.y()
                    x2, y2 = self.selection_end.x(), self.selection_end.y()

                    # 确保坐标顺序正确
                    left = min(x1, x2)
                    top = min(y1, y2)
                    right = max(x1, x2)
                    bottom = max(y1, y2)

                    width = right - left
                    height = bottom - top

                    # 最小选择区域检查（转换到显示坐标系检查）
                    min_display_size = 5
                    min_original_size = int(min_display_size / self.scale_factor)

                    if width > min_original_size and height > min_original_size:
                        self.selection_rect = QRect(left, top, width, height)
                        # 发送信号，传递原图坐标系中的坐标
                        self.area_selected.emit(left, top, width, height)
                    else:
                        self.clear_selection()

        QScrollArea.mouseReleaseEvent(self, event)

    def map_to_original_coords(self, label_pos: QPoint) -> Optional[QPoint]:
        """将图片标签坐标转换为原图坐标.

        Args:
            label_pos: 图片标签坐标系中的点

        Returns:
            原图坐标系中的点，如果转换失败返回None
        """
        if self.image_label.pixmap() is None or self.original_pixmap is None:
            return None

        # 获取图片在标签中的显示区域
        pixmap_rect = self.image_label.pixmap().rect()
        label_rect = self.image_label.rect()

        # 计算图片在标签中的位置（居中显示）
        x_offset = (label_rect.width() - pixmap_rect.width()) // 2
        y_offset = (label_rect.height() - pixmap_rect.height()) // 2

        # 转换到显示图片坐标
        display_x = label_pos.x() - x_offset
        display_y = label_pos.y() - y_offset

        # 检查是否在图片范围内
        if 0 <= display_x < pixmap_rect.width() and 0 <= display_y < pixmap_rect.height():
            # 转换到原图坐标系
            original_x = int(display_x / self.scale_factor)
            original_y = int(display_y / self.scale_factor)

            # 确保不超出原图边界
            original_x = max(0, min(original_x, self.original_pixmap.width() - 1))
            original_y = max(0, min(original_y, self.original_pixmap.height() - 1))

            return QPoint(original_x, original_y)
        return None

    def map_from_original_coords(self, original_pos: QPoint) -> Optional[QPoint]:
        """将原图坐标转换为图片标签坐标.

        Args:
            original_pos: 原图坐标系中的点

        Returns:
            图片标签坐标系中的点，如果转换失败返回None
        """
        if self.image_label.pixmap() is None:
            return None

        # 转换到显示图片坐标
        display_x = int(original_pos.x() * self.scale_factor)
        display_y = int(original_pos.y() * self.scale_factor)

        # 获取图片在标签中的显示区域
        pixmap_rect = self.image_label.pixmap().rect()
        label_rect = self.image_label.rect()

        # 计算图片在标签中的位置（居中显示）
        x_offset = (label_rect.width() - pixmap_rect.width()) // 2
        y_offset = (label_rect.height() - pixmap_rect.height()) // 2

        # 转换到标签坐标
        label_x = display_x + x_offset
        label_y = display_y + y_offset

        return QPoint(label_x, label_y)



    def resizeEvent(self, event):
        """窗口大小改变时重新适应.

        Args:
            event: 窗口大小改变事件
        """
        QScrollArea.resizeEvent(self, event)
        # 如果有图片且当前是适应窗口模式，重新计算缩放
        if self.original_pixmap is not None:
            # 可以根据需要决定是否自动重新适应窗口
            pass


class ImageViewerWidget(QWidget):
    """优化的图片查看器组件.

    提供完整的图片查看功能，包括缩放控制、区域选择等。
    支持从文件路径或OpenCV RGB格式图片数组加载图片。
    """

    area_selected = Signal(int, int, int, int)  # x, y, width, height (原图坐标)
    point_clicked = Signal(int, int)  # x, y (原图坐标)

    def __init__(self, parent=None):
        """初始化图片查看器组件.

        Args:
            parent: 父窗口组件
        """
        QWidget.__init__(self, parent)
        self.current_mode = "click"  # "click", "select"

        # 初始化UI组件属性，避免使用hasattr
        self.selection_label: Optional[QLabel] = None
        self.clear_selection_btn: Optional[PushButton] = None
        self.mode_combo: Optional[ComboBox] = None

        self.setup_ui()

    def setup_ui(self):
        """设置界面.

        创建并布局所有UI组件。
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        # 模式选择
        toolbar_layout.addWidget(BodyLabel(gt("模式:")))
        self.mode_combo = ComboBox()
        self.mode_combo.addItem(gt("点击模式"), userData="click")
        self.mode_combo.addItem(gt("框选模式"), userData="select")
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        toolbar_layout.addWidget(self.mode_combo)

        toolbar_layout.addWidget(BodyLabel("  "))  # 分隔符

        # 缩放控制
        toolbar_layout.addWidget(BodyLabel(gt("缩放比例:")))

        # 缩小按钮（放在输入框左侧）
        self.zoom_out_btn = ToolButton(FluentIcon.ZOOM_OUT, None)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar_layout.addWidget(self.zoom_out_btn)

        self.scale_spinbox = SpinBox()
        self.scale_spinbox.setRange(10, 1000)
        self.scale_spinbox.setValue(100)
        self.scale_spinbox.setSuffix("%")
        self.scale_spinbox.setMinimumWidth(160)
        self.scale_spinbox.valueChanged.connect(self.on_scale_changed)
        toolbar_layout.addWidget(self.scale_spinbox)

        # 放大按钮（放在输入框右侧）
        self.zoom_in_btn = ToolButton(FluentIcon.ZOOM_IN, None)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar_layout.addWidget(self.zoom_in_btn)

        # 适应窗口按钮
        self.fit_btn = PushButton(FluentIcon.FIT_PAGE, gt("适应窗口"))
        self.fit_btn.clicked.connect(self.fit_to_window)
        toolbar_layout.addWidget(self.fit_btn)

        # 原图按钮（100%缩放）
        self.original_btn = PushButton(FluentIcon.ZOOM, gt("原图"))
        self.original_btn.clicked.connect(self.show_original_size)
        toolbar_layout.addWidget(self.original_btn)

        toolbar_layout.addStretch()

        # 选择区域相关控件（默认隐藏）
        self.selection_label = QLabel(gt("选择区域: 未选择"))
        self.selection_label.setVisible(False)
        toolbar_layout.addWidget(self.selection_label)

        self.clear_selection_btn = PushButton(FluentIcon.DELETE, gt("清除选择"))
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        self.clear_selection_btn.setVisible(False)
        toolbar_layout.addWidget(self.clear_selection_btn)

        layout.addLayout(toolbar_layout)

        # 图片显示区域（OptimizedImageDisplayLabel本身就是QScrollArea）
        self.image_label = OptimizedImageDisplayLabel()
        self.image_label.set_interaction_mode("click")  # 默认为点击模式
        self.image_label.area_selected.connect(self.on_area_selected)
        # 连接点击事件
        self.image_label.point_clicked.connect(self.on_point_clicked)

        layout.addWidget(self.image_label)

    def set_image(self, image_source: Union[str, np.ndarray]):
        """设置要显示的图片.

        Args:
            image_source: 图片源，可以是文件路径字符串或OpenCV RGB格式的numpy数组
        """
        self.image_label.set_image(image_source)
        # 更新缩放显示
        self.scale_spinbox.setValue(self.image_label.get_scale_percent())

    def on_scale_changed(self, value: int):
        """缩放比例改变.

        Args:
            value: 新的缩放百分比
        """
        scale_factor = value / 100.0
        self.image_label.set_scale_factor(scale_factor)

    def zoom_in(self):
        """放大图片.

        将缩放比例增加10%。
        """
        current_value = self.scale_spinbox.value()
        new_value = min(1000, current_value + 10)
        self.scale_spinbox.setValue(new_value)

    def zoom_out(self):
        """缩小图片.

        将缩放比例减少10%。
        """
        current_value = self.scale_spinbox.value()
        new_value = max(10, current_value - 10)
        self.scale_spinbox.setValue(new_value)

    def fit_to_window(self):
        """适应窗口大小.

        自动调整图片缩放比例以适应当前窗口大小。
        """
        self.image_label.fit_to_window()
        self.scale_spinbox.setValue(self.image_label.get_scale_percent())

    def show_original_size(self):
        """显示原图大小（100%缩放）."""
        self.scale_spinbox.setValue(100)

    def on_mode_changed(self):
        """模式改变回调."""
        current_data = self.mode_combo.currentData()
        self.current_mode = current_data

        # 设置图片标签的交互模式
        self.image_label.set_interaction_mode(current_data)

        # 显示/隐藏选择相关控件
        is_select_mode = (current_data == "select")
        if self.selection_label is not None:
            self.selection_label.setVisible(is_select_mode)
        if self.clear_selection_btn is not None:
            self.clear_selection_btn.setVisible(is_select_mode)

        # 如果切换到非框选模式，清除当前选择
        if not is_select_mode:
            self.clear_selection()

    def on_area_selected(self, x: int, y: int, width: int, height: int):
        """区域选择回调.

        Args:
            x: 选择区域左上角X坐标（原图坐标系）
            y: 选择区域左上角Y坐标（原图坐标系）
            width: 选择区域宽度
            height: 选择区域高度
        """
        if self.current_mode == "select" and self.selection_label is not None:
            self.selection_label.setText(f"{gt('选择区域')}: ({x}, {y}, {width}, {height})")
            self.area_selected.emit(x, y, width, height)

    def on_point_clicked(self, x: int, y: int):
        """点击事件回调.

        Args:
            x: 点击位置X坐标（原图坐标系）
            y: 点击位置Y坐标（原图坐标系）
        """
        self.point_clicked.emit(x, y)

    def clear_selection(self):
        """清除选择.

        清除当前的选择区域。
        """
        self.image_label.clear_selection()
        if self.current_mode == "select" and self.selection_label is not None:
            self.selection_label.setText(gt("选择区域: 未选择"))

    def set_interaction_mode(self, mode: str):
        """设置交互模式.

        Args:
            mode: 交互模式 "click", "select"
        """
        # 更新模式下拉框
        if mode == "click":
            self.mode_combo.setCurrentText(gt("点击模式"))
        elif mode == "select":
            self.mode_combo.setCurrentText(gt("框选模式"))

    def set_selection_enabled(self, enabled: bool):
        """设置是否启用区域选择（兼容性方法）.

        Args:
            enabled: 是否启用区域选择功能
        """
        # 兼容旧API，转换为新的模式设置
        if enabled:
            self.set_interaction_mode("select")
        else:
            self.set_interaction_mode("click")
