import os
from enum import Enum
from typing import Union, Optional

import numpy as np
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QMouseEvent, QPixmap, QImage
from PySide6.QtWidgets import QWidget
from cv2.typing import MatLike
from qfluentwidgets import ImageLabel

from one_dragon.base.config.config_item import ConfigItem


class ImageScaleEnum(Enum):

    SCALE_100 = ConfigItem(label='原图', value=1)
    SCALE_50 = ConfigItem(label='0.5x', value=0.5)
    X2 = ConfigItem(label='2x', value=2.0)
    X4 = ConfigItem(label='4x', value=4.0)
    X8 = ConfigItem(label='8x', value=8.0)


class ClickImageLabel(ImageLabel):

    clicked_with_pos = Signal(int, int)
    right_clicked_with_pos = Signal(int, int)  # 新增右键点击信号
    drag_released = Signal(int, int, int, int)

    def __init__(self, parent: QWidget = None):
        ImageLabel.__init__(self, parent)

        self._press_pos: QPoint = None
        self._release_pos: QPoint = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
            self.clicked_with_pos.emit(self._press_pos.x(), self._press_pos.y())
        elif event.button() == Qt.MouseButton.RightButton:
            pos = event.pos()
            self.right_clicked_with_pos.emit(pos.x(), pos.y())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._release_pos = event.pos()
            if self._press_pos is not None:
                self.drag_released.emit(self._press_pos.x(), self._press_pos.y(),
                                        self._release_pos.x(), self._release_pos.y())

    def set_image(self, image_source: Union[str, MatLike]):
        """设置要显示的图片.

        Args:
            image_source: 图片源，可以是文件路径字符串或OpenCV RGB格式的numpy数组
        """
        if isinstance(image_source, str):
            # 从文件路径加载图片
            if not os.path.exists(image_source):
                return  # 无效图片，不显示任何内容

            pixmap = QPixmap(image_source)
            if pixmap.isNull():
                return  # 无效图片，不显示任何内容
        elif isinstance(image_source, np.ndarray):
            # 从OpenCV RGB格式数组加载图片
            pixmap = self._numpy_to_pixmap(image_source)
            if pixmap is None:
                return  # 无效图片，不显示任何内容
        else:
            return  # 不支持的格式，不显示任何内容

        self.setImage(pixmap)

    def _numpy_to_pixmap(self, image_array: MatLike) -> Optional[QPixmap]:
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