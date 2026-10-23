from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    FluentStyleSheet,
    IconWidget,
    MessageBoxBase,
    PushButton,
    ScrollArea,
    SimpleCardWidget,
    StrongBodyLabel,
    SubtitleLabel,
    TransparentPushButton,
    setCustomStyleSheet,
    setFont,
)
from qfluentwidgets.components.widgets.card_widget import CardSeparator

from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.bagel import bagel_usage
from zzz_od.application.bagel.bagel_const import (
    APP_ID,
    CLEAN_MODE_CUSTOM,
    DEFAULT_CLEAN_QUALITIES,
    DEFAULT_CLEAN_TYPES,
)
from zzz_od.gui.app_setting.bagel_setting_widgets import (
    AutoSaleSwitch,
    CleanStepCard,
    CountSpinBox,
    SaleModeSelector,
    SaleScopePreview,
    tag_row,
)

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.context.zzz_context import ZContext


class _UsageDialog(MessageBoxBase):
    """按主题折叠的使用说明，不增加启动或保存操作。"""

    def __init__(self, parent: QWidget) -> None:
        """先显示启动检查，其他规则按需展开。"""
        super().__init__(parent)
        self.widget.setFixedWidth(680)
        self.viewLayout.addWidget(SubtitleLabel('使用说明', self))
        intro = BodyLabel('先完成「开始前」的 4 项检查。其他规则可按需展开。', self)
        intro.setWordWrap(True)
        self.viewLayout.addWidget(intro)
        terms = CaptionLabel(
            '入箱：将物品装入局内安全箱。\n入仓：将携带物存入研究站仓库。\n空箱：结算开始时安全箱为空。', self
        )
        terms.setWordWrap(True)
        self.viewLayout.addWidget(terms)
        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(max(240, min(460, parent.height() - 220)))
        contents = QWidget(scroll)
        column = QVBoxLayout(contents)
        column.setContentsMargins(0, 0, 8, 0)
        column.setSpacing(10)
        for index, (title, entries) in enumerate(bagel_usage.HELP_SECTIONS):
            card = SimpleCardWidget(contents)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 10, 12, 12)
            heading = TransparentPushButton(FluentIcon.ARROW_DOWN, title, card)
            heading.setCheckable(True)
            heading.setChecked(index == 0)
            list_tag = 'ol' if index == 0 else 'ul'
            items = ''.join(
                f'<li style="margin-bottom: 8px;"><b>{escape(label)}</b>：{escape(body)}</li>'
                for label, body in entries
            )
            text = BodyLabel(
                f'<{list_tag} style="margin-top: 0; margin-bottom: 0;">{items}</{list_tag}>',
                card,
            )
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setWordWrap(True)
            text.setVisible(index == 0)
            heading.toggled.connect(text.setVisible)
            layout.addWidget(heading, 0, Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(text)
            column.addWidget(card)
        column.addStretch(1)
        scroll.setWidget(contents)
        self.viewLayout.addWidget(scroll)
        self.yesButton.setText('关闭')
        self.hideCancelButton()


class BagelSettingInterface(VerticalScrollInterface, GroupIdMixin):
    """贝果计划精简设置页，配置仍按账号和应用组即时保存。"""

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        """复用主窗口导航与滚动容器。"""
        super().__init__(
            content_widget=None,
            object_name='bagel_setting_interface',
            nav_text_cn='贝果计划设置',
            parent=parent,
        )
        self.ctx: ZContext = ctx
        self.config: BagelConfig | None = None
        self.clean_step_cards: list[CleanStepCard] = []

    def get_content_widget(self) -> QWidget:
        """显示结束条件、入箱优先级与自动出售，首次清空提示放入使用说明。"""
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(SubtitleLabel('贝果计划', widget))
        title.addWidget(CaptionLabel('设置仅用于当前账号和应用组', widget))
        header.addLayout(title)
        header.addStretch(1)
        help_button = TransparentPushButton('使用说明', widget)
        help_button.clicked.connect(self._show_usage)
        header.addWidget(help_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        layout.addWidget(self._make_end_conditions(widget))
        self.blueprint_priority: SwitchSettingCard = SwitchSettingCard(
            icon=FluentIcon.DOCUMENT,
            title='蓝图优先',
            content='开启时优先拾取蓝图。建议开启',
            parent=widget,
        )
        self.blueprint_priority.setFixedHeight(88)
        layout.addWidget(self.blueprint_priority)
        layout.addWidget(self._make_sale_group(widget))
        layout.addStretch(1)
        self._refresh_clean_options()
        return widget

    def _make_end_conditions(self, parent: QWidget) -> QWidget:
        """两个计数输入组成一句话，失败次数仅作显示换算。"""
        card = SimpleCardWidget(parent)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        sentence = QHBoxLayout()
        sentence.setSpacing(8)
        self.success_count: CountSpinBox = CountSpinBox(0, 1000, card)
        self.failure_count: CountSpinBox = CountSpinBox(1, 101, card, display_offset=1)
        self.success_count.setAccessibleName('累计成功次数')
        self.failure_count.setAccessibleName('累计失败次数')
        sentence.addWidget(BodyLabel('累计成功', card))
        sentence.addWidget(self.success_count)
        sentence.addWidget(BodyLabel('次 或 累计失败', card))
        sentence.addWidget(self.failure_count)
        sentence.addWidget(BodyLabel('次后结束任务', card))
        sentence.addStretch(1)
        layout.addLayout(sentence)
        layout.addWidget(
            CaptionLabel('成功次数填 0 表示不限。异常时可能提前停止。', card)
        )
        return card

    def _make_sale_group(self, parent: QWidget) -> QWidget:
        """自动出售父卡片包含间隔、范围和步骤；关闭时收起。"""
        card = SimpleCardWidget(parent)
        card.setBorderRadius(8)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(20, 17, 22, 17)
        header.setSpacing(12)
        icon = IconWidget(FluentIcon.TAG, card)
        icon.setFixedSize(24, 24)
        header.addWidget(icon)
        header.addWidget(StrongBodyLabel('自动出售', card), 1)
        self.auto_clean_switch: AutoSaleSwitch = AutoSaleSwitch(card)
        self.auto_clean_switch.state_changed.connect(self._refresh_clean_options)
        header.addWidget(self.auto_clean_switch)
        layout.addLayout(header)
        layout.addWidget(CardSeparator(card))
        self.sale_children: QFrame = QFrame(card)
        self.sale_children.setObjectName('saleChildren')
        self.sale_children.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        FluentStyleSheet.CARD_WIDGET.apply(self.sale_children)
        setCustomStyleSheet(
            self.sale_children,
            'QFrame#saleChildren { background: #fafbfc; border: none; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }',
            'QFrame#saleChildren { background: #25262a; border: none; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }',
        )
        children = QVBoxLayout(self.sale_children)
        children.setContentsMargins(60, 20, 22, 22)
        children.setSpacing(14)
        interval = QHBoxLayout()
        interval.setSpacing(8)
        self.sell_interval: CountSpinBox = CountSpinBox(1, 999, self.sale_children)
        self.sell_interval.setAccessibleName('出售间隔')
        interval.addWidget(BodyLabel('每累计入仓', self.sale_children))
        interval.addWidget(self.sell_interval)
        interval.addWidget(BodyLabel('次后出售', self.sale_children))
        interval.addStretch(1)
        children.addLayout(interval)
        warning = QVBoxLayout()
        warning.setSpacing(2)
        warning_title = StrongBodyLabel('已有库存也会出售', self.sale_children)
        warning_title.setTextColor('#805000', '#e9c986')
        warning.addWidget(warning_title)
        safe_hint = CaptionLabel(
            '安全箱内符合出售条件的物品也可能被出售。', self.sale_children
        )
        safe_hint.setWordWrap(True)
        warning.addWidget(safe_hint)
        children.addLayout(warning)
        children.addWidget(CardSeparator(self.sale_children))
        scope_header = QHBoxLayout()
        scope_header.setSpacing(20)
        scope_header.addWidget(StrongBodyLabel('出售范围', self.sale_children))
        self.clean_mode: SaleModeSelector = SaleModeSelector(self.sale_children)
        self.clean_mode.state_changed.connect(self._refresh_clean_options)
        scope_header.addWidget(self.clean_mode)
        scope_header.addStretch(1)
        children.addLayout(scope_header)
        self.default_scope: QWidget = self._make_default_scope(self.sale_children)
        children.addWidget(self.default_scope)
        self.custom_scope: QWidget = self._make_custom_scope(self.sale_children)
        children.addWidget(self.custom_scope)
        layout.addWidget(self.sale_children)
        self.sale_disabled: CaptionLabel = CaptionLabel('只入仓，不出售。', card)
        self.sale_disabled.setContentsMargins(60, 13, 22, 15)
        layout.addWidget(self.sale_disabled)
        return card

    def _make_default_scope(self, parent: QWidget) -> QWidget:
        """默认范围以标签显示，数据使用业务常量。"""
        widget = QWidget(parent)
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)
        layout.addWidget(CaptionLabel('物品类型', widget), 0, 0)
        layout.addWidget(tag_row(DEFAULT_CLEAN_TYPES, widget), 0, 1)
        layout.addWidget(CaptionLabel('品质', widget), 1, 0)
        layout.addWidget(tag_row(DEFAULT_CLEAN_QUALITIES, widget), 1, 1)
        layout.addWidget(CardSeparator(widget), 2, 0, 1, 2)
        label = CaptionLabel('默认不出售 Z 品质、装备、战术道具和门禁卡。', widget)
        label.setWordWrap(True)
        layout.addWidget(label, 3, 0, 1, 2)
        return widget

    def _make_custom_scope(self, parent: QWidget) -> QWidget:
        """自定义编辑区下方只有一份总预览。"""
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        hint = CaptionLabel(
            '每步都要选择类型和品质，同时符合才出售。按从上到下的顺序执行。', widget
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.clean_step_layout: QVBoxLayout = QVBoxLayout()
        self.clean_step_layout.setSpacing(10)
        layout.addLayout(self.clean_step_layout)
        self.empty_steps: BodyLabel = BodyLabel(
            '先添加一步，再选择要出售的类型和品质。', widget
        )
        layout.addWidget(self.empty_steps)
        self.add_clean_step_btn: PushButton = PushButton(
            FluentIcon.ADD, '新增出售步骤', widget
        )
        self.add_clean_step_btn.clicked.connect(self._on_add_clean_step)
        layout.addWidget(self.add_clean_step_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.sale_validation: BodyLabel = BodyLabel(widget)
        self.sale_validation.setWordWrap(True)
        self.sale_validation.setTextColor('#a4262c', '#f0b6bb')
        layout.addWidget(self.sale_validation)
        self.z_warning: QLabel = QLabel(
            '已选择 Z 品质或装备类型。红色物品会被出售，请注意确认。', widget
        )
        self.z_warning.setWordWrap(True)
        self.z_warning.setObjectName('zWarning')
        FluentStyleSheet.LABEL.apply(self.z_warning)
        setFont(self.z_warning, 14)
        setCustomStyleSheet(
            self.z_warning,
            'QLabel#zWarning { color: #805000; background: #fff8eb; border: 1px solid #e8d3a7; border-radius: 5px; padding: 10px 12px; }',
            'QLabel#zWarning { color: #e9c986; background: #342b23; border: 1px solid #67503b; border-radius: 5px; padding: 10px 12px; }',
        )
        layout.addWidget(self.z_warning)
        self.total_preview: SaleScopePreview = SaleScopePreview(widget)
        layout.addWidget(self.total_preview)
        return widget

    def _refresh_clean_options(self) -> None:
        """只更新可见区域与总预览，不重建正在操作的多选菜单。"""
        enabled = self.auto_clean_switch.isChecked()
        custom = self.clean_mode.currentRouteKey() == CLEAN_MODE_CUSTOM
        self.sale_children.setVisible(enabled)
        self.sale_disabled.setVisible(not enabled)
        self.default_scope.setVisible(not custom)
        self.custom_scope.setVisible(custom)
        steps = [] if self.config is None else self.config.clean_steps
        incomplete = [
            str(index + 1)
            for index, step in enumerate(steps)
            if not step.types or not step.qualities
        ]
        self.empty_steps.setVisible(not steps)
        if not steps:
            validation = '尚未添加出售步骤，任务无法启动。请新增一步，或改用默认方案。'
        elif incomplete:
            validation = f'第 {"、".join(incomplete)} 步未选全类型和品质，任务无法启动。请补全选项，或删除未选全的步骤。'
        else:
            validation = ''
        self.sale_validation.setText(validation)
        self.sale_validation.setVisible(bool(validation))
        self.z_warning.setVisible(any('Z' in step.qualities for step in steps))
        self.total_preview.set_steps(steps)

    def _rebuild_clean_steps(self) -> None:
        """仅加载、增删或排序时重建；编辑选项时保留菜单与滚动位置。"""
        while self.clean_step_layout.count():
            item = self.clean_step_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self.clean_step_cards.clear()
        steps = [] if self.config is None else self.config.clean_steps
        for index, step in enumerate(steps):
            card = CleanStepCard(index, len(steps), step, self.custom_scope)
            card.changed.connect(lambda current=index: self._save_clean_step(current))
            card.move_requested.connect(
                lambda offset, current=index: self._move_clean_step(current, offset)
            )
            card.delete_requested.connect(
                lambda current=index: self._delete_clean_step(current)
            )
            self.clean_step_layout.addWidget(card)
            self.clean_step_cards.append(card)
        self._refresh_clean_options()

    def _save_clean_step(self, index: int) -> None:
        """改完这一步立刻写入，不关闭菜单或重建步骤。"""
        if self.config is None or not 0 <= index < len(self.clean_step_cards):
            return
        self.config.update_clean_step(index, self.clean_step_cards[index].value())
        self._refresh_clean_options()

    def _on_add_clean_step(self) -> None:
        """追加空步骤，保留不完整配置提示。"""
        if self.config is not None:
            self.config.add_clean_step()
            self._rebuild_clean_steps()

    def _delete_clean_step(self, index: int) -> None:
        """删除指定步骤并刷新总预览。"""
        if self.config is not None:
            self.config.delete_clean_step(index)
            self._rebuild_clean_steps()

    def _move_clean_step(self, index: int, offset: int) -> None:
        """与相邻步骤交换，只改变原有执行顺序。"""
        if self.config is None:
            return
        target = index + offset
        if 0 <= target < len(self.config.clean_steps):
            self.config.move_clean_step(index, target)
            self._rebuild_clean_steps()

    def _show_usage(self) -> None:
        """在主窗口内打开说明，不启动任何游戏操作。"""
        dialog = _UsageDialog(self.window())
        dialog.exec()
        dialog.deleteLater()

    def on_interface_shown(self) -> None:
        """进入页面后绑定当前账号和应用组。"""
        super().on_interface_shown()
        self.init_config()

    def init_config(self) -> None:
        """加载时阻断保存信号，旧的异步加载由适配器代次机制丢弃。"""
        self.config = self.ctx.run_context.get_config(
            app_id=APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.blueprint_priority.init_with_adapter(
            get_prop_adapter(self.config, 'blueprint_priority'),
        )
        for control, field in (
            (self.success_count, 'max_success_rounds'),
            (self.failure_count, 'max_failure_retries'),
            (self.sell_interval, 'sell_interval'),
            (self.auto_clean_switch, 'auto_clean_warehouse'),
            (self.clean_mode, 'clean_mode'),
        ):
            control.setEnabled(False)
            control.init_with_adapter(get_prop_adapter(self.config, field))
        self._rebuild_clean_steps()
