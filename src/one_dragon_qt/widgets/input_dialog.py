from qfluentwidgets import MessageBoxBase, SubtitleLabel, LineEdit

class InputDialog(MessageBoxBase):
    """ Input dialog """

    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self)
        self.lineEdit = LineEdit(self)
        self.lineEdit.setPlaceholderText(content)
        self.lineEdit.setClearButtonEnabled(True)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.lineEdit)

        self.widget.setMinimumWidth(350)
