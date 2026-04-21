from PySide6.QtWidgets import QGridLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    MessageBoxBase,
    SubtitleLabel,
    SwitchButton,
)

from one_dragon.base.config.notify_config import NotifyLevel
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt


class NotifyDialog(MessageBoxBase):
    """通知配置对话框"""

    def __init__(self, ctx: OneDragonContext, parent=None):
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

        # 存储所有应用的 ComboBox
        self.app_combos: dict[str, ComboBox] = {}

        # 网格布局: [label0][combo0][spacer][label1][combo1]
        #  列号:      0       1       2       3       4
        combo_container = QWidget()
        grid_layout = QGridLayout(combo_container)
        grid_layout.setContentsMargins(0, 10, 0, 10)
        grid_layout.setSpacing(10)
        # label 列紧贴文字，combo 列均匀填充，spacer 列固定间距
        grid_layout.setColumnStretch(0, 0)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setColumnMinimumWidth(2, 20)
        grid_layout.setColumnStretch(2, 0)
        grid_layout.setColumnStretch(3, 0)
        grid_layout.setColumnStretch(4, 1)

        column_group_count = 2
        for i, (app_id, app_name) in enumerate(self.ctx.notify_config.app_map.items()):
            row = i // column_group_count
            group = i % column_group_count
            col = group * 3  # 第一组: 0,1  第二组: 3,4

            label = BodyLabel(gt(app_name), self)
            combo = ComboBox(self)
            combo.addItem(gt('关闭'), userData=NotifyLevel.OFF)
            combo.addItem(gt('仅应用'), userData=NotifyLevel.APP)
            combo.addItem(gt('全部（逐条）'), userData=NotifyLevel.ALL)
            combo.addItem(gt('全部（合并）'), userData=NotifyLevel.MERGE)

            level = self.ctx.notify_config.get_app_notify_level(app_id)
            # 根据 userData 匹配当前等级
            for j in range(combo.count()):
                if combo.itemData(j) == level:
                    combo.setCurrentIndex(j)
                    break

            self.app_combos[app_id] = combo
            grid_layout.addWidget(label, row, col)
            grid_layout.addWidget(combo, row, col + 1)

        self.viewLayout.addWidget(combo_container)

        hint = CaptionLabel(gt('逐条 = 每个节点单独推送；合并 = 所有节点合并推送'), self)
        hint.setWordWrap(True)
        self.viewLayout.addWidget(hint)

    def accept(self):
        """点击确定时，更新配置"""
        self.ctx.notify_config.enable_before_notify = self.before_notify_switch.isChecked()
        for app_id, combo in self.app_combos.items():
            level = combo.currentData()
            setattr(self.ctx.notify_config, app_id, level)
        super().accept()
