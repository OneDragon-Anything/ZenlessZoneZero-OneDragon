from __future__ import annotations

from PySide6.QtWidgets import QTextEdit


class OverlayTextWidget(QTextEdit):
    """Read-only text area used by overlay panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setStyleSheet(
            """
            QTextEdit {
                background-color: rgba(0, 0, 0, 150);
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 6px;
                color: #eaeaea;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
                padding: 4px;
            }
            """
        )

