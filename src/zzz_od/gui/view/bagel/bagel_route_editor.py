"""贝果独立流程开发工具：地图、动作、参数与实机测试运行。"""

from __future__ import annotations

import argparse
from dataclasses import replace
from typing import TYPE_CHECKING

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
    FluentIcon,
    LineEdit,
    ListWidget,
    MessageBox,
    PushButton,
    SubtitleLabel,
    Theme,
    setTheme,
)

from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.repo_config import RepoConfig
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_flow import (
    ACTION_CATEGORIES,
    ACTION_LABELS,
    ACTION_RULES,
    BagelFlow,
    BagelStep,
    draft_path,
    load_published_flow,
    read_flow,
    write_flow,
)
from zzz_od.application.bagel.bagel_map_model import BagelMapModel
from zzz_od.application.bagel.bagel_route import (
    MAP_LABELS,
    BagelWaypoint,
    resource_root,
)
from zzz_od.gui.view.bagel.bagel_flow_trial import FlowTrialWorker
from zzz_od.gui.view.bagel.bagel_step_editor import (
    MOVEMENT_MODES,
    BagelStepDialog,
    StepTypeInput,
    change_action,
    change_target,
    move_position,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QCloseEvent, QWheelEvent
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

    from zzz_od.context.zzz_context import ZContext


def route_color(stage: str) -> QColor:
    """普通移动使用统一蓝色，只有靠近目标才按容器区分。"""
    return QColor({'move': '#006cba', 'box': '#a96100', 'safe': '#7851a9'}[stage])


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
        self.setBrush(route_color(point.stage))
        self.setPen(QPen(route_color(point.stage), 0.4))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setZValue(10)
        self.setToolTip(
            f'{point.name}\n'
            f'距离位置 {point.arrival_radius:g} 像素以内算到达；'
            f'走过位置后，{point.passed_radius:g} 像素以内可继续下一段。'
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
    """点击其它移动目的地时选择对应步骤。"""

    def __init__(
        self, xy: tuple[float, float], title: str, selected: Callable[[], None],
        color: QColor,
    ) -> None:
        """仅负责选择，位置拖动由选中移动步骤处理。"""
        super().__init__(-1.5, -1.5, 3, 3)
        self.selected: Callable[[], None] = selected
        self.setPos(*xy)
        self.setBrush(color)
        self.setPen(QPen(Qt.PenStyle.NoPen))
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
        self.setToolTip('滚轮放大或缩小；拖动空白处移动地图；拖动位置修改路线。')
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
        """适应有参考图或位置的范围，排除底图外围的透明留白。"""
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
        self._selected_point: int = -1
        self._close_pending: bool = False
        self.edit_widgets: list[QWidget] = []
        self.setWindowTitle(f'贝果流程开发工具 · 测试运行账号 {instance_idx:02d}')
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

    def _parameter_row(
        self, title: str, check: CheckBox, spin: DoubleSpinBox,
    ) -> None:
        """将参数名称、默认开关和值放在同一行，隐藏时一并隐藏。"""
        label = QWidget(self)
        layout = QVBoxLayout(label)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(BodyLabel(title, label))
        layout.addWidget(check)
        self.property_form.addRow(label, spin)

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
        self._button('载入正式流程', self.restore_default, top)
        self._button('保存草稿', self.save_draft, top)
        self._button('保存为正式流程', self.export_flow, top)
        layout.addLayout(top)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.view: RouteMapView = RouteMapView(self)
        map_panel = QWidget(self)
        map_layout = QVBoxLayout(map_panel)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.addWidget(BodyLabel('移动路线 · 点击选步骤，拖动当前步骤的点改位置'))
        self.trace_check: CheckBox = CheckBox('显示实际测试运行轨迹（绿色虚线）', self)
        self.trace_check.setChecked(True)
        self.trace_check.setToolTip('只显示本次测试运行实际识别到的位置；定位丢失处断开。')
        self.trace_check.toggled.connect(self._draw)
        map_layout.addWidget(self.trace_check)
        map_layout.addWidget(self.view, 1)
        legend = BodyLabel('蓝色：普通移动　橙色：靠近武备箱　紫色：靠近保险箱')
        legend.setWordWrap(True)
        map_layout.addWidget(legend)
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
        row = QHBoxLayout()
        self._button('新增步骤', self.add_step, row)
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
        form.setContentsMargins(16, 16, 16, 16)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(12)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.property_form: QFormLayout = form
        self.action_info: SubtitleLabel = SubtitleLabel(self)
        self.action_info.setWordWrap(True)
        form.addRow(self.action_info)
        self.rules: BodyLabel = BodyLabel(self)
        self.rules.setTextFormat(Qt.TextFormat.PlainText)
        self.rules.setWordWrap(True)
        self.brief: BodyLabel = BodyLabel(self)
        self.brief.setWordWrap(True)
        self.summary: QWidget = QWidget(self)
        self.summary.setObjectName('stepSummary')
        self.summary.setStyleSheet('#stepSummary { background: #edf3fa; border-radius: 6px; }')
        summary_layout = QVBoxLayout(self.summary)
        summary_layout.setContentsMargins(10, 10, 10, 10)
        summary_layout.addWidget(self.brief)
        form.addRow(self.summary)
        self.type_input: StepTypeInput = StepTypeInput(self.map_id, self)
        self.action_combo: ComboBox = self.type_input.action_combo
        self.type_input.edited.connect(self.edit_action)
        form.addRow(self.type_input)
        self.name_edit: LineEdit = LineEdit(self)
        self.name_edit.editingFinished.connect(self.edit_step)
        form.addRow('步骤名称', self.name_edit)
        self.target_combo: ComboBox = ComboBox(self)
        self.target_combo.addItem('武备箱', userData='box')
        self.target_combo.addItem('电子保险箱', userData='safe')
        self.target_combo.currentIndexChanged.connect(self.edit_step)
        form.addRow('操作对象', self.target_combo)
        self.target_help: BodyLabel = BodyLabel(self)
        self.target_help.setWordWrap(True)
        self.point_help: BodyLabel = BodyLabel(self)
        self.point_help.setWordWrap(True)
        self.position_heading: SubtitleLabel = SubtitleLabel('目的地 · 地图像素', self)
        self.position_heading.setToolTip('拖动地图上的当前点，或直接输入 X / Y 坐标。')
        form.addRow(self.position_heading)
        self.point_name: LineEdit = LineEdit(self)
        self.point_name.editingFinished.connect(self.edit_point)
        form.addRow('位置名称', self.point_name)
        self.x_input: DoubleSpinBox = self._spin(-1000, 1000)
        self.y_input: DoubleSpinBox = self._spin(-1000, 1000)
        self.coordinate_row: QWidget = QWidget(self)
        coordinate_layout = QHBoxLayout(self.coordinate_row)
        coordinate_layout.setContentsMargins(0, 0, 0, 0)
        for title, spin in (('X', self.x_input), ('Y', self.y_input)):
            coordinate_layout.addWidget(BodyLabel(title, self.coordinate_row))
            coordinate_layout.addWidget(spin, 1)
            spin.setAccessibleName(f'{title} 坐标（地图像素）')
        form.addRow(self.coordinate_row)
        self.navigation_heading: SubtitleLabel = SubtitleLabel('移动设置', self)
        form.addRow(self.navigation_heading)
        self.mode_combo: ComboBox = ComboBox(self)
        for label, value in MOVEMENT_MODES:
            self.mode_combo.addItem(label, userData=value)
        self.mode_combo.currentIndexChanged.connect(self.edit_navigation)
        form.addRow('移动方式', self.mode_combo)
        self.parameter_help: BodyLabel = BodyLabel('取消“使用默认”即可修改。距离单位为地图像素，与窗口缩放无关。', self)
        self.parameter_help.setWordWrap(True)
        self.timeout_default: CheckBox = CheckBox('使用默认', self)
        self.timeout_input: DoubleSpinBox = self._spin(1, 600)
        self.brake_default: CheckBox = CheckBox('不提前松开移动键', self)
        self.brake_input: DoubleSpinBox = self._spin(0.1, 30)
        self.interaction_default: CheckBox = CheckBox('使用默认', self)
        self.interaction_input: DoubleSpinBox = self._spin(0.1, 30)
        self.timeout_input.setSuffix(' 秒')
        self.brake_input.setSuffix(' 像素')
        self.interaction_input.setSuffix(' 像素')
        self.timeout_default.setToolTip(
            '勾选使用默认值；取消勾选后可修改。超时仍未到达，停止这一步。'
        )
        self.brake_default.setToolTip(
            '进入此距离且纵向偏差不超过 2 像素时松键；停稳后核对位置，未到达则继续短步调整。'
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
        self._parameter_row('识别交互提示的范围', self.interaction_default, self.interaction_input)
        self.effective_info: BodyLabel = BodyLabel(self)
        self.effective_info.setWordWrap(True)
        self.tolerance_input: DoubleSpinBox = self._spin(0.1, 30)
        self.tolerance_default: CheckBox = CheckBox('使用默认', self)
        self.tolerance_input.setSuffix(' 像素')
        self.tolerance_default.setToolTip(
            '距离位置小于此数值就算到达。取消勾选可修改；范围越小，要求越精确。'
        )
        self.stop_check: CheckBox = CheckBox('到达这点先停步，再继续', self)
        for spin in (self.x_input, self.y_input, self.tolerance_input):
            spin.editingFinished.connect(self.edit_point)
        self.tolerance_default.clicked.connect(self.edit_point)
        self.stop_check.clicked.connect(self.edit_point)
        self._parameter_row('到达目的地的范围', self.tolerance_default, self.tolerance_input)
        self.passed_default: CheckBox = CheckBox('跟随到达范围', self)
        self.passed_input: DoubleSpinBox = self._spin(0.1, 30)
        self.passed_input.setSuffix(' 像素')
        self.passed_default.clicked.connect(self.edit_point)
        self.passed_input.editingFinished.connect(self.edit_point)
        self.advanced_toggle: PushButton = PushButton(self)
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._update_disclosures)
        form.addRow(self.advanced_toggle)
        self._parameter_row('最长移动时间', self.timeout_default, self.timeout_input)
        self._parameter_row('越过目的地的允许范围', self.passed_default, self.passed_input)
        self._parameter_row('提前松开移动键距离', self.brake_default, self.brake_input)
        form.addRow(self.stop_check)
        self.help_toggle: PushButton = PushButton('查看说明', self)
        self.help_toggle.setCheckable(True)
        self.help_toggle.toggled.connect(self._update_disclosures)
        form.addRow(self.help_toggle)
        self.help_panel: QWidget = QWidget(self)
        help_layout = QVBoxLayout(self.help_panel)
        help_layout.setContentsMargins(0, 0, 0, 0)
        help_layout.setSpacing(10)
        for label in (
            self.rules, self.target_help, self.point_help,
            self.parameter_help, self.effective_info,
        ):
            help_layout.addWidget(label)
        form.addRow(self.help_panel)
        self.edit_widgets.extend(
            (
                self.type_input,
                self.name_edit,
                self.target_combo,
                self.timeout_default,
                self.brake_default,
                self.interaction_default,
                self.mode_combo,
                self.point_name,
                self.tolerance_default,
                self.passed_default,
                self.stop_check,
            )
        )
        scroll.setWidget(properties)
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
        self._refresh_stop_shortcut()
        layout.addLayout(trial)
        layout.addWidget(
            BodyLabel(
                '按列表顺序执行勾选项，跳过未勾选项。每一步都会实际操作游戏；请先把游戏停在第一项需要的画面。'
            )
        )
        self.trial_info: BodyLabel = BodyLabel('尚未测试运行', self)
        self.trial_info.setWordWrap(True)
        layout.addWidget(self.trial_info)
        self.records: ListWidget = ListWidget(self)
        self.records.setMaximumHeight(64)
        layout.addWidget(self.records)
        self.status: BodyLabel = BodyLabel(self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _refresh_stop_shortcut(self) -> None:
        """显示主程序配置的停止键，不注册独立快捷键。"""
        key = (
            self.ctx.key_stop_running
            if self.ctx is not None
            else EnvConfig(RepoConfig()).key_stop_running
        )
        self.stop_button.setText(f'停止 {key.upper()}')
        self.stop_button.setToolTip('沿用一条龙主程序的停止快捷键，可在游戏中按下。')

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
            message = '步骤顺序检查通过；路线能否走通，请在游戏中测试运行确认'
        except ValueError as error:
            message = f'还不能保存或测试运行：{error}'
        self.status.setText(
            f'{"有未保存修改" if self.flow != self.saved[self.map_id] else "草稿未修改"} · {message}'
        )
        if fit:
            self.view.fit()

    def _select_step(self, _index: int = -1) -> None:
        """选择动作时展示对应属性与位置。"""
        if self._updating:
            return
        self._updating = True
        step = self.step
        self._selected_point = len(step.waypoints) - 1 if step is not None else -1
        if step is not None:
            self.action_info.setText(
                f'第 {self.step_list.currentRow() + 1} 步 · {ACTION_LABELS[step.action]}'
            )
            self.type_input.set_action(step.action, self.map_id)
            self.name_edit.setText(step.name)
            if step.action not in ('move', 'approach'):
                self.rules.setText(ACTION_RULES[step.action])
            self.target_combo.setCurrentIndex(1 if step.target == 'safe' else 0)
            if step.action == 'interact':
                panel = '电子保险箱的光圈解锁界面或已解锁的搜查界面' if step.target == 'safe' else '武备箱的搜查界面'
                self.rules.setText(
                    f'先站在出现{self.target_combo.currentText()}交互提示的位置，再按交互键。\n'
                    f'完成条件：打开{panel}。解锁和收集由后续步骤完成。'
                )
            nav = step.navigation
            self.timeout_default.setChecked(nav.timeout is None)
            self.brake_default.setChecked(nav.brake_distance is None)
            self.interaction_default.setChecked(nav.interaction_distance is None)
            self.interaction_input.setValue(nav.effective_interaction_distance)
            self.timeout_input.setValue(nav.effective_timeout(step.target))
            self.brake_input.setValue(nav.effective_brake_distance)
            mode = nav.final_mode or 'coordinate'
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(mode))
            if step.action == 'approach':
                mode_label = self.mode_combo.currentText()
                self.rules.setText(
                    f'{mode_label}，靠近{self.target_combo.currentText()}。\n'
                    f'完成条件：距目标不超过 {nav.effective_interaction_distance:g} 地图像素，'
                    '且出现对应交互提示。此步不按交互键。'
                )
                self.effective_info.setText(
                    '地图点线圈：识别交互提示的范围。\n'
                    '地图实线圈：到达后停下等待交互提示的范围。'
                )
        else:
            self.action_info.setText('当前步骤')
            self.name_edit.clear()
            self.rules.setText('选择左侧步骤查看设置，也可以在列表下方添加步骤。')
            self.effective_info.clear()
        self.brief.setText(self._completion_summary())
        move = step is not None and step.action in ('move', 'approach')
        approach = step is not None and step.action == 'approach'
        self.property_form.setRowVisible(
            self.target_combo, step is not None and step.target is not None
        )
        self.property_form.labelForField(self.target_combo).setText(
            '交互目标' if approach else '操作对象'
        )
        self.target_help.setText(
            '选择需要识别的交互提示。修改交互目标保留目的地、移动方式和实际参数。'
        )
        self.target_combo.setToolTip(self.target_help.text() if approach else '')
        for widget in (
            self.position_heading,
            self.navigation_heading,
            self.interaction_input,
            self.mode_combo,
            self.point_name,
            self.coordinate_row,
            self.tolerance_input,
            self.stop_check,
        ):
            self.property_form.setRowVisible(widget, move)
        self.property_form.setRowVisible(self.interaction_input, approach)
        self.type_input.setEnabled(step is not None and not self.running)
        self.property_form.setRowVisible(self.stop_check, False)
        if step is not None and step.action == 'move':
            point = step.waypoints[0]
            self.rules.setText(
                f'走向“{point.name}”，完成后松开移动键。\n'
                f'完成条件：进入目的地 {point.arrival_radius:g} 地图像素以内；'
                f'或已越过目的地，且仍在 {point.passed_radius:g} 地图像素以内。'
            )
            self.effective_info.setText(
                '地图实线圈：到达范围。\n'
                '地图虚线圈：越过目的地后，仍可完成本步的范围；与实线圈一样大时不重复画。'
            )
            if step.navigation.brake_distance is not None:
                self.effective_info.setText(
                    self.effective_info.text()
                    + f'\n距目的地 {step.navigation.brake_distance:g} 地图像素以内、'
                    '纵向偏差不超过 2 像素时提前松开移动键；等待 0.5 秒后重新定位，'
                    '未到达则继续短步调整，满足完成条件才进入下一步。'
                )
        self.name_edit.setEnabled(step is not None and not self.running)
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
        # 表单切换到较长说明时，保留说明框所需高度，避免被其它参数行挤掉末行。
        self.summary.setMinimumHeight(self.summary.sizeHint().height())
        self._select_point(self._selected_point)
        self._draw()

    def _completion_summary(self) -> str:
        """常驻区域只用一句话概括完成条件，具体参数留在说明中。"""
        step = self.step
        if step is None:
            return '选择一个步骤，查看或修改设置。'
        if step.action == 'move':
            return '进入到达范围或在允许范围内越过目的地后结束。'
        if step.action == 'interact':
            return (
                '打开电子保险箱的光圈解锁界面或已解锁的搜查界面后结束。'
                if step.target == 'safe' else '打开武备箱的搜查界面后结束。'
            )
        return {
            'spawn': '确认当前位置符合所选出生点。',
            'approach': '出现对应交互提示后完成；到点后等待两秒，仍无提示则停止并报错。',
            'unlock': '完成光圈解锁后结束；若已进入搜查界面，确认后直接完成。',
            'store': '处理物品并装入安全箱，保留搜查界面。',
            'close': '关闭搜查界面，确认回到局内后结束。',
            'exit': '退出本局，到达仓库界面后结束。',
        }[step.action]

    def _update_disclosures(self) -> None:
        """展开仅控制显示，不回填字段、不修改草稿或撤销记录。"""
        step = self.step
        move = step is not None and step.action in ('move', 'approach')
        plain_move = move and step.action == 'move'
        advanced = self.advanced_toggle.isChecked()
        explicit = move and (
            step.navigation.timeout is not None
            or plain_move and (
                step.navigation.brake_distance is not None
                or step.waypoints[0].passed_tolerance is not None
            )
        )
        self.advanced_toggle.setText(
            '高级移动参数'
            + (' · 有单独设置' if explicit else '')
        )
        self.advanced_toggle.setIcon(FluentIcon.ARROW_DOWN if advanced else FluentIcon.CHEVRON_RIGHT)
        self.property_form.setRowVisible(self.advanced_toggle, move)
        self.property_form.setRowVisible(self.timeout_input, move and advanced)
        self.property_form.setRowVisible(self.passed_input, plain_move and advanced)
        self.property_form.setRowVisible(self.brake_input, plain_move and advanced)
        help_open = self.help_toggle.isChecked()
        self.help_toggle.setText('收起说明' if help_open else '查看说明')
        self.help_toggle.setIcon(FluentIcon.ARROW_DOWN if help_open else FluentIcon.CHEVRON_RIGHT)
        self.property_form.setRowVisible(self.help_panel, help_open)
        self.target_help.setVisible(move and step.action == 'approach')
        self.point_help.setVisible(move)
        self.parameter_help.setVisible(move)
        self.effective_info.setVisible(move)

    def _select_point(self, index: int) -> None:
        """位置选择与地图同步；不重建场景，允许鼠标继续拖动。"""
        if self._updating:
            return
        self._updating = True
        self._selected_point = index
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
            point = step.waypoints[-1]
            self.position_heading.setText(
                '目的地 · 地图像素'
            )
            self.point_help.setText(
                '可拖动地图上的实心点，或直接修改 X / Y。两种移动方式都朝这个目的地移动。'
            )
            self.point_name.setText(point.name)
            self.x_input.setValue(point.xy[0])
            self.y_input.setValue(point.xy[1])
            self.tolerance_default.setChecked(point.tolerance is None)
            self.tolerance_input.setValue(point.arrival_radius)
            self.passed_default.setChecked(point.passed_tolerance is None)
            self.passed_input.setValue(point.passed_radius)
            self.stop_check.setChecked(point.stop)
        else:
            self.point_help.clear()
        uses_tolerance = valid
        self.property_form.setRowVisible(self.tolerance_input, uses_tolerance)
        self.tolerance_default.setEnabled(uses_tolerance and not self.running)
        self.tolerance_input.setEnabled(
            uses_tolerance and not self.running and not self.tolerance_default.isChecked()
        )
        plain_move = valid and step.action == 'move'
        self.passed_default.setEnabled(plain_move and not self.running)
        self.passed_input.setEnabled(plain_move and not self.running and not self.passed_default.isChecked())
        for item in self.view.scene().items():
            if isinstance(item, RoutePointItem):
                item.setSelected(item.index == index)
        self._updating = False
        self._update_disclosures()

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

    def edit_action(self) -> None:
        """原位转换当前步骤，适用数据保留，撤销可以恢复完整旧步骤。"""
        if self._updating or self.step is None or self.running:
            return
        action = self.action_combo.currentData()
        if action == 'unlock' and self.map_id == 'janus_high_b':
            self._select_step()
            self.status.setText('白鸽地图没有电子保险箱，请选择其他步骤类型。')
            return
        xy = self.step.waypoints[-1].xy if self.step.waypoints else self.models[self.map_id].spawn
        self._replace_step(change_action(self.step, action, xy))

    def edit_step(self) -> None:
        """改名称或交互目标时保留目的地和移动方式。"""
        if self._updating or self.step is None or self.running:
            return
        step = self.step
        if step.target is not None and step.action != 'unlock':
            target = self.target_combo.currentData()
            if target == 'safe' and self.map_id == 'janus_high_b':
                self._select_step()
                self.status.setText('白鸽地图没有电子保险箱，请选择武备箱。')
                return
            step = change_target(step, target)
        self._replace_step(replace(step, name=self.name_edit.text()))

    def edit_navigation(self) -> None:
        """未覆盖的参数保持为空。"""
        if (
            self._updating
            or self.step is None
            or self.step.action not in ('move', 'approach')
            or self.running
        ):
            return
        navigation = replace(
            self.step.navigation,
            final_mode=self.mode_combo.currentData(),
            timeout=None if self.timeout_default.isChecked() else self.timeout_input.value(),
        )
        if self.step.action == 'move':
            navigation = replace(navigation, brake_distance=(
                None if self.brake_default.isChecked() else self.brake_input.value()
            ))
        else:
            navigation = replace(
                navigation,
                interaction_distance=None if self.interaction_default.isChecked() else self.interaction_input.value(),
            )
        step = replace(self.step, navigation=navigation)
        self._replace_step(step)

    def edit_point(self) -> None:
        """提交位置属性并保留选择。"""
        if self._updating or self.step is None or self.running:
            return
        index = len(self.step.waypoints) - 1
        points = list(self.step.waypoints)
        if not 0 <= index < len(points):
            return
        points[index] = replace(
            points[index],
            name=self.point_name.text(),
            tolerance=None
            if self.tolerance_default.isChecked()
            else self.tolerance_input.value(),
            stop=self.stop_check.isChecked(),
            passed_tolerance=(
                self.passed_input.value()
                if self.step.action == 'move' and not self.passed_default.isChecked()
                else None
            ),
        )
        step = replace(self.step, waypoints=tuple(points))
        self._replace_step(move_position(step, (self.x_input.value(), self.y_input.value())))

    def drag_point(self, index: int, xy: tuple[float, float]) -> None:
        """拖点只修改当前移动步骤。"""
        if self.running or self.step is None:
            return
        if index != 0 or len(self.step.waypoints) != 1:
            return
        step = move_position(self.step, xy)
        self._replace_step(step)
        self._select_point(index)
        if not self.models[self.map_id].contains(xy):
            self.status.setText(
                '该位置没有参考像素，请实机核对；地图覆盖不保证可通行。'
            )

    def add_step(self) -> None:
        """在当前步骤后打开完整的新建表单，取消不产生任何改动。"""
        if self.running:
            return
        previous = next((
            s.waypoints[-1].xy
            for s in reversed(self.flow.steps[:self.step_list.currentRow() + 1])
            if s.waypoints
        ), self.models[self.map_id].spawn)
        dialog = BagelStepDialog(self.map_id, previous, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.step is None:
            dialog.deleteLater()
            return
        index = self.step_list.currentRow() + 1
        steps = list(self.flow.steps)
        steps.insert(index, dialog.step)
        self._change(replace(self.flow, steps=tuple(steps)), index)
        dialog.deleteLater()

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
        """将正式流程载入编辑区，不覆盖用户保存的草稿。"""
        self._change(load_published_flow(self.map_id))

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
        """保存当前地图的正式流程，不自动提交或发布。"""
        try:
            BagelFlow.from_dict(self.flow.to_dict())
            if not MessageBox(
                '替换当前地图的正式流程？',
                '保存后，下次运行正式任务将使用这套步骤和路线。请先在游戏中测试运行确认。此操作只修改本机正式流程文件。',
                self,
            ).exec():
                return
            path = resource_root(self.map_id) / 'flow.yml'
            write_flow(path, self.flow)
            self.status.setText(f'已更新正式流程，下次运行任务生效。文件：{path}')
        except (OSError, ValueError) as error:
            log.error('保存正式流程失败', exc_info=True)
            self.status.setText(f'保存正式流程失败：{error}')

    def _draw(self) -> None:
        """绘制出生位置和移动目的地，选中时显示范围，实测轨迹保留断线。"""
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
        for step_index, step in enumerate(self.flow.steps):
            if step.action not in ('move', 'approach'):
                continue
            selected = step_index == self.step_list.currentRow()
            for point in step.waypoints if selected else step.waypoints[-1:]:
                radius = max(point.arrival_radius, point.passed_radius) if selected else 2
                if selected and step.action == 'approach':
                    radius = max(radius, step.navigation.effective_interaction_distance)
                bounds = bounds.united(
                    QRectF(
                        point.xy[0] - radius,
                        point.xy[1] - radius,
                        radius * 2,
                        radius * 2,
                    )
                )
        self.view.content_rect = bounds.adjusted(-8, -8, 8, 8)
        spawn_selected = self.step is not None and self.step.action == 'spawn'
        spawn_color = QColor('#176b57' if spawn_selected else '#657581')
        spawn_index = next((i for i, step in enumerate(self.flow.steps) if step.action == 'spawn'), -1)
        marker = FlowMarkerItem(
            model.spawn, '出生位置',
            lambda: self.step_list.setCurrentRow(spawn_index) if spawn_index >= 0 else None,
            spawn_color,
        )
        marker.setBrush(spawn_color)
        marker.setPen(QPen(spawn_color, 0.5))
        marker.setToolTip('出生位置：地图固定参照，不可拖动。检查范围为 5 地图像素。')
        marker.setData(0, 'spawn')
        scene.addItem(marker)
        label = scene.addSimpleText('出生位置')
        label.setBrush(spawn_color)
        label.setPos(model.spawn[0] + 3, model.spawn[1] + 2)
        label.setFont(self.font())
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        if spawn_selected:
            circle = scene.addEllipse(
                model.spawn[0] - 5, model.spawn[1] - 5, 10, 10, QPen(spawn_color, 0.5),
            )
            circle.setData(0, 'spawn_range')
        bounds = bounds.united(QRectF(model.spawn[0] - 6, model.spawn[1] - 6, 24, 14))
        self.view.content_rect = bounds.adjusted(-8, -8, 8, 8)
        last = model.spawn
        for step_index, step in enumerate(self.flow.steps):
            if step.action not in ('move', 'approach'):
                continue
            selected = step_index == self.step_list.currentRow()
            destination = step.waypoints[-1]
            color = route_color(destination.stage)
            # 路线从出生位置依次连接各步骤的唯一目的地。
            scene.addLine(*last, *destination.xy, QPen(color, 0.7))
            last = destination.xy
            if selected:
                if step.action in ('move', 'approach'):
                    radius = destination.arrival_radius
                    scene.addEllipse(
                        destination.xy[0] - radius, destination.xy[1] - radius,
                        radius * 2, radius * 2, QPen(color, 0.3),
                    )
                    if step.action == 'move' and destination.passed_radius != radius:
                        passed = destination.passed_radius
                        scene.addEllipse(
                            destination.xy[0] - passed, destination.xy[1] - passed,
                            passed * 2, passed * 2,
                            QPen(color, 0.3, Qt.PenStyle.DashLine),
                        )
                if step.action == 'approach':
                    radius = step.navigation.effective_interaction_distance
                    scene.addEllipse(
                        destination.xy[0] - radius, destination.xy[1] - radius,
                        radius * 2, radius * 2,
                        QPen(color, 0.4, Qt.PenStyle.DotLine),
                    )
            for point_index, point in enumerate(step.waypoints):
                if selected:
                    item = RoutePointItem(
                        point_index,
                        point,
                        self.drag_point,
                        self._select_point,
                    )
                    item.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self.running
                    )
                    scene.addItem(item)
                    item.setSelected(point_index == self._selected_point)
                    if step.action == 'approach':
                        item.setToolTip(
                            f'{point.name}：靠近后需出现对应交互提示才算完成。'
                        )
                else:
                    scene.addItem(
                        FlowMarkerItem(
                            point.xy,
                            step.name,
                            lambda index=step_index: self.step_list.setCurrentRow(
                                index
                            ),
                            color,
                        )
                    )
        path = QPainterPath()
        connected = False
        for position in self.trace if self.trace_check.isChecked() else ():
            if position is None:
                connected = False
            elif connected:
                path.lineTo(QPointF(*position))
            else:
                path.moveTo(QPointF(*position))
                connected = True
        scene.addPath(path, QPen(QColor('#007e50'), 0.8, Qt.PenStyle.DashLine))

    def start_trial(self) -> None:
        """按原列表顺序执行勾选项；空清单或无效流程不启动线程。"""
        if self.running:
            return
        self._refresh_stop_shortcut()
        try:
            flow = BagelFlow.from_dict(self.flow.to_dict())
            selected = tuple(
                step.id
                for step in flow.steps
                if step.id in self.checked_steps[self.map_id]
            )
            if not selected:
                raise ValueError('请先在步骤列表左侧勾选要执行的步骤。')
            self.models[self.map_id] = BagelMapModel.load(self.map_id)
        except (OSError, ValueError) as error:
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
            map_snapshot=self.models[self.map_id].snapshot,
        )
        self.worker.observed.connect(self._observe)
        self.worker.completed.connect(self.trial_info.setText)
        self.worker.finished.connect(self._trial_finished)
        for widget in self.edit_widgets:
            widget.setEnabled(False)
        self.step_list.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.trial_info.setText(
            f'请松开鼠标，工具将自动切到游戏。准备执行勾选的 {len(selected)} 步：'
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
                else '本次测试运行'
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
    """独立开发入口，首次测试运行时初始化游戏控制服务。"""
    parser = argparse.ArgumentParser(description='贝果流程开发工具')
    parser.add_argument(
        '--instance',
        type=int,
        default=1,
        help='已配置账号的编号，仅用于测试运行和旧路线导入',
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
