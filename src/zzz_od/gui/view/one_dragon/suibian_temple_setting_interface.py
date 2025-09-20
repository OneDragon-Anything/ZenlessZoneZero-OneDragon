from typing import Optional

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_dispatch import (
    SuibianTempleAdventureDispatchDuration,
)
from zzz_od.application.suibian_temple.suibian_temple_config import (
    SuibianTempleConfig,
    SuibianTempleAdventureMission,
    BangbooPrice,
)
from zzz_od.context.zzz_context import ZContext


class SuibianTempleSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_suibian_temple_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='随便观'
        )

        self.config: Optional[SuibianTempleConfig] = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.yum_cha_sin_switch = SwitchSettingCard(icon=FluentIcon.GAME, title='饮茶仙')
        content_widget.add_widget(self.yum_cha_sin_switch)

        self.yum_cha_sin_refresh_switch = SwitchSettingCard(icon=FluentIcon.GAME, title='饮茶仙-委托刷新')
        content_widget.add_widget(self.yum_cha_sin_refresh_switch)

        self.adventure_duration_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='派遣-时长',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in SuibianTempleAdventureDispatchDuration
            ]
        )
        content_widget.add_widget(self.adventure_duration_opt)

        self.adventure_mission_1_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='派遣-副本1',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in SuibianTempleAdventureMission
            ]
        )
        content_widget.add_widget(self.adventure_mission_1_opt)

        self.adventure_mission_2_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='派遣-副本2',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in SuibianTempleAdventureMission
            ]
        )
        content_widget.add_widget(self.adventure_mission_2_opt)

        self.adventure_mission_3_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='派遣-副本3',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in SuibianTempleAdventureMission
            ]
        )
        content_widget.add_widget(self.adventure_mission_3_opt)

        self.adventure_mission_4_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='派遣-副本4',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in SuibianTempleAdventureMission
            ]
        )
        content_widget.add_widget(self.adventure_mission_4_opt)

        # 好物铺购买功能设置
        self.good_goods_purchase_switch = SwitchSettingCard(
            icon=FluentIcon.SHOPPING_CART,
            title='好物铺购买',
            content='自动购买好物铺中的指定商品'
        )
        content_widget.add_widget(self.good_goods_purchase_switch)

        # 邦巢设置
        self.boo_box_purchase_switch = SwitchSettingCard(
            icon=FluentIcon.VIDEO, title='邦巢-购买',
            content='自动刷新购买S级别邦布。随便观25级后可用。'
        )
        content_widget.add_widget(self.boo_box_purchase_switch)

        self.boo_box_adventure_price = ComboBoxSettingCard(
            icon=FluentIcon.VIDEO, title='邦巢-游历-最低购买价格',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in BangbooPrice
            ]
        )
        content_widget.add_widget(self.boo_box_adventure_price)

        self.boo_box_craft_price = ComboBoxSettingCard(
            icon=FluentIcon.VIDEO, title='邦巢-制造-最低购买价格',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in BangbooPrice
            ]
        )
        content_widget.add_widget(self.boo_box_craft_price)

        self.boo_box_sell_price = ComboBoxSettingCard(
            icon=FluentIcon.VIDEO, title='邦巢-出售-最低购买价格',
            options_list=[
                ConfigItem(label=i, value=i.name)
                for i in BangbooPrice
            ]
        )
        content_widget.add_widget(self.boo_box_sell_price)

        content_widget.add_stretch(1)
        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.config = self.ctx.run_context.get_config(
            app_id='suibian_temple',
            instance_idx=self.ctx.current_instance_idx,
            group_id='one_dragon'
        )

        self.yum_cha_sin_switch.init_with_adapter(get_prop_adapter(self.config, 'yum_cha_sin'))
        self.yum_cha_sin_refresh_switch.init_with_adapter(get_prop_adapter(self.config, 'yum_cha_sin_period_refresh'))
        self.adventure_duration_opt.init_with_adapter(get_prop_adapter(self.config, 'adventure_duration'))
        self.adventure_mission_1_opt.init_with_adapter(get_prop_adapter(self.config, 'adventure_mission_1'))
        self.adventure_mission_2_opt.init_with_adapter(get_prop_adapter(self.config, 'adventure_mission_2'))
        self.adventure_mission_3_opt.init_with_adapter(get_prop_adapter(self.config, 'adventure_mission_3'))
        self.adventure_mission_4_opt.init_with_adapter(get_prop_adapter(self.config, 'adventure_mission_4'))

        # 初始化好物铺购买功能设置
        self.good_goods_purchase_switch.init_with_adapter(get_prop_adapter(self.config, 'good_goods_purchase_enabled'))

        # 邦巢相关设置
        self.boo_box_purchase_switch.init_with_adapter(get_prop_adapter(self.config, 'boo_box_purchase_enabled'))
        self.boo_box_adventure_price.init_with_adapter(get_prop_adapter(self.config, 'boo_box_adventure_price'))
        self.boo_box_craft_price.init_with_adapter(get_prop_adapter(self.config, 'boo_box_craft_price'))
        self.boo_box_sell_price.init_with_adapter(get_prop_adapter(self.config, 'boo_box_sell_price'))
