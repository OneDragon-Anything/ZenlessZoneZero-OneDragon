from __future__ import annotations

from PySide6.QtCore import Qt
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
        self._refresh_style()

    def set_appearance(self, font_size: int) -> None:
        self._font_size = max(10, min(28, int(font_size)))
        self._refresh_style()

    def _refresh_style(self) -> None:
        self.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                color: #eaeaea;
                font-family: Consolas, 'Courier New', monospace;
                font-size: {self._font_size}px;
                padding: 1px;
            }}
            QTextEdit::viewport {{
                background-color: transparent;
            }}
            """
        )

