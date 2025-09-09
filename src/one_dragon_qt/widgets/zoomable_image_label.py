from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QPixmap, QPainter, QPen, QMouseEvent, QPaintEvent, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QSizePolicy, QLabel

from one_dragon_qt.utils.image_utils import scale_pixmap_for_high_dpi


class ZoomableClickImageLabel(QLabel):

    left_clicked_with_pos = Signal(int, int)
    right_clicked_with_pos = Signal(int, int)
    rect_selected = Signal(int, int, int, int)  # 左上角x,y 和 右下角x,y

    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置为可扩展的尺寸策略，以便在布局中正确填充空间
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 缩放相关变量
        self.scale_factor = 1.0
        self.min_scale = 0.05
        self.max_scale = 8.0
        self.original_pixmap: QPixmap = None
        self.current_scaled_pixmap = QPixmap()  # 保存当前缩放级别的图像

        # 拖动相关变量
        self.is_dragging = False
        self.drag_started = False  # 是否已经开始实际拖拽
        self.last_drag_pos = QPoint()
        self.image_offset = QPoint(0, 0)  # 图像偏移量
        self.drag_threshold = 5  # 最小拖拽距离阈值

        # 矩形选择相关变量
        self.is_selecting = False
        self.selection_start = QPoint()
        self.selection_end = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        """
        鼠标按下事件，处理Ctrl+左键拖动、左键矩形选择和右键单击
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否按下了Ctrl键
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # Ctrl+左键准备拖动图片
                self.is_dragging = True
                self.drag_started = False
                self.last_drag_pos = event.pos()
                self.is_selecting = False
            else:
                # 普通左键开始矩形选择
                self.is_selecting = True
                self.selection_start = event.pos()
                self.selection_end = event.pos()
                self.is_dragging = False
                self.drag_started = False
        elif event.button() == Qt.MouseButton.RightButton:
            image_pos = self.map_display_to_image_coords(event.pos())
            if image_pos is not None:
                self.right_clicked_with_pos.emit(image_pos.x(), image_pos.y())

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        鼠标移动事件，处理Ctrl+左键拖动图片和普通左键矩形选择
        """
        if self.is_dragging and (event.buttons() & Qt.MouseButton.LeftButton) and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            # Ctrl+左键拖动图片
            # 计算移动距离
            delta = event.pos() - self.last_drag_pos

            # 如果还没开始实际拖拽，检查是否超过阈值
            if not self.drag_started:
                total_distance = delta.manhattanLength()
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
        elif self.is_selecting and (event.buttons() & Qt.MouseButton.LeftButton):
            # 普通左键矩形选择
            self.selection_end = event.pos()
            self.update()  # 重绘以显示选择矩形

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        鼠标释放事件，结束拖动、结束矩形选择或触发点击
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_dragging and self.drag_started:
                # 结束Ctrl+左键拖动
                self.is_dragging = False
                self.drag_started = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
            elif self.is_selecting:
                # 结束矩形选择
                self.is_selecting = False

                # 计算矩形范围并转换为图像坐标
                start_pos = self.map_display_to_image_coords(self.selection_start)
                end_pos = self.map_display_to_image_coords(self.selection_end)

                if start_pos is not None and end_pos is not None:
                    # 确保坐标顺序正确（左上角和右下角）
                    x1, y1 = start_pos.x(), start_pos.y()
                    x2, y2 = end_pos.x(), end_pos.y()

                    left = min(x1, x2)
                    top = min(y1, y2)
                    right = max(x1, x2)
                    bottom = max(y1, y2)

                    # 如果矩形有实际大小（不是单点），发送矩形选择信号
                    if abs(right - left) > 2 or abs(bottom - top) > 2:  # 允许小的误差
                        self.rect_selected.emit(left, top, right, bottom)
                    else:
                        # 如果是单点点击，发送点击信号
                        self.left_clicked_with_pos.emit(x1, y1)

                # 清除选择矩形的显示
                self.update()
            else:
                # 普通点击事件（没有拖动也没有选择）
                image_pos = self.map_display_to_image_coords(event.pos())
                if image_pos is not None:
                    self.left_clicked_with_pos.emit(image_pos.x(), image_pos.y())

                # 重置状态
                self.is_dragging = False
                self.drag_started = False
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def setPixmap(self, pixmap: QPixmap, preserve_state: bool = False):
        """
        保存原始图像并进行初次缩放
        :param pixmap: 要设置的图像
        :param preserve_state: 是否保留当前的缩放和位置状态
        """
        old_pixmap = self.original_pixmap
        self.original_pixmap = pixmap

        # 检查是否需要保留状态
        should_preserve = (preserve_state and
                          old_pixmap is not None and
                          pixmap is not None and
                          old_pixmap.size() == pixmap.size())

        if not should_preserve:
            self.image_offset = QPoint(0, 0)  # 重置偏移量
            # 初始加载时，将图片宽度缩放到等于控件宽度
            if self.width() > 0 and self.original_pixmap is not None:
                self.scale_factor = self.width() / self.original_pixmap.width()
                # 应用缩放上下限
                self.scale_factor = max(self.min_scale, min(self.max_scale, self.scale_factor))
            else:
                self.scale_factor = 1.0

        # 应用边界限制
        self.image_offset = self._limit_image_bounds(self.image_offset)
        # 更新缩放后的图像并触发重绘
        self.update_scaled_pixmap()

    def setImage(self, image, preserve_state: bool = False):
        """
        设置图像的接口，兼容Cv2Image和QPixmap
        :param image: 图像对象
        :param preserve_state: 是否保留当前的缩放和位置状态
        """
        if image is None:
            self.original_pixmap = None
            self.current_scaled_pixmap = QPixmap()
            self.update()
            return

        # 如果是Cv2Image对象，获取其QPixmap
        if hasattr(image, 'to_qpixmap'):
            pixmap = image.to_qpixmap()
        elif isinstance(image, QPixmap):
            pixmap = image
        else:
            # 尝试其他可能的转换
            try:
                pixmap = QPixmap(image)
            except:
                return

        self.setPixmap(pixmap, preserve_state)

    def wheelEvent(self, event: QWheelEvent):
        """
        实现以鼠标位置为基点的滚轮缩放
        """
        if self.original_pixmap is None or self.original_pixmap.isNull():
            return

        # 获取鼠标在控件中的位置
        mouse_pos = event.position().toPoint()

        # 直接计算鼠标在原始图像中的浮点坐标，避免int()转换的精度损失
        image_x = (mouse_pos.x() - self.image_offset.x()) / self.scale_factor
        image_y = (mouse_pos.y() - self.image_offset.y()) / self.scale_factor

        # 计算新的缩放比例
        old_scale = self.scale_factor
        if event.angleDelta().y() > 0:
            new_scale = self.scale_factor * 1.1  # 放大
        else:
            new_scale = self.scale_factor / 1.1  # 缩小

        # 应用上下限
        new_scale = max(self.min_scale, min(self.max_scale, new_scale))

        # 如果缩放未发生变化（被限制），则无需继续
        if abs(new_scale - old_scale) < 1e-9:
            return

        # 更新当前缩放并调整偏移，使鼠标仍指向图像上的同一点
        self.scale_factor = new_scale

        new_offset_x = round(mouse_pos.x() - image_x * self.scale_factor)
        new_offset_y = round(mouse_pos.y() - image_y * self.scale_factor)
        self.image_offset = QPoint(new_offset_x, new_offset_y)

        # 缩放后应用边界限制并更新显示
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

        self.current_scaled_pixmap = scale_pixmap_for_high_dpi(
            self.original_pixmap,
            target_size,
            self.devicePixelRatio()
        )

        # 请求重绘，让paintEvent来处理显示
        self.update()

    def paintEvent(self, event: QPaintEvent):
        """
        在控件上高效地绘制图像和选择矩形。
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
        painter.drawPixmap(self.image_offset, self.current_scaled_pixmap)

        # 如果正在进行矩形选择，绘制选择矩形
        if self.is_selecting:

            # 设置画笔样式
            pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            # 计算矩形
            x1, y1 = self.selection_start.x(), self.selection_start.y()
            x2, y2 = self.selection_end.x(), self.selection_end.y()

            left = min(x1, x2)
            top = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)

            # 绘制选择矩形
            rect = QRect(left, top, width, height)
            painter.drawRect(rect)

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

        # # X 维度处理
        # if scaled_width <= widget_width:
        #     # 图像宽度小于等于控件宽度，允许在控件范围内自由移动
        #     min_x = 0
        #     max_x = widget_width - scaled_width
        #     limited_x = max(min_x, min(max_x, offset.x()))
        # else:
        #     # 图像宽度大于控件宽度，边界限制为控件的一半位置
        #     min_x = -(scaled_width - widget_width // 2)
        #     max_x = widget_width // 2
        #     limited_x = max(min_x, min(max_x, offset.x()))

        # # Y 维度处理
        # if scaled_height <= widget_height:
        #     # 图像高度小于等于控件高度，允许在控件范围内自由移动
        #     min_y = 0
        #     max_y = widget_height - scaled_height
        #     limited_y = max(min_y, min(max_y, offset.y()))
        # else:
        #     # 图像高度大于控件高度，边界限制为控件的一半位置
        #     min_y = -(scaled_height - widget_height // 2)
        #     max_y = widget_height // 2
        #     limited_y = max(min_y, min(max_y, offset.y()))

        # X 维度处理
        if scaled_width <= widget_width:
            # 图像宽度小于等于控件宽度，允许在控件范围内自由移动
            min_x = 0
            max_x = widget_width - scaled_width
            limited_x = max(min_x, min(max_x, offset.x()))
        else:
            # 图像宽度大于控件宽度，限制图像不能在控件留有空白
            min_x = -(scaled_width - widget_width)  # 图像右边缘不能超出控件右边界
            max_x = 0  # 图像左边缘不能超出控件左边界
            limited_x = max(min_x, min(max_x, offset.x()))

        # Y 维度处理
        if scaled_height <= widget_height:
            # 图像高度小于等于控件高度，允许在控件范围内自由移动
            min_y = 0
            max_y = widget_height - scaled_height
            limited_y = max(min_y, min(max_y, offset.y()))
        else:
            # 图像高度大于控件高度，限制图像不能在控件留有空白
            min_y = -(scaled_height - widget_height)  # 图像下边缘不能超出控件下边界
            max_y = 0  # 图像上边缘不能超出控件上边界
            limited_y = max(min_y, min(max_y, offset.y()))

        return QPoint(limited_x, limited_y)
