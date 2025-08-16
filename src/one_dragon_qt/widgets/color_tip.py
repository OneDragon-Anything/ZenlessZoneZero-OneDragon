from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (FlyoutViewBase, TeachingTip, TeachingTipTailPosition,
                            FluentIcon, SubtitleLabel, BodyLabel, TransparentToolButton, TransparentPushButton)


class ColorInfoWidget(QWidget):
    """
    单个颜色信息显示控件
    """

    def __init__(self, color_info: Dict[str, Any], parent: Optional[QWidget] = None):
        """
        初始化颜色信息控件

        :param color_info: 颜色信息字典，包含pos, rgb, hsv等信息
        :param parent: 父控件
        """
        super().__init__(parent)
        self.color_info = color_info
        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 获取颜色信息
        pos = self.color_info.get('pos', (0, 0))
        rgb = self.color_info.get('rgb') or self.color_info.get('display_rgb', (0, 0, 0))
        hsv = self.color_info.get('hsv') or self.color_info.get('display_hsv', (0, 0, 0))
        title = self.color_info.get('title', '颜色信息')

        # 标题标签
        title_label = SubtitleLabel(title)
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 颜色块
        color_block = QWidget()
        color_block.setFixedSize(60, 30)
        color_block.setStyleSheet(f"""
            QWidget {{
                background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }}
        """)
        layout.addWidget(color_block, alignment=Qt.AlignmentFlag.AlignCenter)

        # 坐标信息
        pos_container = QHBoxLayout()
        pos_label_left = BodyLabel("坐标")
        pos_str = f'({pos[0]}, {pos[1]})'
        pos_label_right = TransparentPushButton(text=pos_str)
        pos_label_right.clicked.connect(lambda: QTimer.singleShot(0, lambda: QApplication.clipboard().setText(pos_str)))
        pos_container.addSpacing(12)
        pos_container.addWidget(pos_label_left, alignment=Qt.AlignmentFlag.AlignLeft)
        pos_container.addWidget(pos_label_right, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(pos_container)

        # RGB信息
        rgb_container = QHBoxLayout()
        rgb_label_left = BodyLabel("RGB")
        rgb_str = f"({rgb[0]}, {rgb[1]}, {rgb[2]})"
        rgb_label_right = TransparentPushButton(text=rgb_str)
        rgb_label_right.clicked.connect(lambda: QTimer.singleShot(0, lambda: QApplication.clipboard().setText(rgb_str)))
        rgb_container.addSpacing(12)
        rgb_container.addWidget(rgb_label_left, alignment=Qt.AlignmentFlag.AlignLeft)
        rgb_container.addWidget(rgb_label_right, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(rgb_container)

        # HSV信息
        hsv_container = QHBoxLayout()
        hsv_label_left = BodyLabel("HSV")
        hsv_str = f"({hsv[0]}, {hsv[1]}, {hsv[2]})"
        hsv_label_right = TransparentPushButton(text=hsv_str)
        hsv_label_right.clicked.connect(lambda: QTimer.singleShot(0, lambda: QApplication.clipboard().setText(hsv_str)))
        hsv_container.addSpacing(12)
        hsv_container.addWidget(hsv_label_left, alignment=Qt.AlignmentFlag.AlignLeft)
        hsv_container.addWidget(hsv_label_right, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(hsv_container)

        # 设置最小宽度
        self.setMinimumWidth(190)


class MultiColorFlyoutView(FlyoutViewBase):
    """
    多颜色信息显示的 Flyout 视图
    """

    def __init__(self, color_infos: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        """
        初始化多颜色 Flyout 视图

        :param color_infos: 颜色信息列表
        :param parent: 父控件
        """
        super().__init__(parent)
        self.color_infos = color_infos
        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        # 创建水平布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 4, 4, 4)
        layout.setSpacing(0)

        # 为每个颜色信息创建控件
        for idx, color_info in enumerate(self.color_infos):
            if not self._validate_color_info(color_info):
                continue

            color_widget = ColorInfoWidget(color_info)
            layout.addWidget(color_widget)
            if idx < len(self.color_infos) - 1:
                separator = QWidget()
                separator.setFixedSize(1, 170)
                separator.setStyleSheet("background-color: #c0c0c0;")
                layout.addWidget(separator, alignment=Qt.AlignmentFlag.AlignVCenter)

        # 如果没有有效的颜色信息，显示错误消息
        if layout.count() == 0:
            error_label = BodyLabel("无有效颜色信息")
            error_label.setStyleSheet("color: #d13438; padding: 20px;")
            layout.addWidget(error_label)

        self.closeButton = TransparentToolButton(FluentIcon.CLOSE)
        self.closeButton.setFixedSize(32, 32)
        self.closeButton.setIconSize(QSize(12, 12))
        layout.addWidget(self.closeButton, alignment=Qt.AlignmentFlag.AlignTop)

    def _validate_color_info(self, color_info: Dict[str, Any]) -> bool:
        """
        验证颜色信息是否有效

        :param color_info: 颜色信息字典
        :return: 是否有效
        """
        pos = color_info.get('pos')
        rgb = color_info.get('rgb') or color_info.get('display_rgb')
        hsv = color_info.get('hsv') or color_info.get('display_hsv')

        return all([
            pos is not None,
            rgb is not None and len(rgb) == 3,
            hsv is not None and len(hsv) == 3
        ])


class ColorTip:

    _current_tip: Optional[TeachingTip] = None

    @classmethod
    def show_color_tip(cls, target: QWidget, color_infos: List[Dict[str, Any]],
                       parent: Optional[QWidget] = None) -> TeachingTip:
        """
        显示多个颜色信息的提示框

        :param target: 目标控件
        :param color_infos: 颜色信息列表
        :param parent: 父控件
        :return: 配置好的 TeachingTip 实例
        """
        # 关闭现有的提示框
        if cls._current_tip is not None:
            QTimer.singleShot(250, cls._current_tip.close)

        # 创建多颜色控件视图
        content_view = MultiColorFlyoutView(color_infos)

        # 创建并显示 TeachingTip
        tip = TeachingTip.make(
            view=content_view,
            target=target,
            duration=-1,
            tailPosition=TeachingTipTailPosition.BOTTOM,
            parent=parent
        )

        # 保存当前提示框引用
        cls._current_tip = tip
        content_view.closeButton.clicked.connect(cls._current_tip.close)

        return tip
