from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, HyperlinkButton, SimpleCardWidget, StrongBodyLabel

from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_selection_combo_box_setting_card import (
    MultiSelectionComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.bagel import bagel_usage
from zzz_od.application.bagel.bagel_config import (
    BagelCleanMode,
    BagelCleanQuality,
    BagelCleanType,
)
from zzz_od.application.bagel.bagel_const import APP_ID, CLEAN_MODE_CUSTOM

if TYPE_CHECKING:
    from PySide6.QtGui import QResizeEvent

    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.context.zzz_context import ZContext


class _BagelMultiSelectionCard(MultiSelectionComboBoxSettingCard):
    """贝果筛选使用无信号赋值，并同步选中项说明。"""

    def _set_value_from_adapter(self, value: list[str] | None) -> None:
        """明确走多选接口，避免通用适配器选中 Fluent 父类的 setValue。"""
        self.set_value(value, emit_signal=False)


class _WrappedHintLabel(QLabel):
    """根据当前宽度保留完整文案所需高度。"""

    def __init__(self, text: str, parent: QWidget) -> None:
        """沿用设置卡片的文本样式和自动换行。"""
        super().__init__(text, parent)
        self.setObjectName('contentLabel')
        self.setWordWrap(True)
        self.setMaximumWidth(500)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """宽度改变后通知布局，避免滚动容器压缩多行文本。"""
        super().resizeEvent(event)
        self.setMinimumHeight(self.heightForWidth(self.width()))

    def setText(self, text: str) -> None:
        """出售方案切换时按新文案重新计算高度。"""
        super().setText(text)
        self.setMinimumHeight(self.heightForWidth(self.width()))


def _wrap_card(card: SettingCardBase) -> None:
    """仅调整贝果设置卡片的换行和高度，不改通用组件。"""
    previous = card.contentLabel
    card.contentLabel = _WrappedHintLabel(previous.text(), card)
    card.vBoxLayout.replaceWidget(previous, card.contentLabel)
    previous.hide()
    previous.deleteLater()
    card.setMaximumHeight(16777215)
    card.setMinimumHeight(76)
    card.contentLabel.setWordWrap(True)
    card.contentLabel.setMinimumWidth(0)
    card.contentLabel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    card.hBoxLayout.setContentsMargins(16, 12, 16, 12)
    card.hBoxLayout.setStretch(1, 1)
    card.hBoxLayout.setStretch(3, 0)
    card.vBoxLayout.setAlignment(card.contentLabel, Qt.AlignmentFlag(0))
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


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
        self.usage_card: SimpleCardWidget = SimpleCardWidget(widget)
        tips = QVBoxLayout(self.usage_card)
        tips.setContentsMargins(16, 16, 16, 16)
        tips.setSpacing(8)
        for title, content in (
            ('角色选择', bagel_usage.ROLE_HINT),
            (bagel_usage.LOADOUT_TITLE, bagel_usage.LOADOUT_HINT),
        ):
            tips.addWidget(StrongBodyLabel(title, self.usage_card))
            label = BodyLabel(content, self.usage_card)
            label.setWordWrap(True)
            tips.addWidget(label)
        self.sale_title: StrongBodyLabel = StrongBodyLabel('已有库存也会出售', self.usage_card)
        self.sale_hint: BodyLabel = BodyLabel(bagel_usage.CLEAN_HINT, self.usage_card)
        self.sale_hint.setWordWrap(True)
        tips.addWidget(self.sale_title)
        tips.addWidget(self.sale_hint)
        self.guide_link: HyperlinkButton = HyperlinkButton(
            bagel_usage.GUIDE_URL, '使用说明与问题反馈', self.usage_card,
        )
        tips.addWidget(self.guide_link)
        layout.addWidget(self.usage_card)
        account_hint = BodyLabel(bagel_usage.ACCOUNT_HINT, widget)
        account_hint.setWordWrap(True)
        layout.addWidget(account_hint)
        self.success_rounds_card: SpinBoxSettingCard = SpinBoxSettingCard(
            icon='', title='成功次数', content=bagel_usage.SUCCESS_HINT,
            minimum=0, maximum=1000,
        )
        layout.addWidget(self.success_rounds_card)
        self.failure_retries_card: SpinBoxSettingCard = SpinBoxSettingCard(
            icon='', title='整体重试次数',
            content=bagel_usage.RETRY_HINT,
            minimum=0, maximum=100,
        )
        layout.addWidget(self.failure_retries_card)
        self.auto_clean_switch: SwitchSettingCard = SwitchSettingCard(
            icon='',
            title='清理仓库',
            content=bagel_usage.CLEAN_SWITCH_HINT,
        )
        self.auto_clean_switch.value_changed.connect(self._refresh_clean_options)
        layout.addWidget(self.auto_clean_switch)
        self.clean_mode_card: ComboBoxSettingCard = ComboBoxSettingCard(
            icon='', title='出售方案',
            content=bagel_usage.DEFAULT_SALE_HINT,
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
        self.sale_validation: BodyLabel = BodyLabel(bagel_usage.INCOMPLETE_SALE_HINT, widget)
        self.sale_validation.setWordWrap(True)
        layout.addWidget(self.sale_validation)
        self.clean_types_card.value_changed.connect(self._refresh_clean_options)
        self.clean_qualities_card.value_changed.connect(self._refresh_clean_options)
        for card in (self.success_rounds_card, self.failure_retries_card,
                     self.auto_clean_switch, self.clean_mode_card):
            _wrap_card(card)
        self._refresh_clean_options()
        layout.addStretch(1)
        return widget

    def _refresh_clean_options(self, *_args: object) -> None:
        """仅开启清理时显示方案，自定义时显示两组筛选。"""
        enabled = self.auto_clean_switch.btn.isChecked()
        self.clean_mode_card.setVisible(enabled)
        visible = enabled and self.clean_mode_card.getValue() == CLEAN_MODE_CUSTOM
        self.clean_types_card.setVisible(visible)
        self.clean_qualities_card.setVisible(visible)
        self.sale_title.setText('已有库存也会出售' if enabled else '已关闭自动出售')
        self.sale_hint.setText(bagel_usage.CLEAN_HINT if enabled else bagel_usage.NO_CLEAN_HINT)
        # 通用卡片的 setContent 会省略长文案，此页用换行标签保留完整内容。
        self.clean_mode_card.contentLabel.setText(
            bagel_usage.CUSTOM_SALE_HINT if visible else bagel_usage.DEFAULT_SALE_HINT,
        )
        self.sale_validation.setVisible(visible and (
            not self.clean_types_card.get_value() or not self.clean_qualities_card.get_value()
        ))

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
        self.auto_clean_switch._on_adapter_value_applied = self._clean_value_loaded
        self.clean_mode_card._on_adapter_value_applied = self._clean_value_loaded
        self.clean_types_card._on_adapter_value_applied = self._clean_value_loaded
        self.clean_qualities_card._on_adapter_value_applied = self._clean_value_loaded
