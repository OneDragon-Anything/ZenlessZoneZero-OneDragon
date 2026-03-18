import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, ToolButton

from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.game_assistant.auto_battle import auto_battle_const
from zzz_od.application.game_assistant.auto_battle_config import (
    get_auto_battle_config_file_path,
    get_auto_battle_op_config_list,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.game_assistant.battle_assistant_run_interface import (
    BattleAssistantRunInterface,
)


class AutoBattleInterface(BattleAssistantRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        BattleAssistantRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=auto_battle_const.APP_ID,
            object_name='auto_battle_interface',
            nav_text_cn='自动战斗',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )
        self.app: ZApplication | None = None

        self.config_opt: ComboBoxSettingCard | None = None
        self.del_btn: ToolButton | None = None
        self.auto_ultimate_opt: SwitchSettingCard | None = None
        self.merged_opt: SwitchSettingCard | None = None

        if hasattr(ctx, 'telemetry') and ctx.telemetry:
            ctx.telemetry.track_ui_interaction('auto_battle_interface', 'view', {
                'interface_type': 'game_assistant',
                'feature': 'auto_battle',
            })

    def get_widget_at_top(self) -> QWidget:
        top_widget = Column()

        # 1) 使用说明
        self._add_help_card(top_widget)
        # 2) 战斗模式
        self._add_mode_card(top_widget)

        self.config_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='战斗配置',
            content='全配队通用会自动为您的队伍匹配专属配队，遇到问题请反馈。',
        )
        self.del_btn = ToolButton(FluentIcon.DELETE)
        self.del_btn.clicked.connect(self._on_del_clicked)
        self.config_opt.hBoxLayout.addWidget(self.del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.config_opt.hBoxLayout.addSpacing(16)
        top_widget.add_widget(self.config_opt)

        # 同名卡片由基类统一创建（GPU/截图间隔/操作方式）
        self._add_shared_common_cards(top_widget)

        # 自动战斗独有配置，随模式切换（页面切换）自然显隐
        self.auto_ultimate_opt = SwitchSettingCard(
            icon=FluentIcon.GAME,
            title='终结技一好就放',
            content='终结技无视时机立刻释放',
        )
        top_widget.add_widget(self.auto_ultimate_opt)

        self.merged_opt = SwitchSettingCard(
            icon=FluentIcon.GAME,
            title='使用合并配置文件',
            content='关闭用于调试模板文件 正常开启即可',
        )
        top_widget.add_widget(self.merged_opt)

        return top_widget

    def get_content_widget(self) -> QWidget:
        # 统一由父级 BattleAssistantInterface 展示右侧状态面板
        return BattleAssistantRunInterface.get_content_widget(self)

    def on_interface_shown(self) -> None:
        BattleAssistantRunInterface.on_interface_shown(self)

        self._update_auto_battle_config_opts()
        if self.config_opt is not None:
            self.config_opt.init_with_adapter(get_prop_adapter(self.ctx.game_assistant_config, 'auto_battle_config'))

        self._init_shared_common_cards()

        if self.auto_ultimate_opt is not None:
            self.auto_ultimate_opt.init_with_adapter(
                get_prop_adapter(self.ctx.game_assistant_config, 'auto_ultimate_enabled')
            )
        if self.merged_opt is not None:
            self.merged_opt.init_with_adapter(get_prop_adapter(self.ctx.game_assistant_config, 'use_merged_file'))

    def on_interface_hidden(self) -> None:
        BattleAssistantRunInterface.on_interface_hidden(self)

    def _update_auto_battle_config_opts(self) -> None:
        if self.config_opt is None:
            return
        self.config_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))

    def _on_del_clicked(self) -> None:
        if self.config_opt is None:
            return

        item: str = self.config_opt.getValue()
        if item is None:
            return

        path = get_auto_battle_config_file_path('auto_battle', item)
        if os.path.exists(path):
            os.remove(path)

        self._update_auto_battle_config_opts()
