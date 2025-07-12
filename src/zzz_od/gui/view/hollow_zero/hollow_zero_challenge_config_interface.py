from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, FluentThemeColor, PlainTextEdit, SubtitleLabel, BodyLabel, \
     TitleLabel, PushButton, ToolButton
from typing import List, Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig, \
    get_all_hollow_zero_challenge_config, get_hollow_zero_challenge_new_name, HollowZeroChallengePathFinding


class HollowZeroChallengeConfigInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='hollow_zero_challenge_config_interface',
            parent=parent,
            content_widget=None,
            nav_text_cn='挑战配置-枯'
        )

        self.ctx: ZContext = ctx
        self.chosen_config: Optional[HollowZeroChallengeConfig] = None

    def get_content_widget(self) -> QWidget:
        content_widget = Row()

        content_widget.add_widget(self._init_left_part(), stretch=1)
        content_widget.add_widget(self._init_right_part(), stretch=1)

        return content_widget

    def _init_left_part(self) -> QWidget:
        widget = Column()

        btn_row = Row()
        widget.add_widget(btn_row)

        self.existed_yml_btn = ComboBox()
        self.existed_yml_btn.setPlaceholderText(gt('选择已有'))
        self.existed_yml_btn.currentIndexChanged.connect(self._on_choose_existed_yml)
        btn_row.add_widget(self.existed_yml_btn)

        self.create_btn = PushButton(text=gt('新建'))
        self.create_btn.clicked.connect(self._on_create_clicked)
        btn_row.add_widget(self.create_btn)

        self.copy_btn = PushButton(text=gt('复制'))
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        btn_row.add_widget(self.copy_btn)

        self.delete_btn = ToolButton(FluentIcon.DELETE)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row.add_widget(self.delete_btn)

        self.cancel_btn = PushButton(text=gt('取消'))
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.add_widget(self.cancel_btn)

        btn_row.add_stretch(1)

        self.error_message = BodyLabel(text='')
        self.error_message.setTextColor(FluentThemeColor.RED.value)
        widget.add_widget(self.error_message)

        self.name_opt = TextSettingCard(icon=FluentIcon.GAME, title='配置名称', content='默认配置复制后可修改')
        self.name_opt.value_changed.connect(self._on_name_changed)
        widget.add_widget(self.name_opt)

        self.agent_btn_list: List[EditableComboBox] = []
        for i in range(3):
            agent_btn = EditableComboBox()
            agent_btn.currentIndexChanged.connect(self._on_agent_changed)
            self.agent_btn_list.append(agent_btn)

        self.agents_opt = MultiPushSettingCard(btn_list=self.agent_btn_list, icon=FluentIcon.PEOPLE,
                                               title='目标配队', content='按照自动战斗配置 选择角色位置')
        widget.add_widget(self.agents_opt)

        self.buy_only_priority_opt = SwitchSettingCard(icon=FluentIcon.BROOM,
                                                       title='仅购买优先级', content='邦布商人购买时只购买符合优先级的')
        self.buy_only_priority_opt.value_changed.connect(self._on_buy_only_priority_changed)
        widget.add_widget(self.buy_only_priority_opt)

        self.auto_battle_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='自动战斗')
        self.auto_battle_opt.value_changed.connect(self._on_auto_battle_config_changed)
        widget.add_widget(self.auto_battle_opt)

        self.path_finding_opt = ComboBoxSettingCard(icon=FluentIcon.MARKET, title='寻路方式',
                                                    options_enum=HollowZeroChallengePathFinding)
        self.path_finding_opt.value_changed.connect(self._on_path_finding_changed)
        widget.add_widget(self.path_finding_opt)

        go_in_1_step_widget = Column()
        go_in_1_step_title = SubtitleLabel(text=gt('一步可达时前往'))
        go_in_1_step_widget.v_layout.addWidget(go_in_1_step_title)
        self.go_in_1_step_input = PlainTextEdit()
        self.go_in_1_step_input.textChanged.connect(self._on_go_in_1_step_changed)
        go_in_1_step_widget.v_layout.addWidget(self.go_in_1_step_input)

        waypoint_widget = Column()
        waypoint_title = SubtitleLabel(text=gt('优先途经点'))
        waypoint_widget.v_layout.addWidget(waypoint_title)
        self.waypoint_input = PlainTextEdit()
        self.waypoint_input.textChanged.connect(self._on_waypoint_changed)
        waypoint_widget.v_layout.addWidget(self.waypoint_input)

        avoid_widget = Column()
        avoid_title = SubtitleLabel(text=gt('避免途经点'))
        avoid_widget.v_layout.addWidget(avoid_title)
        self.avoid_input = PlainTextEdit()
        self.avoid_input.textChanged.connect(self._on_avoid_changed)
        avoid_widget.v_layout.addWidget(self.avoid_input)

        self.pathfinding_widget = Row()
        self.pathfinding_widget.h_layout.addWidget(go_in_1_step_widget)
        self.pathfinding_widget.h_layout.addWidget(waypoint_widget)
        self.pathfinding_widget.h_layout.addWidget(avoid_widget)

        widget.add_widget(self.pathfinding_widget)

        widget.add_stretch(1)
        return widget

    def _init_right_part(self) -> QWidget:
        widget = Column()

        resonium_title = TitleLabel(text=gt('奖励优先级'))
        widget.add_widget(resonium_title)
        self.resonium_priority_input = PlainTextEdit()
        self.resonium_priority_input.textChanged.connect(self._on_resonium_priority_changed)
        widget.add_widget(self.resonium_priority_input)

        event_priority_title = TitleLabel(text=gt('选项优先级'))
        event_priority_title.setVisible(False)
        widget.add_widget(event_priority_title)
        self.event_priority_input = PlainTextEdit()
        self.event_priority_input.textChanged.connect(self._on_event_priority_changed)
        widget.add_widget(self.event_priority_input)
        self.event_priority_input.setVisible(False)

        widget.add_stretch(1)

        return widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self._update_whole_display()

    def _update_whole_display(self) -> None:
        """
        根据画面图片，统一更新界面的显示
        :return:
        """
        chosen = self.chosen_config is not None
        is_sample = self.chosen_config is None or self.chosen_config.is_sample

        self.existed_yml_btn.setDisabled(chosen)
        self.create_btn.setDisabled(chosen)
        self.copy_btn.setDisabled(not chosen)
        self.delete_btn.setDisabled(not chosen or is_sample)
        self.cancel_btn.setDisabled(not chosen)

        self.name_opt.setDisabled(not chosen or is_sample)
        self.auto_battle_opt.setDisabled(not chosen or is_sample)
        self.path_finding_opt.setDisabled(not chosen or is_sample)
        self.agents_opt.setDisabled(not chosen or is_sample)
        for agent_btn in self.agent_btn_list:
            agent_btn.setDisabled(not chosen or is_sample)
        self.buy_only_priority_opt.setDisabled(not chosen or is_sample)
        self.resonium_priority_input.setDisabled(not chosen or is_sample)
        self.event_priority_input.setDisabled(not chosen or is_sample)

        self._update_existed_yml_options()
        self._update_auto_battle_opts()

        if chosen:
            self.name_opt.setValue(self.chosen_config.module_name)
            self.auto_battle_opt.setValue(self.chosen_config.auto_battle)
            self.path_finding_opt.setValue(self.chosen_config.path_finding)
            agent_opts = [
                             ConfigItem(agent_type_enum.value)
                             for agent_type_enum in AgentTypeEnum
                             if agent_type_enum.value != '未知'
                         ] + [
                             ConfigItem(label=agent_enum.value.agent_name, value=agent_enum.value.agent_id)
                             for agent_enum in AgentEnum
                         ]
            agents = self.chosen_config.target_agents
            for i in range(3):
                btn = self.agent_btn_list[i]
                btn.set_items(agent_opts, agents[i])
            self.buy_only_priority_opt.setValue(self.chosen_config.buy_only_priority)
            self.resonium_priority_input.setPlainText(self.chosen_config.resonium_priority_str)
            self.event_priority_input.setPlainText(self.chosen_config.event_priority_str)

            self._update_pathfinding_input_display()

        if is_sample:
            self._update_error_message('当前为默认配置，点击复制后可修改')
        else:
            self._update_error_message('')

    def _update_existed_yml_options(self) -> None:
        """
        更新已有的yml选项
        :return:
        """
        self.existed_yml_btn.blockSignals(True)
        self.existed_yml_btn.clear()
        config_list: List[HollowZeroChallengeConfig] = get_all_hollow_zero_challenge_config()
        for config in config_list:
            self.existed_yml_btn.addItem(text=config.module_name, icon=None, userData=config)
        self.existed_yml_btn.setCurrentIndex(-1)
        self.existed_yml_btn.setPlaceholderText(gt('选择已有'))
        self.existed_yml_btn.blockSignals(False)

    def _update_auto_battle_opts(self) -> None:
        """
        自动战斗的配置下拉框
        :return:
        """
        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))

    def _update_pathfinding_input_display(self) -> None:
        """
        寻路相关的显示
        :return:
        """
        chosen = self.chosen_config is not None
        is_sample = self.chosen_config is None or self.chosen_config.is_sample
        custom = self.chosen_config is not None and self.chosen_config.path_finding == HollowZeroChallengePathFinding.CUSTOM.value.value

        self.go_in_1_step_input.setDisabled(not chosen or is_sample or not custom)
        self.waypoint_input.setDisabled(not chosen or is_sample or not custom)
        self.avoid_input.setDisabled(not chosen or is_sample or not custom)

        self.pathfinding_widget.setVisible(custom)
        if custom:
            if self.chosen_config.go_in_1_step is not None:
                self.go_in_1_step_input.setPlainText('\n'.join(self.chosen_config.go_in_1_step))
            if self.chosen_config.waypoint is not None:
                self.waypoint_input.setPlainText('\n'.join(self.chosen_config.waypoint))
            if self.chosen_config.avoid is not None:
                self.avoid_input.setPlainText('\n'.join(self.chosen_config.avoid))

    def _on_choose_existed_yml(self, idx: int):
        """
        选择了已有的yml
        :param idx:
        :return:
        """
        self.chosen_config: HollowZeroChallengeConfig = self.existed_yml_btn.items[idx].userData
        self._update_whole_display()

    def _on_create_clicked(self):
        """
        创建一个新的
        :return:
        """
        if self.chosen_config is not None:
            return

        self.chosen_config = HollowZeroChallengeConfig(get_hollow_zero_challenge_new_name(), False)
        self.chosen_config.remove_sample()

        self._update_whole_display()

    def _on_copy_clicked(self):
        """
        复制一个
        :return:
        """
        if self.chosen_config is None:
            return

        self.chosen_config.copy_new()
        self._update_whole_display()

    def _on_save_clicked(self) -> None:
        """
        保存配置
        :return:
        """
        if self.chosen_config is None:
            return

        self.chosen_config.save()
        self._update_existed_yml_options()

    def _on_delete_clicked(self) -> None:
        """
        删除
        :return:
        """
        if self.chosen_config is None:
            return
        self.chosen_config.delete()
        self.chosen_config = None
        self._update_whole_display()

    def _on_cancel_clicked(self) -> None:
        """
        取消编辑
        :return:
        """
        if self.chosen_config is None:
            return
        self.chosen_config = None
        self.existed_yml_btn.setCurrentIndex(-1)
        self._update_whole_display()

    def _on_name_changed(self, value: str) -> None:
        if self.chosen_config is None:
            return

        self.chosen_config.update_module_name(value)

    def _on_buy_only_priority_changed(self, value: bool):
        if self.chosen_config is None:
            return
        self.chosen_config.buy_only_priority = value

    def _on_auto_battle_config_changed(self, index, value) -> None:
        if self.chosen_config is None:
            return

        self.chosen_config.auto_battle = value

    def _on_path_finding_changed(self, index, value) -> None:
        if self.chosen_config is None:
            return

        self.chosen_config.path_finding = value

        if value == HollowZeroChallengePathFinding.CUSTOM.value.value:
            if self.chosen_config.go_in_1_step is None:
                self.chosen_config.go_in_1_step = self.ctx.hollow.data_service.get_default_go_in_1_step_entry_list()
            if self.chosen_config.waypoint is None:
                self.chosen_config.waypoint = self.ctx.hollow.data_service.get_default_waypoint_entry_list()
            if self.chosen_config.avoid is None:
                self.chosen_config.avoid = self.ctx.hollow.data_service.get_default_avoid_entry_list()

        self._update_pathfinding_input_display()

    def _update_error_message(self, msg: str) -> None:
        if msg is None or len(msg) == 0:
            self.error_message.setVisible(False)
        else:
            self.error_message.setText(msg)
            self.error_message.setVisible(True)

    def _on_resonium_priority_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.resonium_priority_input.toPlainText()
        priority_list, err_msg = self.ctx.hollow.data_service.check_resonium_priority(value)
        self._update_error_message(err_msg)

        self.chosen_config.resonium_priority = priority_list

    def _on_event_priority_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.event_priority_input.toPlainText()

        self.chosen_config.event_priority = [i.strip() for i in value.split('\n')]

    def _on_go_in_1_step_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.go_in_1_step_input.toPlainText()
        entry_list, err_msg = self.ctx.hollow.data_service.check_entry_list_input(value)
        self._update_error_message(err_msg)

        self.chosen_config.go_in_1_step = entry_list

    def _on_waypoint_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.waypoint_input.toPlainText()
        entry_list, err_msg = self.ctx.hollow.data_service.check_entry_list_input(value)
        self._update_error_message(err_msg)

        self.chosen_config.waypoint = entry_list

    def _on_avoid_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.avoid_input.toPlainText()
        entry_list, err_msg = self.ctx.hollow.data_service.check_entry_list_input(value)
        self._update_error_message(err_msg)

        self.chosen_config.avoid = entry_list

    def _on_agent_changed(self, idx: int) -> None:
        if self.chosen_config is None:
            return

        agents = []
        for i in range(3):
            if self.agent_btn_list[i].currentIndex() == -1:
                agents.append(None)
            else:
                agents.append(self.agent_btn_list[i].currentData())

        self.chosen_config.target_agents = agents