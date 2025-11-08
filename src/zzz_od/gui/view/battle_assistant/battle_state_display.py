from __future__ import annotations

import time
from typing import List, Dict, TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTableWidgetItem, QWidget, QVBoxLayout
from qfluentwidgets import TableWidget, isDarkTheme, LineEdit

from one_dragon.base.conditional_operation.state_recorder import StateRecord, StateRecorder
from one_dragon.utils.i18_utils import gt

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


# 自定义颜色定义
class StateIndicatorColors:
    """状态指示器颜色定义 - 支持亮暗主题"""
    @staticmethod
    def get_theme_colors(is_dark_theme: bool = False):
        if is_dark_theme:
            # 暗色主题下的颜色 - 使用较亮但低饱和度的绿色
            return {
                "deepest": QColor(76, 175, 80),     # 较深但可见
                "deep": QColor(102, 187, 106),      # 稍亮
                "medium": QColor(129, 199, 132),    # 中等亮度
                "light": QColor(165, 214, 167),     # 较亮
                "lightest": QColor(200, 230, 201)   # 最亮
            }
        else:
            # 亮色主题下的颜色 - 使用柔和的绿色
            return {
                "deepest": QColor(56, 142, 60),     # 较深橄榄绿
                "deep": QColor(76, 175, 80),        # 柔和森林绿
                "medium": QColor(129, 199, 132),    # 淡青绿
                "light": QColor(165, 214, 167),     # 薄荷绿
                "lightest": QColor(200, 230, 201)   # 最浅薄荷绿
            }


class BattleStateDisplay(QWidget):

    def __init__(self, ctx: ZContext, parent=None):
        super().__init__(parent=parent)

        self.ctx: ZContext = ctx
        self.last_states: List[StateRecord] = []
        self.state_trigger_history: Dict[str, List[float]] = {}
        self._filter_text = ""  # 新增：用于存储过滤文本

        # 1. 创建控件
        self.filter_input = LineEdit(self)
        self.filter_input.setPlaceholderText(gt("输入状态关键词过滤..."))  # 提示文字
        self.table = TableWidget(self)  # 创建表格实例

        # 2. 设置布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 边距设置为0
        layout.addWidget(self.filter_input)
        layout.addWidget(self.table)
        self.setLayout(layout)

        # 3. 将原有的表格设置转移到 self.table 上
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(True)
        self.table.setColumnCount(3)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 60)
        self.table.verticalHeader().hide()
        self.table.setHorizontalHeaderLabels([
            gt("状态"),
            gt("触发秒数"),
            gt("状态值"),
        ])

        # 4. 初始化定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)

    def get_state_trigger_color(self, state_name: str, trigger_time: float) -> QColor:
        """按“最近5次触发”的相对次序取色：最新=最深；避免同一帧重复累计。"""
        history = self.state_trigger_history.setdefault(state_name, [])
        # 仅在出现“新的触发时间”时记录（同一帧内两处调用不会重复追加）
        if not history or history[-1] != trigger_time:
            history.append(trigger_time)
            if len(history) > 5:
                history.pop(0)
        # 颜色表（按主题）
        theme_colors = StateIndicatorColors.get_theme_colors(isDarkTheme())
        # 计算从“最新”开始的排名（0=最新，4=最旧）；容错：未找到时按最旧处理
        try:
            rank_newest_first = history[::-1].index(trigger_time)
        except ValueError:
            rank_newest_first = 4
        if rank_newest_first == 0:
            return theme_colors["deepest"]
        elif rank_newest_first == 1:
            return theme_colors["deep"]
        elif rank_newest_first == 2:
            return theme_colors["medium"]
        elif rank_newest_first == 3:
            return theme_colors["light"]
        else:
            return theme_colors["lightest"]

    def set_update_display(self, to_update: bool) -> None:
        if to_update:
            self.update_timer.stop()
            self.update_timer.start(100)
        else:
            self.update_timer.stop()

    def _update_display(self) -> None:
        auto_op = self.ctx.auto_battle_context.auto_op
        if auto_op is None or not auto_op.is_running:
            self.table.setRowCount(0)
            return

        states = auto_op.usage_states
        state_recorders: list[StateRecorder] = []
        for state in states:
            recorder = self.ctx.auto_battle_context.state_record_service.get_state_recorder(state)
            if recorder is None:
                continue
            state_recorders.append(recorder)

        now = time.time()
        new_states = []
        for recorder in state_recorders:
            if recorder.last_record_time == -1:
                continue
            if (
                    recorder.last_record_time == 0
                    and
                    recorder.state_name.startswith(("前台-", "后台-"))
            ):
                continue
            new_states.append(StateRecord(recorder.state_name, recorder.last_record_time, recorder.last_value))

        # 核心修改：排序逻辑
        filter_text = self.filter_input.text().strip()
        if filter_text:
            keywords = filter_text.split()
            def sort_key(record: StateRecord):
                # 检查状态名是否包含任意一个关键词
                matches = any(keyword in record.state_name for keyword in keywords)
                # 匹配的排在前面 (返回 False 即 0), 不匹配的排在后面 (返回 True 即 1)
                # 之后再按字母顺序排序
                return (not matches, record.state_name)
            new_states.sort(key=sort_key)
        else:
            # 无过滤时，按默认名称排序
            new_states.sort(key=lambda x: x.state_name)

        total = len(new_states)
        self.table.setRowCount(total)
        theme_colors = StateIndicatorColors.get_theme_colors(isDarkTheme())
        for i in range(total):
            state_item = QTableWidgetItem(new_states[i].state_name)
            if i >= len(self.last_states) or new_states[i].state_name != self.last_states[i].state_name:
                # 状态名称变化使用浅绿
                state_item.setBackground(QBrush(theme_colors["light"]))

            time_diff = now - new_states[i].trigger_time
            if time_diff > 999:
                time_diff = 999
            time_item = QTableWidgetItem("%.4f" % time_diff)

            # 检查是否需要设置颜色
            trigger_color = None
            if i >= len(self.last_states) or new_states[i].trigger_time != self.last_states[i].trigger_time:
                # 根据触发次序设置颜色
                trigger_color = self.get_state_trigger_color(new_states[i].state_name, new_states[i].trigger_time)
                time_item.setBackground(QBrush(trigger_color))

            value_item = QTableWidgetItem(str(new_states[i].value) if new_states[i].value is not None else "")
            if i >= len(self.last_states) or new_states[i].value != self.last_states[i].value:
                # 根据触发次序设置颜色（与时间列同色）
                if trigger_color is None:
                    trigger_color = self.get_state_trigger_color(new_states[i].state_name, new_states[i].trigger_time)
                value_item.setBackground(QBrush(trigger_color))

            self.table.setItem(i, 0, state_item)
            self.table.setItem(i, 1, time_item)
            self.table.setItem(i, 2, value_item)

        self.last_states = new_states


class TaskDisplay(TableWidget):

    def __init__(self, ctx: ZContext, parent=None):
        TableWidget.__init__(self, parent=parent)

        self.ctx: ZContext = ctx

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
        auto_op = self.ctx.auto_battle_context.auto_op
        if auto_op is None or not auto_op.is_running:
            data = [
                ["[触发器]", "/"],
                ["[条件集]", "/"],
                ["[持续时间]", "/"]
            ]

            for i, row in enumerate(data):
                for col in range(2):
                    self.setItem(i, col, QTableWidgetItem(row[col]))

            return

        info = auto_op.current_execution_info
        executor = auto_op.running_executor
        now = time.time()

        if info is None or executor is None:
            return

        # 计算持续时间
        trigger_time = executor.trigger_time
        past_time = str(round(now - trigger_time, 4))
        states = info.expr_display

        data = [
            ["[触发器]", info.trigger_display],
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
