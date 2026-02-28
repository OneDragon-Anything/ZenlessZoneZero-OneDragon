from __future__ import annotations

from PySide6.QtWidgets import QTextEdit


class OverlayTextWidget(QTextEdit):
    """Read-only text area used by overlay panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self._font_size = 12
        self._text_opacity = 100
        self._refresh_style()

    def set_appearance(self, font_size: int, text_opacity: int) -> None:
        self._font_size = max(10, min(28, int(font_size)))
        self._text_opacity = max(20, min(100, int(text_opacity)))
        self._refresh_style()

    def _refresh_style(self) -> None:
        text_alpha = int(255 * self._text_opacity / 100.0)
        self.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: rgba(0, 0, 0, 150);
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 6px;
                color: rgba(234, 234, 234, {text_alpha});
                font-family: Consolas, 'Courier New', monospace;
                font-size: {self._font_size}px;
                padding: 4px;
            }}
            """
        )

