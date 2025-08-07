# coding: utf-8
import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QDialog, QPushButton, QFrame, QScrollArea


class ColorChannelDialog(QDialog):
    """
    色彩通道显示弹窗
    显示RGB、HSV、YUV、LAB四种色彩空间的通道分解
    """

    def __init__(self, image: np.ndarray, parent: QWidget):
        super().__init__(parent=parent)
        self.setWindowTitle('色彩通道分析')
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # 存储原始图像
        self.image = image

        # 初始化UI
        self._init_ui()

        # 生成并显示通道图像
        self._generate_channel_images()

    def _init_ui(self):
        """初始化UI布局"""
        main_layout = QVBoxLayout(self)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # 创建内容容器
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(20)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 确定按钮
        self.confirm_button = QPushButton('确定')
        self.confirm_button.clicked.connect(self.accept)
        main_layout.addWidget(self.confirm_button, 0, Qt.AlignmentFlag.AlignRight)

    def _generate_channel_images(self):
        """生成各种色彩空间的通道图像"""
        if self.image is None:
            return
            
        # 确保图像是RGB格式
        if len(self.image.shape) == 2:
            # 如果是灰度图，转换为RGB
            rgb_image = cv2.cvtColor(self.image, cv2.COLOR_GRAY2RGB)
        else:
            rgb_image = self.image.copy()
        
        # 生成各色彩空间的通道
        color_spaces = {
            'RGB': self._get_rgb_channels(rgb_image),
            'HSV': self._get_hsv_channels(rgb_image),
            'YUV': self._get_yuv_channels(rgb_image),
            'LAB': self._get_lab_channels(rgb_image)
        }
        
        # 为每个色彩空间创建显示行
        for space_name, (channels, channel_names) in color_spaces.items():
            self._create_color_space_row(space_name, channels, channel_names)

    def _get_rgb_channels(self, image: np.ndarray) -> tuple:
        """获取RGB通道"""
        r_channel = image[:, :, 0]
        g_channel = image[:, :, 1]
        b_channel = image[:, :, 2]
        return ([r_channel, g_channel, b_channel], ['R', 'G', 'B'])

    def _get_hsv_channels(self, image: np.ndarray) -> tuple:
        """获取HSV通道"""
        hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        h_channel = hsv_image[:, :, 0]
        s_channel = hsv_image[:, :, 1]
        v_channel = hsv_image[:, :, 2]
        return ([h_channel, s_channel, v_channel], ['H', 'S', 'V'])

    def _get_yuv_channels(self, image: np.ndarray) -> tuple:
        """获取YUV通道"""
        yuv_image = cv2.cvtColor(image, cv2.COLOR_RGB2YUV)
        y_channel = yuv_image[:, :, 0]
        u_channel = yuv_image[:, :, 1]
        v_channel = yuv_image[:, :, 2]
        return ([y_channel, u_channel, v_channel], ['Y', 'U', 'V'])

    def _get_lab_channels(self, image: np.ndarray) -> tuple:
        """获取LAB通道"""
        lab_image = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l_channel = lab_image[:, :, 0]
        a_channel = lab_image[:, :, 1]
        b_channel = lab_image[:, :, 2]
        return ([l_channel, a_channel, b_channel], ['L', 'A', 'B'])

    def _create_color_space_row(self, space_name: str, channels: list, channel_names: list):
        """创建一行色彩空间显示"""
        # 创建行容器
        row_frame = QFrame()
        row_frame.setFrameShape(QFrame.Shape.StyledPanel)
        row_layout = QVBoxLayout(row_frame)
        
        # 色彩空间标题
        title_label = QLabel(f"{space_name} 色彩空间")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 5px;")
        row_layout.addWidget(title_label)
        
        # 通道图像容器
        channels_layout = QHBoxLayout()
        channels_layout.setSpacing(10)
        
        for i, (channel, name) in enumerate(zip(channels, channel_names)):
            channel_widget = self._create_channel_widget(channel, f"{space_name} - {name}")
            channels_layout.addWidget(channel_widget)
        
        row_layout.addLayout(channels_layout)
        self.content_layout.addWidget(row_frame)

    def _create_channel_widget(self, channel: np.ndarray, title: str) -> QWidget:
        """创建单个通道显示控件"""
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # 通道标题
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 12px; font-weight: bold; margin: 5px;")
        layout.addWidget(title_label)

        # 通道图像
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setMinimumSize(250, 180)
        image_label.setMaximumSize(350, 250)
        image_label.setScaledContents(True)
        image_label.setStyleSheet("border: 2px solid #ccc; background-color: #f5f5f5;")

        # 转换通道为QPixmap
        pixmap = self._channel_to_pixmap(channel)
        image_label.setPixmap(pixmap)

        layout.addWidget(image_label)
        return widget

    def _channel_to_pixmap(self, channel: np.ndarray) -> QPixmap:
        """将单通道图像转换为QPixmap"""
        # 确保通道是uint8格式
        if channel.dtype != np.uint8:
            channel = np.clip(channel, 0, 255).astype(np.uint8)
        channel_copy = channel.copy()
        # 创建QImage
        height, width = channel.shape
        q_image = QImage(channel_copy.data, width, height, width, QImage.Format.Format_Grayscale8)
        
        # 转换为QPixmap
        return QPixmap.fromImage(q_image)
