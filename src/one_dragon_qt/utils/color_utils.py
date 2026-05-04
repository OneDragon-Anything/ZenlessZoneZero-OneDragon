"""
Qt 颜色处理工具函数
提供 Qt GUI 相关的颜色计算、转换等功能
"""
import math

import cv2
import numpy as np
from PySide6.QtGui import QColor, QImage


def calculate_luminance(r: int, g: int, b: int) -> float:
    """计算颜色的相对亮度 (ITU-R BT.709)"""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def get_foreground_color(r: int, g: int, b: int, threshold: float = 160) -> str:
    """根据背景色返回合适的前景色 "#000000" 或 "#FFFFFF" """
    return "#000000" if calculate_luminance(r, g, b) >= threshold else "#FFFFFF"


def _qimage_to_rgb_array(image: QImage) -> np.ndarray | None:
    """将 QImage 转为 RGB numpy 数组 (H, W, 3)"""
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    w, h = image.width(), image.height()
    bytes_per_line = image.bytesPerLine()
    ptr = image.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bytes_per_line)
    return arr[:, :w * 3].reshape(h, w, 3).copy()


def extract_dominant_hue(image: QImage | None, max_dim: int = 200) -> float | None:
    """
    从图片提取主色调色相

    使用 cv2 + numpy 向量化计算。
    图片先缩放到 max_dim 以内，然后批量转 HSV 并做加权圆周平均。

    Returns:
        色相角度 0-360，灰色图或无效图片返回 None
    """
    if image is None or image.isNull():
        return None

    w, h = image.width(), image.height()
    if w <= 0 or h <= 0:
        return None

    scale = min(1.0, max_dim / max(w, h))
    if scale < 1.0:
        image = image.scaled(int(w * scale), int(h * scale))

    rgb = _qimage_to_rgb_array(image)
    if rgb is None:
        return None

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    h_ch = hsv[:, :, 0].astype(np.float64)  # 0-180
    s_ch = hsv[:, :, 1].astype(np.float64) / 255.0
    v_ch = hsv[:, :, 2].astype(np.float64) / 255.0

    # 过滤灰阶和暗色像素
    mask = (s_ch > 0.05) & (v_ch > 0.1)
    if not np.any(mask):
        return None

    h_masked = h_ch[mask]
    s_masked = s_ch[mask]
    v_masked = v_ch[mask]

    weight = s_masked * v_masked

    angle = h_masked * (np.pi / 90.0)  # 0-180 → 0-2π
    sum_cos = np.sum(np.cos(angle) * weight)
    sum_sin = np.sum(np.sin(angle) * weight)

    if math.hypot(sum_cos, sum_sin) < 1e-6:
        return None

    return math.degrees(math.atan2(sum_sin, sum_cos)) % 360.0


def hue_to_theme_color(hue: float, saturation: float = 0.6,
                       value: float = 0.7) -> tuple[int, int, int]:
    """
    根据色相生成主题色 (HSV 空间)

    S 和 V 使用固定值，不依赖图片原始亮度。
    """
    color = QColor.fromHsvF(hue / 360.0, saturation, value)
    return color.red(), color.green(), color.blue()
