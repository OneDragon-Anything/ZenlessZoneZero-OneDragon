from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, FluentThemeColor, PlainTextEdit, SubtitleLabel, BodyLabel, \
     PushButton, ToolButton
from typing import List, Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidChallengeConfig, \
    get_lost_void_challenge_new_name, get_all_lost_void_challenge_config, LostVoidPeriodBuffNo
from zzz_od.context.zzz_context import ZContext


class LostVoidChallengeConfigInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='lost_void_challenge_config_interface',
            parent=parent,
            content_widget=None,
            nav_text_cn='挑战配置-迷'
        )

        self.ctx: ZContext = ctx
        self.chosen_config: Optional[LostVoidChallengeConfig] = None

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

        self.predefined_team_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='预备编队')
        widget.add_widget(self.predefined_team_opt)

        self.priority_team_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='当期UP代理人',
                                                   content='每周第1次 优先选择包含当期UP的编队 覆盖预备编队选项')
        widget.add_widget(self.priority_team_opt)

        self.auto_battle_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='自动战斗',
                                                   content='预备编队使用游戏内配队时生效')
        self.auto_battle_opt.value_changed.connect(self._on_auto_battle_config_changed)
        widget.add_widget(self.auto_battle_opt)

        self.investigation_strategy_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='调查战略',
                                                              options_enum=LostVoidPeriodBuffNo)
        widget.add_widget(self.investigation_strategy_opt)

        self.period_buff_no_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='周期增益',
                                                      options_enum=LostVoidPeriodBuffNo)
        widget.add_widget(self.period_buff_no_opt)

        self.store_blood_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='商店-使用血量购买',
                                                 content='练度低情况下 仅建议绝境武备开启')
        widget.add_widget(self.store_blood_opt)

        self.store_blood_min_opt = TextSettingCard(icon=FluentIcon.GAME, title='商店-使用血量购买',
                                                   content='血量 ≥ x% 时 才会进行购买')
        widget.add_widget(self.store_blood_min_opt)

        self.priority_new_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='优先选择NEW!藏品',
                                                  content='最高优先级 但不保证识别正确')
        widget.add_widget(self.priority_new_opt)

        self.buy_only_priority_1_opt = TextSettingCard(icon=FluentIcon.GAME, title='只购买第一优先级',
                                                       content='刷新多少次数内 只购买第一优先级内的藏品')
        widget.add_widget(self.buy_only_priority_1_opt)

        self.buy_only_priority_2_opt = TextSettingCard(icon=FluentIcon.GAME, title='只购买第二优先级',
                                                       content='刷新多少次数内 只购买第二优先级内的藏品')
        widget.add_widget(self.buy_only_priority_2_opt)

        widget.add_stretch(1)
        return widget

    def _init_right_part(self) -> QWidget:
        widget = Column()

        artifact_priority_widget = Column()
        widget.add_widget(artifact_priority_widget)
        artifact_priority_title = SubtitleLabel(text=gt('藏品第一优先级'))
        artifact_priority_widget.v_layout.addWidget(artifact_priority_title)
        self.artifact_priority_input = PlainTextEdit()
        self.artifact_priority_input.textChanged.connect(self._on_artifact_priority_changed)
        artifact_priority_widget.v_layout.addWidget(self.artifact_priority_input)

        artifact_priority_widget_2 = Column()
        widget.add_widget(artifact_priority_widget_2)
        artifact_priority_title_2 = SubtitleLabel(text=gt('藏品第二优先级 (无刷新时考虑)'))
        artifact_priority_widget.v_layout.addWidget(artifact_priority_title_2)
        self.artifact_priority_input_2 = PlainTextEdit()
        self.artifact_priority_input_2.textChanged.connect(self._on_artifact_priority_2_changed)
        artifact_priority_widget.v_layout.addWidget(self.artifact_priority_input_2)

        region_priority_widget = Column()
        widget.add_widget(region_priority_widget)
        region_priority_title = SubtitleLabel(text=gt('区域类型优先级'))
        region_priority_widget.v_layout.addWidget(region_priority_title)
        self.region_type_priority_input = PlainTextEdit()
        self.region_type_priority_input.textChanged.connect(self._on_region_type_priority_changed)
        region_priority_widget.v_layout.addWidget(self.region_type_priority_input)

        widget.add_stretch(1)

        return widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.ctx.lost_void.load_artifact_data()
        self.ctx.lost_void.load_investigation_strategy()
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
        self.predefined_team_opt.setDisabled(not chosen or is_sample)
        self.priority_team_opt.setDisabled(not chosen or is_sample)
        self.auto_battle_opt.setDisabled(not chosen or is_sample)
        self.investigation_strategy_opt.setDisabled(not chosen or is_sample)
        self.period_buff_no_opt.setDisabled(not chosen or is_sample)
        self.store_blood_opt.setDisabled(not chosen or is_sample)
        self.store_blood_min_opt.setDisabled(not chosen or is_sample)
        self.priority_new_opt.setDisabled(not chosen or is_sample)
        self.buy_only_priority_1_opt.setDisabled(not chosen or is_sample)
        self.buy_only_priority_2_opt.setDisabled(not chosen or is_sample)
        self.artifact_priority_input.setDisabled(not chosen or is_sample)
        self.artifact_priority_input_2.setDisabled(not chosen or is_sample)
        self.region_type_priority_input.setDisabled(not chosen or is_sample)

        self._update_existed_yml_options()
        team_config_list = ([ConfigItem('游戏内配队', -1)] +
                       [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.predefined_team_opt.set_options_by_list(team_config_list)
        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))
        self.investigation_strategy_opt.set_options_by_list([
            ConfigItem(i.strategy_name)
            for i in self.ctx.lost_void.investigation_strategy_list
        ])

        if chosen:
            self.name_opt.setValue(self.chosen_config.module_name)
            self.predefined_team_opt.init_with_adapter(self.chosen_config.get_prop_adapter('predefined_team_idx'))
            self.priority_team_opt.init_with_adapter(self.chosen_config.get_prop_adapter('choose_team_by_priority'))
            self.auto_battle_opt.setValue(self.chosen_config.auto_battle)
            self.investigation_strategy_opt.init_with_adapter(self.chosen_config.get_prop_adapter('investigation_strategy'))
            self.period_buff_no_opt.init_with_adapter(self.chosen_config.get_prop_adapter('period_buff_no'))
            self.store_blood_opt.init_with_adapter(self.chosen_config.get_prop_adapter('store_blood'))
            self.store_blood_min_opt.init_with_adapter(self.chosen_config.get_prop_adapter('store_blood_min', getter_convert='str', setter_convert='int'))
            self.priority_new_opt.init_with_adapter(self.chosen_config.get_prop_adapter('artifact_priority_new'))
            self.buy_only_priority_1_opt.init_with_adapter(self.chosen_config.get_prop_adapter('buy_only_priority_1', getter_convert='str', setter_convert='int'))
            self.buy_only_priority_2_opt.init_with_adapter(self.chosen_config.get_prop_adapter('buy_only_priority_2', getter_convert='str', setter_convert='int'))

            self.artifact_priority_input.blockSignals(True)
            self.artifact_priority_input.setPlainText(self.chosen_config.artifact_priority_str)
            self.artifact_priority_input.blockSignals(False)

            self.artifact_priority_input_2.blockSignals(True)
            self.artifact_priority_input_2.setPlainText(self.chosen_config.artifact_priority_2_str)
            self.artifact_priority_input_2.blockSignals(False)

            self.region_type_priority_input.blockSignals(True)
            self.region_type_priority_input.setPlainText(self.chosen_config.region_type_priority_str)
            self.region_type_priority_input.blockSignals(False)

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
        config_list: List[LostVoidChallengeConfig] = get_all_lost_void_challenge_config()
        for config in config_list:
            self.existed_yml_btn.addItem(text=config.module_name, icon=None, userData=config)
        self.existed_yml_btn.setCurrentIndex(-1)
        self.existed_yml_btn.setPlaceholderText(gt('选择已有'))
        self.existed_yml_btn.blockSignals(False)

    def _on_choose_existed_yml(self, idx: int):
        """
        选择了已有的yml
        :param idx:
        :return:
        """
        self.chosen_config: LostVoidChallengeConfig = self.existed_yml_btn.items[idx].userData
        self._update_whole_display()

    def _on_create_clicked(self):
        """
        创建一个新的
        :return:
        """
        if self.chosen_config is not None:
            return

        self.chosen_config = LostVoidChallengeConfig(get_lost_void_challenge_new_name(), False)
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

    def _update_error_message(self, msg: str) -> None:
        if msg is None or len(msg) == 0:
            self.error_message.setVisible(False)
        else:
            self.error_message.setText(msg)
            self.error_message.setVisible(True)

    def _on_artifact_priority_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.artifact_priority_input.toPlainText()
        entry_list, err_msg = self.ctx.lost_void.check_artifact_priority_input(value)
        self._update_error_message(err_msg)

        self.chosen_config.artifact_priority = entry_list

    def _on_artifact_priority_2_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.artifact_priority_input_2.toPlainText()
        entry_list, err_msg = self.ctx.lost_void.check_artifact_priority_input(value)
        self._update_error_message(err_msg)

        self.chosen_config.artifact_priority_2 = entry_list

    def _on_region_type_priority_changed(self) -> None:
        if self.chosen_config is None:
            return

        value = self.region_type_priority_input.toPlainText()
        entry_list, err_msg = self.ctx.lost_void.check_region_type_priority_input(value)
        self._update_error_message(err_msg)

        self.chosen_config.region_type_priority = entry_list
