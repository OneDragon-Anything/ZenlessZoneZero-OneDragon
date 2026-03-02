from __future__ import annotations

from typing import Optional

from cv2.typing import MatLike
from PySide6.QtWidgets import QHBoxLayout, QFrame
from qfluentwidgets import (
    BodyLabel,
    PushButton,
    SimpleCardWidget,
    FluentIcon,
    PrimaryPushButton,
)

from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.fixed_size_image_label import FixedSizeImageLabel
from one_dragon_qt.widgets.row import Row


class TemplateCardWidget(SimpleCardWidget):
    """单个模板的卡片组件"""

    def __init__(self, title: str, template_config: dict, parent=None):
        SimpleCardWidget.__init__(self, parent=parent)

        self.template_config = template_config
        self.screen_image: Optional[MatLike] = None
        self.preview_image: Optional[MatLike] = None
        self.is_saved: bool = False

        # 单行布局：标题 | 三个按钮 | 预览框
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # 标题
        self.title_label = BodyLabel(text=title)
        layout.addWidget(self.title_label)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 三个按钮
        btn_row = Row(spacing=10, margins=(0, 0, 0, 0))
        layout.addWidget(btn_row)

        self.btn_choose_screenshot = PushButton(text='选择截图', icon=FluentIcon.FOLDER)
        btn_row.add_widget(self.btn_choose_screenshot)

        self.btn_capture_game = PushButton(text='游戏截图', icon=FluentIcon.CAMERA)
        btn_row.add_widget(self.btn_capture_game)

        self.btn_save = PrimaryPushButton(text='保存', icon=FluentIcon.SAVE)
        self.btn_save.setEnabled(False)
        btn_row.add_widget(self.btn_save)

        # 分割线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.VLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line2)

        # 预览框
        self.preview_label = FixedSizeImageLabel(120)
        layout.addWidget(self.preview_label)

    def set_preview_image(self, image: Optional[MatLike]) -> None:
        self.preview_image = image
        if image is None:
            self.preview_label.setImage(None)
        else:
            self.preview_label.setImage(Cv2Image(image))

    def set_saved(self, saved: bool) -> None:
        self.is_saved = saved
        if saved:
            self.btn_save.setEnabled(False)

    def set_buttons_enabled(self, enabled: bool) -> None:
        self.btn_choose_screenshot.setEnabled(enabled)
        self.btn_capture_game.setEnabled(enabled)
        if not enabled:
            self.btn_save.setEnabled(False)

    def reset_preview(self) -> None:
        self.screen_image = None
        self.preview_image = None
        self.is_saved = False
        self.preview_label.setImage(None)
        self.btn_save.setEnabled(False)
