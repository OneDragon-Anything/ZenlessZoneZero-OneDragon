import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QTableWidgetItem
from qfluentwidgets import TableWidget, FluentThemeColor
from typing import Optional, List

from one_dragon.base.conditional_operation.state_recorder import StateRecord, StateRecorder
from one_dragon.utils.i18_utils import gt
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator


class BattleStateDisplay(TableWidget):

    def __init__(self, parent=None):
        TableWidget.__init__(self, parent=parent)

        self.auto_op: Optional[AutoBattleOperator] = None
        self.last_states: List[StateRecord] = []

        self.setBorderVisible(True)
        self.setBorderRadius(8)

        self.setWordWrap(True)
        self.setColumnCount(3)
        self.setColumnWidth(0, 150)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 60)
        self.verticalHeader().hide()
        self.setHorizontalHeaderLabels([
            gt('状态'),
            gt('触发秒数'),
            gt('状态值'),
        ])

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)

    def set_update_display(self, to_update: bool) -> None:
        if to_update:
            self.update_timer.stop()
            self.update_timer.start(100)
        else:
            self.update_timer.stop()

    def _update_display(self) -> None:
        if self.auto_op is None or not self.auto_op.is_running:
            self.setRowCount(0)
            return

        states = self.auto_op.get_usage_states()
        states = sorted(states)

        state_recorders: List[StateRecorder] = sorted([i for i in self.auto_op.state_recorders.values()
                                                       if i.state_name in states],
                                                      key=lambda x: x.state_name)

        now = time.time()
        new_states = []
        for recorder in state_recorders:
            if recorder.last_record_time == -1:
                continue
            if (
                    recorder.last_record_time == 0
                    and
                    (
                            recorder.state_name.startswith('前台-')
                            or recorder.state_name.startswith('后台-')
                    )
            ):
                continue
            new_states.append(StateRecord(recorder.state_name, recorder.last_record_time, recorder.last_value))

        total = len(new_states)
        self.setRowCount(total)
        for i in range(total):
            state_item = QTableWidgetItem(new_states[i].state_name)
            if i >= len(self.last_states) or new_states[i].state_name != self.last_states[i].state_name:
                state_item.setBackground(QBrush(FluentThemeColor.RED.value))

            time_diff = now - new_states[i].trigger_time
            if time_diff > 999:
                time_diff = 999
            time_item = QTableWidgetItem('%.4f' % time_diff)
            if i >= len(self.last_states) or new_states[i].trigger_time != self.last_states[i].trigger_time:
                time_item.setBackground(QBrush(FluentThemeColor.RED.value))

            value_item = QTableWidgetItem(str(new_states[i].value) if new_states[i].value is not None else '')
            if i >= len(self.last_states) or new_states[i].value != self.last_states[i].value:
                value_item.setBackground(QBrush(FluentThemeColor.RED.value))

            self.setItem(i, 0, state_item)
            self.setItem(i, 1, time_item)
            self.setItem(i, 2, value_item)

        self.last_states = new_states


class TaskDisplay(TableWidget):

    def __init__(self, parent=None):
        TableWidget.__init__(self, parent=parent)

        self.auto_op: Optional[AutoBattleOperator] = None

        self.setBorderVisible(True)
        self.setBorderRadius(8)

        self.setWordWrap(True)

        self.setRowCount(3)
        self.setColumnCount(2)

        self.setColumnWidth(0, 100)
        self.setColumnWidth(1, 220)

        self.horizontalHeader().hide()
        self.verticalHeader().hide()

        # 隐藏垂直和水平滚动条
        self.verticalScrollBar().setVisible(False)
        self.horizontalScrollBar().setVisible(False)

        data = [
            ["[触发器]", "/"],
            ["[条件集]", "/"],
            ["[持续时间]", "/"]
        ]

        for i, row in enumerate(data):
            for col in range(2):
                self.setItem(i, col, QTableWidgetItem(row[col]))

        # 设置表格高度为行高总和
        self.adjustTableHeight()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)

    def set_update_display(self, to_update: bool) -> None:
        if to_update:
            self.update_timer.start(100)
        else:
            self.update_timer.stop()

    def _update_display(self) -> None:
        if self.auto_op is None or not self.auto_op.is_running:
            data = [
                ["[触发器]", "/"],
                ["[条件集]", "/"],
                ["[持续时间]", "/"]
            ]

            for i, row in enumerate(data):
                for col in range(2):
                    self.setItem(i, col, QTableWidgetItem(row[col]))

            return

        task = self.auto_op.running_task
        now = time.time()

        if task is None:
            return

        # 计算持续时间
        past_time = str(round(now - self.auto_op.last_trigger_time.get(task.trigger_display, 0), 4))
        states = task.expr_display

        data = [
            ["[触发器]", task.trigger_display],
            ["[条件集]", states],
            ["[持续时间]", past_time]
        ]

        for i, row in enumerate(data):
            for col in range(2):
                self.setItem(i, col, QTableWidgetItem(row[col]))

    def adjustTableHeight(self):
        total_height = 0
        for i in range(self.rowCount()):
            total_height += self.rowHeight(i)
        self.setFixedHeight(total_height+4)
