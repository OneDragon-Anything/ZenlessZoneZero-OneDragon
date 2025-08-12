from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QSize
from typing import TypeVar

# 定义泛型类型，支持 QPixmap 和 QImage
ImageType = TypeVar('ImageType', QPixmap, QImage)


def _scale_image_object_for_high_dpi(
    image_obj: ImageType,
    target_size: QSize,
    pixel_ratio: float,
    aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio
) -> ImageType:
    """
    对QPixmap或QImage进行高DPI缩放处理的通用实现。

    :param image_obj: 原始图像对象（QPixmap或QImage）
    :param target_size: 目标逻辑尺寸
    :param pixel_ratio: 设备像素比
    :param aspect_ratio_mode: 纵横比模式，默认保持比例
    :return: 处理好的图像对象
    """
    if image_obj.isNull():
        return type(image_obj)()

    # 计算目标的物理像素尺寸
    physical_size = target_size * pixel_ratio

    # 直接使用 scaled 进行高质量缩放
    scaled_obj = image_obj.scaled(
        physical_size,
        aspect_ratio_mode,
        Qt.TransformationMode.SmoothTransformation
    )

    # 设置正确的设备像素比
    scaled_obj.setDevicePixelRatio(pixel_ratio)

    return scaled_obj


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
    return _scale_image_object_for_high_dpi(pixmap, target_size, pixel_ratio, aspect_ratio_mode)


def scale_image_for_high_dpi(
    image: QImage,
    target_size: QSize,
    pixel_ratio: float,
    aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio
) -> QImage:
    """
    对已有的QImage进行高DPI缩放处理。

    :param image: 原始QImage对象
    :param target_size: 目标逻辑尺寸
    :param pixel_ratio: 设备像素比
    :param aspect_ratio_mode: 纵横比模式，默认保持比例
    :return: 处理好的QImage
    """
    return _scale_image_object_for_high_dpi(image, target_size, pixel_ratio, aspect_ratio_mode)
