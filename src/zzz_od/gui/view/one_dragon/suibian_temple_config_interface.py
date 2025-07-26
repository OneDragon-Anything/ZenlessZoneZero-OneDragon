from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.column import Column
from zzz_od.context.zzz_context import ZContext


class SuibianTempleConfigInterface(VerticalScrollInterface):
    """随便观配置界面"""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_suibian_temple_config_interface',
            content_widget=None, parent=parent,
            nav_text_cn='随便观配置'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        # 总开关
        self.overall_switch = SwitchSettingCard(
            icon=FluentIcon.SETTING,
            title='总开关',
            content='控制是否执行任何随便观功能'
        )
        content_widget.add_widget(self.overall_switch)

        # 小队游历开关
        self.adventure_squad_switch = SwitchSettingCard(
            icon=FluentIcon.PEOPLE,
            title='小队游历',
            content='控制是否执行小队游历功能'
        )
        content_widget.add_widget(self.adventure_squad_switch)

        # 制造坊开关
        self.craft_switch = SwitchSettingCard(
            icon=FluentIcon.SETTING,
            title='制造坊',
            content='控制是否执行制造坊功能'
        )
        content_widget.add_widget(self.craft_switch)

        # 饮茶仙开关
        self.yum_cha_sin_switch = SwitchSettingCard(
            icon=FluentIcon.CAFE,
            title='饮茶仙',
            content='控制是否执行饮茶仙功能'
        )
        content_widget.add_widget(self.yum_cha_sin_switch)

        # 邦巢开关
        self.boobox_switch = SwitchSettingCard(
            icon=FluentIcon.HOME,
            title='邦巢',
            content='控制是否执行邦巢功能'
        )
        content_widget.add_widget(self.boobox_switch)

        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        # 初始化开关状态，连接到配置
        self.overall_switch.init_with_adapter(
            self.ctx.suibian_temple_config.get_prop_adapter('overall_enabled')
        )
        self.adventure_squad_switch.init_with_adapter(
            self.ctx.suibian_temple_config.get_prop_adapter('adventure_squad_enabled')
        )
        self.craft_switch.init_with_adapter(
            self.ctx.suibian_temple_config.get_prop_adapter('craft_enabled')
        )
        self.yum_cha_sin_switch.init_with_adapter(
            self.ctx.suibian_temple_config.get_prop_adapter('yum_cha_sin_enabled')
        )
        self.boobox_switch.init_with_adapter(
            self.ctx.suibian_temple_config.get_prop_adapter('boobox_enabled')
        )

        # 连接总开关变更事件
        self.overall_switch.value_changed.connect(self._on_overall_switch_changed)

        # 连接各功能开关变更事件
        self.adventure_squad_switch.value_changed.connect(
            lambda value: self._on_feature_switch_changed('adventure_squad_enabled', value)
        )
        self.craft_switch.value_changed.connect(
            lambda value: self._on_feature_switch_changed('craft_enabled', value)
        )
        self.yum_cha_sin_switch.value_changed.connect(
            lambda value: self._on_feature_switch_changed('yum_cha_sin_enabled', value)
        )
        self.boobox_switch.value_changed.connect(
            lambda value: self._on_feature_switch_changed('boobox_enabled', value)
        )

        # 同步配置状态到界面
        self._sync_config_state_to_interface()

        # 更新子开关状态
        self._update_sub_switches_state()

    def _on_overall_switch_changed(self, value: bool) -> None:
        """总开关变更时的处理"""
        # 保存配置
        self.ctx.suibian_temple_config.save()

        # 更新子开关状态
        self._update_sub_switches_state()

    def _on_feature_switch_changed(self, feature: str, value: bool) -> None:
        """功能开关变更时的处理"""
        # 配置已经通过adapter自动更新，这里只需要保存
        self.ctx.suibian_temple_config.save()

    def _sync_config_state_to_interface(self) -> None:
        """同步配置状态到界面显示"""
        # 获取当前配置状态
        config = self.ctx.suibian_temple_config

        # 同步各开关状态（adapter已经处理了基本同步，这里处理额外的状态）
        # 确保界面状态与配置完全一致
        pass  # adapter已经处理了状态同步

    def _update_sub_switches_state(self) -> None:
        """更新子开关的启用状态"""
        overall_enabled = self.ctx.suibian_temple_config.overall_enabled

        # 当总开关关闭时，禁用所有子开关
        self.adventure_squad_switch.setEnabled(overall_enabled)
        self.craft_switch.setEnabled(overall_enabled)
        self.yum_cha_sin_switch.setEnabled(overall_enabled)
        self.boobox_switch.setEnabled(overall_enabled)