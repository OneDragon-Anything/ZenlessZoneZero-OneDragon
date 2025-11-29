from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    MessageBoxBase,
    SubtitleLabel,
    SwitchButton,
)

from one_dragon.base.config.notify_config import NotifyLevel
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt


class NotifyDialog(MessageBoxBase):
    """通知配置对话框"""

    def __init__(self, parent=None, ctx=OneDragonContext):
        super().__init__(parent)
        self.ctx: OneDragonContext = ctx

        self.yesButton.setText(gt('确定'))
        self.cancelButton.setText(gt('取消'))

        self.titleLabel = SubtitleLabel(gt('通知设置'))
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)

        self.before_notify_switch = SwitchButton(self)
        self.before_notify_switch.setChecked(self.ctx.notify_config.enable_before_notify)
        self.before_notify_switch._onText = gt('开始前通知')
        self.before_notify_switch._offText = gt('开始前通知')
        self.before_notify_switch.label.setText(gt('开始前通知'))
        self.viewLayout.addWidget(self.before_notify_switch)

        self.viewLayout.addWidget(BodyLabel(gt('未选 = 关闭；半选 = 应用级通知；全选 = 应用+节点级通知')))

        # 存储所有应用的复选框
        self.app_checkboxes = {}

        # 使用网格布局放置复选框
        checkbox_container = QWidget()
        grid_layout = QGridLayout(checkbox_container)
        grid_layout.setContentsMargins(0, 10, 0, 10)
        grid_layout.setSpacing(10)

        # 每行放置3个复选框
        column_count = 3
        # 使用 enumerate 和 items() 遍历字典获取索引、键和值
        for i, (app_id, app_name) in enumerate(self.ctx.notify_config.app_map.items()):
            row = i // column_count
            col = i % column_count

            # 使用 app_name 作为 CheckBox 的文本
            checkbox = CheckBox(gt(app_name), self)
            checkbox.setTristate(True)

            level = self.ctx.notify_config.get_app_notify_level(app_id)
            if level == NotifyLevel.OFF:
                checkbox.setCheckState(Qt.CheckState.Unchecked)
            elif level == NotifyLevel.APP:
                checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                checkbox.setCheckState(Qt.CheckState.Checked)

            # 保存复选框引用，使用 app_id 作为键
            self.app_checkboxes[app_id] = checkbox

            grid_layout.addWidget(checkbox, row, col)

        self.viewLayout.addWidget(checkbox_container)

    def accept(self):
        """点击确定时，更新配置"""
        self.ctx.notify_config.enable_before_notify = self.before_notify_switch.isChecked()
        for app_id, checkbox in self.app_checkboxes.items():
            state = checkbox.checkState()
            if state == Qt.CheckState.Unchecked:
                level = NotifyLevel.OFF
            elif state == Qt.CheckState.PartiallyChecked:
                level = NotifyLevel.APP
            else:
                level = NotifyLevel.ALL
            setattr(self.ctx.notify_config, app_id, level)
        super().accept()
