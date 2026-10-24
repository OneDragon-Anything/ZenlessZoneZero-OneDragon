from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.battle_assistant.battle_assistant_interface import (
    BattleAssistantInterface,
)
from zzz_od.gui.view.game_assistant.commission_assistant_interface import (
    CommissionAssistantRunInterface,
)


class GameAssistantInterface(PivotNavigatorInterface):
    """
    游戏助手界面，继承自 PivotNavigatorInterface。
    负责集成各类与战斗相关的子界面。
    """

    def __init__(self, ctx: ZContext, parent=None):
        """
        初始化游戏助手界面。

        :param ctx: 应用程序上下文，包含配置和状态信息。
        :param parent: 父组件，默认为 None。
        """
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(self, object_name='game_assistant_interface', parent=parent,
                                         nav_text_cn='游戏助手', nav_icon=FluentIcon.GAME)

    def create_sub_interface(self):
        """
        创建并添加游戏助手的各个子界面，包括战斗助手和委托助手界面。
        """
        self.add_sub_interface(BattleAssistantInterface(self.ctx))
        self.add_sub_interface(CommissionAssistantRunInterface(self.ctx))
