from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import PushButton, ToolButton, FluentIcon, SettingCardGroup, HyperlinkCard
from typing import Optional, List

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum


class TeamSettingCard(MultiPushSettingCard):

    value_changed = Signal(List[str])

    def __init__(self):
        config_list = [ConfigItem(i.value.agent_name) for i in AgentEnum] + [ConfigItem(i.value) for i in AgentTypeEnum if i != AgentTypeEnum.UNKNOWN]
        self.btn_list: List[ComboBox] = []
        for i in range(3):
            opt = ComboBox()
            opt.set_items(config_list)
            opt.currentIndexChanged.connect(self.on_character_chosen)
            opt.setDisabled(True)
            self.btn_list.append(opt)

        MultiPushSettingCard.__init__(self, icon=FluentIcon.PEOPLE, title='配队', btn_list=self.btn_list)

    def init_team(self, character_list: List[str]) -> None:
        """
        初始化
        :param character_list:
        :return:
        """
        if character_list is None:
            return
        for i in range(3):
            if i >= len(character_list):
                self.btn_list[i].init_with_value(None)
            else:
                self.btn_list[i].init_with_value(character_list[i])

    def on_character_chosen(self) -> None:
        self.value_changed.emit([opt.currentData() for opt in self.btn_list])


class AutoBattleEditorInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='auto_battle_editor_interface',
            parent=parent,
            content_widget=None,
            nav_text_cn='配置信息'
        )

        self.ctx: ZContext = ctx
        self.chosen_config: Optional[AutoBattleOperator] = None

    def get_content_widget(self) -> QWidget:
        content_widget = Row()

        content_widget.add_widget(self.init_left_part(), stretch=1)
        content_widget.add_widget(self.init_right_part(), stretch=1)

        return content_widget

    def init_left_part(self) -> QWidget:
        widget = Column()

        info_opt = HyperlinkCard(icon=FluentIcon.INFO, title='当前仅用于信息展示',
                                 content='角色顺序 朱青妮 跟 青妮朱 是一样的',
                                 text='', url='')
        info_opt.linkButton.hide()
        info_opt.setFixedHeight(50)
        widget.add_widget(info_opt)

        btn_row = Row()
        widget.add_widget(btn_row)

        self.existed_yml_btn = ComboBox()
        self.existed_yml_btn.setPlaceholderText(gt('选择已有'))
        self.existed_yml_btn.currentIndexChanged.connect(self.on_config_chosen)
        btn_row.add_widget(self.existed_yml_btn)

        self.create_btn = PushButton(text=gt('新建'))
        # self.create_btn.clicked.connect(self._on_create_clicked)
        btn_row.add_widget(self.create_btn)

        self.copy_btn = PushButton(text=gt('复制'))
        # self.copy_btn.clicked.connect(self._on_copy_clicked)
        btn_row.add_widget(self.copy_btn)

        self.delete_btn = ToolButton(FluentIcon.DELETE)
        # self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row.add_widget(self.delete_btn)

        self.cancel_btn = PushButton(text=gt('取消'))
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        btn_row.add_widget(self.cancel_btn)

        btn_row.add_stretch(1)

        basic_group = SettingCardGroup('基础信息')
        widget.add_widget(basic_group)
        self.author_opt = HyperlinkCard(icon=FluentIcon.PEOPLE, title='作者', text='作者',
                                        url=self.ctx.project_config.qq_link)
        self.author_opt.setContent('制作不易 可以到作者主页点个赞')
        basic_group.addSettingCard(self.author_opt)
        self.version_opt = HyperlinkCard(icon=FluentIcon.INFO, title='版本', text='1.0', url='')
        basic_group.addSettingCard(self.version_opt)
        self.introduction_opt = HyperlinkCard(icon=FluentIcon.INFO, title='简介', text='', url='')
        self.introduction_opt.linkButton.hide()
        basic_group.addSettingCard(self.introduction_opt)

        self.team_group = SettingCardGroup('适用配队')
        self.team_opt_list: List[TeamSettingCard] = []
        widget.add_widget(self.team_group)

        widget.add_stretch(1)
        return widget

    def init_right_part(self) -> QWidget:
        widget = Column()

        widget.add_stretch(1)

        return widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.update_auto_battle_config_opts()
        self.update_display_by_config()

    def update_auto_battle_config_opts(self) -> None:
        self.existed_yml_btn.set_items(
            get_auto_battle_op_config_list('auto_battle'),
            target_value=self.chosen_config.module_name if self.chosen_config is not None else None
        )

    def update_display_by_config(self) -> None:
        chosen = self.chosen_config is not None

        self.existed_yml_btn.setDisabled(chosen)
        self.create_btn.setDisabled(True)
        self.copy_btn.setDisabled(True)
        self.delete_btn.setDisabled(True)
        self.cancel_btn.setDisabled(not chosen)

        self.update_team_group_display()

        if chosen:
            self.author_opt.linkButton.setText(self.chosen_config.author)
            self.author_opt.linkButton.setUrl(self.chosen_config.homepage)
            self.version_opt.linkButton.setText(self.chosen_config.version)
            self.version_opt.setContent(
                f'感谢 {self.chosen_config.thanks}' if self.chosen_config.thanks != '' else ''
            )
            self.introduction_opt.setContent(self.chosen_config.introduction)
        else:
            self.author_opt.linkButton.setText('作者')
            self.author_opt.linkButton.setUrl(self.ctx.project_config.qq_link)
            self.version_opt.linkButton.setText('1.0')
            self.version_opt.setContent('')
            self.introduction_opt.setContent('')

    def update_team_group_display(self) -> None:
        if self.chosen_config is None:
            for i in self.team_opt_list:
                i.setVisible(False)
        else:
            # 删除多余的卡片
            while len(self.team_opt_list) > len(self.chosen_config.team_list):
                opt = self.team_opt_list.pop()
                self.team_group.cardLayout.removeWidget(opt)
                self.team_group.adjustSize()

            # 增加不足的卡片
            while len(self.team_opt_list) < len(self.chosen_config.team_list):
                opt = TeamSettingCard()
                # opt.value_changed.connect(self.on_team_changed)
                self.team_group.addSettingCard(opt)
                self.team_opt_list.append(opt)

            # 初始化数据
            for i in range(len(self.team_opt_list)):
                self.team_opt_list[i].init_team(self.chosen_config.team_list[i])
                self.team_opt_list[i].setVisible(True)

    def on_config_chosen(self, idx: int) -> None:
        module_name = self.existed_yml_btn.currentData()
        self.chosen_config = AutoBattleOperator(self.ctx, 'auto_battle', module_name)
        self.update_display_by_config()

    def on_cancel_clicked(self) -> None:
        self.chosen_config = None
        self.existed_yml_btn.blockSignals(True)
        self.existed_yml_btn.setCurrentIndex(-1)
        self.existed_yml_btn.blockSignals(False)
        self.update_display_by_config()