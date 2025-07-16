from PySide6.QtWidgets import QWidget, QTableWidgetItem
from qfluentwidgets import TableWidget, CheckBox, FluentIcon

from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import DmgTypeEnum

from one_dragon_qt.widgets.column import Column

class ShiyuDefenseInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_shiyu_defense_interface',
            content_widget=None, parent=parent,
            nav_text_cn='式舆防卫战'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.critical_reset_opt = PushSettingCard(icon=FluentIcon.SYNC, title='剧变节点 重置运行记录',
                                                  text=gt('重置'))
        self.critical_reset_opt.clicked.connect(self.on_critical_reset_clicked)
        content_widget.add_widget(self.critical_reset_opt)

        self.team_table = TableWidget()

        self.team_table.setBorderVisible(True)
        self.team_table.setBorderRadius(8)
        self.team_table.setWordWrap(True)
        self.team_table.verticalHeader().hide()
        self.team_table.setMinimumHeight(500)

        labels = ['预备配队', '剧变节点'] + [i.value for i in DmgTypeEnum if i != DmgTypeEnum.UNKNOWN]

        self.team_table.setColumnCount(len(labels))
        for i in range(len(labels)):
            self.team_table.setColumnWidth(i, (200 if i == 0 else 70))
        self.team_table.setHorizontalHeaderLabels([gt(i) for i in labels])

        content_widget.add_widget(self.team_table, stretch=1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        team_list = self.ctx.team_config.team_list
        new_len = len(team_list)

        while self.team_table.rowCount() > new_len:
            self.team_table.removeRow(self.team_table.rowCount() - 1)

        old_len = self.team_table.rowCount()
        if new_len > self.team_table.rowCount():
            self.team_table.setRowCount(new_len)

            for idx in range(old_len, new_len):
                btn = CheckBox()
                btn.checkStateChanged.connect(self.on_critical_changed)
                self.team_table.setCellWidget(idx, 1, btn)

                for i, dmg_type in enumerate(DmgTypeEnum):
                    btn = CheckBox()
                    btn.checkStateChanged.connect(self.on_weakness_check_changed)
                    self.team_table.setCellWidget(idx, i + 2, btn)

        for row, team in enumerate(team_list):
            team_config = self.ctx.shiyu_defense_config.get_config_by_team_idx(team.idx)

            self.team_table.setItem(row, 0, QTableWidgetItem(team.name))

            btn: CheckBox = self.team_table.cellWidget(row, 1)
            btn.setProperty('team_idx', team.idx)

            btn.blockSignals(True)
            btn.setChecked(team_config.for_critical)
            btn.blockSignals(False)

            for col, dmg_type in enumerate(DmgTypeEnum):
                if dmg_type == DmgTypeEnum.UNKNOWN:
                    continue

                btn: CheckBox = self.team_table.cellWidget(row, col + 2)
                btn.setProperty('team_idx', team.idx)
                btn.setProperty('type', dmg_type.name)

                btn.blockSignals(True)
                btn.setChecked(dmg_type in team_config.weakness_list)
                btn.blockSignals(False)

    def on_weakness_check_changed(self) -> None:
        """
        属性勾选变更
        """
        btn: CheckBox = self.sender()
        team_idx = btn.property('team_idx')
        dmg_type = DmgTypeEnum.from_name(btn.property('type'))

        if btn.isChecked():
            self.ctx.shiyu_defense_config.add_weakness(team_idx, dmg_type)
        else:
            self.ctx.shiyu_defense_config.remove_weakness(team_idx, dmg_type)

    def on_critical_changed(self) -> None:
        """
        是否参与剧变节点变更
        @return:
        """
        btn: CheckBox = self.sender()
        team_idx = btn.property('team_idx')
        self.ctx.shiyu_defense_config.change_for_critical(team_idx, btn.isChecked())

    def on_critical_reset_clicked(self) -> None:
        self.ctx.shiyu_defense_record.reset_record()