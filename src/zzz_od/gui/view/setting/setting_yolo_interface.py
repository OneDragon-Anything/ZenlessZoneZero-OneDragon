from PySide6.QtWidgets import QWidget
from qfluentwidgets import SettingCardGroup, FluentIcon, HyperlinkCard

from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.yolo_model_card import ModelDownloadSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from zzz_od.config.yolo_config import ZZZ_MODEL_DOWNLOAD_URL, get_flash_classifier_opts, get_hollow_zero_event_opts, \
    get_lost_void_det_opts
from zzz_od.context.zzz_context import ZContext


class SettingYoloInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='setting_yolo_interface',
            content_widget=None, parent=parent,
            nav_text_cn='模型选择'
        )

        self.ctx: ZContext = ctx

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        content_widget.add_widget(self._init_model_group())
        content_widget.add_widget(self._init_log_group())
        content_widget.add_stretch(1)

        return content_widget

    def _init_model_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt('模型', 'ui'))

        self.help_opt = HyperlinkCard(icon=FluentIcon.HELP, title='下载说明', text='',
                                      url='')
        self.help_opt.linkButton.hide()
        self.help_opt.setContent('下载失败时 请尝试到「脚本环境」更改网络代理')
        group.addSettingCard(self.help_opt)

        self.flash_classifier_opt = ModelDownloadSettingCard(
            ctx=self.ctx, sub_dir='flash_classifier', download_url=ZZZ_MODEL_DOWNLOAD_URL,
            icon=FluentIcon.GLOBE, title='闪光识别')
        self.flash_classifier_opt.value_changed.connect(self._on_flash_classifier_changed)
        group.addSettingCard(self.flash_classifier_opt)

        self.flash_classifier_gpu_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='闪光识别-GPU运算')
        group.addSettingCard(self.flash_classifier_gpu_opt)

        self.hollow_zero_event_opt = ModelDownloadSettingCard(
            ctx=self.ctx, sub_dir='hollow_zero_event', download_url=ZZZ_MODEL_DOWNLOAD_URL,
            icon=FluentIcon.GLOBE, title='空洞格子识别')
        self.hollow_zero_event_opt.value_changed.connect(self._on_hollow_zero_event_changed)
        group.addSettingCard(self.hollow_zero_event_opt)

        self.hollow_zero_event_gpu_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='空洞格子识别-GPU运算')
        group.addSettingCard(self.hollow_zero_event_gpu_opt)

        self.lost_void_det_opt = ModelDownloadSettingCard(
            ctx=self.ctx, sub_dir='lost_void_det', download_url=ZZZ_MODEL_DOWNLOAD_URL,
            icon=FluentIcon.GLOBE, title='迷失之地识别')
        self.lost_void_det_opt.value_changed.connect(self._on_hollow_zero_event_changed)
        group.addSettingCard(self.lost_void_det_opt)

        self.lost_void_det_gpu_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='迷失之地识别-GPU运算')
        group.addSettingCard(self.lost_void_det_gpu_opt)

        return group

    def _init_log_group(self) -> SettingCardGroup:
        log_group = SettingCardGroup(gt('安装日志', 'ui'))
        self.log_card = LogDisplayCard()
        log_group.addSettingCard(self.log_card)

        return log_group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self._init_flash_classifier_opts()
        self.flash_classifier_gpu_opt.init_with_adapter(self.ctx.yolo_config.get_prop_adapter('flash_classifier_gpu'))

        self._init_hollow_zero_event_opts()
        self.hollow_zero_event_gpu_opt.init_with_adapter(self.ctx.yolo_config.get_prop_adapter('hollow_zero_event_gpu'))

        self._init_lost_void_det_opts()
        self.lost_void_det_gpu_opt.init_with_adapter(self.ctx.yolo_config.get_prop_adapter('lost_void_det_gpu'))

        self.log_card.start()

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.log_card.stop()

    def _init_flash_classifier_opts(self) -> None:
        self.flash_classifier_opt.blockSignals(True)
        self.flash_classifier_opt.set_options_by_list(get_flash_classifier_opts())
        self.flash_classifier_opt.setValue(self.ctx.yolo_config.flash_classifier)
        self.flash_classifier_opt.check_and_update_display()
        self.flash_classifier_opt.blockSignals(False)

    def _init_hollow_zero_event_opts(self) -> None:
        self.hollow_zero_event_opt.blockSignals(True)
        self.hollow_zero_event_opt.set_options_by_list(get_hollow_zero_event_opts())
        self.hollow_zero_event_opt.setValue(self.ctx.yolo_config.hollow_zero_event)
        self.hollow_zero_event_opt.check_and_update_display()
        self.hollow_zero_event_opt.blockSignals(False)

    def _init_lost_void_det_opts(self) -> None:
        self.lost_void_det_opt.blockSignals(True)
        self.lost_void_det_opt.set_options_by_list(get_lost_void_det_opts())
        self.lost_void_det_opt.setValue(self.ctx.yolo_config.lost_void_det)
        self.lost_void_det_opt.check_and_update_display()
        self.lost_void_det_opt.blockSignals(False)

    def _on_flash_classifier_changed(self, index: int, value: str) -> None:
        self.ctx.yolo_config.flash_classifier = value
        self.flash_classifier_opt.check_and_update_display()

    def _on_hollow_zero_event_changed(self, index: int, value: str) -> None:
        self.ctx.yolo_config.hollow_zero_event = value
        self.hollow_zero_event_opt.check_and_update_display()

    def _on_lost_void_det_changed(self, index: int, value: str) -> None:
        self.ctx.yolo_config.lost_void_det = value
        self.lost_void_det_opt.check_and_update_display()
