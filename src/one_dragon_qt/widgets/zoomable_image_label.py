# coding: utf-8
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QWheelEvent, QPixmap
from PySide6.QtWidgets import QSizePolicy

from one_dragon_qt.widgets.click_image_label import ClickImageLabel


class ZoomableClickImageLabel(ClickImageLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scale_factor = 1.0
        self.original_pixmap: QPixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def setPixmap(self, pixmap: QPixmap):
        """
        重写 setPixmap，保存原始图像并进行初次缩放
        """
        self.original_pixmap = pixmap
        # 初始加载时，将图片宽度缩放到等于控件宽度
        if self.width() > 0 and self.original_pixmap is not None:
            self.scale_factor = self.width() / self.original_pixmap.width()
        else:
            self.scale_factor = 1.0
        self.update_scaled_pixmap()

    def wheelEvent(self, event: QWheelEvent):
        """
        重写 wheelEvent，实现 Ctrl+滚轮 缩放
        """
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.scale_factor *= 1.1  # 放大
            else:
                self.scale_factor /= 1.1  # 缩小
            self.update_scaled_pixmap()
        else:
            # 如果没有按住Ctrl，事件将交给父控件处理（例如，滚动条）
            super().wheelEvent(event)

    def update_scaled_pixmap(self):
        """
        根据当前的缩放比例，更新显示的图像
        """
        if self.original_pixmap is None:
            return

        new_width = int(self.original_pixmap.width() * self.scale_factor)
        scaled_pixmap = self.original_pixmap.scaledToWidth(new_width, Qt.TransformationMode.SmoothTransformation)
        super().setPixmap(scaled_pixmap)

    def map_display_to_image_coords(self, display_pos: QPoint) -> QPoint:
        """
        将显示坐标转换为原始图像坐标
        :param display_pos: 在控件上点击的坐标
        :return: 在原始图片上的坐标
        """
        if self.original_pixmap is None:
            return None

        # a = self.original_pixmap.width()
        # b = self.width()
        # c = self.scale_factor
        #
        # d = display_pos.x()
        # e = int(display_pos.x() / self.scale_factor)
        image_x = int(display_pos.x() / self.scale_factor)
        image_y = int(display_pos.y() / self.scale_factor)

        return QPoint(image_x, image_y)