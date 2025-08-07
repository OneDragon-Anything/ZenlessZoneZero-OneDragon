from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import SettingCardGroup, FluentIcon, BodyLabel, setFont

from one_dragon.base.config.basic_model_config import get_ocr_opts
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.install_card.launcher_install_card import LauncherInstallCard
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.onnx_model_download_card import OnnxModelDownloadCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class ResourceDownloadInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='resource_download_interface',
            content_widget=None, parent=parent,
            nav_text_cn='资源下载'
        )

        self.ctx: OneDragonContext = ctx

    def get_content_widget(self) -> QWidget:

        content_widget = QWidget()
        control_layout = QVBoxLayout(content_widget)

        control_layout.addWidget(self._init_common_group())

        log_label = BodyLabel(gt('日志显示'))
        setFont(log_label, 20)
        control_layout.addWidget(log_label)

        self.log_card = LogDisplayCard()
        control_layout.addWidget(self.log_card, stretch=1)

        return content_widget

    def _init_common_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt('资源下载'))

        self.help_opt = HelpCard(title='下载说明', content='下载失败时 请尝试到「脚本环境」更改网络代理')
        group.addSettingCard(self.help_opt)

        self.launcher_opt = LauncherInstallCard(self.ctx)
        self.launcher_opt.install_btn.setText(gt('下载'))
        self.launcher_opt.check_and_update_display()
        group.addSettingCard(self.launcher_opt)

        self.ocr_opt = OnnxModelDownloadCard(ctx=self.ctx, icon=FluentIcon.GLOBE, title='OCR识别')
        self.ocr_opt.value_changed.connect(self.on_ocr_changed)
        self.ocr_opt.gpu_changed.connect(self.on_ocr_gpu_changed)
        group.addSettingCard(self.ocr_opt)

        self._add_model_cards(group)

        return group

    def _add_model_cards(self) -> None:
        pass

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.log_card.start()
        self.init_ocr_opts()

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.log_card.stop()

    def init_ocr_opts(self) -> None:
        self.ocr_opt.blockSignals(True)
        self.ocr_opt.set_options_by_list(get_ocr_opts())
        self.ocr_opt.set_value_by_save_file_name(f'{self.ctx.model_config.ocr}.zip')
        self.ocr_opt.gpu_opt.setChecked(self.ctx.model_config.ocr_gpu)
        self.ocr_opt.check_and_update_display()
        self.ocr_opt.blockSignals(False)

    def on_ocr_changed(self, index: int, value: CommonDownloaderParam) -> None:
        self.ctx.model_config.ocr = value.save_file_name[:-4]
        self.ocr_opt.check_and_update_display()

    def on_ocr_gpu_changed(self, value: bool) -> None:
        self.ctx.model_config.ocr_gpu = value
