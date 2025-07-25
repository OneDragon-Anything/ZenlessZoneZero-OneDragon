# coding: utf-8
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QDialog, QPushButton, QFrame


class ColorInfoDialog(QDialog):

    def __init__(self, color_info: dict, parent: QWidget):
        super().__init__(parent=parent)
        self.setWindowTitle('像素颜色信息')

        # 解析传入的数据
        pos = color_info.get('pos')
        source_pos = color_info.get('source_pos')
        display_rgb = color_info.get('display_rgb')
        display_hsv = color_info.get('display_hsv')
        source_rgb = color_info.get('source_rgb')
        source_hsv = color_info.get('source_hsv')

        # 整体布局
        main_layout = QVBoxLayout(self)

        # 包含两个颜色信息的水平布局
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 10)
        content_layout.setSpacing(20)

        # 当前颜色信息
        if display_rgb and display_hsv:
            pos_text = f"当前坐标: ({pos[0]}, {pos[1]})"
            display_widget = self._create_color_widget("当前图像", pos_text, display_rgb, display_hsv)
            content_layout.addWidget(display_widget)

        # 原始颜色信息
        if source_rgb and source_hsv:
            pos_text = f"原始坐标: ({source_pos[0]}, {source_pos[1]})"
            source_widget = self._create_color_widget("原始图像", pos_text, source_rgb, source_hsv)
            content_layout.addWidget(source_widget)

        main_layout.addLayout(content_layout)

        # 按钮
        self.confirm_button = QPushButton('确定')
        self.confirm_button.clicked.connect(self.accept)
        main_layout.addWidget(self.confirm_button, 0, Qt.AlignmentFlag.AlignRight)

        self.setLayout(main_layout)

    def _create_color_widget(self, title: str, pos_text: str, rgb: tuple, hsv: tuple) -> QWidget:
        """
        创建一个显示颜色信息的小组件 (预览+文本)
        """
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        color_preview = QLabel()
        color_preview.setFixedSize(60, 60)
        color_preview.setStyleSheet(f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]}); border: 1px solid gray;")

        info_text = (f"{pos_text}\n"
                     f"RGB: ({rgb[0]}, {rgb[1]}, {rgb[2]})\n"
                     f"HSV: ({hsv[0]}, {hsv[1]}, {hsv[2]})")
        info_label = QLabel(info_text)

        layout.addWidget(title_label)
        layout.addWidget(color_preview, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        return widget