from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.column import Column
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.context.zzz_context import ZContext


class StatusDisplayCard(SettingCardBase):
    """功能完成状态显示卡片"""

    def __init__(self, icon, title, ctx: ZContext, feature_type: str, parent=None):
        super().__init__(icon, title, parent=parent)
        self.ctx = ctx
        self.feature_type = feature_type

        # 创建状态显示标签
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(80)

        # 添加到布局
        self.hBoxLayout.addWidget(self.status_label)

        # 初始化状态显示
        self.update_status()

    def update_status(self):
        """更新状态显示"""
        config = self.ctx.suibian_temple_config

        # 检查总开关是否启用
        if not config.overall_enabled:
            self.status_label.setText("总开关已关闭")
            self.status_label.setStyleSheet("color: #666666; font-weight: bold;")
            self.iconLabel.setIcon(FluentIcon.PAUSE.icon(color="#666666"))
            return

        # 检查对应功能开关是否启用
        feature_enabled = self._is_feature_enabled()
        if not feature_enabled:
            self.status_label.setText("功能已禁用")
            self.status_label.setStyleSheet("color: #666666; font-weight: bold;")
            self.iconLabel.setIcon(FluentIcon.PAUSE.icon(color="#666666"))
            return

        # 检查完成状态
        status = self._get_completion_status()

        if status == AppRunRecord.STATUS_SUCCESS:
            self.status_label.setText("已完成")
            self.status_label.setStyleSheet("color: #0078d4; font-weight: bold;")
            self.iconLabel.setIcon(FluentIcon.COMPLETED.icon(color=FluentThemeColor.DEFAULT_BLUE.value))
        elif status == AppRunRecord.STATUS_RUNNING:
            self.status_label.setText("运行中")
            self.status_label.setStyleSheet("color: #ff8c00; font-weight: bold;")
            self.iconLabel.setIcon(FluentIcon.SYNC)
        elif status == AppRunRecord.STATUS_FAIL:
            self.status_label.setText("执行失败")
            self.status_label.setStyleSheet("color: #d13438; font-weight: bold;")
            self.iconLabel.setIcon(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value))
        else:  # STATUS_WAIT
            self.status_label.setText("未完成")
            self.status_label.setStyleSheet("color: #666666; font-weight: bold;")
            self.iconLabel.setIcon(FluentIcon.INFO)

    def _is_feature_enabled(self) -> bool:
        """检查对应功能是否启用"""
        config = self.ctx.suibian_temple_config

        if self.feature_type == 'adventure_squad':
            return config.adventure_squad_enabled
        elif self.feature_type == 'craft':
            return config.craft_enabled
        elif self.feature_type == 'yum_cha_sin':
            return config.yum_cha_sin_enabled
        elif self.feature_type == 'boobox':
            return config.boobox_enabled
        else:
            return False

    def _get_completion_status(self) -> int:
        """获取功能完成状态"""
        if self.feature_type == 'adventure_squad':
            # 小队游历功能完成状态
            # 检查随便观记录 - 如果随便观整体成功且小队游历功能启用，认为已完成
            record = self.ctx.suibian_temple_record
            return record.run_status_under_now

        elif self.feature_type == 'craft':
            # 制造坊功能完成状态
            # 检查随便观记录 - 如果随便观整体成功且制造坊功能启用，认为已完成
            record = self.ctx.suibian_temple_record
            return record.run_status_under_now

        elif self.feature_type == 'yum_cha_sin':
            # 饮茶仙功能完成状态
            # 检查随便观记录 - 如果随便观整体成功且饮茶仙功能启用，认为已完成
            record = self.ctx.suibian_temple_record
            return record.run_status_under_now

        elif self.feature_type == 'boobox':
            # 邦巢功能完成状态
            # 检查邦巢记录 - 邦巢有独立的记录
            record = self.ctx.boobox_run_record
            return record.run_status_under_now

        else:
            return AppRunRecord.STATUS_WAIT


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

        # 小队游历开关和状态
        self.adventure_squad_switch = SwitchSettingCard(
            icon=FluentIcon.PEOPLE,
            title='小队游历',
            content='控制是否执行小队游历功能'
        )
        content_widget.add_widget(self.adventure_squad_switch)

        self.adventure_squad_status = StatusDisplayCard(
            icon=FluentIcon.PEOPLE,
            title='小队游历完成状态',
            ctx=self.ctx,
            feature_type='adventure_squad'
        )
        content_widget.add_widget(self.adventure_squad_status)

        # 制造坊开关和状态
        self.craft_switch = SwitchSettingCard(
            icon=FluentIcon.SETTING,
            title='制造坊',
            content='控制是否执行制造坊功能'
        )
        content_widget.add_widget(self.craft_switch)

        self.craft_status = StatusDisplayCard(
            icon=FluentIcon.SETTING,
            title='制造坊完成状态',
            ctx=self.ctx,
            feature_type='craft'
        )
        content_widget.add_widget(self.craft_status)

        # 饮茶仙开关和状态
        self.yum_cha_sin_switch = SwitchSettingCard(
            icon=FluentIcon.CAFE,
            title='饮茶仙',
            content='控制是否执行饮茶仙功能'
        )
        content_widget.add_widget(self.yum_cha_sin_switch)

        self.yum_cha_sin_status = StatusDisplayCard(
            icon=FluentIcon.CAFE,
            title='饮茶仙完成状态',
            ctx=self.ctx,
            feature_type='yum_cha_sin'
        )
        content_widget.add_widget(self.yum_cha_sin_status)

        # 邦巢开关和状态
        self.boobox_switch = SwitchSettingCard(
            icon=FluentIcon.HOME,
            title='邦巢',
            content='控制是否执行邦巢功能'
        )
        content_widget.add_widget(self.boobox_switch)

        self.boobox_status = StatusDisplayCard(
            icon=FluentIcon.HOME,
            title='邦巢完成状态',
            ctx=self.ctx,
            feature_type='boobox'
        )
        content_widget.add_widget(self.boobox_status)

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

        # 更新状态显示
        self._update_status_displays()

    def _on_overall_switch_changed(self, value: bool) -> None:
        """总开关变更时的处理"""
        # 保存配置
        self.ctx.suibian_temple_config.save()

        # 更新子开关状态
        self._update_sub_switches_state()

        # 更新状态显示
        self._update_status_displays()

    def _on_feature_switch_changed(self, feature: str, value: bool) -> None:
        """功能开关变更时的处理"""
        # 配置已经通过adapter自动更新，这里只需要保存
        self.ctx.suibian_temple_config.save()

        # 更新状态显示
        self._update_status_displays()

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

    def _update_status_displays(self) -> None:
        """更新所有状态显示"""
        self.adventure_squad_status.update_status()
        self.craft_status.update_status()
        self.yum_cha_sin_status.update_status()
        self.boobox_status.update_status()

    def refresh_status_displays(self) -> None:
        """公共方法：刷新状态显示"""
        self._update_status_displays()