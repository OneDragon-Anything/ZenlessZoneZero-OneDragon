from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.battle_assistant.auto_battle_editor_interface import AutoBattleEditorInterface
from zzz_od.gui.view.battle_assistant.auto_battle_interface import AutoBattleInterface
from zzz_od.gui.view.battle_assistant.dodge_assistant_interface import DodgeAssistantInterface
from zzz_od.gui.view.battle_assistant.operation_debug_interface import OperationDebugInterface


class BattleAssistantInterface(PivotNavigatorInterface):
    """
    战斗助手界面，继承自 PivotNavigatorInterface。
    负责集成各类与战斗相关的子界面。
    """

    def __init__(self, ctx: ZContext, parent=None):
        """
        初始化战斗助手界面。

        :param ctx: 应用程序上下文，包含配置和状态信息。
        :param parent: 父组件，默认为 None。
        """
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(self, object_name='battle_assistant_interface', parent=parent,
                                         nav_text_cn='战斗助手', nav_icon=FluentIcon.GAME)

    def create_sub_interface(self):
        """
        创建并添加战斗助手的各个子界面，包括躲避助手、自动战斗和操作调试界面。
        """
        self.add_sub_interface(DodgeAssistantInterface(self.ctx))
        self.add_sub_interface(AutoBattleInterface(self.ctx))
        self.add_sub_interface(OperationDebugInterface(self.ctx))
        self.add_sub_interface(AutoBattleEditorInterface(self.ctx))
