from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from qfluentwidgets import FluentIconBase, FluentStyleSheet, SettingCard
from qfluentwidgets.components.settings.setting_card import SettingIconWidget

from one_dragon.utils.i18_utils import (
    gt,
    subscribe_language_changed,
    unsubscribe_language_changed,
)
from one_dragon_qt.utils.layout_utils import IconSize, Margins


class SettingCardBase(SettingCard):

    _title_msgid: str
    _content_msgid: str | None

    def __init__(self, icon: str | QIcon | FluentIconBase, title, content=None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 parent=None):
        QFrame.__init__(self, parent=parent)

        # 初始化布局
        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()

        # 设置固定高度
        self.setFixedHeight(50)

        # 设置水平布局属性
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(margins.left, 0, margins.right, 0)
        self.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 设置垂直布局属性
        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._title_msgid = title
        self._content_msgid = content
        self.titleLabel = QLabel(gt(title), self)
        self.contentLabel = QLabel('', self)

        # 设置最大宽度限制，防止文字过长撑大窗口
        self.contentLabel.setMaximumWidth(500)

        # 处理内容显示
        self._language_callback = self.retranslate_ui
        subscribe_language_changed(self._language_callback)
        self.destroyed.connect(self._on_destroyed)
        self.setContent(content)

        # 如果有图标，初始化图标组件
        if icon:
            self.iconLabel = SettingIconWidget(icon, self)
            self.iconLabel.setFixedSize(icon_size.width, icon_size.height)
            self.hBoxLayout.addWidget(self.iconLabel, 0, Qt.AlignmentFlag.AlignLeft)

        # 添加组件到布局
        self.hBoxLayout.addSpacing(margins.top)
        self.hBoxLayout.addLayout(self.vBoxLayout)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignLeft)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.addSpacing(margins.bottom)
        self.hBoxLayout.addStretch(1)

        # 设置样式
        self.contentLabel.setObjectName("contentLabel")
        FluentStyleSheet.SETTING_CARD.apply(self)

    def _on_destroyed(self, _object: QObject | None = None) -> None:
        """Unsubscribe the card after Qt destroys it."""
        unsubscribe_language_changed(self._language_callback)

    def _set_content_text(self, content: str | None) -> None:
        """Render translated content while keeping the source message id."""
        translated_content = gt(content)
        if translated_content is not None:
            font_metrics = self.contentLabel.fontMetrics()
            max_width = self.contentLabel.maximumWidth()
            elided_text = font_metrics.elidedText(
                translated_content,
                Qt.TextElideMode.ElideRight,
                max_width,
            )
            self.contentLabel.setText(elided_text)
            if font_metrics.horizontalAdvance(translated_content) > max_width:
                self.contentLabel.setToolTip(translated_content)
            else:
                self.contentLabel.setToolTip("")
        else:
            self.contentLabel.setText("")
            self.contentLabel.setToolTip("")
        self.contentLabel.setVisible(
            translated_content is not None and len(translated_content) > 0
        )

    def setContent(self, content: str | None) -> None:
        """Set the card description and remember its source message id."""
        self._content_msgid = content
        self._set_content_text(content)

    def retranslate_ui(self, _language: str | None = None) -> None:
        """Refresh the card text after the application language changes."""
        self.titleLabel.setText(gt(self._title_msgid))
        self._set_content_text(self._content_msgid)

    def setIconSize(self, width: int, height: int):
        """设置图标的固定大小"""
        if hasattr(self, "iconLabel"):  # 确保 iconLabel 已初始化
            self.iconLabel.setFixedSize(width, height)
