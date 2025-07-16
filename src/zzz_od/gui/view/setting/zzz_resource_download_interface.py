from PySide6.QtWidgets import QWidget
from qfluentwidgets import SettingCardGroup, FluentIcon

from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon_qt.view.setting.resource_download_interface import ResourceDownloadInterface
from one_dragon_qt.widgets.setting_card.onnx_model_download_card import OnnxModelDownloadCard
from zzz_od.config.model_config import get_flash_classifier_opts, get_hollow_zero_event_opts, get_lost_void_det_opts
from zzz_od.context.zzz_context import ZContext


class ZResourceDownloadInterface(ResourceDownloadInterface):

    def __init__(self, ctx: ZContext, parent=None):
        ResourceDownloadInterface.__init__(self, ctx, parent)
        self.ctx: ZContext = ctx

    def _add_model_cards(self, group: SettingCardGroup) -> None:

        self.flash_classifier_opt = OnnxModelDownloadCard(ctx=self.ctx, icon=FluentIcon.GLOBE, title='闪光识别')
        self.flash_classifier_opt.value_changed.connect(self.on_flash_classifier_changed)
        self.flash_classifier_opt.gpu_changed.connect(self.on_flash_classifier_gpu_changed)
        group.addSettingCard(self.flash_classifier_opt)

        self.hollow_zero_event_opt = OnnxModelDownloadCard(ctx=self.ctx, icon=FluentIcon.GLOBE, title='空洞格子识别')
        self.hollow_zero_event_opt.value_changed.connect(self.on_hollow_zero_event_changed)
        self.hollow_zero_event_opt.gpu_changed.connect(self.on_hollow_zero_event_gpu_changed)
        group.addSettingCard(self.hollow_zero_event_opt)

        self.lost_void_det_opt = OnnxModelDownloadCard(ctx=self.ctx, icon=FluentIcon.GLOBE, title='迷失之地识别')
        self.lost_void_det_opt.value_changed.connect(self.on_lost_void_det_changed)
        self.lost_void_det_opt.gpu_changed.connect(self.on_lost_void_det_gpu_changed)
        group.addSettingCard(self.lost_void_det_opt)

    def _set_log_card_height(self, log_card: QWidget) -> None:
        log_card.setFixedHeight(186)

    def on_interface_shown(self) -> None:
        ResourceDownloadInterface.on_interface_shown(self)

        self.init_flash_classifier()
        self.init_hollow_zero_event_opts()
        self.init_lost_void_det_opts()

    def init_flash_classifier(self) -> None:
        self.flash_classifier_opt.blockSignals(True)
        self.flash_classifier_opt.set_options_by_list(get_flash_classifier_opts())
        self.flash_classifier_opt.set_value_by_save_file_name(f'{self.ctx.model_config.flash_classifier}.zip')
        self.flash_classifier_opt.gpu_opt.setChecked(self.ctx.model_config.flash_classifier_gpu)
        self.flash_classifier_opt.check_and_update_display()
        self.flash_classifier_opt.blockSignals(False)

    def init_hollow_zero_event_opts(self) -> None:
        self.hollow_zero_event_opt.blockSignals(True)
        self.hollow_zero_event_opt.set_options_by_list(get_hollow_zero_event_opts())
        self.hollow_zero_event_opt.set_value_by_save_file_name(f'{self.ctx.model_config.hollow_zero_event}.zip')
        self.hollow_zero_event_opt.gpu_opt.setChecked(self.ctx.model_config.hollow_zero_event_gpu)
        self.hollow_zero_event_opt.check_and_update_display()
        self.hollow_zero_event_opt.blockSignals(False)

    def init_lost_void_det_opts(self) -> None:
        self.lost_void_det_opt.blockSignals(True)
        self.lost_void_det_opt.set_options_by_list(get_lost_void_det_opts())
        self.lost_void_det_opt.set_value_by_save_file_name(f'{self.ctx.model_config.lost_void_det}.zip')
        self.lost_void_det_opt.gpu_opt.setChecked(self.ctx.model_config.lost_void_det_gpu)
        self.lost_void_det_opt.check_and_update_display()
        self.lost_void_det_opt.blockSignals(False)

    def on_flash_classifier_changed(self, index: int, value: CommonDownloaderParam) -> None:
        self.ctx.model_config.flash_classifier = value.save_file_name[:-4]
        self.flash_classifier_opt.check_and_update_display()

    def on_flash_classifier_gpu_changed(self, value: bool) -> None:
        self.ctx.model_config.flash_classifier_gpu = value

    def on_hollow_zero_event_changed(self, index: int, value: CommonDownloaderParam) -> None:
        self.ctx.model_config.hollow_zero_event = value.save_file_name[:-4]
        self.hollow_zero_event_opt.check_and_update_display()

    def on_hollow_zero_event_gpu_changed(self, value: bool) -> None:
        self.ctx.model_config.hollow_zero_event_gpu = value

    def on_lost_void_det_changed(self, index: int, value: CommonDownloaderParam) -> None:
        self.ctx.model_config.lost_void_det = value.save_file_name[:-4]
        self.lost_void_det_opt.check_and_update_display()

    def on_lost_void_det_gpu_changed(self, value: bool) -> None:
        self.ctx.model_config.lost_void_det_gpu = value
