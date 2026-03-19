from PySide6.QtCore import Signal
from qfluentwidgets import CaptionLabel, FluentIcon, LineEdit, ToolButton

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.draggable_list import DraggableListItem
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiLineSettingCard,
)
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.notorious_hunt.notorious_hunt_config import (
    NotoriousHuntBuffEnum,
    NotoriousHuntLevelEnum,
)
from zzz_od.context.zzz_context import ZContext


class NotoriousHuntCard(DraggableListItem):

    changed = Signal(int, ChargePlanItem)
    move_top = Signal(int)

    def __init__(self, ctx: ZContext,
                 idx: int, plan: ChargePlanItem):
        self.ctx: ZContext = ctx
        self.idx: int = idx
        self.plan: ChargePlanItem = plan

        self.mission_type_combo_box = ComboBox()
        self.mission_type_combo_box.setDisabled(True)
        self.mission_type_combo_box.currentIndexChanged.connect(self._on_mission_type_changed)

        self.level_combo_box = ComboBox()
        self.level_combo_box.currentIndexChanged.connect(self._on_level_changed)

        self.predefined_team_opt = ComboBox()
        self.predefined_team_opt.currentIndexChanged.connect(self.on_predefined_team_changed)

        self.auto_battle_combo_box = ComboBox()
        self.auto_battle_combo_box.currentIndexChanged.connect(self._on_auto_battle_changed)

        self.buff_opt = ComboBox()
        self.buff_opt.currentIndexChanged.connect(self.on_buff_changed)

        run_times_label = CaptionLabel(text=gt('已运行次数'))
        self.run_times_input = LineEdit()
        self.run_times_input.textChanged.connect(self._on_run_times_changed)

        plan_times_label = CaptionLabel(text=gt('计划次数'))
        self.plan_times_input = LineEdit()
        self.plan_times_input.textChanged.connect(self._on_plan_times_changed)

        self.move_top_btn = ToolButton(FluentIcon.PIN, None)
        self.move_top_btn.clicked.connect(self._on_move_top_clicked)

        content_widget = MultiLineSettingCard(
            icon=FluentIcon.CALENDAR,
            title='',
            line_list=[
                [
                    self.mission_type_combo_box,
                    self.level_combo_box,
                    self.predefined_team_opt,
                    self.auto_battle_combo_box,
                    self.buff_opt,
                ],
                [
                    run_times_label,
                    self.run_times_input,
                    plan_times_label,
                    self.plan_times_input,
                    self.move_top_btn,
                ]
            ]
        )

        DraggableListItem.__init__(
            self,
            data=plan,
            index=idx,
            content_widget=content_widget
        )

        self.init_with_plan(plan)

    def after_update_item(self) -> None:
        self.idx = self.index
        self.init_with_plan(self.data)

    def _on_move_top_clicked(self) -> None:
        self.move_top.emit(self.idx)

    def init_with_plan(self, plan: ChargePlanItem) -> None:
        """
        以一个体力计划进行初始化
        """
        self.plan = plan

        self.init_mission_type_combo_box()
        self.init_predefined_team_opt()
        self.init_auto_battle_box()
        self.init_level_combo_box()
        self.init_buff_combo_box()

        self.init_plan_times_input()
        self.init_run_times_input()

    def init_mission_type_combo_box(self) -> None:
        config_list = self.ctx.compendium_service.get_notorious_hunt_plan_mission_type_list(self.plan.category_name)
        self.mission_type_combo_box.set_items(config_list, self.plan.mission_type_name)

    def init_level_combo_box(self) -> None:
        config_list = [i.value for i in NotoriousHuntLevelEnum]
        self.level_combo_box.set_items(config_list, self.plan.level)

    def init_buff_combo_box(self) -> None:
        config_list = [i.value for i in NotoriousHuntBuffEnum]
        self.buff_opt.set_items(config_list, self.plan.notorious_hunt_buff_num)

    def init_auto_battle_box(self) -> None:
        config_list = get_auto_battle_op_config_list(sub_dir='auto_battle')
        self.auto_battle_combo_box.set_items(config_list, self.plan.auto_battle_config)
        self.auto_battle_combo_box.setVisible(self.plan.predefined_team_idx == -1)

    def init_predefined_team_opt(self) -> None:
        """
        初始化预备编队的下拉框
        """
        config_list = ([ConfigItem('游戏内配队', -1)] +
                       [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.predefined_team_opt.set_items(config_list, self.plan.predefined_team_idx)

    def init_run_times_input(self) -> None:
        self.run_times_input.blockSignals(True)
        self.run_times_input.setText(str(self.plan.run_times))
        self.run_times_input.blockSignals(False)

    def init_plan_times_input(self) -> None:
        self.plan_times_input.blockSignals(True)
        self.plan_times_input.setText(str(self.plan.plan_times))
        self.plan_times_input.blockSignals(False)

    def _on_mission_type_changed(self, idx: int) -> None:
        mission_type_name = self.mission_type_combo_box.itemData(idx)
        self.plan.mission_type_name = mission_type_name

        self._emit_value()

    def _on_level_changed(self, idx: int) -> None:
        level = self.level_combo_box.itemData(idx)
        self.plan.level = level

        self._emit_value()

    def on_buff_changed(self, idx: int) -> None:
        self.plan.notorious_hunt_buff_num = self.buff_opt.currentData()
        self._emit_value()

    def on_predefined_team_changed(self, idx: int) -> None:
        self.plan.predefined_team_idx = self.predefined_team_opt.currentData()
        self.init_auto_battle_box()
        self._emit_value()

    def _on_auto_battle_changed(self, idx: int) -> None:
        auto_battle = self.auto_battle_combo_box.itemData(idx)
        self.plan.auto_battle_config = auto_battle

        self._emit_value()

    def _on_run_times_changed(self) -> None:
        self.plan.run_times = int(self.run_times_input.text())
        self._emit_value()

    def _on_plan_times_changed(self) -> None:
        self.plan.plan_times = int(self.plan_times_input.text())
        self._emit_value()

    def _emit_value(self) -> None:
        self.changed.emit(self.idx, self.plan)
