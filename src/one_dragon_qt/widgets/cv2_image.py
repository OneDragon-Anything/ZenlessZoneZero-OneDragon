import cv2
from cv2.typing import MatLike
from PySide6.QtGui import QImage


class Cv2Image(QImage):

    def __init__(self, cv_image: MatLike):
        if cv_image.ndim == 2:  # 如果是灰度图
            converted = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2RGB)
        elif cv_image.shape[2] == 3:  # 如果是BGR图像
            converted = cv_image  # 转换到RGB
        elif cv_image.shape[2] == 4:  # 如果是BGRA图像
            converted = cv_image

        height, width, channel = converted.shape
        QImage.__init__(self, converted.data, width, height, 3 * width, QImage.Format.Format_RGB888)
