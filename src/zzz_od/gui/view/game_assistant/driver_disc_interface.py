from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QFileDialog
from qfluentwidgets import FluentIcon

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
