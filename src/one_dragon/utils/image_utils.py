from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize


def scale_pixmap_for_high_dpi(
    pixmap: QPixmap,
    target_size: QSize,
    pixel_ratio: float,
    aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio
) -> QPixmap:
    """
    对已有的QPixmap进行高DPI缩放处理。

    :param pixmap: 原始QPixmap对象
    :param target_size: 目标逻辑尺寸
    :param pixel_ratio: 设备像素比
    :param aspect_ratio_mode: 纵横比模式，默认保持比例
    :return: 处理好的QPixmap
    """
    if pixmap.isNull():
        return QPixmap()

    # 计算目标的物理像素尺寸
    physical_size = target_size * pixel_ratio

    # 直接使用 QPixmap.scaled 进行高质量缩放
    scaled_pixmap = pixmap.scaled(
        physical_size,
        aspect_ratio_mode,
        Qt.TransformationMode.SmoothTransformation
    )

    # 设置正确的设备像素比
    scaled_pixmap.setDevicePixelRatio(pixel_ratio)

    return scaled_pixmap
