from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QTextEdit


class OverlayTextWidget(QTextEdit):
    """Read-only text area used by overlay panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(0.0)
        self._font_size = 12
        self._text_color = "#eaeaea"
        self._refresh_style()

    def set_appearance(self, font_size: int) -> None:
        self._font_size = max(10, min(28, int(font_size)))
        self._refresh_style()

    def set_text_color(self, color: str) -> None:
        self._text_color = str(color or "").strip() or "#eaeaea"
        self._refresh_style()

    def visible_line_count(self) -> int:
        """Estimate how many single-height lines fit in the visible viewport."""
        fm = QFontMetrics(self.currentFont())
        line_h = fm.lineSpacing()
        if line_h <= 0:
            line_h = self._font_size + 4
        vp_h = self.viewport().height()
        return max(1, vp_h // line_h)

    def setHtml(self, text: str) -> None:
        super().setHtml(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def _refresh_style(self) -> None:
        self.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                color: {self._text_color};
                font-family: Consolas, 'Courier New', monospace;
                font-size: {self._font_size}px;
                padding: 1px;
            }}
            QTextEdit::viewport {{
                background-color: transparent;
            }}
            """
        )
