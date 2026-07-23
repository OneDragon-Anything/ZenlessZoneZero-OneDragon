from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.coffee import coffee_app_const
from zzz_od.application.coffee.coffee_config import (
    CoffeeChallengeWay,
    CoffeeChooseWay,
    CoffeeConfig,
    CoffeeTransportPoint,
)
from zzz_od.context.zzz_context import ZContext


class CoffeeSettingInterface(VerticalScrollInterface, GroupIdMixin):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_coffee_plan_interface',
            content_widget=None, parent=parent,
            nav_text_cn='咖啡计划'
        )

        self.config: CoffeeConfig | None = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.transport_point_opt = ComboBoxSettingCard(icon=FluentIcon.SEND, title='传送地点', options_enum=CoffeeTransportPoint)
        content_widget.add_widget(self.transport_point_opt)

        self.choose_way_opt = ComboBoxSettingCard(icon=FluentIcon.CALENDAR, title='咖啡选择', options_enum=CoffeeChooseWay)
        content_widget.add_widget(self.choose_way_opt)

        self.challenge_way_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='喝后挑战', content='决定喝完咖啡后是否运行体力计划', options_enum=CoffeeChallengeWay)
        content_widget.add_widget(self.challenge_way_opt)

        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.config = self.ctx.run_context.get_config(
            app_id=coffee_app_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        self.transport_point_opt.init_with_adapter(get_prop_adapter(self.config, 'transport_point'))
        self.choose_way_opt.init_with_adapter(get_prop_adapter(self.config, 'choose_way'))
        self.challenge_way_opt.init_with_adapter(get_prop_adapter(self.config, 'challenge_way'))
