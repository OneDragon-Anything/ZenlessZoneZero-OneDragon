from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, CaptionLabel, LineEdit
from typing import List

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiLineSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntLevelEnum, NotoriousHuntBuffEnum
from zzz_od.context.zzz_context import ZContext


class ChargePlanCard(MultiLineSettingCard):

    changed = Signal(int, ChargePlanItem)

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

        MultiLineSettingCard.__init__(
            self,
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
                ]
            ]
        )

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


class NotoriousHuntPlanInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_notorious_hunt_plan_interface',
            content_widget=None, parent=parent,
            nav_text_cn='恶名狩猎计划'
        )

    def get_content_widget(self) -> QWidget:
        self.content_widget = Column()

        self.card_list: List[ChargePlanCard] = []
        self.last_empty_widget: QWidget = QWidget()

        return self.content_widget

    def update_plan_list_display(self):
        plan_list = self.ctx.notorious_hunt_config.plan_list

        if len(plan_list) > len(self.card_list):
            self.content_widget.remove_widget(self.last_empty_widget)

            while len(self.card_list) < len(plan_list):
                idx = len(self.card_list)
                card = ChargePlanCard(self.ctx, idx, self.ctx.notorious_hunt_config.plan_list[idx])
                card.changed.connect(self._on_plan_item_changed)

                self.card_list.append(card)
                self.content_widget.add_widget(card)

            self.content_widget.add_widget(self.last_empty_widget, stretch=1)

        for idx, plan in enumerate(plan_list):
            card = self.card_list[idx]
            card.init_with_plan(plan)

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.update_plan_list_display()

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)

    def _on_plan_item_changed(self, idx: int, plan: ChargePlanItem) -> None:
        self.ctx.notorious_hunt_config.update_plan(idx, plan)
