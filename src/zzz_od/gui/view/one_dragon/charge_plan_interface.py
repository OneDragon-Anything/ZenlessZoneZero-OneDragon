from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    CaptionLabel,
    Dialog,
    FluentIcon,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application import application_const
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.draggable_list import DraggableList, DraggableListItem
from one_dragon_qt.widgets.horizontal_setting_card_group import (
    HorizontalSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiLineSettingCard,
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    CardNumEnum,
    ChargePlanConfig,
    ChargePlanItem,
    RestoreChargeEnum,
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


class ChargePlanInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_charge_plan_interface',
            content_widget=None, parent=parent,
            nav_text_cn='体力计划'
        )

        self.config: ChargePlanConfig | None = None

    def get_content_widget(self) -> QWidget:
        self.content_widget = Column()

        self.loop_opt = SwitchSettingCard(icon=FluentIcon.SYNC, title='循环执行', content='开启时 会循环执行到体力用尽')
        self.skip_plan_opt = SwitchSettingCard(icon=FluentIcon.FLAG, title='跳过计划', content='开启时 自动跳过体力不足的计划')
        self.content_widget.add_widget(HorizontalSettingCardGroup([self.loop_opt, self.skip_plan_opt], spacing=6))

        # 2.5版本已移除家政券功能，暂时关闭UI
        # self.coupon_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='使用家政券', content='运行区域巡防时使用家政券')
        self.restore_charge_opt = ComboBoxSettingCard(icon=FluentIcon.ADD_TO, title='恢复电量', options_enum=RestoreChargeEnum)
        # self.content_widget.add_widget(HorizontalSettingCardGroup([self.coupon_opt, self.restore_charge_opt], spacing=6))
        self.content_widget.add_widget(self.restore_charge_opt)

        self.cancel_btn = PushButton(icon=FluentIcon.CANCEL, text=gt('撤销'))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)

        self.remove_all_completed_btn = PushButton(
            icon=FluentIcon.DELETE, text='删除已完成'
        )
        self.remove_all_completed_btn.clicked.connect(self._on_remove_all_completed_clicked)

        self.remove_all_btn = PushButton(
            icon=FluentIcon.DELETE, text='删除所有'
        )
        self.remove_all_btn.clicked.connect(self._on_remove_all_clicked)

        self.remove_setting_card = MultiPushSettingCard(btn_list=[
            self.cancel_btn,
            self.remove_all_completed_btn,
            self.remove_all_btn
        ], icon=FluentIcon.DELETE, title='删除体力计划')
        self.content_widget.add_widget(self.remove_setting_card)

        # 创建可拖动的列表容器
        self.drag_list = DraggableList()
        self.drag_list.order_changed.connect(self._on_order_changed)
        self.content_widget.add_widget(self.drag_list)

        self.card_list: list[ChargePlanCard] = []

        self.plus_btn = PrimaryPushButton(text=gt('新增'))
        self.plus_btn.clicked.connect(self._on_add_clicked)
        self.content_widget.add_widget(self.plus_btn, stretch=1)

        return self.content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.config = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.update_plan_list_display()

        self.loop_opt.init_with_adapter(get_prop_adapter(self.config, 'loop'))
        self.skip_plan_opt.init_with_adapter(get_prop_adapter(self.config, 'skip_plan'))
        # self.coupon_opt.init_with_adapter(get_prop_adapter(self.config, 'use_coupon'))
        self.restore_charge_opt.init_with_adapter(get_prop_adapter(self.config, 'restore_charge'))

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)

    def update_plan_list_display(self):
        plan_list = self.config.plan_list

        if len(plan_list) > len(self.card_list):
            # 需要添加新的卡片
            while len(self.card_list) < len(plan_list):
                idx = len(self.card_list)
                card = ChargePlanCard(self.ctx, idx, self.config.plan_list[idx],
                                      config=self.config)
                card.changed.connect(self._on_plan_item_changed)
                card.delete.connect(self._on_plan_item_deleted)
                card.move_top.connect(self._on_plan_item_move_top)

                self.card_list.append(card)
                # 使用 DraggableList 的 add_list_item 方法直接添加 ChargePlanCard
                self.drag_list.add_list_item(card)

        elif len(plan_list) < len(self.card_list):
            # 需要移除多余的卡片
            while len(self.card_list) > len(plan_list):
                card = self.card_list[-1]
                self.drag_list.remove_item(len(self.card_list) - 1)
                self.card_list.pop(-1)

        # 更新所有卡片的显示
        for idx, plan in enumerate(plan_list):
            self.card_list[idx].update_item(plan, idx)

    def _on_add_clicked(self) -> None:
        from zzz_od.gui.view.one_dragon.charge_plan_dialog import ChargePlanDialog
        dialog = ChargePlanDialog(self.ctx, self.config, parent=self)
        result = dialog.exec()
        if result:
            self.config.add_plan(dialog.plan)
        self.update_plan_list_display()

    def _on_plan_item_changed(self, idx: int, plan: ChargePlanItem) -> None:
        self.config.update_plan(idx, plan)

    def _on_plan_item_deleted(self, idx: int) -> None:
        self.config.delete_plan(idx)
        self.update_plan_list_display()

    def _on_plan_item_move_top(self, idx: int) -> None:
        self.config.move_top(idx)
        self.update_plan_list_display()

    def _on_remove_all_completed_clicked(self) -> None:
        dialog = Dialog('警告', '是否删除所有已完成的体力计划？', self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText('确定')
        dialog.cancelButton.setText('取消')
        if dialog.exec():
            self.plan_list_backup = self.config.plan_list.copy()
            not_completed_plans = [plan for plan in self.config.plan_list
                                   if plan.run_times < plan.plan_times]
            self.config.plan_list = not_completed_plans.copy()
            self.config.save()
            self.cancel_btn.setEnabled(True)
        self.update_plan_list_display()

    def _on_remove_all_clicked(self) -> None:
        dialog = Dialog('警告', '是否删除所有体力计划？', self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText('确定')
        dialog.cancelButton.setText('取消')
        if dialog.exec():
            self.plan_list_backup = self.config.plan_list.copy()
            self.config.plan_list.clear()
            self.config.save()
            self.cancel_btn.setEnabled(True)
        self.update_plan_list_display()

    def _on_cancel_clicked(self) -> None:
        self.config.plan_list = self.plan_list_backup.copy()
        self.cancel_btn.setEnabled(False)
        self.update_plan_list_display()

    def _on_order_changed(self, new_data_list: list) -> None:
        """
        拖拽改变顺序后的回调

        Args:
            new_data_list: 新顺序的数据列表
        """
        # 更新配置中的 plan_list 顺序
        self.config.plan_list = new_data_list
        self.config.save()

        # 重新构建 card_list 的顺序
        new_card_list: list[ChargePlanCard] = []
        for data in new_data_list:
            # 找到对应数据的 card
            for card in self.card_list:
                if card.data == data:
                    new_card_list.append(card)
                    break
        self.card_list = new_card_list

        # 更新所有卡片的索引
        for idx, card in enumerate(self.card_list):
            card.update_item(card.data, idx)
