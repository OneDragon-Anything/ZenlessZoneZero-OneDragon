"""贝果设置页的句式输入、步骤编辑与范围预览组件。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FlowLayout,
    FluentIcon,
    FluentStyleSheet,
    IndicatorPosition,
    SegmentedWidget,
    SimpleCardWidget,
    SpinBox,
    StrongBodyLabel,
    SwitchButton,
    TransparentPushButton,
    TransparentToolButton,
    setCustomStyleSheet,
    setFont,
)

from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.multi_selection_combo_box import MultiSelectionComboBox
from zzz_od.application.bagel.bagel_config import (
    BagelCleanMode,
    BagelCleanQuality,
    BagelCleanStep,
    BagelCleanType,
)
from zzz_od.application.bagel.bagel_const import (
    CLEAN_MODE_DEFAULT,
    CLEAN_QUALITIES,
    CLEAN_TYPES,
)

if TYPE_CHECKING:
    from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class CountSpinBox(SpinBox, AdapterInitMixin):
    """句式中的计数输入；显示偏移只用于界面，不改变配置语义。"""

    def __init__(
        self, minimum: int, maximum: int, parent: QWidget, display_offset: int = 0
    ) -> None:
        """设置范围，失败上限通过偏移 1 显示为累计失败次数。"""
        SpinBox.__init__(self, parent)
        AdapterInitMixin.__init__(self)
        self._display_offset: int = display_offset
        self.setRange(minimum, maximum)
        # Fluent 的两个步进按钮并排显示，须为四位数保留输入宽度。
        self.setFixedWidth(140)
        self.setKeyboardTracking(False)
        self.valueChanged.connect(self._save_value)

    def _get_adapter_value(self, adapter: YamlConfigAdapter) -> int:
        """读取后加上显示偏移。"""
        return adapter.get_value() + self._display_offset

    def _set_value_from_adapter(self, value: int) -> None:
        """阻断初始化信号，防止加载时写回。"""
        with QtCore.QSignalBlocker(self):
            self.setValue(value)
        self.setEnabled(True)

    def _save_value(self, value: int) -> None:
        """用户修改后减去偏移，再即时保存。"""
        if self.adapter is not None:
            self.adapter.set_value(value - self._display_offset)


class AutoSaleSwitch(SwitchButton, AdapterInitMixin):
    """绑定自动出售开关，载入与编辑后都通知页面更新子设置。"""

    state_changed = Signal()

    def __init__(self, parent: QWidget) -> None:
        """沿用 Fluent 开关和适配器。"""
        SwitchButton.__init__(self, parent, indicatorPos=IndicatorPosition.RIGHT)
        AdapterInitMixin.__init__(self)
        self.setOnText('已开启')
        self.setOffText('已关闭')
        self.setAccessibleName('自动出售')
        self.checkedChanged.connect(self._save_value)

    def _set_value_from_adapter(self, value: bool) -> None:
        """载入开关值，不发送保存信号。"""
        with QtCore.QSignalBlocker(self):
            self.setChecked(value)
        self.setEnabled(True)
        self.state_changed.emit()

    def _save_value(self, value: bool) -> None:
        """先保存开关，再刷新可见区域。"""
        if self.adapter is not None:
            self.adapter.set_value(value)
        self.state_changed.emit()


class SaleModeSelector(SegmentedWidget, AdapterInitMixin):
    """紧邻出售范围标题的默认、自定义切换。"""

    state_changed = Signal()

    def __init__(self, parent: QWidget) -> None:
        """从现有枚举创建选项，不增加方案或保存步骤。"""
        SegmentedWidget.__init__(self, parent)
        AdapterInitMixin.__init__(self)
        for mode in BagelCleanMode:
            self.addItem(mode.value.value, mode.value.ui_text)
        self.setCurrentItem(CLEAN_MODE_DEFAULT)
        self.setFixedWidth(180)
        self.setAccessibleName('出售方案')
        self.currentItemChanged.connect(self._save_value)

    def _set_value_from_adapter(self, value: str) -> None:
        """阻断初始化信号，保留原配置。"""
        with QtCore.QSignalBlocker(self):
            self.setCurrentItem(value)
        self.setEnabled(True)
        self.state_changed.emit()

    def _save_value(self, value: str) -> None:
        """保存当前方案，但不清空自定义步骤。"""
        if self.adapter is not None:
            self.adapter.set_value(value)
        self.state_changed.emit()


class CleanStepCard(SimpleCardWidget):
    """一步一张卡，仅编辑条件；总预览由页面统一显示。"""

    changed = Signal()
    move_requested = Signal(int)
    delete_requested = Signal()

    def __init__(
        self, index: int, count: int, step: BagelCleanStep, parent: QWidget
    ) -> None:
        """复用正式多选框，保留连续勾选和标签移除行为。"""
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        heading.addWidget(StrongBodyLabel(f'第 {index + 1} 步', self))
        heading.addStretch(1)
        for offset, icon, text in (
            (-1, FluentIcon.UP, '上移'),
            (1, FluentIcon.DOWN, '下移'),
        ):
            button = TransparentToolButton(icon, self)
            button.setFixedSize(28, 28)
            button.setToolTip(text)
            button.setAccessibleName(f'{text}第 {index + 1} 步')
            button.setEnabled(0 <= index + offset < count)
            button.clicked.connect(
                lambda _checked=False, delta=offset: self.move_requested.emit(delta)
            )
            heading.addWidget(button)
        delete_button = TransparentPushButton('删除', self)
        delete_button.setAccessibleName(f'删除第 {index + 1} 步')
        delete_button.clicked.connect(self.delete_requested)
        heading.addWidget(delete_button)
        layout.addLayout(heading)

        self.types_box: MultiSelectionComboBox = MultiSelectionComboBox(
            fixed_width=160, parent=self
        )
        self.qualities_box: MultiSelectionComboBox = MultiSelectionComboBox(
            fixed_width=120, parent=self
        )
        self.types_box.set_items([item.value for item in BagelCleanType])
        self.qualities_box.set_items([item.value for item in BagelCleanQuality])
        self.types_box.set_value(list(step.types), emit_signal=False)
        self.qualities_box.set_value(list(step.qualities), emit_signal=False)
        self._fields: list[tuple[QWidget, MultiSelectionComboBox]] = []
        self._resize_timer: QTimer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._fit_fields)
        fields = QHBoxLayout()
        fields.setSpacing(18)
        for title, box, stretch in (
            ('物品类型 · 可多选', self.types_box, 135),
            ('品质 · 可多选', self.qualities_box, 100),
        ):
            field = QWidget(self)
            field.setMinimumWidth(0)
            field.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            column = QVBoxLayout(field)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(6)
            label = CaptionLabel(title, field)
            label.setBuddy(box)
            column.addWidget(label)
            column.addWidget(box)
            column.addStretch(1)
            fields.addWidget(field, stretch)
            box.setAccessibleName(f'第 {index + 1} 步{title}')
            box.selection_changed.connect(self._on_selection_changed)
            self._fields.append((field, box))
            field.installEventFilter(self)
        layout.addLayout(fields)
        self._resize_timer.start(0)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """字段宽度变化后重排标签；计时器随卡片销毁。"""
        if watched is not self and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._resize_timer.start(0)
        return super().eventFilter(watched, event)

    def _fit_fields(self) -> None:
        """按字段实际宽度换行，不让选中的标签撑宽整页。"""
        for field, box in self._fields:
            box.setFixedWidth(max(120, field.width()))
            # 固定宽度后先应用子布局，再测量标签换行高度。
            dropdown = box._dropdown_btn
            dropdown.layout().activate()
            flow_widget = dropdown._flow_widget
            flow_widget.parentWidget().layout().activate()
            height = dropdown._flow_layout.heightForWidth(max(1, flow_widget.width()))
            dropdown.setMinimumHeight(max(32, height + 8))
            box.updateGeometry()
        self.updateGeometry()

    def _on_selection_changed(self, _values: list[str]) -> None:
        """不重建卡片或菜单，只保存值并更新总预览。"""
        self._resize_timer.start(0)
        self.changed.emit()

    def value(self) -> BagelCleanStep:
        """读取这一步的两项条件。"""
        return BagelCleanStep(
            tuple(self.types_box.get_value()), tuple(self.qualities_box.get_value())
        )


def scope_groups(steps: list[BagelCleanStep]) -> list[BagelCleanStep]:
    """合并已填完整步骤的范围，不产生跨步骤的额外类型与品质组合。"""
    groups: dict[tuple[str, ...], list[str]] = {}
    for item_type in CLEAN_TYPES:
        qualities = tuple(
            quality
            for quality in CLEAN_QUALITIES
            if any(
                item_type in step.types and quality in step.qualities for step in steps
            )
        )
        if qualities:
            groups.setdefault(qualities, []).append(item_type)
    return [
        BagelCleanStep(tuple(types), qualities) for qualities, types in groups.items()
    ]


def tag_row(values: tuple[str, ...], parent: QWidget) -> QWidget:
    """显示可换行标签；品质使用粗体字母和对应底色，兼容明暗主题。"""
    widget = QWidget(parent)
    flow = FlowLayout(widget)
    flow.setContentsMargins(0, 0, 0, 0)
    flow.setHorizontalSpacing(6)
    flow.setVerticalSpacing(6)
    # 每组依次为文字、底色和边框；品质名称仍靠字母识别，不只靠颜色。
    quality_colors = {
        'C': (('#404650', '#edf0f4', '#bcc3cd'), ('#e0e4eb', '#353b44', '#656e7b')),
        'B': (('#145b87', '#e8f3fc', '#8db9d9'), ('#a6d9ff', '#203a4d', '#4b85ab')),
        'A': (('#6939a0', '#f1eafb', '#b99bd9'), ('#dbc0ff', '#3a2c4e', '#8e6bb7')),
        'S': (('#795200', '#fff3d6', '#d8b366'), ('#ffda82', '#473a20', '#a88b49')),
        'Z': (('#a32849', '#ffe9ef', '#dd97aa'), ('#ffb3c6', '#4b2935', '#b56d84')),
    }
    for value in values:
        label = QLabel(value, widget)
        label.setObjectName('scopeTag')
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        FluentStyleSheet.LABEL.apply(label)
        is_quality = value in CLEAN_QUALITIES
        setFont(
            label,
            14 if is_quality else 12,
            QFont.Weight.Bold if is_quality else QFont.Weight.Normal,
        )
        if is_quality:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        light, dark = quality_colors.get(
            value,
            (('#3d3d3d', '#ffffff', '#dfe2e7'), ('#d8d9dd', '#303136', '#484950')),
        )
        styles = [
            f'QLabel#scopeTag {{ color: {text}; background: {background}; border: 1px solid {border}; border-radius: 4px; padding: 3px 10px; }}'
            for text, background, border in (light, dark)
        ]
        setCustomStyleSheet(label, styles[0], styles[1])
        flow.addWidget(label)
    return widget


class SaleScopePreview(SimpleCardWidget):
    """全部自定义步骤共用的出售范围总预览。"""

    def __init__(self, parent: QWidget) -> None:
        """预览只显示选择范围，不查询库存。"""
        super().__init__(parent)
        self._layout: QVBoxLayout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 15, 16, 15)
        self._layout.setSpacing(12)
        heading = QHBoxLayout()
        heading.addWidget(StrongBodyLabel('出售范围总预览', self))
        self._incomplete_hint: CaptionLabel = CaptionLabel('仅汇总已填完整的步骤', self)
        heading.addWidget(self._incomplete_hint)
        heading.addStretch(1)
        self._layout.addLayout(heading)
        self._table: QWidget = QWidget(self)
        self._layout.addWidget(self._table)

    def set_steps(self, steps: list[BagelCleanStep]) -> None:
        """按类型汇总品质并去重，品质集合相同的类型合为一行。"""
        groups = scope_groups(steps)
        self._incomplete_hint.setVisible(
            bool(groups) and any(not step.types or not step.qualities for step in steps)
        )
        table = QWidget(self)
        grid = QGridLayout(table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 56)
        grid.setColumnStretch(1, 44)
        if groups:
            grid.addWidget(CaptionLabel('物品类型', table), 0, 0)
            grid.addWidget(CaptionLabel('品质', table), 0, 1)
            for row, group in enumerate(groups, start=1):
                grid.addWidget(
                    tag_row(group.types, table), row, 0, Qt.AlignmentFlag.AlignTop
                )
                grid.addWidget(
                    tag_row(group.qualities, table), row, 1, Qt.AlignmentFlag.AlignTop
                )
        else:
            text = (
                '补全类型和品质后显示。'
                if steps
                else '添加步骤并选择类型和品质后显示。'
            )
            grid.addWidget(BodyLabel(text, table), 0, 0, 1, 2)
        self._layout.replaceWidget(self._table, table)
        self._table.hide()
        self._table.deleteLater()
        self._table = table
