from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QLabel, QComboBox, QHBoxLayout
from qfluentwidgets import PrimaryPushButton, FluentIcon, Dialog

from one_dragon.utils import os_utils
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class DriverDiscReadSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="驱动盘识别配置", parent=parent)
        self.history_combo = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        # 历史记录选择区域
        history_card = SettingCardBase(icon=FluentIcon.HISTORY, title="历史记录回溯")
        
        self.history_combo = QComboBox()
        self.history_combo.setMinimumWidth(300)

        load_btn = PrimaryPushButton("加载选中记录", self)
        load_btn.clicked.connect(self._on_load_clicked)
        
        # 将组件添加到 card 的布局中
        history_card.hBoxLayout.addWidget(self.history_combo)
        history_card.hBoxLayout.addSpacing(10)
        history_card.hBoxLayout.addWidget(load_btn)
        history_card.hBoxLayout.addSpacing(16)

        content_widget.add_widget(history_card)
        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()
        self._refresh_history_list()

    def _refresh_history_list(self):
        if not self.history_combo:
            return
            
        self.history_combo.clear()
        
        history_dir = Path(os_utils.get_path_under_work_dir('driver_disc', 'history'))
        if not history_dir.exists():
            self.history_combo.addItem("无历史记录")
            self.history_combo.setEnabled(False)
            return

        # 获取所有 json 文件并按修改时间倒序排序
        files = sorted(history_dir.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)
        
        if not files:
            self.history_combo.addItem("无历史记录")
            self.history_combo.setEnabled(False)
            return

        self.history_combo.setEnabled(True)
        for f in files:
            # 显示文件名和修改时间
            # 格式: scan_20251021_120000.json
            self.history_combo.addItem(f.name, str(f))

    def _on_load_clicked(self):
        selected_path = self.history_combo.currentData()
        if not selected_path:
            self._show_message('提示', '请先选择一条历史记录')
            return

        source_file = Path(selected_path)
        if not source_file.exists():
            self._show_message('错误', '选中的文件不存在')
            return

        target_file = Path(os_utils.get_path_under_work_dir('driver_disc', 'cache.json'))
        
        try:
            shutil.copy2(source_file, target_file)
            self._show_message('成功', f'已加载历史记录: {source_file.name}')
        except Exception as e:
            self._show_message('错误', f'加载失败: {e}')

    def _show_message(self, title, content):
        w = Dialog(title, content, self)
        w.exec()
