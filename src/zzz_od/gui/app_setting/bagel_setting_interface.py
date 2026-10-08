from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QVBoxLayout, QWidget

from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_selection_combo_box_setting_card import (
    MultiSelectionComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.bagel.bagel_config import (
    BagelCleanMode,
    BagelCleanQuality,
    BagelCleanType,
)
from zzz_od.application.bagel.bagel_const import APP_ID, CLEAN_MODE_CUSTOM

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.context.zzz_context import ZContext


class _BagelMultiSelectionCard(MultiSelectionComboBoxSettingCard):
    """贝果筛选使用无信号赋值，并同步选中项说明。"""

    def _set_value_from_adapter(self, value: list[str] | None) -> None:
        """明确走多选接口，避免通用适配器选中 Fluent 父类的 setValue。"""
        self.set_value(value, emit_signal=False)


class BagelSettingInterface(VerticalScrollInterface, GroupIdMixin):
    """贝果计划的完整设置页，复用主窗口导航与滚动容器。"""

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        """创建设置页，配置在每次进入时绑定当前账号和应用组。"""
        super().__init__(
            content_widget=None,
            object_name='bagel_setting_interface',
            nav_text_cn='贝果计划设置',
            parent=parent,
        )
        self.ctx: ZContext = ctx
        self.config: BagelConfig | None = None

    def get_content_widget(self) -> QWidget:
        """构建可滚动的设置卡片列表。"""
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.success_rounds_card: SpinBoxSettingCard = SpinBoxSettingCard(
            icon='', title='成功次数', content='成功局数上限；填 0 不限次数。',
            minimum=0, maximum=1000,
        )
        layout.addWidget(self.success_rounds_card)
        self.failure_retries_card: SpinBoxSettingCard = SpinBoxSettingCard(
            icon='', title='整体重试次数',
            content='失败后最多额外重开多少局；成功不清零，填 0 不重开。',
            minimum=0, maximum=100,
        )
        layout.addWidget(self.failure_retries_card)
        self.auto_clean_switch: SwitchSettingCard = SwitchSettingCard(
            icon='',
            title='清理仓库',
            content='成功与失败局入仓后清理仓库',
        )
        self.auto_clean_switch.value_changed.connect(self._refresh_clean_options)
        layout.addWidget(self.auto_clean_switch)
        self.sell_interval_card: SpinBoxSettingCard = SpinBoxSettingCard(
            icon='', title='出售频率',
            content='多少个成功入仓局出售一次，填 1 表示每局都卖。仓库已满时不受此限制，照样出售腾位。',
            minimum=1, maximum=999,
        )
        layout.addWidget(self.sell_interval_card)
        self.clean_mode_card: ComboBoxSettingCard = ComboBoxSettingCard(
            icon='', title='出售方案',
            content='默认出售贵重物品、战术棱镜和其他物品的 C–S 品质',
            options_enum=BagelCleanMode,
        )
        self.clean_mode_card.value_changed.connect(self._refresh_clean_options)
        layout.addWidget(self.clean_mode_card)
        self.clean_types_card: _BagelMultiSelectionCard = _BagelMultiSelectionCard(
            icon='', title='出售类型', options_enum=BagelCleanType,
        )
        layout.addWidget(self.clean_types_card)
        self.clean_qualities_card: _BagelMultiSelectionCard = _BagelMultiSelectionCard(
            icon='', title='出售品质', options_enum=BagelCleanQuality,
        )
        layout.addWidget(self.clean_qualities_card)
        layout.addStretch(1)
        return widget

    def _refresh_clean_options(self, *_args: object) -> None:
        """仅开启清理时显示方案，自定义时显示两组筛选。"""
        enabled = self.auto_clean_switch.btn.isChecked()
        self.clean_mode_card.setVisible(enabled)
        self.sell_interval_card.setVisible(enabled)
        visible = enabled and self.clean_mode_card.getValue() == CLEAN_MODE_CUSTOM
        self.clean_types_card.setVisible(visible)
        self.clean_qualities_card.setVisible(visible)

    def _clean_value_loaded(self, _value: object) -> None:
        """适配器异步载入后同步选项的显示状态。"""
        self._refresh_clean_options()

    def on_interface_shown(self) -> None:
        """进入页面时初始化布局并重新绑定当前账号与应用组。"""
        super().on_interface_shown()
        self.init_config()

    def init_config(self) -> None:
        """绑定当前账号与应用组，刷新时不写配置。"""
        self.config = self.ctx.run_context.get_config(
            app_id=APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.auto_clean_switch.init_with_adapter(
            get_prop_adapter(self.config, 'auto_clean_warehouse'),
        )
        self.clean_mode_card.init_with_adapter(get_prop_adapter(self.config, 'clean_mode'))
        self.clean_types_card.init_with_adapter(get_prop_adapter(self.config, 'clean_types'))
        self.clean_qualities_card.init_with_adapter(get_prop_adapter(self.config, 'clean_qualities'))
        self.failure_retries_card.init_with_adapter(get_prop_adapter(self.config, 'max_failure_retries'))
        self.success_rounds_card.init_with_adapter(get_prop_adapter(self.config, 'max_success_rounds'))
        self.sell_interval_card.init_with_adapter(get_prop_adapter(self.config, 'sell_interval'))
        self.auto_clean_switch._on_adapter_value_applied = self._clean_value_loaded
        self.clean_mode_card._on_adapter_value_applied = self._clean_value_loaded
