"""插件详情弹窗。

点击插件卡片后弹出，展示名称、版本、作者、标签、简介、README 与更新日志，
并按插件的当前状态给出订阅 / 取消订阅 / 更新 / 忽略此版本等操作。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    MaskDialogBase,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    TextBrowser,
    TransparentToolButton,
    isDarkTheme,
    setCustomStyleSheet,
)

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.fast_scroll_area import FastScrollArea

ACTION_SUBSCRIBE = 'subscribe'
ACTION_UNSUBSCRIBE = 'unsubscribe'
ACTION_UNINSTALL = 'uninstall'
ACTION_UPDATE = 'update'
ACTION_IGNORE = 'ignore'

DIALOG_WIDTH = 720
DIALOG_HEIGHT = 560


@dataclass
class PluginDetailData:
    """详情弹窗需要的全部数据，由调用方组装。"""

    title: str
    initial: str
    meta_text: str = ''
    tags: list[str] = field(default_factory=list)
    summary: str = ''
    readme_html: str = ''
    changelog_html: str = ''
    changelog_version: str = ''
    status_text: str = ''
    status_kind: str = ''
    warning_text: str = ''
    """灰色警示，用于仓库失联这类维护状态提示。"""
    homepage: str = ''
    actions: list[tuple[str, str]] = field(default_factory=list)
    """可执行操作，元素为 (动作标识, 按钮文字)；第一个动作按主要按钮绘制。"""

    action_enabled: bool = True


class HtmlView(TextBrowser):
    """只做静态展示的富文本视图。

    插件 README 与更新日志来自第三方仓库，属于不可信内容：这里禁止加载远程
    资源，链接点击也只交给系统浏览器处理，不在应用内打开。
    """

    HTML_STYLE = (
        '<style>'
        'p { margin-top: 4px; margin-bottom: 4px; }'
        'li { margin-top: 2px; margin-bottom: 2px; }'
        'code { font-family: Consolas, monospace; }'
        'img { max-width: 100%; }'
        '</style>'
    )

    HEADING_TAG_PATTERN = re.compile(r'<(/?)h([1-6])([^>]*)>', re.IGNORECASE)
    """README 里的 h1~h6 会被换成同字号的小标题段落。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._syncing_height: bool = False
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        setCustomStyleSheet(
            self,
            'TextBrowser { background-color: transparent; border: none; }',
            'TextBrowser { background-color: transparent; border: none; }',
        )
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.document().documentLayout().documentSizeChanged.connect(self._sync_height)

    def set_html(self, html: str) -> None:
        self.setHtml(self.HTML_STYLE + self._flatten_headings(html))
        self._sync_height()

    @classmethod
    def _flatten_headings(cls, html: str) -> str:
        """把 h1~h6 换成小字号段落。

        QTextDocument 不认 <style> 里给标题设的字号，标题会以远大于正文的字号
        显示，这里直接在标签层面换掉。
        """

        def replace(match: re.Match) -> str:
            closing, _level, _attrs = match.groups()
            if closing:
                return '</p>'
            return '<p style="font-size: 13px; font-weight: 600;">'

        return cls.HEADING_TAG_PATTERN.sub(replace, html)

    def loadResource(self, resource_type: int, url: QUrl) -> object:
        # 一律不加载外部资源，避免插件 README 里的远程图片与样式
        return None

    def _sync_height(self, _size: QSize | None = None) -> None:
        if self._syncing_height:
            return
        self._syncing_height = True
        try:
            height = int(self.document().size().height()) + 8
            if height != self.height():
                self.setFixedHeight(max(40, height))
        finally:
            self._syncing_height = False

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sync_height()

    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() in ('http', 'https'):
            QDesktopServices.openUrl(url)


class PluginDetailDialog(MaskDialogBase):
    """插件详情弹窗，居中显示在遮罩上。"""

    action_triggered = Signal(str)

    def __init__(
        self,
        data: PluginDetailData,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data: PluginDetailData = data
        self._isClosableOnMaskClicked = True

        # 把默认的空 QFrame 换成不透明卡片容器，避免透出背后的列表
        placeholder = self.widget
        self._hBoxLayout.removeWidget(placeholder)
        placeholder.hide()
        placeholder.deleteLater()

        self.widget = QFrame()
        self.widget.setObjectName('pluginDetailCard')
        self._hBoxLayout.addWidget(self.widget, 1, Qt.AlignmentFlag.AlignCenter)
        self.widget.setFixedSize(DIALOG_WIDTH, DIALOG_HEIGHT)
        background = '#202020' if isDarkTheme() else '#f7f7f7'
        self.widget.setStyleSheet(
            f'QFrame#pluginDetailCard {{'
            f'  background-color: {background};'
            f'  border-radius: 8px;'
            f'}}'
        )
        self.setShadowEffect(60, (0, 10), QColor(0, 0, 0, 60))
        self.setMaskColor(QColor(0, 0, 0, 150))

        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_action_row(), 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._build_body(), 1)

    # ------------------------------------------------------------------
    # 结构
    # ------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QWidget(self.widget)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        icon = BodyLabel(header)
        icon.setText(self._data.initial)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(52, 52)
        font = icon.font()
        font.setPointSize(20)
        font.setBold(True)
        icon.setFont(font)
        setCustomStyleSheet(
            icon,
            'BodyLabel {'
            '  background-color: rgba(0, 120, 212, 0.14);'
            '  border-radius: 10px;'
            '  color: #0078d4;'
            '}',
            'BodyLabel {'
            '  background-color: rgba(76, 194, 255, 0.18);'
            '  border-radius: 10px;'
            '  color: #4cc2ff;'
            '}',
        )
        layout.addWidget(icon)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)

        title = StrongBodyLabel(header)
        title.setText(self._data.title)
        font = title.font()
        font.setPointSize(16)
        title.setFont(font)
        text_box.addWidget(title)

        meta_parts = [part for part in (self._data.meta_text, self._data.status_text) if part]
        if meta_parts:
            meta = CaptionLabel(header)
            meta.setText(' · '.join(meta_parts))
            meta.setTextColor('#606060', '#c8c8c8')
            text_box.addWidget(meta)

        if self._data.tags:
            tags = CaptionLabel(header)
            tags.setText(' · '.join(self._data.tags))
            tags.setTextColor('#8a8a8a', '#9a9a9a')
            text_box.addWidget(tags)

        if self._data.warning_text:
            warning = CaptionLabel(header)
            warning.setText(self._data.warning_text)
            warning.setTextColor('#8a6d00', '#e0b000')
            text_box.addWidget(warning)

        layout.addLayout(text_box, 1)

        home_url = QUrl(self._data.homepage)
        if home_url.scheme().lower() in ('http', 'https'):
            home_btn = PushButton(FluentIcon.GITHUB, gt('主页'), header)
            home_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(home_url)
            )
            layout.addWidget(home_btn, 0, Qt.AlignmentFlag.AlignTop)

        close_btn = TransparentToolButton(FluentIcon.CLOSE, header)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        return header

    def _build_action_row(self) -> QWidget:
        row = QWidget(self.widget)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for index, (action, text) in enumerate(self._data.actions):
            btn = PrimaryPushButton(text, row) if index == 0 else PushButton(text, row)
            btn.setEnabled(self._data.action_enabled)
            btn.clicked.connect(lambda _checked=False, a=action: self._trigger(a))
            layout.addWidget(btn)

        return row

    def _build_body(self) -> QWidget:
        scroll = FastScrollArea(orient=Qt.Orientation.Vertical, parent=self.widget)
        scroll.viewport().setAutoFillBackground(False)

        content = QWidget(scroll)
        content.setStyleSheet('background-color: transparent;')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        if self._data.summary:
            summary = BodyLabel(content)
            summary.setText(self._data.summary)
            summary.setWordWrap(True)
            layout.addWidget(summary)

        if self._data.readme_html:
            layout.addWidget(self._build_section(gt('插件说明'), self._data.readme_html))
        else:
            layout.addWidget(self._build_placeholder(gt('该插件暂无可展示的说明')))

        if self._data.changelog_html:
            title = gt('更新日志')
            if self._data.changelog_version:
                title = f'{title} · v{self._data.changelog_version}'
            layout.addWidget(self._build_section(title, self._data.changelog_html))

        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _build_section(self, title: str, html: str) -> QWidget:
        card = QWidget(self.widget)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        section_title = StrongBodyLabel(card)
        section_title.setText(title)
        layout.addWidget(section_title)
        view = HtmlView(card)
        view.set_html(html)
        layout.addWidget(view)
        return card

    def _build_placeholder(self, text: str) -> QWidget:
        label = CaptionLabel(self.widget)
        label.setText(text)
        label.setTextColor('#8a8a8a', '#9a9a9a')
        return label

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------

    def _trigger(self, action: str) -> None:
        """先关闭弹窗再发出动作，具体处理交给页面。

        信号是同步连接的，先关再发才能保证处理函数（可能弹确认框、重建卡片）
        运行时详情弹窗已经不在前台。
        """
        self.close()
        self.action_triggered.emit(action)
