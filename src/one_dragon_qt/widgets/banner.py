import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QImage
from PySide6.QtWidgets import QWidget


class Banner(QWidget):
    """展示带有圆角的固定大小横幅小部件"""

    def __init__(self, image_path: str, parent=None):
        QWidget.__init__(self, parent)
        self.image_path = image_path
        self.banner_image = self.load_banner_image(image_path)
        self.scaled_image = None
        self.update_scaled_image()

    def load_banner_image(self, image_path: str) -> QImage:
        """加载横幅图片，或创建渐变备用图片"""
        if os.path.isfile(image_path):
            return QImage(image_path)
        return self._create_fallback_image()

    def _create_fallback_image(self) -> QImage:
        """创建渐变备用图片"""
        fallback_image = QImage(2560, 1280, QImage.Format.Format_RGB32)
        fallback_image.fill(Qt.GlobalColor.gray)
        return fallback_image

    def update_scaled_image(self) -> None:
        """
        更新缩放后的图片
        :return:
        """
        if self.banner_image.isNull():
            return

        # 获取设备像素比例用于高DPI适配
        pixel_ratio = self.devicePixelRatio()
        target_size = self.size()

        scaled_image = self.banner_image.scaled(
            target_size * pixel_ratio,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        self.scaled_image = QPixmap.fromImage(scaled_image)
        self.scaled_image.setDevicePixelRatio(pixel_ratio)
        self.update()

    def paintEvent(self, event):
        """重载 paintEvent 以绘制缩放后的图片"""
        if self.scaled_image:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            # 创建圆角路径
            path = QPainterPath()
            path.addRoundedRect(self.rect(), 20, 20)
            painter.setClipPath(path)

            # 计算绘制位置，使图片居中
            pixel_ratio = self.scaled_image.devicePixelRatio()
            logical_width = self.scaled_image.width() // pixel_ratio
            logical_height = self.scaled_image.height() // pixel_ratio
            x = (self.width() - logical_width) // 2
            y = (self.height() - logical_height) // 2

            # 绘制缩放后的图片
            painter.drawPixmap(x, y, self.scaled_image)

    def resizeEvent(self, event):
        """重载 resizeEvent 以更新缩放后的图片"""
        self.update_scaled_image()
        QWidget.resizeEvent(self, event)

    def set_percentage_size(self, width_percentage, height_percentage):
        """设置 Banner 的大小为窗口大小的百分比"""
        parent = self.parentWidget()
        if parent:
            new_width = int(parent.width() * width_percentage)
            new_height = int(parent.height() * height_percentage)
            self.setFixedSize(new_width, new_height)
            self.update_scaled_image()

    def set_banner_image(self, image_path: str) -> None:
        """
        设置背景图片
        :param image_path: 图片路径
        :return:
        """
        self.image_path = image_path
        self.banner_image = self.load_banner_image(image_path)
        self.update_scaled_image()
