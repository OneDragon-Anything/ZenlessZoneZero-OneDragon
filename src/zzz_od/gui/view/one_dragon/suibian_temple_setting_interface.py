from typing import Optional

from PySide6.QtWidgets import QWidget, QLabel
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_dispatch import (
    SuibianTempleAdventureDispatchDuration,
)
from zzz_od.application.suibian_temple.suibian_temple_config import (
    SuibianTempleConfig,
    SuibianTempleAdventureMission,
    BangbooPrice,
    PawnshopOmnicoinGoods,
    PawnshopCrestGoods,
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

        adventure_mission_options_list = [
            ConfigItem(label=i, value=i.name) for i in SuibianTempleAdventureMission
        ]
        self.adventure_mission_1_opt = ComboBox()
        self.adventure_mission_1_opt.set_items(adventure_mission_options_list)
        self.adventure_mission_2_opt = ComboBox()
        self.adventure_mission_2_opt.set_items(adventure_mission_options_list)
        self.adventure_mission_3_opt = ComboBox()
        self.adventure_mission_3_opt.set_items(adventure_mission_options_list)
        self.adventure_mission_4_opt = ComboBox()
        self.adventure_mission_4_opt.set_items(adventure_mission_options_list)

        self.adventure_mission_opt = MultiPushSettingCard(
            icon=FluentIcon.GAME, title='派遣-副本优先级',
            content='按优先级将剩余小队派遣',
            btn_list=[
                self.adventure_mission_1_opt,
                self.adventure_mission_2_opt,
                self.adventure_mission_3_opt,
                self.adventure_mission_4_opt,
            ],
        )
        content_widget.add_widget(self.adventure_mission_opt)

        # 制造坊
        self.craft_drag_times = SpinBoxSettingCard(
            icon=FluentIcon.GAME,
            title="制造坊-最大下拉次数",
            content="跳过底部的低级商品",
        )
        content_widget.add_widget(self.craft_drag_times)

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

        boo_box_price_options = [ConfigItem(label=i, value=i.name) for i in BangbooPrice]
        self.boo_box_adventure_price = ComboBox()
        self.boo_box_adventure_price.set_items(boo_box_price_options)
        self.boo_box_craft_price = ComboBox()
        self.boo_box_craft_price.set_items(boo_box_price_options)
        self.boo_box_sell_price = ComboBox()
        self.boo_box_sell_price.set_items(boo_box_price_options)

        self.boo_box_price = MultiPushSettingCard(
            icon=FluentIcon.VIDEO,
            title="邦巢-最低购买价格",
            btn_list=[
                QLabel('游历'),
                self.boo_box_adventure_price,
                QLabel('制造'),
                self.boo_box_craft_price,
                QLabel('售卖'),
                self.boo_box_sell_price,
            ]
        )
        content_widget.add_widget(self.boo_box_price)

        # 德丰大押配置
        self.pawnshop_omnicoin_switch = SwitchSettingCard(
            icon=FluentIcon.GAME,
            title="德丰大押-百宝通-开关",
            content="自动兑换百宝通奖励",
        )
        content_widget.add_widget(self.pawnshop_omnicoin_switch)

        pawnshop_omnicoin_options = [
            ConfigItem(label=i, value=i.name) for i in PawnshopOmnicoinGoods
        ]
        self.pawnshop_omnicoin_priority_1 = ComboBox()
        self.pawnshop_omnicoin_priority_1.set_items(pawnshop_omnicoin_options)
        self.pawnshop_omnicoin_priority_1.currentIndexChanged.connect(self._on_pawnshop_omnicoin_priority_changed)

        self.pawnshop_omnicoin_priority_2 = ComboBox()
        self.pawnshop_omnicoin_priority_2.set_items(pawnshop_omnicoin_options)
        self.pawnshop_omnicoin_priority_2.currentIndexChanged.connect(self._on_pawnshop_omnicoin_priority_changed)

        self.pawnshop_omnicoin_priority_3 = ComboBox()
        self.pawnshop_omnicoin_priority_3.set_items(pawnshop_omnicoin_options)
        self.pawnshop_omnicoin_priority_3.currentIndexChanged.connect(self._on_pawnshop_omnicoin_priority_changed)

        self.pawnshop_omnicoin_priority_4 = ComboBox()
        self.pawnshop_omnicoin_priority_4.set_items(pawnshop_omnicoin_options)
        self.pawnshop_omnicoin_priority_4.currentIndexChanged.connect(self._on_pawnshop_omnicoin_priority_changed)

        self.pawnshop_omnicoin_priority_5 = ComboBox()
        self.pawnshop_omnicoin_priority_5.set_items(pawnshop_omnicoin_options)
        self.pawnshop_omnicoin_priority_5.currentIndexChanged.connect(self._on_pawnshop_omnicoin_priority_changed)

        self.pawnshop_omnicoin_priority = MultiPushSettingCard(
            icon=FluentIcon.GAME, title='德丰大押-百宝通-兑换优先级',
            btn_list=[
                self.pawnshop_omnicoin_priority_1,
                self.pawnshop_omnicoin_priority_2,
                self.pawnshop_omnicoin_priority_3,
                self.pawnshop_omnicoin_priority_4,
                self.pawnshop_omnicoin_priority_5,
            ]
        )
        content_widget.add_widget(self.pawnshop_omnicoin_priority)

        self.pawnshop_crest_switch = SwitchSettingCard(
            icon=FluentIcon.GAME,
            title="德丰大押-云纹徽-开关",
            content="自动兑换云纹徽奖励",
        )
        content_widget.add_widget(self.pawnshop_crest_switch)

        pawnshop_crest_options = [
            ConfigItem(label=i, value=i.name) for i in PawnshopCrestGoods
        ]
        self.pawnshop_crest_priority_1 = ComboBox()
        self.pawnshop_crest_priority_1.set_items(pawnshop_crest_options)
        self.pawnshop_crest_priority_1.currentIndexChanged.connect(self._on_pawnshop_crest_priority_changed)

        self.pawnshop_crest_priority_2 = ComboBox()
        self.pawnshop_crest_priority_2.set_items(pawnshop_crest_options)
        self.pawnshop_crest_priority_2.currentIndexChanged.connect(self._on_pawnshop_crest_priority_changed)

        self.pawnshop_crest_priority = MultiPushSettingCard(
            icon=FluentIcon.GAME, title='德丰大押-云纹徽-兑换优先级',
            btn_list=[
                self.pawnshop_crest_priority_1,
                self.pawnshop_crest_priority_2,
            ]
        )
        content_widget.add_widget(self.pawnshop_crest_priority)

        self.pawnshop_crest_unlimited_denny_switch = SwitchSettingCard(
            icon=FluentIcon.GAME,
            title="德丰大押-云纹徽-不限购丁尼-开关",
            content="限购商品兑换完后，再兑换不限购的",
        )
        content_widget.add_widget(self.pawnshop_crest_unlimited_denny_switch)

        content_widget.add_stretch(1)
        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.config: Optional[SuibianTempleConfig] = self.ctx.run_context.get_config(
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

        # 制造坊
        self.craft_drag_times.init_with_adapter(get_prop_adapter(self.config, 'craft_drag_times'))

        # 初始化好物铺购买功能设置
        self.good_goods_purchase_switch.init_with_adapter(get_prop_adapter(self.config, 'good_goods_purchase_enabled'))

        # 邦巢相关设置
        self.boo_box_purchase_switch.init_with_adapter(get_prop_adapter(self.config, 'boo_box_purchase_enabled'))
        self.boo_box_adventure_price.init_with_adapter(get_prop_adapter(self.config, 'boo_box_adventure_price'))
        self.boo_box_craft_price.init_with_adapter(get_prop_adapter(self.config, 'boo_box_craft_price'))
        self.boo_box_sell_price.init_with_adapter(
            get_prop_adapter(self.config, "boo_box_sell_price")
        )

        # 德丰大押相关设置
        self.pawnshop_omnicoin_switch.init_with_adapter(get_prop_adapter(self.config, 'pawnshop_omnicoin_enabled'))
        priority_list = self.config.pawnshop_omnicoin_priority
        self.pawnshop_omnicoin_priority_1.set_value(priority_list[0], emit_signal=False)
        self.pawnshop_omnicoin_priority_2.set_value(priority_list[1], emit_signal=False)
        self.pawnshop_omnicoin_priority_3.set_value(priority_list[2], emit_signal=False)
        self.pawnshop_omnicoin_priority_4.set_value(priority_list[3], emit_signal=False)
        self.pawnshop_omnicoin_priority_5.set_value(priority_list[4], emit_signal=False)

        self.pawnshop_crest_switch.init_with_adapter(get_prop_adapter(self.config, 'pawnshop_crest_enabled'))
        priority_list = self.config.pawnshop_crest_priority
        self.pawnshop_crest_priority_1.set_value(priority_list[0], emit_signal=False)
        self.pawnshop_crest_priority_2.set_value(priority_list[1], emit_signal=False)
        self.pawnshop_crest_unlimited_denny_switch.init_with_adapter(get_prop_adapter(self.config, 'pawnshop_crest_unlimited_denny_enabled'))

    def _on_pawnshop_omnicoin_priority_changed(self, _) -> None:
        priority_list = [
            self.pawnshop_omnicoin_priority_1.get_value(),
            self.pawnshop_omnicoin_priority_2.get_value(),
            self.pawnshop_omnicoin_priority_3.get_value(),
            self.pawnshop_omnicoin_priority_4.get_value(),
            self.pawnshop_omnicoin_priority_5.get_value(),
        ]
        self.config.pawnshop_omnicoin_priority = priority_list

    def _on_pawnshop_crest_priority_changed(self, _) -> None:
        priority_list = [
            self.pawnshop_crest_priority_1.get_value(),
            self.pawnshop_crest_priority_2.get_value(),
        ]
        self.config.pawnshop_crest_priority = priority_list