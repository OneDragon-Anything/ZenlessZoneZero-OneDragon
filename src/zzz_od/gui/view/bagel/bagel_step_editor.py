"""步骤分类、创建与编辑共用的转换规则。"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    DoubleSpinBox,
    LineEdit,
    PushButton,
    SubtitleLabel,
)

from zzz_od.application.bagel.bagel_flow import (
    ACTION_CATEGORIES,
    ACTION_LABELS,
    BagelFlow,
    BagelStep,
    NavigationOptions,
)
from zzz_od.application.bagel.bagel_route import BagelWaypoint

MOVEMENT_MODES: tuple[tuple[str, str], ...] = (
    ('正常移动', 'coordinate'),
    ('碎步接近', 'small_steps'),
)


def move_position(step: BagelStep, xy: tuple[float, float]) -> BagelStep:
    """修改唯一目的地，不保存独立方向。"""
    return replace(step, waypoints=(replace(step.waypoints[-1], xy=xy),))


def change_target(step: BagelStep, target: str) -> BagelStep:
    """更换识别目标时保留坐标与之前实际生效的参数。"""
    if step.target == target:
        return step
    navigation = step.navigation
    if step.action == 'approach':
        navigation = replace(
            navigation,
            timeout=navigation.effective_timeout(step.target),
            final_mode=navigation.effective_final_mode(step.target),
        )
    return replace(
        step, target=target, navigation=navigation,
        waypoints=tuple(replace(p, stage=target, tolerance=p.arrival_radius) for p in step.waypoints),
    )


def new_step(
    action: str, target: str, xy: tuple[float, float],
    mode: str = 'coordinate', name: str = '',
) -> BagelStep:
    """从明确输入创建步骤，不读取正式路线或推测容器。"""
    container = None if action in ('spawn', 'move', 'exit') else ('safe' if action == 'unlock' else target)
    step = BagelStep(uuid4().hex, action, name.strip() or ACTION_LABELS[action], container)
    if action in ('move', 'approach'):
        point = BagelWaypoint(
            '新位置' if action == 'move' else '靠近位置', xy,
            container or 'move', 'turn' if action == 'move' else 'target',
        )
        step = replace(step, waypoints=(point,))
    if action in ('move', 'approach'):
        step = replace(step, navigation=NavigationOptions(final_mode=mode))
    return step


def change_action(step: BagelStep, action: str, xy: tuple[float, float]) -> BagelStep:
    """保留步骤标识与适用参数；不适用的数据由编辑器撤销记录保留。"""
    if action == step.action:
        return step
    result = new_step(action, step.target or 'box', xy)
    result = replace(result, id=step.id, name=step.name)
    if step.waypoints and result.waypoints:
        old = step.waypoints[-1]
        point = replace(
            result.waypoints[-1], name=old.name, xy=old.xy,
            tolerance=old.tolerance,
            passed_tolerance=old.passed_tolerance if action == 'move' else None,
        )
        result = replace(result, waypoints=(point,), navigation=replace(
            result.navigation,
            timeout=step.navigation.effective_timeout(step.target),
            final_mode=step.navigation.final_mode,
        ))
    return result


class StepTypeInput(QWidget):
    """先选大类，移动类选完成条件，其它类选具体操作。"""

    edited: Signal = Signal()

    def __init__(self, map_id: str, parent: QWidget | None = None) -> None:
        """新增和编辑共用同一分类与地图限制。"""
        super().__init__(parent)
        self.map_id: str = map_id
        self.category_combo: ComboBox = ComboBox(self)
        for category in ('移动', '箱子操作', '检查与退出'):
            self.category_combo.addItem(category)
        self.action_combo: ComboBox = ComboBox(self)
        self.form: QFormLayout = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.addRow('大类', self.category_combo)
        self.form.addRow('完成条件', self.action_combo)
        self.category_combo.currentIndexChanged.connect(self._change_category)
        self.action_combo.currentIndexChanged.connect(self.edited)
        self._populate('移动')

    def _populate(self, category: str) -> None:
        """分类切换时只提供当前地图支持的操作。"""
        self.action_combo.blockSignals(True)
        self.action_combo.clear()
        for action, label in ACTION_LABELS.items():
            if ACTION_CATEGORIES[action] == category and (action != 'unlock' or self.map_id == 'janus_high_a'):
                self.action_combo.addItem('到达目的地' if action == 'move' else label, userData=action)
        self.form.labelForField(self.action_combo).setText('完成条件' if category == '移动' else '具体操作')
        self.action_combo.blockSignals(False)

    def _change_category(self) -> None:
        """一次分类切换只提交一次操作变更。"""
        self._populate(self.category_combo.currentText())
        self.edited.emit()

    def set_action(self, action: str, map_id: str | None = None) -> None:
        """回填已有步骤，不发送修改信号。"""
        if map_id is not None:
            self.map_id = map_id
        category = ACTION_CATEGORIES[action]
        self.category_combo.blockSignals(True)
        self.category_combo.setCurrentText(category)
        self.category_combo.blockSignals(False)
        self._populate(category)
        self.action_combo.blockSignals(True)
        self.action_combo.setCurrentIndex(self.action_combo.findData(action))
        self.action_combo.blockSignals(False)


class BagelStepDialog(QDialog):
    """新增时一次选清类型、目标、位置和方式，不先套用旧模板。"""

    def __init__(self, map_id: str, xy: tuple[float, float], parent: QWidget | None = None) -> None:
        """初始位置来自编辑上下文，目标和方式由用户明确选择。"""
        super().__init__(parent)
        self.map_id: str = map_id
        self.step: BagelStep | None = None
        self.setWindowTitle('新增步骤')
        self.setMinimumWidth(510)
        layout = QVBoxLayout(self)
        layout.addWidget(SubtitleLabel('新增步骤', self))
        self.form: QFormLayout = QFormLayout()
        self.form.setVerticalSpacing(12)
        layout.addLayout(self.form)
        self.type_input: StepTypeInput = StepTypeInput(map_id, self)
        self.action_combo: ComboBox = self.type_input.action_combo
        self.form.addRow(self.type_input)
        self.name_edit: LineEdit = LineEdit(self)
        self.name_edit.setPlaceholderText('留空使用步骤类型名称')
        self.form.addRow('步骤名称', self.name_edit)
        self.target_combo: ComboBox = ComboBox(self)
        self.target_combo.addItem('武备箱', userData='box')
        if map_id == 'janus_high_a':
            self.target_combo.addItem('电子保险箱', userData='safe')
        self.form.addRow('交互目标', self.target_combo)
        self.mode_combo: ComboBox = ComboBox(self)
        for label, mode in MOVEMENT_MODES:
            self.mode_combo.addItem(label, userData=mode)
        self.form.addRow('移动方式', self.mode_combo)
        self.position: QWidget = QWidget(self)
        coordinates = QHBoxLayout(self.position)
        coordinates.setContentsMargins(0, 0, 0, 0)
        self.x_input: DoubleSpinBox = DoubleSpinBox(self)
        self.y_input: DoubleSpinBox = DoubleSpinBox(self)
        for label, spin, value in zip(('X', 'Y'), (self.x_input, self.y_input), xy, strict=True):
            spin.setRange(-1000, 1000)
            spin.setDecimals(1)
            spin.setValue(value)
            spin.setAccessibleName(f'{label} 坐标（地图像素）')
            coordinates.addWidget(BodyLabel(label, self))
            coordinates.addWidget(spin)
        self.form.addRow('目的地', self.position)
        self.summary: BodyLabel = BodyLabel(self)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.error: BodyLabel = BodyLabel(self)
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        self.cancel_button: PushButton = PushButton('取消', self)
        self.add_button: PushButton = PushButton('添加', self)
        self.cancel_button.clicked.connect(self.reject)
        self.add_button.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.add_button)
        layout.addLayout(buttons)
        self.type_input.edited.connect(self._update_fields)
        self.mode_combo.currentIndexChanged.connect(self._update_fields)
        self._update_fields()

    def _update_fields(self) -> None:
        """只显示本类型可编辑的字段，切换目标不会重设移动方式。"""
        action = self.action_combo.currentData()
        movement = action in ('move', 'approach')
        self.form.setRowVisible(self.target_combo, action in ('approach', 'interact', 'unlock', 'store', 'close'))
        self.form.labelForField(self.target_combo).setText('交互目标' if action == 'approach' else '操作对象')
        self.target_combo.setEnabled(action != 'unlock')
        if action == 'unlock':
            self.target_combo.setCurrentIndex(self.target_combo.findData('safe'))
        self.form.setRowVisible(self.mode_combo, movement)
        self.form.setRowVisible(self.position, movement)
        self.summary.setText(
            '在目的地附近看到对应交互提示后完成；到点后等待两秒，仍无提示则停止并报错。'
            if action == 'approach' else
            '完成条件：进入到达范围，或在允许范围内走过目的地。添加后可在地图调整位置。'
            if action == 'move' else ACTION_LABELS[action]
        )
        self.error.clear()

    def accept(self) -> None:
        """添加前进行单步结构校验，错误保留在窗口内供修正。"""
        step = new_step(
            self.action_combo.currentData(), self.target_combo.currentData(),
            (self.x_input.value(), self.y_input.value()),
            self.mode_combo.currentData(), self.name_edit.text(),
        )
        try:
            BagelFlow.from_dict(BagelFlow('draft', '新增步骤', self.map_id, (step,)).to_dict(), validate_order=False)
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.step = step
        super().accept()
