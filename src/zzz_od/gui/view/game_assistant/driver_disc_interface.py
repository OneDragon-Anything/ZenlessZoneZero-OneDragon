import csv
import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QHeaderView, QTableWidgetItem, QFileDialog
from qfluentwidgets import FluentIcon, PushButton, TableWidget, InfoBar, InfoBarPosition

from one_dragon.utils import os_utils
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
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
            content='自动识别驱动盘属性并导出。支持 GPU 多进程并行处理，推荐配置 4-6 个 worker 进程以获得最佳性能。'
        )
        content.add_widget(self.help_opt)

        # OCR worker 进程数配置
        self.ocr_worker_card = SpinBoxSettingCard(
            icon=FluentIcon.IOT,
            title='OCR Worker 进程数',
            content='并行处理 OCR 识别的进程数量。GPU 模式推荐 4-6，CPU 模式推荐 2-4。每个进程独立占用约 500MB 内存。修改后需重启程序生效。',
            minimum=1,
            maximum=8,
            step=1
        )
        # 初始化时加载配置值
        self.ocr_worker_card.init_with_adapter(get_prop_adapter(self.ctx.model_config, 'ocr_worker_count'))
        content.add_widget(self.ocr_worker_card)

        # 表格区域
        table_row = Row()

        # 创建表格
        self.disc_table = TableWidget()
        self.disc_table.setMinimumHeight(300)

        # 启用边框和圆角
        self.disc_table.setBorderVisible(True)
        self.disc_table.setBorderRadius(8)

        # 设置表头
        headers = ['驱动盘名称', '等级', '评级', '主属性', '副属性1', '副属性2', '副属性3', '副属性4']
        self.disc_table.setColumnCount(len(headers))
        self.disc_table.setHorizontalHeaderLabels(headers)

        # 设置表格属性
        self.disc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.disc_table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)  # 只读
        self.disc_table.setWordWrap(False)

        # 初始化为空表格（数据将在界面显示时自动加载）
        self.disc_table.setRowCount(0)

        table_row.add_widget(self.disc_table, stretch=1)
        content.add_widget(table_row)

        # 导出按钮行
        button_row = Row()

        self.load_btn = PushButton(
            text='加载数据',
            icon=FluentIcon.SYNC
        )
        self.load_btn.clicked.connect(self._on_load_clicked)
        button_row.add_widget(self.load_btn)

        self.export_btn = PushButton(
            text='导出数据',
            icon=FluentIcon.SAVE
        )
        self.export_btn.clicked.connect(self._on_export_clicked)
        button_row.add_widget(self.export_btn)

        button_row.add_stretch(1)

        content.add_widget(button_row)

        return content

    def _on_load_clicked(self) -> None:
        """加载数据按钮点击事件"""
        self._load_disc_data()

    def _on_export_clicked(self) -> None:
        """导出按钮点击事件"""
        # 获取上次导出路径
        last_export_path = self.ctx.one_dragon_config.get('last_disc_export_path', '')

        # 默认导出目录
        default_dir = os_utils.get_path_under_work_dir('driver_disc')

        # 如果有上次路径，使用上次的目录
        if last_export_path and os.path.exists(os.path.dirname(last_export_path)):
            initial_path = last_export_path
        else:
            # 确保默认目录存在
            os.makedirs(default_dir, exist_ok=True)
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            initial_path = os.path.join(default_dir, f'driver_disc_data_{timestamp}.csv')

        # 打开文件保存对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出驱动盘数据",
            initial_path,
            "CSV 文件 (*.csv)"
        )

        if file_path:
            success = self._export_disc_data(file_path)
            if success:
                # 保存此次导出路径
                self.ctx.one_dragon_config.update('last_disc_export_path', file_path)
                InfoBar.success(
                    title='导出成功',
                    content=f'数据已导出到：{file_path}',
                    orient=InfoBarPosition.TOP,
                    isClosable=True,
                    parent=self
                )
            else:
                InfoBar.error(
                    title='导出失败',
                    content='没有可导出的数据，请先运行识别',
                    orient=InfoBarPosition.TOP,
                    isClosable=True,
                    parent=self
                )

    def _load_disc_data(self) -> None:
        """从最新的 CSV 文件加载驱动盘数据到表格"""
        try:
            # 查找最新的 CSV 文件
            data_dir = os_utils.get_path_under_work_dir('config', 'driver_disc_data')
            if not os.path.exists(data_dir):
                InfoBar.warning(
                    title='无数据',
                    content='未找到驱动盘数据，请先运行识别',
                    orient=InfoBarPosition.TOP,
                    isClosable=True,
                    parent=self
                )
                return

            csv_files = list(Path(data_dir).glob('*.csv'))
            if not csv_files:
                InfoBar.warning(
                    title='无数据',
                    content='未找到驱动盘数据文件',
                    orient=InfoBarPosition.TOP,
                    isClosable=True,
                    parent=self
                )
                return

            # 获取最新的文件
            latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)

            # 读取 CSV 文件
            with open(latest_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # 更新表格
            self.disc_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                # 提取并格式化数据
                name = row.get('name', '')
                level = row.get('level', '')
                rating = row.get('rating', '')
                main_stat = f"{row.get('main_stat', '')} {row.get('main_stat_value', '')}".strip()
                sub_stats = []
                for j in range(1, 5):
                    stat = row.get(f'sub_stat{j}', '')
                    value = row.get(f'sub_stat{j}_value', '')
                    if stat:
                        sub_stats.append(f"{stat} {value}".strip())
                    else:
                        sub_stats.append('')

                # 填充表格：名称、等级、评级、主属性、副属性1-4
                data = [name, level, rating, main_stat] + sub_stats
                for col, cell_data in enumerate(data):
                    self.disc_table.setItem(i, col, QTableWidgetItem(cell_data))

            InfoBar.success(
                title='加载成功',
                content=f'已加载 {len(rows)} 条驱动盘数据',
                orient=InfoBarPosition.TOP,
                isClosable=True,
                parent=self
            )

        except Exception as e:
            InfoBar.error(
                title='加载失败',
                content=f'加载数据时出错: {str(e)}',
                orient=InfoBarPosition.TOP,
                isClosable=True,
                parent=self
            )

    def _export_disc_data(self, file_path: str) -> bool:
        """导出表格数据到 CSV 文件"""
        try:
            # 检查表格是否有数据
            if self.disc_table.rowCount() == 0:
                return False

            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 写入 CSV
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)

                # 写入表头
                headers = []
                for col in range(self.disc_table.columnCount()):
                    headers.append(self.disc_table.horizontalHeaderItem(col).text())
                writer.writerow(headers)

                # 写入数据
                for row in range(self.disc_table.rowCount()):
                    row_data = []
                    for col in range(self.disc_table.columnCount()):
                        item = self.disc_table.item(row, col)
                        row_data.append(item.text() if item else '')
                    writer.writerow(row_data)

            return True

        except Exception as e:
            print(f'导出失败: {e}')
            return False

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
        # 自动加载最新数据
        self._load_disc_data()
