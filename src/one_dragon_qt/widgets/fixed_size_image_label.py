from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from one_dragon_qt.utils.image_utils import scale_pixmap_for_high_dpi


class FixedSizeImageLabel(QLabel):
    """
    固定大小的图片标签，支持高DPI缩放和保持长宽比
    可以固定宽度让高度自适应，或固定高度让宽度自适应
    """

    def __init__(self, fixed_width: int = 150, fixed_height: int = None, parent=None):
        super().__init__(parent)

        self.fixed_width = fixed_width
        self.fixed_height = fixed_height
        self.original_pixmap: QPixmap = None
        self.aspect_ratio_mode = "width_fixed" if fixed_height is None else "both_fixed"

        # 根据模式设置初始大小
        if self.aspect_ratio_mode == "width_fixed":
            # 只固定宽度，高度会根据图片比例调整
            self.setFixedWidth(fixed_width)
            self.setMinimumHeight(20)  # 设置最小高度
            self.setMaximumHeight(16777215)  # 允许高度变化
            # 设置尺寸策略：宽度固定，高度最小
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        else:
            # 固定宽度和高度
            self.setFixedSize(fixed_width, fixed_height)
            # 设置尺寸策略：固定大小
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 设置对齐方式为居中
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def setPixmap(self, pixmap: QPixmap):
        """
        设置图片，自动进行高DPI缩放和长宽比保持
        """
        if pixmap is None or pixmap.isNull():
            # 清空标签
            super().setPixmap(QPixmap())
            self.original_pixmap = None
            # 重置组件大小
            if self.aspect_ratio_mode == "width_fixed":
                self.resize(self.fixed_width, 20)
                self.setMinimumHeight(20)
                self.setMaximumHeight(20)
            return

        self.original_pixmap = pixmap

        # 如果是宽度固定模式，先计算逻辑目标高度
        logical_target_height = None
        if self.aspect_ratio_mode == "width_fixed":
            original_width = pixmap.width()
            original_height = pixmap.height()
            if original_width > 0:
                aspect_ratio = original_height / original_width
                logical_target_height = int(self.fixed_width * aspect_ratio)

        scaled_pixmap = self._scale_pixmap_keep_ratio(pixmap)

        # 如果是宽度固定模式，使用逻辑高度设置组件高度
        if self.aspect_ratio_mode == "width_fixed" and logical_target_height is not None:
            # 使用逻辑高度而不是物理高度
            self.setFixedHeight(logical_target_height)
            self.setMinimumHeight(logical_target_height)
            self.setMaximumHeight(logical_target_height)

        # 调用父类方法
        super().setPixmap(scaled_pixmap)

    def setImage(self, image):
        """
        设置图像的接口，兼容Cv2Image和QPixmap
        """
        if image is None:
            self.setPixmap(None)
            return

        if isinstance(image, QPixmap):
            pixmap = image
        else:
            # 尝试从QImage创建QPixmap
            try:
                pixmap = QPixmap.fromImage(image)
            except Exception:
                return

        self.setPixmap(pixmap)

    def _scale_pixmap_keep_ratio(self, pixmap: QPixmap) -> QPixmap:
        """
        按比例缩放图片，保持长宽比
        """
        if pixmap is None or pixmap.isNull():
            return pixmap

        if self.aspect_ratio_mode == "width_fixed":
            # 宽度固定模式：根据固定宽度计算对应高度
            original_width = pixmap.width()
            original_height = pixmap.height()

            if original_width == 0:
                return pixmap

            # 计算按固定宽度缩放后的高度
            aspect_ratio = original_height / original_width
            target_height = int(self.fixed_width * aspect_ratio)
            target_size = QSize(self.fixed_width, target_height)

        else:
            # 固定宽高模式：按比例缩放到固定尺寸
            target_size = QSize(self.fixed_width, self.fixed_height)

        # 直接使用高DPI缩放，内部会处理比例缩放
        return scale_pixmap_for_high_dpi(
            pixmap,
            target_size,
            self.devicePixelRatio(),
            Qt.AspectRatioMode.KeepAspectRatio
        )

    def setFixedSize(self, width: int, height: int):
        """
        重写setFixedSize方法，同时更新内部的固定尺寸参数
        """
        self.fixed_width = width
        self.fixed_height = height
        self.aspect_ratio_mode = "both_fixed"
        super().setFixedSize(width, height)

        # 如果有原始图片，重新缩放
        if self.original_pixmap is not None:
            scaled_pixmap = self._scale_pixmap_keep_ratio(self.original_pixmap)
            super().setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """
        处理控件大小变化事件，重新应用缩放
        """
        super().resizeEvent(event)
        if self.original_pixmap is not None:
            # 重新计算并设置正确的组件高度
            if self.aspect_ratio_mode == "width_fixed":
                original_width = self.original_pixmap.width()
                original_height = self.original_pixmap.height()
                if original_width > 0:
                    aspect_ratio = original_height / original_width
                    logical_target_height = int(self.fixed_width * aspect_ratio)
                    self.setFixedHeight(logical_target_height)
                    self.setMinimumHeight(logical_target_height)
                    self.setMaximumHeight(logical_target_height)

            scaled_pixmap = self._scale_pixmap_keep_ratio(self.original_pixmap)
            super().setPixmap(scaled_pixmap)
