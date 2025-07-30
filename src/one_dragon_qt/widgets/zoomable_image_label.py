from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QWheelEvent, QPixmap, QMouseEvent, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import QSizePolicy

from one_dragon_qt.widgets.click_image_label import ClickImageLabel


class ZoomableClickImageLabel(ClickImageLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scale_factor = 1.0
        self.original_pixmap: QPixmap = None
        self.current_scaled_pixmap = QPixmap()  # 保存当前缩放级别的图像
        # 设置为可扩展的尺寸策略，以便在布局中正确填充空间
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 拖动相关变量
        self.is_dragging = False
        self.drag_started = False  # 是否已经开始实际拖拽
        self.last_drag_pos = QPoint()
        self.image_offset = QPoint(0, 0)  # 图像偏移量
        self.drag_threshold = 5  # 最小拖拽距离阈值

    def setPixmap(self, pixmap: QPixmap):
        """
        重写 setPixmap，保存原始图像并进行初次缩放
        """
        self.original_pixmap = pixmap
        self.image_offset = QPoint(0, 0)  # 重置偏移量
        # 初始加载时，将图片宽度缩放到等于控件宽度
        if self.width() > 0 and self.original_pixmap is not None:
            self.scale_factor = self.width() / self.original_pixmap.width()
        else:
            self.scale_factor = 1.0

        # 应用边界限制
        self.image_offset = self._limit_image_bounds(self.image_offset)
        # 更新缩放后的图像并触发重绘
        self.update_scaled_pixmap()

    def wheelEvent(self, event: QWheelEvent):
        """
        重写 wheelEvent，实现滚轮缩放
        """
        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.1  # 放大
        else:
            self.scale_factor /= 1.1  # 缩小

        # 缩放后应用边界限制
        self.image_offset = self._limit_image_bounds(self.image_offset)
        self.update_scaled_pixmap()

    def resizeEvent(self, event: QResizeEvent):
        """
        控件尺寸变化时，重新应用边界限制并更新显示
        """
        super().resizeEvent(event)
        if self.original_pixmap is not None and not self.original_pixmap.isNull():
            # 应用边界限制
            self.image_offset = self._limit_image_bounds(self.image_offset)
            # 触发重绘以适应新尺寸
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        """
        重写鼠标按下事件，处理左键拖动
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # 左键准备拖动
            self.is_dragging = True
            self.drag_started = False
            self.last_drag_pos = event.pos()
            # 同时调用父类方法保持原有的点击功能
            super().mousePressEvent(event)
        else:
            # 其他情况交给父类处理
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        重写鼠标移动事件，处理拖动
        """
        if self.is_dragging:
            # 计算移动距离
            delta = event.pos() - self.last_drag_pos

            # 如果还没开始实际拖拽，检查是否超过阈值
            if not self.drag_started:
                total_distance = (event.pos() - self.last_drag_pos).manhattanLength()
                if total_distance >= self.drag_threshold:
                    self.drag_started = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                else:
                    return  # 未达到阈值，不进行拖拽

            # 计算新的偏移量并限制边界
            new_offset = self.image_offset + delta
            limited_offset = self._limit_image_bounds(new_offset)

            # 只有在偏移量确实改变时才更新
            if limited_offset != self.image_offset:
                self.image_offset = limited_offset
                self.last_drag_pos = event.pos()
                # 拖动时只需要请求重绘，不需要重新缩放
                self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        重写鼠标释放事件，结束拖动
        """
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            # 保存拖拽状态用于判断
            was_dragging = self.drag_started

            # 结束拖动
            self.is_dragging = False
            self.drag_started = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

            # 如果没有实际拖拽，继续传递给父类处理点击事件
            if not was_dragging:
                super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def update_scaled_pixmap(self):
        """
        根据缩放比例更新用于绘制的pixmap，并请求重绘。
        这个函数只在缩放比例变化时调用。
        """
        if self.original_pixmap is None or self.original_pixmap.isNull():
            return

        # 计算目标逻辑尺寸
        new_width = int(self.original_pixmap.width() * self.scale_factor)
        new_height = int(self.original_pixmap.height() * self.scale_factor)
        target_size = QSize(new_width, new_height)

        # 获取设备像素比，实现高DPI支持
        pixel_ratio = self.devicePixelRatio()

        # 计算目标的物理像素尺寸
        physical_size = target_size * pixel_ratio

        # 直接使用 QPixmap.scaled 进行高质量缩放，避免格式转换开销
        self.current_scaled_pixmap = self.original_pixmap.scaled(
            physical_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # 设置正确的设备像素比
        self.current_scaled_pixmap.setDevicePixelRatio(pixel_ratio)

        # 请求重绘，让paintEvent来处理显示
        self.update()

    def paintEvent(self, event: QPaintEvent):
        """
        在控件上高效地绘制图像。
        """
        # 如果没有可绘制的图像，调用父类的paintEvent
        if self.current_scaled_pixmap.isNull():
            super().paintEvent(event)
            return

        # 创建一个painter
        painter = QPainter(self)

        # 清空背景
        painter.eraseRect(self.rect())

        # 根据当前的偏移量，直接将缩放好的图像绘制到控件上
        # 这是性能最高的做法！
        painter.drawPixmap(self.image_offset, self.current_scaled_pixmap)

    def map_display_to_image_coords(self, display_pos: QPoint) -> QPoint:
        """
        将显示坐标转换为原始图像坐标
        :param display_pos: 在控件上点击的坐标
        :return: 在原始图片上的坐标
        """
        if self.original_pixmap is None:
            return None

        # 考虑图像偏移量，先减去偏移量得到在缩放图像上的真实坐标
        adjusted_pos = display_pos - self.image_offset

        # 然后除以缩放比例得到原始图像坐标
        image_x = int(adjusted_pos.x() / self.scale_factor)
        image_y = int(adjusted_pos.y() / self.scale_factor)

        return QPoint(image_x, image_y)

    def _limit_image_bounds(self, offset: QPoint) -> QPoint:
        """
        限制图像偏移量，确保图像不会完全离开屏幕
        :param offset: 原始偏移量
        :return: 限制后的偏移量
        """
        if self.original_pixmap is None:
            return offset

        # 获取缩放后的图像尺寸
        scaled_width = int(self.original_pixmap.width() * self.scale_factor)
        scaled_height = int(self.original_pixmap.height() * self.scale_factor)

        # 获取控件尺寸
        widget_width = self.width()
        widget_height = self.height()

        # 设置最小可见区域（比如图像至少要有50像素在屏幕内）
        min_visible = 50

        # 计算边界限制
        # 左边界：图像右边缘至少要有min_visible像素在屏幕内
        min_x = -(scaled_width - min_visible)
        # 右边界：图像左边缘至少要有min_visible像素在屏幕内
        max_x = widget_width - min_visible
        # 上边界：图像下边缘至少要有min_visible像素在屏幕内
        min_y = -(scaled_height - min_visible)
        # 下边界：图像上边缘至少要有min_visible像素在屏幕内
        max_y = widget_height - min_visible

        # 如果图像小于控件，居中显示
        if scaled_width <= widget_width:
            limited_x = (widget_width - scaled_width) // 2
        else:
            limited_x = max(min_x, min(max_x, offset.x()))

        if scaled_height <= widget_height:
            limited_y = (widget_height - scaled_height) // 2
        else:
            limited_y = max(min_y, min(max_y, offset.y()))

        return QPoint(limited_x, limited_y)

    def reset_image_position(self):
        """
        重置图像偏移量到原始位置
        """
        self.image_offset = QPoint(0, 0)
        # 应用边界限制
        self.image_offset = self._limit_image_bounds(self.image_offset)
        # 位置重置时只需要重绘，不需要重新缩放
        self.update()

    def doubleClickEvent(self, event: QMouseEvent):
        """
        双击重置图像位置
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_image_position()
        else:
            super().doubleClickEvent(event)
