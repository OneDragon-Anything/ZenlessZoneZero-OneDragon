import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtWidgets import QWidget, QFileDialog, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout
from qfluentwidgets import FluentIcon, PushButton, Dialog

from one_dragon.utils import os_utils
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from zzz_od.application.driver_disc_read import driver_disc_read_const
from zzz_od.context.zzz_context import ZContext


class DriverDiscInterface(AppRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

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
            content='自动识别驱动盘属性并导出到指定路径。支持 GPU 多进程并行处理，修改配置后需重启程序生效。'
        )
        content.add_widget(self.help_opt)

        # OCR worker 进程数配置
        self.ocr_worker_card = SpinBoxSettingCard(
            icon=FluentIcon.IOT,
            title='OCR Worker 进程数',
            content='并行处理 OCR 识别的进程数量。GPU 模式推荐 4-6，CPU 模式推荐 2-4。每个进程独立占用约 500MB 内存。',
            minimum=1,
            maximum=8,
            step=1
        )
        # 初始化时加载配置值
        self.ocr_worker_card.init_with_adapter(get_prop_adapter(self.ctx.model_config, 'ocr_worker_count'))
        content.add_widget(self.ocr_worker_card)

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
        
        self.preview_btn = PushButton(text='预览缓存', icon=FluentIcon.VIEW)
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        button_layout.addWidget(self.preview_btn)

        self.export_btn = PushButton(text='导出缓存', icon=FluentIcon.SAVE)
        self.export_btn.clicked.connect(self._on_export_clicked)
        button_layout.addWidget(self.export_btn)
        
        content.add_widget(button_container)

        return content

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
        fieldnames = ['name', 'level', 'rating', 'main_stat', 'main_stat_value',
                      'sub_stat1', 'sub_stat1_value', 'sub_stat2', 'sub_stat2_value',
                      'sub_stat3', 'sub_stat3_value', 'sub_stat4', 'sub_stat4_value']
        headers = ['名称', '等级', '评级', '主属性', '主属性值', 
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

    def _on_export_clicked(self):
        cache_file = Path(os_utils.get_path_under_work_dir('driver_disc')) / 'cache.json'
        if not cache_file.exists():
            self.show_message_box('提示', '暂无缓存数据，请先运行识别')
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                disc_data_list = json.load(f)
            
            if not disc_data_list:
                self.show_message_box('提示', '缓存数据为空')
                return

            # Export logic
            export_path = self.ctx.one_dragon_config.get('disc_export_path', '')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            if export_path:
                user_path = Path(export_path)
                if not user_path.is_absolute():
                    user_path = Path(os_utils.get_work_dir()) / user_path

                if user_path.suffix:
                    base_dir = user_path.parent
                    file_stem = user_path.stem
                    file_suffix = user_path.suffix
                else:
                    base_dir = user_path
                    file_stem = 'driver_disc_data'
                    file_suffix = '.csv'
            else:
                base_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
                file_stem = 'driver_disc_data'
                file_suffix = '.csv'

            csv_file = base_dir / f'{file_stem}_{timestamp}{file_suffix}'
            base_dir.mkdir(parents=True, exist_ok=True)

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                        fieldnames = ['name', 'level', 'rating', 'main_stat', 'main_stat_value',
                                      'sub_stat1', 'sub_stat1_value', 'sub_stat2', 'sub_stat2_value',
                                      'sub_stat3', 'sub_stat3_value', 'sub_stat4', 'sub_stat4_value']
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writerow({'name': '驱动盘名称', 'level': '等级', 'rating': '评级',
                                         'main_stat': '主属性', 'main_stat_value': '主属性值',
                                         'sub_stat1': '副属性1', 'sub_stat1_value': '副属性1值',
                                         'sub_stat2': '副属性2', 'sub_stat2_value': '副属性2值',
                                         'sub_stat3': '副属性3', 'sub_stat3_value': '副属性3值',
                                         'sub_stat4': '副属性4', 'sub_stat4_value': '副属性4值'})
                        writer.writerows(disc_data_list)
                    
                    self.show_message_box('成功', f'已保存 {len(disc_data_list)} 条数据到:\n{csv_file}')
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        timestamp_new = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                        csv_file = base_dir / f'{file_stem}_{timestamp_new}{file_suffix}'
                        time.sleep(0.1)
                    else:
                        self.show_message_box('失败', f'保存失败: 文件被占用，请关闭 {csv_file.name} 后重试')

        except Exception as e:
            self.show_message_box('错误', f'导出失败: {e}')

    def show_message_box(self, title, content):
        w = Dialog(title, content, self)
        w.exec()
