import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, ToolButton

from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_config_file_path,
    get_auto_battle_op_config_list,
)
from zzz_od.application.battle_assistant.dodge_assitant import dodge_assistant_const
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.game_assistant.battle_assistant_run_interface import (
    BattleAssistantRunInterface,
)


class DodgeAssistantInterface(BattleAssistantRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        BattleAssistantRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=dodge_assistant_const.APP_ID,
            object_name='dodge_assistant_interface',
            nav_text_cn='闪避助手',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )

        self.dodge_opt: ComboBoxSettingCard | None = None
        self.del_btn: ToolButton | None = None

    def get_widget_at_top(self) -> QWidget:
        top_widget = Column()

        # 1) 使用说明
        self._add_help_card(top_widget)
        # 2) 战斗模式
        self._add_mode_card(top_widget)

        self.dodge_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='闪避方式')
        top_widget.add_widget(self.dodge_opt)

        self.del_btn = ToolButton(FluentIcon.DELETE)
        self.dodge_opt.hBoxLayout.addWidget(self.del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.dodge_opt.hBoxLayout.addSpacing(16)
        self.del_btn.clicked.connect(self._on_del_clicked)

        # 同名卡片由基类统一创建（GPU/截图间隔/操作方式）
        self._add_shared_common_cards(top_widget)

        return top_widget

    def get_content_widget(self) -> QWidget:
        # 统一由父级 BattleAssistantInterface 展示右侧状态面板
        return BattleAssistantRunInterface.get_content_widget(self)

    def on_interface_shown(self) -> None:
        BattleAssistantRunInterface.on_interface_shown(self)

        self._update_dodge_way_opts()
        if self.dodge_opt is not None:
            self.dodge_opt.init_with_adapter(get_prop_adapter(self.ctx.battle_assistant_config, 'dodge_assistant_config'))
        self._init_shared_common_cards()

    def on_interface_hidden(self) -> None:
        BattleAssistantRunInterface.on_interface_hidden(self)

    def _update_dodge_way_opts(self) -> None:
        if self.dodge_opt is None:
            return
        self.dodge_opt.set_options_by_list(get_auto_battle_op_config_list('dodge'))

    def _on_del_clicked(self) -> None:
        if self.dodge_opt is None:
            return

        item: str = self.dodge_opt.getValue()
        if item is None:
            return

        path = get_auto_battle_config_file_path('dodge', item)
        if os.path.exists(path):
            os.remove(path)

        self._update_dodge_way_opts()
