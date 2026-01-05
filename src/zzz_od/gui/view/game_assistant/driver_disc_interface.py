import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtWidgets import QWidget, QFileDialog, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout
from qfluentwidgets import FluentIcon, PushButton, Dialog

from one_dragon.base.operation.application import application_const
from one_dragon.utils import os_utils
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from zzz_od.application.driver_disc_read import driver_disc_read_const
from zzz_od.application.driver_disc_read.drive_disk_exporter import DriveDiskExporter
from zzz_od.application.driver_disc_read.driver_disc_parser import DriverDiscParser
from zzz_od.context.zzz_context import ZContext


class DriverDiscInterface(AppRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.parser = DriverDiscParser()
        self.exporter = DriveDiskExporter()

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=driver_disc_read_const.APP_ID,
            object_name='driver_disc_interface',
            nav_text_cn='驱动盘识别',
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        content = Column()

        # 帮助卡片
        self.help_opt = HelpCard(
            title='驱动盘识别',
            content='自动识别驱动盘属性并导出到指定路径。'
        )
        content.add_widget(self.help_opt)

        # OCR 批量大小配置
        self.ocr_batch_card = SpinBoxSettingCard(
            icon=FluentIcon.SYNC,
            title='OCR 批量大小',
            content='批量推理的批次大小。数值越大 GPU 利用率越高，但首批结果延迟会增加。',
            minimum=4,
            maximum=128,
            step=4
        )
        self.ocr_batch_card.init_with_adapter(get_prop_adapter(self.ctx.model_config, 'ocr_batch_size'))
        content.add_widget(self.ocr_batch_card)

        # 导出路径配置
        self.export_path_adapter = get_prop_adapter(self.ctx.one_dragon_config, 'disc_export_path')
        current_export_path = self.export_path_adapter.get_value()

        self.export_path_card = PushSettingCard(
            icon=FluentIcon.FOLDER,
            title='导出路径',
            text='选择文件夹',
            content=self._format_export_path(current_export_path),
        )
        self.export_path_card.clicked.connect(self._on_choose_export_path)
        content.add_widget(self.export_path_card)

        # 操作按钮
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        
        self.history_btn = PushButton(text='加载历史', icon=FluentIcon.HISTORY)
        self.history_btn.clicked.connect(self._on_history_clicked)
        button_layout.addWidget(self.history_btn)

        self.clean_btn = PushButton(text='数据清洗', icon=FluentIcon.BROOM)
        self.clean_btn.clicked.connect(self._on_clean_clicked)
        button_layout.addWidget(self.clean_btn)

        self.preview_btn = PushButton(text='预览缓存', icon=FluentIcon.VIEW)
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        button_layout.addWidget(self.preview_btn)

        self.export_csv_btn = PushButton(text='导出CSV', icon=FluentIcon.SAVE)
        self.export_csv_btn.clicked.connect(self._on_export_csv_clicked)
        button_layout.addWidget(self.export_csv_btn)

        self.export_zod_btn = PushButton(text='导出ZOD', icon=FluentIcon.SHARE)
        self.export_zod_btn.clicked.connect(self._on_export_zod_clicked)
        button_layout.addWidget(self.export_zod_btn)
        
        content.add_widget(button_container)

        return content

    def _on_history_clicked(self):
        self.ctx.shared_dialog_manager.show_driver_disc_read_setting_dialog(
            parent=self,
            group_id=application_const.DEFAULT_GROUP_ID
        )

    def _on_clean_clicked(self):
        """
        执行数据清洗逻辑
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            self.show_message_box('错误', '未找到缓存文件，请先运行识别或导入')
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                raw_data_list = json.load(f)
            
            # 备份原始数据
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            history_dir = cache_dir / 'history'
            history_dir.mkdir(parents=True, exist_ok=True)
            backup_file = history_dir / f'pre_clean_{timestamp}.json'
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(raw_data_list, f, ensure_ascii=False, indent=4)

            cleaned_data = []
            for raw_item in raw_data_list:
                # 使用 parse_flat 保持扁平结构
                parsed = self.parser.parse_flat(raw_item)
                cleaned_data.append(parsed)

            # 保存回缓存
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=4)

            self.show_message_box('成功', f'清洗完成，已更新 {len(cleaned_data)} 条数据')
        except Exception as e:
            self.show_message_box('错误', f'数据清洗失败: {e}')

    def _get_export_dir(self) -> Path:
        """获取导出目录，优先使用配置的路径"""
        configured_path = self.export_path_adapter.get_value()
        if configured_path:
            export_dir = Path(configured_path)
        else:
            export_dir = Path(os_utils.get_path_under_work_dir('export'))
        
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir

    def _on_export_csv_clicked(self):
        """
        执行导出 CSV 逻辑
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            self.show_message_box('错误', '未找到缓存文件')
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
            
            if not data_list:
                self.show_message_box('提示', '缓存数据为空')
                return

            export_dir = self._get_export_dir()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = export_dir / f'driver_disc_{timestamp}.csv'

            # 获取所有可能的字段名作为表头
            fieldnames = set()
            for item in data_list:
                fieldnames.update(item.keys())
            
            # 排序字段：name, slot, level, rating, main_stat...
            sorted_fields = ['name', 'slot', 'level', 'rating', 'main_stat', 'main_stat_value']
            other_fields = sorted(list(fieldnames - set(sorted_fields)))
            fieldnames = sorted_fields + other_fields

            with open(export_file, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data_list)

            self.show_message_box('成功', f'CSV已导出至: {export_file}')
        except Exception as e:
            self.show_message_box('错误', f'导出CSV失败: {e}')

    def _on_export_zod_clicked(self):
        """
        执行导出 ZOD 逻辑
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            self.show_message_box('错误', '未找到缓存数据')
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                flat_data_list = json.load(f)
            
            # 先转换为嵌套结构，再导出
            nested_data_list = [self.parser.parse(item) for item in flat_data_list]
            zod_data = self.exporter.convert_to_zod_json(nested_data_list)
            
            export_dir = self._get_export_dir()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = export_dir / f'driver_disc_zod_{timestamp}.json'
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(zod_data, f, ensure_ascii=False, indent=4)
                
            self.show_message_box('成功', f'ZOD格式数据已导出至: {export_file}')
        except Exception as e:
            self.show_message_box('错误', f'导出失败: {e}')

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)

    def _on_choose_export_path(self) -> None:
        """弹出文件夹选择器并保存结果"""
        current_value = self.export_path_adapter.get_value()
        if current_value:
            current_path = Path(current_value)
            if not current_path.is_absolute():
                current_path = Path(os_utils.get_work_dir()) / current_path
        else:
            current_path = Path(os_utils.get_path_under_work_dir('driver_disc'))

        selected_dir = QFileDialog.getExistingDirectory(self, '选择导出文件夹', str(current_path))
        if not selected_dir:
            return

        selected_path = Path(selected_dir)
        work_dir = Path(os_utils.get_work_dir())

        try:
            relative_path = selected_path.relative_to(work_dir)
            save_value = relative_path.as_posix()
        except ValueError:
            save_value = str(selected_path)

        self.export_path_adapter.set_value(save_value)
        self.export_path_card.setContent(self._format_export_path(save_value))

    @staticmethod
    def _format_export_path(path_value: Optional[str]) -> str:
        """格式化导出路径显示"""
        if not path_value:
            return '使用默认路径（driver_disc）'
        return path_value

    def _on_preview_clicked(self):
        cache_file = Path(os_utils.get_path_under_work_dir('driver_disc')) / 'cache.json'
        if not cache_file.exists():
            self.show_message_box('提示', '暂无缓存数据，请先运行识别')
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                self.show_message_box('提示', '缓存数据为空')
                return

            self._show_preview_window(data)
        except Exception as e:
            self.show_message_box('错误', f'读取缓存失败: {e}')

    def _show_preview_window(self, data: List[Dict]):
        self.preview_window = QWidget()
        self.preview_window.setWindowTitle(f'驱动盘预览 ({len(data)}条)')
        self.preview_window.resize(1000, 600)
        
        layout = QVBoxLayout(self.preview_window)
        
        table = QTableWidget()
        fieldnames = ['name', 'slot', 'level', 'rating', 'main_stat', 'main_stat_value',
                      'sub_stat1', 'sub_stat1_value', 'sub_stat2', 'sub_stat2_value',
                      'sub_stat3', 'sub_stat3_value', 'sub_stat4', 'sub_stat4_value']
        headers = ['名称', '位置', '等级', '评级', '主属性', '主属性值', 
                   '副属性1', '副属性1值', '副属性2', '副属性2值', 
                   '副属性3', '副属性3值', '副属性4', '副属性4值']
        
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(data))
        
        for row, item in enumerate(data):
            for col, key in enumerate(fieldnames):
                val = item.get(key, '')
                table.setItem(row, col, QTableWidgetItem(str(val)))
        
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table)
        
        self.preview_window.show()

    def show_message_box(self, title, content):
        w = Dialog(title, content, self)
        w.exec()
