from qfluentwidgets import FluentIcon, HyperlinkCard

from one_dragon.utils.i18_utils import (
    gt,
    subscribe_language_changed,
    unsubscribe_language_changed,
)


class HelpCard(HyperlinkCard):
    def __init__(self,
                 url: str = '',
                 text: str = '点此查看指南',
                 title: str = '使用说明',
                 content: str = '先看说明 再使用与提问',
                 parent=None):
        self._text_msgid = text
        self._title_msgid = title
        self._content_msgid = content
        super().__init__(url, gt(text), FluentIcon.HELP, gt(title), gt(content), parent)
        self.setFixedHeight(50)
        if not url:
            self.linkButton.setVisible(False)
        self._language_callback = self.retranslate_ui
        subscribe_language_changed(self._language_callback)
        self.destroyed.connect(self._on_destroyed)

    def _on_destroyed(self, _object=None) -> None:
        """Unsubscribe the card after Qt destroys it."""
        unsubscribe_language_changed(self._language_callback)

    def retranslate_ui(self, _language: str | None = None) -> None:
        """Refresh the help card after the application language changes."""
        self.linkButton.setText(gt(self._text_msgid))
        self.titleLabel.setText(gt(self._title_msgid))
        self.contentLabel.setText(gt(self._content_msgid))
