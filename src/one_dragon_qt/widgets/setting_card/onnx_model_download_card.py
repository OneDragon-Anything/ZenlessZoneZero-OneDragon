from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, Qt
from qfluentwidgets import FluentIconBase, SwitchButton, IndicatorPosition
from typing import Union

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon_qt.widgets.setting_card.common_download_card import ZipDownloaderSettingCard


class OnnxModelDownloadCard(ZipDownloaderSettingCard):

    gpu_changed = Signal(bool)

    def __init__(
            self,
            ctx: OneDragonContext,
            icon: Union[str, QIcon, FluentIconBase],
            title: str,
            content=None,
            parent=None
    ):
        self.gpu_opt = SwitchButton(indicatorPos=IndicatorPosition.LEFT)
        self.gpu_opt._offText = 'CPU'
        self.gpu_opt._onText = 'GPU'
        self.gpu_opt.label.setText(self.gpu_opt._offText)
        self.gpu_opt.checkedChanged.connect(self.on_gpu_value_changed)

        ZipDownloaderSettingCard.__init__(
            self,
            ctx=ctx,
            icon=icon,
            title=title,
            content=content,
            extra_btn_list=[self.gpu_opt],
            parent=parent
        )

    def on_gpu_value_changed(self, value: bool) -> None:
        self.gpu_changed.emit(value)
