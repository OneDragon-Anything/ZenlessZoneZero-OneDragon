"""Native task flyout: one draggable target list, account-local transactional save."""

from copy import deepcopy
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
)
from qfluentwidgets import BodyLabel, ComboBox, PushButton, SpinBox

from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from zzz_od.application.inventory_maintain.inventory_maintain import (
    ROOT,
    ROUTES,
    StockStore,
    material_options,
    unavailable_materials,
    validate_targets,
)


class InventoryMaintainSettings(AppSettingFlyout):
    def __init__(
        self, ctx: Any, group_id: Any, parent: Any = None, *, root: Any = ROOT
    ) -> None:
        self.root = root
        self.instance_idx = ctx.current_instance_idx
        self.store = StockStore(self.instance_idx, root)
        self.history, self.options = ({}, [])
        super().__init__(ctx, group_id, parent)

    def _setup_ui(self, layout: Any) -> Any:
        self.setMinimumWidth(460)
        layout.addWidget(
            BodyLabel('按列表顺序补齐材料；达标或自然电量不足就结束。', self)
        )
        self.notice = BodyLabel('', self)
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        bar = QHBoxLayout()
        self.material = ComboBox(self)
        self.add_button = PushButton('新增', self)
        self.remove_button = PushButton('移除', self)
        bar.addWidget(self.material, 1)
        bar.addWidget(self.add_button)
        bar.addWidget(self.remove_button)
        layout.addLayout(bar)
        self.items = QListWidget(self)
        self.items.setMinimumHeight(160)
        self.items.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.items.setDefaultDropAction(Qt.DropAction.MoveAction)
        layout.addWidget(self.items)
        self.coverage = BodyLabel('', self)
        self.coverage.setWordWrap(True)
        layout.addWidget(self.coverage)
        self.unsupported = QListWidget(self)
        self.unsupported.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.unsupported.setMaximumHeight(130)
        layout.addWidget(self.unsupported)
        detail = QHBoxLayout()
        detail.addWidget(BodyLabel('目标数量', self))
        self.target = SpinBox(self)
        self.target.setRange(0, 10000000)
        detail.addWidget(self.target)
        detail.addStretch()
        layout.addLayout(detail)
        self.route_label = BodyLabel('', self)
        self.route_label.setWordWrap(True)
        layout.addWidget(self.route_label)
        footer = QHBoxLayout()
        self.save_button = PushButton('保存', self)
        self.reset_button = PushButton('撤销未保存修改', self)
        footer.addWidget(self.save_button)
        footer.addWidget(self.reset_button)
        footer.addStretch()
        layout.addLayout(footer)
        self.add_button.clicked.connect(self.add_material)
        self.remove_button.clicked.connect(self.remove_material)
        self.items.currentItemChanged.connect(self.show_detail)
        self.target.valueChanged.connect(self.change_target)
        self.save_button.clicked.connect(self.save_targets)
        self.reset_button.clicked.connect(self.init_config)

    def editable(self) -> Any:
        return (
            self.ctx.current_instance_idx == self.instance_idx
            and self.ctx.run_context.is_context_stop is True
        )

    def init_config(self) -> Any:
        try:
            saved = self.store.read()
            self.options = material_options(self.root)
            scope = unavailable_materials(self.root)
            self.coverage.setText(
                f'可补刷 {scope["available_items"]} 种材料；扩展识别仍为试用。以下尚无补刷入口，不会自动刷取。'
            )
            self.unsupported.clear()
            for row in scope['missing']:
                self.unsupported.addItem(f'{row["name"]}：数量未知 · 未接入补刷')
            self.unsupported.setVisible(bool(scope['missing']))
            self.history = saved['history']
            self.material.clear()
            for row in self.options:
                self.material.addItem(row['name'], userData=deepcopy(row))
            self.items.clear()
            for row in saved['targets']:
                self.append_row(row)
            self.items.setCurrentRow(0)
            pending = bool(saved['pending'])
            self.notice.setText(
                '上次补刷尚未核实，不会自动重刷。请先检查日志。'
                if pending
                else '拖动调整顺序。数量是上次识别结果，运行时会重新检查。'
            )
            enabled = self.editable() and (not pending)
        except Exception as exc:
            self.notice.setText('库存设置暂不可用：' + str(exc)[:180])
            enabled = False
        for widget in (
            self.material,
            self.add_button,
            self.remove_button,
            self.items,
            self.target,
            self.save_button,
        ):
            widget.setEnabled(enabled)

    def quantity(self, row: Any) -> Any:
        matches = [
            value
            for value in self.history.get('materials', [])
            if value.get('id') == row['id'] and value.get('name') == row['name']
        ]
        if (
            len(matches) == 1
            and matches[0].get('status') == 'confirmed'
            and (type(matches[0].get('quantity')) is int)
            and (matches[0]['quantity'] >= 0)
        ):
            return str(matches[0]['quantity'])
        return '未知'

    def append_row(self, row: Any) -> Any:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, deepcopy(row))
        self.update_text(item)
        self.items.addItem(item)

    def update_text(self, item: Any) -> Any:
        row = item.data(Qt.ItemDataRole.UserRole)
        item.setText(f'{row["name"]}: {self.quantity(row)}/{row["target"]}')

    def add_material(self) -> Any:
        if not self.editable():
            return
        row = self.material.currentData()
        if not row:
            return
        if any(
            self.items.item(i).data(Qt.ItemDataRole.UserRole)['id'] == row['id']
            for i in range(self.items.count())
        ):
            self.notice.setText('此材料已在列表中。')
            return
        self.append_row(dict(row, target=20))
        self.items.setCurrentRow(self.items.count() - 1)

    def remove_material(self) -> Any:
        if self.editable() and self.items.currentRow() >= 0:
            self.items.takeItem(self.items.currentRow())

    def show_detail(self, current: Any = None, previous: Any = None) -> Any:
        self.target.blockSignals(True)
        if current is None:
            self.target.setValue(0)
            self.route_label.setText('选择材料后查看刷取入口。')
        else:
            row = current.data(Qt.ItemDataRole.UserRole)
            self.target.setValue(row['target'])
            observed = self.history.get('observed_at')
            try:
                timestamp = (
                    datetime.fromisoformat(observed)
                    .astimezone()
                    .strftime('%m-%d %H:%M')
                )
            except (ValueError, TypeError):
                timestamp = '尚未识别'
            route = ROUTES.get(row['route'], {})
            detail = (
                f'刷取入口：{route.get("name", "尚未接入")} · 上次识别：{timestamp}'
            )
            if row['id'] in (
                'advanced-attack-seal',
                'pioneer-certification-seal',
                'advanced-physical-chip',
                'specialized-physical-chip',
                'basic-freeze-chip',
                'advanced-freeze-chip',
                'specialized-freeze-chip',
            ):
                detail += '\n每场20电量，按实际品质重新计数；不会自动合成。'
            if route.get('category') == '恶名狩猎':
                detail += '\nLv.65深度追猎，每场60电量；请先用完免费周本次数。'
            elif route.get('category') == '专业挑战室':
                detail += '\n每场40自然电量；每打完一场重新检查库存。'
            self.route_label.setText(detail)
        self.target.blockSignals(False)

    def change_target(self, value: Any) -> Any:
        item = self.items.currentItem()
        if item is not None and self.editable():
            row = item.data(Qt.ItemDataRole.UserRole)
            row['target'] = value
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.update_text(item)

    def save_targets(self) -> Any:
        try:
            if not self.editable():
                raise RuntimeError('请先停止任务，并保持当前账号不变')
            if self.store.read()['pending']:
                raise RuntimeError('上次补刷尚未核实，不修改刷取目标')
            rows = [
                self.items.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.items.count())
            ]
            rows = validate_targets(rows, self.root)
            self.store.update('targets', rows)
            self.notice.setText('已保存。此任务不恢复电量，也不影响原清体力计划。')
        except Exception as exc:
            self.notice.setText('未保存：' + str(exc)[:180])
