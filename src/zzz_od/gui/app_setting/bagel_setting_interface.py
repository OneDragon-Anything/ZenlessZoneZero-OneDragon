from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QRect, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    PrimaryPushButton,
    SimpleCardWidget,
    StrongBodyLabel,
    SubtitleLabel,
    ToolButton,
)

from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.multi_selection_combo_box import MultiSelectionComboBox
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.bagel import bagel_usage
from zzz_od.application.bagel.bagel_config import (
    BagelCleanMode,
    BagelCleanQuality,
    BagelCleanStep,
    BagelCleanType,
)
from zzz_od.application.bagel.bagel_const import APP_ID, CLEAN_MODE_CUSTOM

if TYPE_CHECKING:
    from PySide6.QtGui import QResizeEvent

    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.context.zzz_context import ZContext


class _CleanStepHeightFilter(QObject):
    """复用多选设置卡的做法：下拉框变高后抬高卡片。"""

    def __init__(self, card: QWidget, fit: object) -> None:
        """过滤器挂在卡片上，生命周期与卡片一致。"""
        super().__init__(card)
        self._card: QWidget = card
        self._fit = fit

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """不拦截事件，只在尺寸变化后延迟重算。"""
        if event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, lambda: self._fit(self._card))
        return False


class _WrappedHintLabel(QLabel):
    """按当前字体和宽度计算文本高度，支持卡片随换行增高或收回。"""

    def __init__(self, text: str, parent: QWidget) -> None:
        """沿用 Fluent 说明样式，不固定说明区域的宽度。"""
        super().__init__(text, parent)
        self.setObjectName('contentLabel')
        self.setWordWrap(True)

    def _update_height(self) -> None:
        """直接测量文本，避免 heightForWidth 被旧的最小高度限制。"""
        height = self.fontMetrics().boundingRect(
            QRect(0, 0, max(1, self.width()), 10000),
            Qt.TextFlag.TextWordWrap, self.text(),
        ).height()
        self.setMinimumHeight(height)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """窗口宽度变化后重新测量。"""
        super().resizeEvent(event)
        self._update_height()

    def changeEvent(self, event: QEvent) -> None:
        """Fluent 样式或字体加载后重新测量。"""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._update_height()

    def setText(self, text: str) -> None:
        """切换出售方案后重新测量，允许高度缩小。"""
        super().setText(text)
        self._update_height()


def _wrap_card(card: SettingCardBase) -> None:
    """仅调整贝果卡片，保留文本与控件间距并支持多行说明。"""
    previous = card.contentLabel
    card.contentLabel = _WrappedHintLabel(previous.text(), card)
    card.vBoxLayout.replaceWidget(previous, card.contentLabel)
    previous.hide()
    previous.deleteLater()
    card.setMaximumHeight(16777215)
    card.setMinimumHeight(76)
    card.contentLabel.setWordWrap(True)
    card.contentLabel.setMaximumWidth(16777215)
    card.contentLabel.setMinimumWidth(0)
    card.contentLabel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    card.hBoxLayout.setContentsMargins(4, 14, 4, 14)
    card.hBoxLayout.setStretch(1, 1)
    card.hBoxLayout.setStretch(3, 0)
    card.vBoxLayout.setSpacing(4)
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
        layout.addWidget(SubtitleLabel('贝果计划', widget))
        account_hint = CaptionLabel(bagel_usage.ACCOUNT_HINT, widget)
        account_hint.setWordWrap(True)
        layout.addWidget(account_hint)
        self.usage_card: QWidget = QWidget(widget)
        tips = QHBoxLayout(self.usage_card)
        tips.setContentsMargins(0, 0, 0, 0)
        tips.setSpacing(12)
        self.hint_cards: list[SimpleCardWidget] = []
        for title, content in (
            ('角色选择', bagel_usage.ROLE_HINT),
            (bagel_usage.LOADOUT_TITLE, bagel_usage.LOADOUT_HINT),
            ('已有库存也会出售', bagel_usage.CLEAN_HINT),
        ):
            card = SimpleCardWidget(self.usage_card)
            column = QVBoxLayout(card)
            column.setContentsMargins(16, 16, 16, 16)
            column.setSpacing(8)
            heading = StrongBodyLabel(title, card)
            heading.setWordWrap(True)
            column.addWidget(heading)
            label = BodyLabel(content, card)
            label.setWordWrap(True)
            column.addWidget(label)
            column.addStretch(1)
            tips.addWidget(card, 1)
            self.hint_cards.append(card)
        self.sale_card: SimpleCardWidget = card
        self.sale_title: StrongBodyLabel = heading
        self.sale_hint: BodyLabel = label
        layout.addWidget(self.usage_card)
        self.settings_heading: SubtitleLabel = SubtitleLabel('运行与结算设置', widget)
        layout.addWidget(self.settings_heading)
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
        self.sell_interval_card: SpinBoxSettingCard = SpinBoxSettingCard(
            icon='', title='出售间隔',
            content=bagel_usage.SELL_INTERVAL_HINT,
            minimum=1, maximum=999,
        )
        layout.addWidget(self.sell_interval_card)
        self.clean_mode_card: ComboBoxSettingCard = ComboBoxSettingCard(
            icon='', title='出售方案',
            content=bagel_usage.DEFAULT_SALE_HINT,
            options_enum=BagelCleanMode,
        )
        self.clean_mode_card.value_changed.connect(self._refresh_clean_options)
        layout.addWidget(self.clean_mode_card)
        self.clean_step_list: QWidget = QWidget(widget)
        self.clean_step_layout: QVBoxLayout = QVBoxLayout(self.clean_step_list)
        self.clean_step_layout.setContentsMargins(0, 0, 0, 0)
        self.clean_step_layout.setSpacing(8)
        layout.addWidget(self.clean_step_list)
        self.clean_step_cards: list[MultiPushSettingCard] = []
        self.add_clean_step_btn: PrimaryPushButton = PrimaryPushButton(text='新增出售步骤')
        self.add_clean_step_btn.clicked.connect(self._on_add_clean_step)
        layout.addWidget(self.add_clean_step_btn)
        self.sale_validation: BodyLabel = BodyLabel(bagel_usage.INCOMPLETE_SALE_HINT, widget)
        self.sale_validation.setWordWrap(True)
        layout.addWidget(self.sale_validation)
        for card in (self.success_rounds_card, self.failure_retries_card,
                     self.auto_clean_switch, self.sell_interval_card, self.clean_mode_card):
            _wrap_card(card)
        self.success_rounds_card.spin_box.setFixedWidth(140)
        self.failure_retries_card.spin_box.setFixedWidth(140)
        self.sell_interval_card.spin_box.setFixedWidth(140)
        self.clean_mode_card.combo_box.setFixedWidth(140)
        self._refresh_clean_options()
        layout.addStretch(1)
        return widget

    def _refresh_clean_options(self, *_args: object) -> None:
        """仅开启清理时显示方案，自定义时显示可增删的出售步骤。"""
        enabled = self.auto_clean_switch.btn.isChecked()
        self.clean_mode_card.setVisible(enabled)
        self.sell_interval_card.setVisible(enabled)
        visible = enabled and self.clean_mode_card.getValue() == CLEAN_MODE_CUSTOM
        self.clean_step_list.setVisible(visible)
        self.add_clean_step_btn.setVisible(visible)
        self.sale_title.setText('已有库存也会出售' if enabled else '已关闭自动出售')
        self.sale_hint.setText(bagel_usage.CLEAN_HINT if enabled else bagel_usage.NO_CLEAN_HINT)
        # 通用卡片的 setContent 会省略长文案，此页用换行标签保留完整内容。
        self.clean_mode_card.contentLabel.setText(
            bagel_usage.CUSTOM_SALE_HINT if visible else bagel_usage.DEFAULT_SALE_HINT,
        )
        steps = () if self.config is None else self.config.clean_steps
        incomplete = any(not step.types or not step.qualities for step in steps)
        self.sale_validation.setVisible(visible and (not steps or incomplete))

    def _rebuild_clean_steps(self) -> None:
        """按当前配置重画步骤。加载时不写回。"""
        while self.clean_step_layout.count():
            item = self.clean_step_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.clean_step_cards.clear()
        if self.config is None:
            return
        for index, step in enumerate(self.config.clean_steps):
            self.clean_step_layout.addWidget(self._make_clean_step_card(index, step))
        self._refresh_clean_options()

    def _make_clean_step_card(self, index: int, step: BagelCleanStep) -> MultiPushSettingCard:
        """一步一张卡：类型、品质、上移、下移、删除。"""
        types_box = MultiSelectionComboBox(min_width=160)
        types_box.set_items([item.value for item in BagelCleanType])
        types_box.set_value(list(step.types), emit_signal=False)
        qualities_box = MultiSelectionComboBox(min_width=120)
        qualities_box.set_items([item.value for item in BagelCleanQuality])
        qualities_box.set_value(list(step.qualities), emit_signal=False)
        up_btn = ToolButton(FluentIcon.UP)
        down_btn = ToolButton(FluentIcon.DOWN)
        delete_btn = ToolButton(FluentIcon.DELETE)
        card = MultiPushSettingCard(
            icon='', title=f'第 {index + 1} 步',
            content='同一步里，类型和品质都符合才出售',
            btn_list=[types_box, qualities_box, up_btn, down_btn, delete_btn],
        )
        card.types_box = types_box
        card.qualities_box = qualities_box
        # 与多选设置卡相同：去掉固定高度，跟随下拉框换行后的最小高度。
        card.setMaximumHeight(16777215)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        height_filter = _CleanStepHeightFilter(card, self._fit_clean_step_card)
        card.height_filter = height_filter
        for box in (types_box, qualities_box):
            box.setContentsMargins(0, 9, 0, 9)
            box.installEventFilter(height_filter)
            box.selection_changed.connect(lambda _value, current=card: QTimer.singleShot(0, lambda: self._fit_clean_step_card(current)))
        types_box.selection_changed.connect(lambda _value, current=index: self._save_clean_step(current))
        qualities_box.selection_changed.connect(lambda _value, current=index: self._save_clean_step(current))
        up_btn.clicked.connect(lambda _checked=False, current=index: self._move_clean_step(current, -1))
        down_btn.clicked.connect(lambda _checked=False, current=index: self._move_clean_step(current, 1))
        delete_btn.clicked.connect(lambda _checked=False, current=index: self._delete_clean_step(current))
        self.clean_step_cards.append(card)
        return card

    def _fit_clean_step_card(self, card: MultiPushSettingCard) -> None:
        """取两个多选框里更高的一个，卡片只设置最小高度。"""
        heights = []
        for box in (card.types_box, card.qualities_box):
            margins = box.contentsMargins()
            heights.append(box._dropdown_btn.minimumHeight() + margins.top() + margins.bottom())
        card.setMinimumHeight(max(heights))
        card.updateGeometry()

    def _save_clean_step(self, index: int) -> None:
        """改完这一步立刻写入，不关闭页面。"""
        if self.config is None or not 0 <= index < len(self.clean_step_cards):
            return
        card = self.clean_step_cards[index]
        self.config.update_clean_step(index, BagelCleanStep(
            tuple(card.types_box.get_value()), tuple(card.qualities_box.get_value()),
        ))
        self._refresh_clean_options()

    def _on_add_clean_step(self) -> None:
        """追加空步骤，留在当前页继续填。"""
        if self.config is None:
            return
        self.config.add_clean_step()
        self._rebuild_clean_steps()

    def _delete_clean_step(self, index: int) -> None:
        """删掉这一步并重排序号。"""
        if self.config is None:
            return
        self.config.delete_clean_step(index)
        self._rebuild_clean_steps()

    def _move_clean_step(self, index: int, offset: int) -> None:
        """和相邻步骤交换，出售按新顺序执行。"""
        if self.config is None:
            return
        target = index + offset
        if not 0 <= target < len(self.config.clean_steps):
            return
        self.config.move_clean_step(index, target)
        self._rebuild_clean_steps()

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
        self._rebuild_clean_steps()
        self.failure_retries_card.init_with_adapter(get_prop_adapter(self.config, 'max_failure_retries'))
        self.success_rounds_card.init_with_adapter(get_prop_adapter(self.config, 'max_success_rounds'))
        self.sell_interval_card.init_with_adapter(get_prop_adapter(self.config, 'sell_interval'))
        self.auto_clean_switch._on_adapter_value_applied = self._clean_value_loaded
        self.clean_mode_card._on_adapter_value_applied = self._clean_value_loaded
