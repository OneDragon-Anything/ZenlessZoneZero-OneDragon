from typing import Optional

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.utils import os_utils
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
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
        self.export_path_card = TextSettingCard(
            icon=FluentIcon.FOLDER,
            title='导出路径',
            content='驱动盘数据 CSV 文件的导出路径。留空则保存到使用默认路径 driver_disc 下'
        )
        self.export_path_card.init_with_adapter(get_prop_adapter(self.ctx.one_dragon_config, 'disc_export_path'))
        content.add_widget(self.export_path_card)

        return content

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
