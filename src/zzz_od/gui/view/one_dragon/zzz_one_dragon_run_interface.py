from PySide6.QtWidgets import QWidget
from qfluentwidgets import BodyLabel, SettingCardGroup

from one_dragon_qt.view.one_dragon.one_dragon_run_interface import OneDragonRunInterface
from one_dragon_qt.widgets.column import Column
from zzz_od.context.zzz_context import ZContext


class ZOneDragonRunInterface(OneDragonRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        OneDragonRunInterface.__init__(
            self,
            ctx=ctx,
            parent=parent,
            help_url='https://one-dragon.com/zzz/zh/feat_one_dragon/quickstart.html',
        )
        self._dodge_count_label: BodyLabel | None = None

    def get_widget_at_top(self) -> QWidget:
        top: Column = OneDragonRunInterface.get_widget_at_top(self)

        # 格挡统计卡片
        stats_group = SettingCardGroup('战斗统计')
        self._dodge_count_label = BodyLabel()
        self._dodge_count_label.setStyleSheet('font-size: 14px; padding: 8px 16px;')
        self._update_dodge_count_text()
        stats_group.addSettingCard(self._dodge_count_label)

        top.add_widget(stats_group)
        return top

    def _update_dodge_count_text(self) -> None:
        if self._dodge_count_label is None:
            return
        count = self.ctx.user_stats.dodge_count
        self._dodge_count_label.setText(f'  一条龙已经为你格挡 {count} 次！  ')

    def on_interface_shown(self) -> None:
        OneDragonRunInterface.on_interface_shown(self)
        self._update_dodge_count_text()
