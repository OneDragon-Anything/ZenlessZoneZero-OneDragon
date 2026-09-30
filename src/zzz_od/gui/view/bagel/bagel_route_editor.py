"""贝果独立流程开发工具：地图、动作、参数与实机试跑。"""

from __future__ import annotations

import argparse
from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    DoubleSpinBox,
    LineEdit,
    ListWidget,
    MessageBox,
    PushButton,
    SubtitleLabel,
    Theme,
    setTheme,
)

from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_flow import (
    ACTION_CATEGORIES,
    ACTION_LABELS,
    ACTION_RULES,
    BagelFlow,
    BagelStep,
    NavigationOptions,
    draft_path,
    flow_from_route,
    load_published_flow,
    read_flow,
    write_flow,
)
from zzz_od.application.bagel.bagel_map_model import BagelMapModel
from zzz_od.application.bagel.bagel_route import (
    MAP_LABELS,
    ROLE_LABELS,
    BagelRouteConfig,
    BagelWaypoint,
    resource_root,
)
from zzz_od.gui.view.bagel.bagel_flow_trial import FlowTrialWorker

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QCloseEvent, QWheelEvent
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

    from zzz_od.context.zzz_context import ZContext


class RoutePointItem(QGraphicsEllipseItem):
    """拖动结束后提交一次撤销记录，点击同步选择。"""

    def __init__(
        self,
        index: int,
        point: BagelWaypoint,
        changed: Callable[[int, tuple[float, float]], None],
        selected: Callable[[int], None],
    ) -> None:
        """直接使用参考图坐标。"""
        super().__init__(-2, -2, 4, 4)
        self.index: int = index
        self.changed: Callable[[int, tuple[float, float]], None] = changed
        self.selected: Callable[[int], None] = selected
        self.setPos(*point.xy)
        self.setBrush(QColor('#a96100' if point.stage == 'box' else '#006cba'))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setZValue(10)
        self.setToolTip(
            f'{point.name} · {ROLE_LABELS[point.role]}\n'
            f'距离路点 {point.arrival_radius:g} 像素以内算到达；'
            f'走过路点后，{point.passed_radius:g} 像素以内可继续下一段。'
        )

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """选点时不重建正在接收鼠标事件的场景。"""
        self.selected(self.index)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """松手后延迟交回坐标，避免销毁当前事件接收对象。"""
        super().mouseReleaseEvent(event)
        index, changed = self.index, self.changed
        xy = (round(self.pos().x(), 1), round(self.pos().y(), 1))
        QTimer.singleShot(0, lambda: changed(index, xy))


class FlowMarkerItem(QGraphicsEllipseItem):
    """点击其它移动段或交互位置时选择对应业务步骤。"""

    def __init__(
        self, xy: tuple[float, float], title: str, selected: Callable[[], None]
    ) -> None:
        """仅负责选择，路点拖动由选中移动步骤处理。"""
        super().__init__(-1.5, -1.5, 3, 3)
        self.selected: Callable[[], None] = selected
        self.setPos(*xy)
        self.setBrush(QColor('#9037a0'))
        self.setToolTip(title)
        self.setZValue(5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """延迟选择，避免重绘销毁当前鼠标事件接收者。"""
        super().mouseReleaseEvent(event)
        QTimer.singleShot(0, self.selected)


class RouteMapView(QGraphicsView):
    """横屏地图，支持滚轮缩放和空白拖动平移。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """创建独立场景。"""
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor('#eef1f6'))
        self.content_rect: QRectF = QRectF()
        self.setToolTip('滚轮放大或缩小；拖动空白处移动地图；拖动路点修改路线。')
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(460, 440)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """限制缩放范围。"""
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        if 0.5 <= self.transform().m11() * factor <= 20:
            self.scale(factor, factor)
        event.accept()

    def fit(self) -> None:
        """适应有参考图或路点的范围，排除底图外围的透明留白。"""
        rect = (
            self.content_rect if not self.content_rect.isEmpty() else self.sceneRect()
        )
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


class BagelRouteEditor(QDialog):
    """源码开发入口；草稿不会自动影响账号的正式任务。"""

    def __init__(
        self,
        instance_idx: int,
        ctx: ZContext | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """加载开发草稿；损坏文件直接报错，不回退到另一条路线。"""
        super().__init__(parent)
        self.setFont(QFont('Microsoft YaHei UI', 10))
        palette = self.palette()
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Button):
            palette.setColor(role, QColor(248, 249, 252))
        palette.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
        ):
            palette.setColor(role, QColor('#202020'))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.instance_idx: int = instance_idx
        self.ctx: ZContext | None = ctx
        self.owns_context: bool = ctx is None
        self.models: dict[str, BagelMapModel] = {
            key: BagelMapModel.load(key) for key in MAP_LABELS
        }
        self.drafts: dict[str, BagelFlow] = {
            key: read_flow(draft_path(key))
            if draft_path(key).exists()
            else load_published_flow(key)
            for key in MAP_LABELS
        }
        if any(flow.map_id != key for key, flow in self.drafts.items()):
            raise ValueError('草稿与文件地图标识不一致')
        self.saved: dict[str, BagelFlow] = dict(self.drafts)
        self.undo_stack: dict[str, list[BagelFlow]] = {key: [] for key in MAP_LABELS}
        self.redo_stack: dict[str, list[BagelFlow]] = {key: [] for key in MAP_LABELS}
        self.checked_steps: dict[str, set[str]] = {key: set() for key in MAP_LABELS}
        self.worker: FlowTrialWorker | None = None
        self.trace: list[tuple[float, float] | None] = []
        self._updating: bool = False
        self._close_pending: bool = False
        self.edit_widgets: list[QWidget] = []
        self.setWindowTitle(f'贝果流程开发工具 · 试跑账号 {instance_idx:02d}')
        self.resize(1680, 960)
        self._build_ui()
        self._refresh(fit=True)
        QTimer.singleShot(0, self.view.fit)

    @property
    def map_id(self) -> str:
        """当前出生地。"""
        return self.map_combo.currentData()

    @property
    def flow(self) -> BagelFlow:
        """当前内存草稿。"""
        return self.drafts[self.map_id]

    @property
    def step(self) -> BagelStep | None:
        """当前选择的业务步骤。"""
        index = self.step_list.currentRow()
        return self.flow.steps[index] if 0 <= index < len(self.flow.steps) else None

    @property
    def running(self) -> bool:
        """线程清理完成前保持运行状态。"""
        return self.worker is not None and self.worker.isRunning()

    def _button(
        self, text: str, callback: Callable, layout: QHBoxLayout, editable: bool = True
    ) -> PushButton:
        """统一创建 Fluent 按钮。"""
        button = PushButton(text, self)
        button.clicked.connect(callback)
        layout.addWidget(button)
        if editable:
            self.edit_widgets.append(button)
        return button

    def _spin(self, low: float, high: float) -> DoubleSpinBox:
        """有界数值输入，结束编辑才提交一次变更。"""
        spin = DoubleSpinBox(self)
        spin.setRange(low, high)
        spin.setDecimals(1)
        self.edit_widgets.append(spin)
        return spin

    def _build_ui(self) -> None:
        """地图、步骤、滚动属性三栏，记录在下方。"""
        layout = QVBoxLayout(self)
        layout.addWidget(SubtitleLabel('贝果流程开发工具'))
        top = QHBoxLayout()
        self.map_combo: ComboBox = ComboBox(self)
        for key, label in MAP_LABELS.items():
            self.map_combo.addItem(label, userData=key)
        self.map_combo.currentIndexChanged.connect(self._switch_map)
        self.edit_widgets.append(self.map_combo)
        top.addWidget(self.map_combo)
        self._button('显示完整地图', lambda: self.view.fit(), top, False)
        self.undo_button: PushButton = self._button('撤销', self.undo, top)
        self.redo_button: PushButton = self._button('重做', self.redo, top)
        self._button('恢复正式流程', self.restore_default, top)
        self._button('导入旧账号路线', self.import_legacy, top)
        self._button('保存草稿', self.save_draft, top)
        self._button('导出为正式流程', self.export_flow, top)
        layout.addLayout(top)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.view: RouteMapView = RouteMapView(self)
        map_panel = QWidget(self)
        map_layout = QVBoxLayout(map_panel)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.addWidget(
            BodyLabel('路线地图 · 滚轮缩放，拖动空白处平移，拖动圆点改路线')
        )
        map_layout.addWidget(self.view, 1)
        splitter.addWidget(map_panel)
        middle = QWidget(self)
        steps = QVBoxLayout(middle)
        steps.addWidget(BodyLabel('勾选要执行的步骤 · 点击行可编辑'))
        self.step_list: ListWidget = ListWidget(self)
        self.step_list.currentRowChanged.connect(self._select_step)
        self.step_list.itemChanged.connect(self._checked_changed)
        steps.addWidget(self.step_list, 1)
        row = QHBoxLayout()
        self._button('全选', lambda: self.check_steps(True), row)
        self._button('清空勾选', lambda: self.check_steps(False), row)
        self._button('只勾当前', self.check_current, row)
        steps.addLayout(row)
        self.action_combo: ComboBox = ComboBox(self)
        for key, title in ACTION_LABELS.items():
            self.action_combo.addItem(
                f'{ACTION_CATEGORIES[key]} · {title}', userData=key
            )
        self.action_combo.setCurrentIndex(1)
        steps.addWidget(self.action_combo)
        row = QHBoxLayout()
        self._button('添加步骤', self.add_step, row)
        self._button('删除步骤', self.delete_step, row)
        steps.addLayout(row)
        row = QHBoxLayout()
        self._button('上移一步', lambda: self.move_step(-1), row)
        self._button('下移一步', lambda: self.move_step(1), row)
        steps.addLayout(row)
        middle.setMinimumWidth(260)
        splitter.addWidget(middle)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        properties = QWidget(self)
        form = QFormLayout(properties)
        self.property_form: QFormLayout = form
        self.action_info: BodyLabel = BodyLabel(self)
        form.addRow(self.action_info)
        self.name_edit: LineEdit = LineEdit(self)
        self.name_edit.editingFinished.connect(self.edit_step)
        form.addRow('步骤名称', self.name_edit)
        self.rules: BodyLabel = BodyLabel(self)
        self.rules.setWordWrap(True)
        form.addRow(self.rules)
        self.target_combo: ComboBox = ComboBox(self)
        self.target_combo.addItem('武备箱', userData='box')
        self.target_combo.addItem('电子保险箱', userData='safe')
        self.target_combo.currentIndexChanged.connect(self.edit_step)
        form.addRow('关联容器', self.target_combo)
        self.timeout_default: CheckBox = CheckBox('默认移动时限', self)
        self.timeout_input: DoubleSpinBox = self._spin(1, 600)
        self.brake_default: CheckBox = CheckBox('默认提前停步', self)
        self.brake_input: DoubleSpinBox = self._spin(0.1, 30)
        self.interaction_default: CheckBox = CheckBox('默认交互范围', self)
        self.interaction_input: DoubleSpinBox = self._spin(0.1, 30)
        self.timeout_input.setSuffix(' 秒')
        self.brake_input.setSuffix(' 像素')
        self.interaction_input.setSuffix(' 像素')
        self.timeout_default.setToolTip(
            '勾选使用默认值；取消勾选后可修改。超时仍未到达，停止这一步。'
        )
        self.brake_default.setToolTip(
            '小步前进时，离接近点还有多远就松开前进键。取消勾选可修改。'
        )
        self.interaction_default.setToolTip(
            '离终点多近时，才通过游戏中的交互提示确认到达。取消勾选可修改。'
        )
        for check, spin in (
            (self.timeout_default, self.timeout_input),
            (self.brake_default, self.brake_input),
            (self.interaction_default, self.interaction_input),
        ):
            check.clicked.connect(self.edit_navigation)
            spin.editingFinished.connect(self.edit_navigation)
            form.addRow(check, spin)
        self.mode_combo: ComboBox = ComboBox(self)
        for label, value in (
            ('使用默认方式', None),
            ('沿最后一段方向小步前进', 'short_steps'),
            ('按地图坐标靠近目标', 'coordinate'),
        ):
            self.mode_combo.addItem(label, userData=value)
        self.mode_combo.currentIndexChanged.connect(self.edit_navigation)
        form.addRow('最后如何靠近', self.mode_combo)
        self.effective_info: BodyLabel = BodyLabel(self)
        self.effective_info.setWordWrap(True)
        form.addRow(self.effective_info)
        self.point_list: ListWidget = ListWidget(self)
        self.point_list.setMaximumHeight(180)
        self.point_list.currentRowChanged.connect(self._select_point)
        form.addRow(self.point_list)
        self.point_name: LineEdit = LineEdit(self)
        self.point_name.editingFinished.connect(self.edit_point)
        form.addRow('路点名称', self.point_name)
        self.x_input: DoubleSpinBox = self._spin(-1000, 1000)
        self.y_input: DoubleSpinBox = self._spin(-1000, 1000)
        self.tolerance_input: DoubleSpinBox = self._spin(0.1, 30)
        self.tolerance_default: CheckBox = CheckBox('默认到达范围', self)
        self.tolerance_input.setSuffix(' 像素')
        self.tolerance_default.setToolTip(
            '距离路点小于此数值就算到达。取消勾选可修改；范围越小，要求越精确。'
        )
        self.stop_check: CheckBox = CheckBox('到达这点先停步，再继续', self)
        for spin in (self.x_input, self.y_input, self.tolerance_input):
            spin.editingFinished.connect(self.edit_point)
        self.tolerance_default.clicked.connect(self.edit_point)
        self.stop_check.clicked.connect(self.edit_point)
        form.addRow('横坐标 X', self.x_input)
        form.addRow('纵坐标 Y', self.y_input)
        form.addRow(self.tolerance_default, self.tolerance_input)
        form.addRow(self.stop_check)
        self.edit_widgets.extend(
            (
                self.action_combo,
                self.name_edit,
                self.target_combo,
                self.timeout_default,
                self.brake_default,
                self.interaction_default,
                self.mode_combo,
                self.point_list,
                self.point_name,
                self.tolerance_default,
                self.stop_check,
            )
        )
        properties_container = QWidget(self)
        properties_layout = QVBoxLayout(properties_container)
        properties_layout.setContentsMargins(0, 0, 0, 0)
        properties_layout.addWidget(properties)
        properties_layout.addStretch(1)
        scroll.setWidget(properties_container)
        scroll.setMinimumWidth(360)
        splitter.addWidget(scroll)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([860, 340, 430])
        layout.addWidget(splitter, 1)
        trial = QHBoxLayout()
        self.run_button: PushButton = self._button(
            '执行勾选步骤', self.start_trial, trial
        )
        self.selection_info: BodyLabel = BodyLabel(self)
        trial.addWidget(self.selection_info, 1)
        self.stop_button: PushButton = self._button(
            '停止', self.stop_trial, trial, False
        )
        self.stop_button.setEnabled(False)
        layout.addLayout(trial)
        layout.addWidget(
            BodyLabel(
                '按列表顺序执行勾选项，跳过未勾选项。每一步都会实际操作游戏；请先把游戏停在第一项需要的画面。'
            )
        )
        self.trial_info: BodyLabel = BodyLabel('尚未试跑', self)
        self.trial_info.setWordWrap(True)
        layout.addWidget(self.trial_info)
        self.records: ListWidget = ListWidget(self)
        self.records.setMaximumHeight(64)
        layout.addWidget(self.records)
        self.status: BodyLabel = BodyLabel(self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _switch_map(self) -> None:
        """保留各地图草稿，清空旧地图轨迹。"""
        self.trace.clear()
        self._refresh(fit=True)

    def _refresh(self, fit: bool = False, selected: int | None = None) -> None:
        """回填时屏蔽编辑信号，勾选使用稳定标识，不受改名或排序影响。"""
        self._updating = True
        index = self.step_list.currentRow() if selected is None else selected
        self.step_list.clear()
        for i, step in enumerate(self.flow.steps):
            item = QListWidgetItem(
                f'{i + 1}. [{ACTION_CATEGORIES[step.action]}] {step.name}'
            )
            item.setToolTip(
                f'{ACTION_LABELS[step.action]}\n{ACTION_RULES[step.action]}\n勾选加入执行清单；点击此行只查看和编辑。'
            )
            item.setSizeHint(QSize(0, 28))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if step.id in self.checked_steps[self.map_id]
                else Qt.CheckState.Unchecked
            )
            self.step_list.addItem(item)
        self.step_list.setCurrentRow(max(0, min(index, len(self.flow.steps) - 1)))
        self.undo_button.setEnabled(bool(self.undo_stack[self.map_id]))
        self.redo_button.setEnabled(bool(self.redo_stack[self.map_id]))
        self._updating = False
        self._select_step()
        self._update_selection()
        try:
            self.flow.validate_order()
            message = '步骤顺序检查通过；路线能否走通，请在游戏中试跑确认'
        except ValueError as error:
            message = f'还不能保存或试跑：{error}'
        self.status.setText(
            f'{"有未保存修改" if self.flow != self.saved[self.map_id] else "草稿未修改"} · {message}'
        )
        if fit:
            self.view.fit()

    def _select_step(self, _index: int = -1) -> None:
        """选择动作时展示对应属性与路点。"""
        if self._updating:
            return
        self._updating = True
        step = self.step
        point_index = self.point_list.currentRow()
        self.point_list.clear()
        if step is not None:
            self.action_info.setText(
                f'类型：{ACTION_CATEGORIES[step.action]} · {ACTION_LABELS[step.action]}'
            )
            self.name_edit.setText(step.name)
            self.rules.setText(ACTION_RULES[step.action])
            self.target_combo.setCurrentIndex(1 if step.target == 'safe' else 0)
            for i, point in enumerate(step.waypoints):
                prefix = (
                    '方向起点（不走回这里）'
                    if step.action == 'approach' and len(step.waypoints) == 2 and i == 0
                    else '目的地'
                )
                self.point_list.addItem(f'{prefix}：{point.name}')
            self.point_list.setFixedHeight(44 if len(step.waypoints) <= 1 else 80)
            self.point_list.setCurrentRow(
                max(0, min(point_index, len(step.waypoints) - 1))
            )
            nav = step.navigation
            self.timeout_default.setChecked(nav.timeout is None)
            self.brake_default.setChecked(nav.brake_distance is None)
            self.interaction_default.setChecked(nav.interaction_distance is None)
            self.interaction_input.setValue(nav.effective_interaction_distance)
            self.timeout_input.setValue(nav.effective_timeout(step.target))
            self.brake_input.setValue(nav.effective_brake_distance)
            self.mode_combo.setCurrentIndex(
                {None: 0, 'short_steps': 1, 'coordinate': 2}[nav.final_mode]
            )
            self.effective_info.setText(
                f'最多移动 {nav.effective_timeout(step.target):g} 秒。最后'
                f'{"沿路线方向小步前进" if nav.effective_final_mode(step.target) == "short_steps" else "按地图坐标靠近目标"}。\n'
                f'进入终点周围 {nav.effective_interaction_distance:g} 像素后，通过游戏提示确认到达。\n'
                '实线圆：到达范围。虚线圆：走过路点后，还能继续下一段的范围。'
            )
        else:
            self.name_edit.clear()
            self.rules.setText('选择左侧步骤查看设置，也可以在列表下方添加步骤。')
        move = step is not None and step.action in ('move', 'approach')
        approach = step is not None and step.action == 'approach'
        self.property_form.setRowVisible(
            self.target_combo, step is not None and step.target is not None
        )
        for widget in (
            self.timeout_input,
            self.brake_input,
            self.interaction_input,
            self.mode_combo,
            self.effective_info,
            self.point_list,
            self.point_name,
            self.x_input,
            self.y_input,
            self.tolerance_input,
            self.stop_check,
        ):
            self.property_form.setRowVisible(widget, move)
        self.property_form.setRowVisible(self.interaction_input, approach)
        self.property_form.setRowVisible(self.mode_combo, approach)
        self.property_form.setRowVisible(
            self.brake_input,
            move and step.action == 'move' and step.waypoints[0].role == 'approach',
        )
        self.property_form.setRowVisible(self.stop_check, False)
        if step is not None and step.action == 'move':
            self.effective_info.setText(
                f'最多移动 {step.navigation.effective_timeout(step.target):g} 秒，到达路点后停步。\n实线圆是到达范围，虚线圆是走过路点后仍可结束本步的范围。'
            )
        self.target_combo.setEnabled(
            not self.running
            and step is not None
            and step.target is not None
            and step.action != 'unlock'
        )
        for widget in (
            self.timeout_default,
            self.brake_default,
            self.interaction_default,
            self.mode_combo,
            self.point_list,
        ):
            widget.setEnabled(move and not self.running)
        self.timeout_input.setEnabled(
            move and not self.running and not self.timeout_default.isChecked()
        )
        self.brake_input.setEnabled(
            move and not self.running and not self.brake_default.isChecked()
        )
        self.interaction_input.setEnabled(
            move and not self.running and not self.interaction_default.isChecked()
        )
        self._updating = False
        self._select_point(self.point_list.currentRow())
        self._draw()

    def _select_point(self, index: int) -> None:
        """路点选择与地图同步；不重建场景，允许鼠标继续拖动。"""
        if self._updating:
            return
        self._updating = True
        step = self.step
        valid = step is not None and 0 <= index < len(step.waypoints)
        for widget in (
            self.point_name,
            self.x_input,
            self.y_input,
            self.tolerance_default,
            self.stop_check,
        ):
            widget.setEnabled(valid and not self.running)
        if valid:
            point = step.waypoints[index]
            self.point_name.setText(point.name)
            self.x_input.setValue(point.xy[0])
            self.y_input.setValue(point.xy[1])
            self.tolerance_default.setChecked(point.tolerance is None)
            self.tolerance_input.setValue(point.arrival_radius)
            self.stop_check.setChecked(point.stop)
        self.tolerance_input.setEnabled(
            valid and not self.running and not self.tolerance_default.isChecked()
        )
        for item in self.view.scene().items():
            if isinstance(item, RoutePointItem):
                item.setSelected(item.index == index)
        self._updating = False

    def _checked_changed(self, item: QListWidgetItem) -> None:
        """勾选只决定本次执行清单，不修改保存的流程。"""
        if self._updating or self.running:
            return
        step = self.flow.steps[self.step_list.row(item)]
        if item.checkState() == Qt.CheckState.Checked:
            self.checked_steps[self.map_id].add(step.id)
        else:
            self.checked_steps[self.map_id].discard(step.id)
        self._update_selection()

    def _update_selection(self) -> None:
        """明确列出实际执行编号，空清单不能启动。"""
        selected = [
            (i + 1, step)
            for i, step in enumerate(self.flow.steps)
            if step.id in self.checked_steps[self.map_id]
        ]
        numbers = ' → '.join(str(i) for i, _ in selected)
        self.selection_info.setText(
            f'已勾选 {len(selected)} 步 · 顺序：{numbers}'
            if selected
            else '尚未勾选 · 在步骤列表左侧打勾'
        )
        self.selection_info.setToolTip(
            '\n'.join(f'{i}. {step.name}' for i, step in selected)
        )
        self.run_button.setEnabled(bool(selected) and not self.running)

    def check_steps(self, checked: bool) -> None:
        """全选或清空当前地图，不影响其他地图。"""
        if self.running:
            return
        self.checked_steps[self.map_id] = (
            {step.id for step in self.flow.steps} if checked else set()
        )
        self._refresh()

    def check_current(self) -> None:
        """只勾选当前查看的步骤，点击执行按钮后才运行。"""
        if self.running or self.step is None:
            return
        self.checked_steps[self.map_id] = {self.step.id}
        self._refresh()

    def _change(self, flow: BagelFlow, selected: int | None = None) -> None:
        """编辑阶段允许暂时不完整的顺序，但不接受坏坐标或未知动作。"""
        if self.running:
            return
        try:
            flow = BagelFlow.from_dict(flow.to_dict(), validate_order=False)
        except ValueError as error:
            self._select_step()
            self.status.setText(str(error))
            return
        if flow != self.flow:
            self.undo_stack[self.map_id].append(self.flow)
            self.redo_stack[self.map_id].clear()
            self.drafts[self.map_id] = flow
        self._refresh(selected=selected)

    def _replace_step(self, step: BagelStep) -> None:
        """替换选中步骤。"""
        steps = list(self.flow.steps)
        index = self.step_list.currentRow()
        steps[index] = step
        self._change(replace(self.flow, steps=tuple(steps)), index)

    def edit_step(self) -> None:
        """目标类型变化时加载该类型的发布路点，形成可撤销变更。"""
        if self._updating or self.step is None or self.running:
            return
        step = self.step
        target = self.target_combo.currentData() if step.target is not None else None
        points = step.waypoints
        navigation = step.navigation
        if step.action in ('move', 'approach') and target != step.target:
            candidate = next(
                (
                    s
                    for s in load_published_flow(self.map_id).steps
                    if s.action == step.action and s.target == target
                ),
                None,
            )
            if candidate is None:
                self._select_step()
                self.status.setText('该地图没有此目标的已建档路线')
                return
            points = candidate.waypoints
            navigation = candidate.navigation
        self._replace_step(
            replace(
                step,
                name=self.name_edit.text(),
                target=target,
                waypoints=points,
                navigation=navigation,
            )
        )

    def edit_navigation(self) -> None:
        """未覆盖的参数保持为空。"""
        if (
            self._updating
            or self.step is None
            or self.step.action not in ('move', 'approach')
            or self.running
        ):
            return
        navigation = NavigationOptions(
            None if self.timeout_default.isChecked() else self.timeout_input.value(),
            None if self.brake_default.isChecked() else self.brake_input.value(),
            self.mode_combo.currentData(),
            None
            if self.interaction_default.isChecked()
            else self.interaction_input.value(),
        )
        points = self.step.waypoints
        if self.step.action == 'approach':
            if navigation.effective_final_mode(self.step.target) == 'coordinate':
                points = points[-1:]
            elif len(points) == 1:
                previous = next(
                    (
                        s.waypoints[-1]
                        for s in reversed(
                            self.flow.steps[: self.step_list.currentRow()]
                        )
                        if s.waypoints
                    ),
                    None,
                )
                if previous is None or previous.xy == points[-1].xy:
                    self._select_step()
                    self.status.setText(
                        '小步前进需要方向起点，请先添加一个位置不同的移动步骤。'
                    )
                    return
                points = (
                    replace(previous, stage=self.step.target, role='approach'),
                    *points,
                )
        self._replace_step(replace(self.step, navigation=navigation, waypoints=points))

    def edit_point(self) -> None:
        """提交路点属性并保留选择。"""
        if self._updating or self.step is None or self.running:
            return
        index = self.point_list.currentRow()
        points = list(self.step.waypoints)
        if not 0 <= index < len(points):
            return
        points[index] = replace(
            points[index],
            name=self.point_name.text(),
            xy=(self.x_input.value(), self.y_input.value()),
            tolerance=None
            if self.tolerance_default.isChecked()
            else self.tolerance_input.value(),
            stop=self.stop_check.isChecked(),
        )
        self._replace_step(replace(self.step, waypoints=tuple(points)))
        self.point_list.setCurrentRow(index)

    def drag_point(self, index: int, xy: tuple[float, float]) -> None:
        """拖点只修改当前移动步骤。"""
        if self.running or self.step is None:
            return
        points = list(self.step.waypoints)
        points[index] = replace(points[index], xy=xy)
        self._replace_step(replace(self.step, waypoints=tuple(points)))
        self.point_list.setCurrentRow(index)
        if not self.models[self.map_id].contains(xy):
            self.status.setText(
                '该位置没有参考像素，请实机核对；地图覆盖不保证可通行。'
            )

    def add_step(self) -> None:
        """在所选步骤后新增业务动作。"""
        action = self.action_combo.currentData()
        target = (
            self.step.target if self.step is not None and self.step.target else 'box'
        )
        if action in ('spawn', 'exit'):
            target = None
        elif action == 'unlock':
            target = 'safe'
        if target == 'safe' and self.map_id == 'janus_high_b':
            self.status.setText('白鸽地图没有电子保险箱，请选择其他动作。')
            return
        points = ()
        navigation = NavigationOptions()
        if action in ('move', 'approach'):
            previous = next(
                (
                    s.waypoints[-1].xy
                    for s in reversed(
                        self.flow.steps[: self.step_list.currentRow() + 1]
                    )
                    if s.waypoints
                ),
                self.models[self.map_id].spawn,
            )
            points = (
                BagelWaypoint('新路点', (previous[0] + 5, previous[1]), target, 'turn'),
            )
        if action == 'approach':
            candidate = next(
                (
                    s for s in load_published_flow(self.map_id).steps
                    if s.action == action and s.target == target
                ),
                None,
            )
            if candidate is not None:
                points, navigation = candidate.waypoints, candidate.navigation
            else:
                target_point = BagelWaypoint(
                    '新交互目标', (previous[0] + 5, previous[1]), target, 'target',
                )
                points = (
                    (BagelWaypoint('小步方向起点', previous, target, 'approach'), target_point)
                    if navigation.effective_final_mode(target) == 'short_steps'
                    else (target_point,)
                )
        step = BagelStep(
            uuid4().hex, action, ACTION_LABELS[action], target, points, navigation
        )
        index = self.step_list.currentRow() + 1
        steps = list(self.flow.steps)
        steps.insert(index, step)
        self._change(replace(self.flow, steps=tuple(steps)), index)
        if action == 'approach' and candidate is None:
            self.status.setText('已添加靠近步骤，请在地图上调整交互目标后再试跑。')

    def delete_step(self) -> None:
        """删除动作，完整前置条件在保存前校验。"""
        if self.step is not None:
            steps = list(self.flow.steps)
            steps.pop(self.step_list.currentRow())
            self._change(replace(self.flow, steps=tuple(steps)))

    def move_step(self, delta: int) -> None:
        """交换相邻业务步骤。"""
        index = self.step_list.currentRow()
        other = index + delta
        steps = list(self.flow.steps)
        if 0 <= index < len(steps) and 0 <= other < len(steps):
            steps[index], steps[other] = steps[other], steps[index]
            self._change(replace(self.flow, steps=tuple(steps)), other)

    def undo(self) -> None:
        """恢复整个流程快照。"""
        if not self.running and self.undo_stack[self.map_id]:
            self.redo_stack[self.map_id].append(self.flow)
            self.drafts[self.map_id] = self.undo_stack[self.map_id].pop()
            self._refresh()

    def redo(self) -> None:
        """重做整个流程修改。"""
        if not self.running and self.redo_stack[self.map_id]:
            self.undo_stack[self.map_id].append(self.flow)
            self.drafts[self.map_id] = self.redo_stack[self.map_id].pop()
            self._refresh()

    def restore_default(self) -> None:
        """只恢复内存草稿，不覆盖用户保存的文件。"""
        self._change(load_published_flow(self.map_id))

    def import_legacy(self) -> None:
        """旧账号文件只读；不能推导真实坐标的旧朝向配置拒绝导入。"""
        try:
            config = BagelRouteConfig(self.instance_idx)
            if self.map_id in config.migrated_maps:
                raise ValueError(
                    '旧配置只有朝向和移动时间，无法转换成地图路点。请先恢复正式流程，再修改路线。'
                )
            if self.map_id not in config.data.get('routes', {}):
                raise ValueError('该账号没有保存此地图的旧路线')
            self._change(flow_from_route(config.route(self.map_id)))
            self.status.setText(
                '旧路线已导入，并补上了开箱、收集和退出步骤。旧文件保持不变；请试跑确认后保存。'
            )
        except (OSError, ValueError) as error:
            log.error('旧路线导入失败', exc_info=True)
            self.status.setText(f'导入失败：{error}')

    def save_draft(self) -> None:
        """只保存开发草稿并回读。"""
        try:
            write_flow(draft_path(self.map_id), self.flow)
            self.saved[self.map_id] = read_flow(draft_path(self.map_id))
            self._refresh()
            self.status.setText(
                '草稿已保存，下次打开可以继续编辑。正式任务仍使用原来的流程。'
            )
        except (OSError, ValueError) as error:
            log.error('保存流程草稿失败', exc_info=True)
            self.status.setText(f'保存失败：{error}')

    def export_flow(self) -> None:
        """导出为可审查的仓库资源，不自动提交或发布。"""
        try:
            BagelFlow.from_dict(self.flow.to_dict())
            if not MessageBox(
                '替换当前地图的正式流程？',
                '导出后，下次运行正式任务将使用这套步骤和路线。请先在游戏中试跑确认。导出只修改本机文件，不会自动提交或发布。',
                self,
            ).exec():
                return
            path = resource_root(self.map_id) / 'flow.yml'
            write_flow(path, self.flow)
            self.status.setText(f'已更新正式流程，下次运行任务生效。文件：{path}')
        except (OSError, ValueError) as error:
            log.error('导出流程资源失败', exc_info=True)
            self.status.setText(f'导出失败：{error}')

    def _draw(self) -> None:
        """展示全部移动步骤、可靠交互位置、到达范围与断线轨迹。"""
        scene = self.view.scene()
        scene.clear()
        model = self.models[self.map_id]
        h, w = model.rgba.shape[:2]
        image = QImage(
            model.rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888
        ).copy()
        # 仅反转界面副本的 RGB，使游戏深色底图适合浅色界面；保留透明区和定位原图。
        image.invertPixels(QImage.InvertMode.InvertRgb)
        scene.addPixmap(QPixmap.fromImage(image)).setPos(*model.origin)
        scene.setSceneRect(model.origin[0] - 15, model.origin[1] - 15, w + 30, h + 30)
        ys, xs = model.coverage.nonzero()
        if len(xs):
            bounds = QRectF(
                model.origin[0] + int(xs.min()),
                model.origin[1] + int(ys.min()),
                int(xs.max() - xs.min()) + 1,
                int(ys.max() - ys.min()) + 1,
            )
        else:
            bounds = scene.sceneRect()
        for step in self.flow.steps:
            for point in step.waypoints:
                radius = max(point.arrival_radius, point.passed_radius)
                bounds = bounds.united(
                    QRectF(
                        point.xy[0] - radius,
                        point.xy[1] - radius,
                        radius * 2,
                        radius * 2,
                    )
                )
        self.view.content_rect = bounds.adjusted(-8, -8, 8, 8)
        last = model.spawn
        for step_index, step in enumerate(self.flow.steps):
            for point_index, point in enumerate(step.waypoints):
                color = QColor('#a96100' if point.stage == 'box' else '#006cba')
                scene.addLine(*last, *point.xy, QPen(color, 0.7))
                radius = point.arrival_radius
                scene.addEllipse(
                    point.xy[0] - radius,
                    point.xy[1] - radius,
                    radius * 2,
                    radius * 2,
                    QPen(color, 0.3),
                )
                if point.role != 'target' and point.passed_radius != radius:
                    passed = point.passed_radius
                    pen = QPen(color, 0.3, Qt.PenStyle.DashLine)
                    scene.addEllipse(
                        point.xy[0] - passed,
                        point.xy[1] - passed,
                        passed * 2,
                        passed * 2,
                        pen,
                    )
                if step_index == self.step_list.currentRow():
                    item = RoutePointItem(
                        point_index,
                        point,
                        self.drag_point,
                        self.point_list.setCurrentRow,
                    )
                    item.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self.running
                    )
                    scene.addItem(item)
                    item.setSelected(point_index == self.point_list.currentRow())
                else:
                    scene.addItem(
                        FlowMarkerItem(
                            point.xy,
                            step.name,
                            lambda index=step_index: self.step_list.setCurrentRow(
                                index
                            ),
                        )
                    )
                last = point.xy
            if step.action in ('interact', 'unlock', 'store', 'close'):
                # 仅当前面确有靠近步骤时才将交互挂在已知位置。
                if any(s.action == 'approach' for s in self.flow.steps[:step_index]):
                    offset = {'interact': -12, 'unlock': -5, 'store': 2, 'close': 9}[
                        step.action
                    ]
                    label = scene.addSimpleText(
                        f'{step_index + 1} {ACTION_LABELS[step.action]}'
                    )
                    label.setBrush(QColor('#702580'))
                    label.setScale(0.38)
                    label.setZValue(2)
                    label.setPos(last[0] + 3, last[1] + offset)
                    backdrop = scene.addRect(
                        label.sceneBoundingRect().adjusted(-1, -0.5, 1, 0.5),
                        QPen(Qt.PenStyle.NoPen),
                        QColor(255, 255, 255, 230),
                    )
                    backdrop.setZValue(1)
                    backdrop.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                    marker_xy = (
                        last[0] + 2,
                        last[1] + offset,
                    )
                    scene.addItem(
                        FlowMarkerItem(
                            marker_xy,
                            step.name,
                            lambda index=step_index: self.step_list.setCurrentRow(
                                index
                            ),
                        )
                    )
        for name, position in model.landmarks:
            scene.addEllipse(
                position[0] - 1.5, position[1] - 1.5, 3, 3, QPen(QColor('#9037a0'), 0.5)
            ).setToolTip(name)
        path = QPainterPath()
        connected = False
        for position in self.trace:
            if position is None:
                connected = False
            elif connected:
                path.lineTo(QPointF(*position))
            else:
                path.moveTo(QPointF(*position))
                connected = True
        scene.addPath(path, QPen(QColor('#007e50'), 0.8))

    def start_trial(self) -> None:
        """按原列表顺序执行勾选项；空清单或无效流程不启动线程。"""
        if self.running:
            return
        try:
            flow = BagelFlow.from_dict(self.flow.to_dict())
            selected = tuple(
                step.id
                for step in flow.steps
                if step.id in self.checked_steps[self.map_id]
            )
            if not selected:
                raise ValueError('请先在步骤列表左侧勾选要执行的步骤。')
        except ValueError as error:
            self.trial_info.setText(str(error))
            return
        self.trace.clear()
        self.records.clear()
        self.worker = FlowTrialWorker(
            self.instance_idx,
            flow,
            selected,
            self.ctx,
            self,
        )
        self.worker.observed.connect(self._observe)
        self.worker.completed.connect(self.trial_info.setText)
        self.worker.finished.connect(self._trial_finished)
        for widget in self.edit_widgets:
            widget.setEnabled(False)
        self.step_list.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.trial_info.setText(
            f'准备执行勾选的 {len(selected)} 步：'
            + ' → '.join(step.name for step in flow.steps if step.id in selected)
        )
        self.worker.start()
        self._draw()

    def _observe(self, event: dict[str, object]) -> None:
        """实际事件驱动步骤高亮和轨迹，识别缺失时断线。"""
        if event['kind'] == 'observation':
            self.trace.append(event['position'])
            self.trial_info.setText(
                f'实测位置：{event["position"]} · 朝向：{event["angle"]}'
            )
            self._draw()
        elif event['kind'] in ('start', 'done', 'failed', 'finished'):
            if 'index' in event:
                self.step_list.setCurrentRow(event['index'])
            index = event.get('index')
            name = (
                self.flow.steps[index].name
                if isinstance(index, int) and 0 <= index < len(self.flow.steps)
                else '本次试跑'
            )
            state = {
                'start': '准备执行',
                'done': '已完成',
                'failed': '未完成',
                'finished': '已结束',
            }[event['kind']]
            elapsed = f' · 用时 {event["elapsed"]:.2f} 秒' if 'elapsed' in event else ''
            text = f'{name} · {state} · {event.get("status", "")}{elapsed}'
            self.records.addItem(text)
            self.records.scrollToBottom()
            self.trial_info.setText(text)

    def stop_trial(self) -> None:
        """请求停止，保留线程直到清理完成。"""
        if self.worker is not None:
            self.worker.stop()

    def _trial_finished(self) -> None:
        """线程完成后恢复编辑，并复用已经初始化的上下文。"""
        worker = self.worker
        if worker is not None:
            if worker.ctx is not None:
                self.ctx = worker.ctx
            self.worker = None
            worker.deleteLater()
        for widget in self.edit_widgets:
            widget.setEnabled(True)
        self.step_list.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._refresh()
        if self._close_pending:
            self._close_pending = False
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭时先停止并异步等待线程，不销毁运行中的 QThread。"""
        if self.running:
            self._close_pending = True
            self.stop_trial()
            self.trial_info.setText('正在停止并松开按键，请稍候…')
            event.ignore()
            return
        if (
            self.drafts != self.saved
            and not MessageBox(
                '放弃未保存的修改？',
                '关闭后，这次未保存的修改会丢失。已保存的草稿和正式流程保持不变。',
                self,
            ).exec()
        ):
            event.ignore()
            return
        if self.owns_context and self.ctx is not None:
            self.ctx.after_app_shutdown()
        event.accept()

    def reject(self) -> None:
        """Esc 同样等待运行结束。"""
        self.close()


def main() -> int:
    """独立开发入口，首次试跑时初始化游戏控制服务。"""
    parser = argparse.ArgumentParser(description='贝果流程开发工具')
    parser.add_argument(
        '--instance',
        type=int,
        default=1,
        help='已配置账号的编号，仅用于试跑和旧路线导入',
    )
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    setTheme(Theme.LIGHT)
    editor = BagelRouteEditor(args.instance)
    editor.show()
    editor.view.fit()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
