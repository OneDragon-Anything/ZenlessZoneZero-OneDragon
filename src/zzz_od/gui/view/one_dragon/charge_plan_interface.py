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
from zzz_od.application.charge_plan.charge_plan_config import (
    CardNumEnum,
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.application.notorious_hunt.notorious_hunt_config import (
    NotoriousHuntBuffEnum,
)
from zzz_od.context.zzz_context import ZContext


class ChargePlanCard(DraggableListItem):

    changed = Signal(int, ChargePlanItem)
    delete = Signal(int)
    move_top = Signal(int)

    def __init__(self, ctx: ZContext,
                 idx: int, plan: ChargePlanItem,
                 config: ChargePlanConfig):
        self.ctx: ZContext = ctx
        self.idx: int = idx
        self.plan: ChargePlanItem = plan
        self.config: ChargePlanConfig = config

        # 创建所有控件
        self.category_combo_box = ComboBox()
        self.category_combo_box.currentIndexChanged.connect(self._on_category_changed)

        self.mission_type_combo_box = ComboBox()
        self.mission_type_combo_box.currentIndexChanged.connect(self._on_mission_type_changed)

        self.mission_combo_box = ComboBox()
        self.mission_combo_box.currentIndexChanged.connect(self._on_mission_changed)

        self.card_num_box = ComboBox()
        self.card_num_box.currentIndexChanged.connect(self._on_card_num_changed)

        self.notorious_hunt_buff_num_opt = ComboBox()
        self.notorious_hunt_buff_num_opt.currentIndexChanged.connect(self.on_notorious_hunt_buff_num_changed)

        self.predefined_team_opt = ComboBox()
        self.predefined_team_opt.currentIndexChanged.connect(self.on_predefined_team_changed)

        self.auto_battle_combo_box = ComboBox()
        self.auto_battle_combo_box.currentIndexChanged.connect(self._on_auto_battle_changed)

        run_times_label = CaptionLabel(text=gt('已运行次数'))
        self.run_times_input = LineEdit()
        self.run_times_input.textChanged.connect(self._on_run_times_changed)

        plan_times_label = CaptionLabel(text=gt('计划次数'))
        self.plan_times_input = LineEdit()
        self.plan_times_input.textChanged.connect(self._on_plan_times_changed)

        self.move_top_btn = ToolButton(FluentIcon.PIN, None)
        self.move_top_btn.clicked.connect(self._on_move_top_clicked)
        self.del_btn = ToolButton(FluentIcon.DELETE, None)
        self.del_btn.clicked.connect(self._on_del_clicked)

        # 创建 MultiLineSettingCard 作为 content_widget
        content_widget = MultiLineSettingCard(
            icon=FluentIcon.CALENDAR,
            title='',
            line_list=[
                [
                    self.category_combo_box,
                    self.mission_type_combo_box,
                    self.mission_combo_box,
                    self.card_num_box,
                    self.notorious_hunt_buff_num_opt,
                    self.predefined_team_opt,
                    self.auto_battle_combo_box,
                ],
                [
                    run_times_label,
                    self.run_times_input,
                    plan_times_label,
                    self.plan_times_input,
                    self.move_top_btn,
                    self.del_btn,
                ]
            ]
        )

        # 调用 DraggableListItem 的 __init__
        DraggableListItem.__init__(
            self,
            data=plan,
            index=idx,
            content_widget=content_widget
        )

        self.init_with_plan(plan, config)

    def after_update_item(self) -> None:
        self.idx = self.index
        self.init_with_plan(self.data, self.config)

    def init_category_combo_box(self) -> None:
        config_list = self.ctx.compendium_service.get_charge_plan_category_list()
        self.category_combo_box.set_items(config_list, self.plan.category_name)

    def init_mission_type_combo_box(self) -> None:
        config_list = self.ctx.compendium_service.get_charge_plan_mission_type_list(self.plan.category_name)
        self.mission_type_combo_box.set_items(config_list, self.plan.mission_type_name)

    def init_mission_combo_box(self) -> None:
        config_list = self.ctx.compendium_service.get_charge_plan_mission_list(self.plan.category_name, self.plan.mission_type_name)
        self.mission_combo_box.set_items(config_list, self.plan.mission_name)
        self.mission_combo_box.setVisible(self.plan.category_name == '实战模拟室')

    def init_card_num_box(self) -> None:
        config_list = [config_enum.value for config_enum in CardNumEnum]
        self.card_num_box.set_items(config_list, self.plan.card_num)
        self.card_num_box.setVisible(self.plan.category_name == '实战模拟室')

    def init_notorious_hunt_buff_num_opt(self) -> None:
        """
        初始化不透明度下拉框
        """
        config_list = [config_enum.value for config_enum in NotoriousHuntBuffEnum]
        self.notorious_hunt_buff_num_opt.set_items(config_list, self.plan.notorious_hunt_buff_num)
        self.notorious_hunt_buff_num_opt.setVisible(self.plan.category_name == '恶名狩猎')

    def init_predefined_team_opt(self) -> None:
        """
        初始化预备编队的下拉框
        """
        config_list = ([ConfigItem('游戏内配队', -1)] +
                       [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.predefined_team_opt.set_items(config_list, self.plan.predefined_team_idx)

    def init_auto_battle_box(self) -> None:
        config_list = get_auto_battle_op_config_list(sub_dir='auto_battle')
        self.auto_battle_combo_box.set_items(config_list, self.plan.auto_battle_config)
        self.auto_battle_combo_box.setVisible(self.plan.predefined_team_idx == -1)

    def init_run_times_input(self) -> None:
        self.run_times_input.blockSignals(True)
        self.run_times_input.setText(str(self.plan.run_times))
        self.run_times_input.blockSignals(False)

    def init_plan_times_input(self) -> None:
        self.plan_times_input.blockSignals(True)
        self.plan_times_input.setText(str(self.plan.plan_times))
        self.plan_times_input.blockSignals(False)

    def init_with_plan(
        self,
        plan: ChargePlanItem,
        config: ChargePlanConfig,
    ) -> None:
        """
        以一个体力计划进行初始化
        """
        self.plan = plan
        self.config = config

        self.init_category_combo_box()
        self.init_mission_type_combo_box()
        self.init_mission_combo_box()

        self.init_card_num_box()
        self.init_notorious_hunt_buff_num_opt()
        self.init_predefined_team_opt()
        self.init_auto_battle_box()

        self.init_run_times_input()
        self.init_plan_times_input()

    def _on_category_changed(self, idx: int) -> None:
        category_name = self.category_combo_box.itemData(idx)
        self.plan.category_name = category_name
        self.plan.tab_name = '训练'

        self.init_mission_type_combo_box()
        self.init_mission_combo_box()
        self.init_card_num_box()
        self.init_notorious_hunt_buff_num_opt()

        self.update_by_history()

        self._emit_value()

    def _on_mission_type_changed(self, idx: int) -> None:
        mission_type_name = self.mission_type_combo_box.itemData(idx)
        self.plan.mission_type_name = mission_type_name

        self.init_mission_combo_box()

        self.update_by_history()
        self._emit_value()

    def _on_mission_changed(self, idx: int) -> None:
        mission_name = self.mission_combo_box.itemData(idx)
        self.plan.mission_name = mission_name

        self.update_by_history()
        self._emit_value()

    def _on_card_num_changed(self, idx: int) -> None:
        self.plan.card_num = self.card_num_box.itemData(idx)
        self._emit_value()

    def on_notorious_hunt_buff_num_changed(self, idx: int) -> None:
        self.plan.notorious_hunt_buff_num = self.notorious_hunt_buff_num_opt.currentData()
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

    def _on_move_top_clicked(self) -> None:
        self.move_top.emit(self.idx)

    def _on_del_clicked(self) -> None:
        self.delete.emit(self.idx)

    def update_by_history(self) -> None:
        """
        根据历史记录更新
        """
        history = self.config.get_history_by_uid(self.plan)
        if history is None:
            return

        self.plan.card_num = history.card_num
        self.plan.notorious_hunt_buff_num = history.notorious_hunt_buff_num
        self.plan.predefined_team_idx = history.predefined_team_idx
        self.plan.auto_battle_config = history.auto_battle_config
        self.plan.plan_times = history.plan_times

        self.init_card_num_box()
        self.init_notorious_hunt_buff_num_opt()
        self.init_predefined_team_opt()
        self.init_auto_battle_box()
        self.init_plan_times_input()
