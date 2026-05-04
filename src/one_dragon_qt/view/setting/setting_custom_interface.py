import ctypes
import os
import shutil
from ctypes import wintypes

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import (
    ColorDialog,
    Dialog,
    FluentIcon,
    PrimaryPushButton,
    SettingCardGroup,
    Theme,
    setTheme,
)

from one_dragon.base.config.custom_config import (
    BackgroundTypeEnum,
    ThemeEnum,
    UILanguageEnum,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.theme_manager import ThemeManager
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.password_switch_setting_card import (
    PasswordSwitchSettingCard,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class SettingCustomInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, parent=None):
        self.ctx: OneDragonContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='setting_custom_interface',
            content_widget=None, parent=parent,
            nav_text_cn='自定义设置'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column(self)

        content_widget.add_widget(self._init_basic_group())

        return content_widget

    def _init_basic_group(self) -> SettingCardGroup:
        basic_group = SettingCardGroup(gt('外观'))

        self.ui_language_opt = ComboBoxSettingCard(
            icon=FluentIcon.LANGUAGE, title='界面语言',
            options_enum=UILanguageEnum
        )
        self.ui_language_opt.value_changed.connect(self._on_ui_language_changed)
        basic_group.addSettingCard(self.ui_language_opt)

        self.theme_opt = ComboBoxSettingCard(
            icon=FluentIcon.CONSTRACT, title='界面主题',
            options_enum=ThemeEnum
        )
        self.theme_opt.value_changed.connect(self._on_theme_changed)
        basic_group.addSettingCard(self.theme_opt)

        # 自定义主题色按钮
        self.custom_theme_color_btn = PrimaryPushButton(icon=FluentIcon.PALETTE, text=gt('自定义主题色'))
        self.custom_theme_color_btn.clicked.connect(self._on_custom_theme_color_clicked)

        # 主题色模式（密码保护）
        self.theme_color_mode_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.PALETTE,
            title='自定义主题色',
            content='开启后可自定义主题色',
            extra_btn=self.custom_theme_color_btn,
            password_hint='使用此功能需要密码哦~',
            password_hash='b0cd76b7d7829362d581b739c0b295abf53182792609078bb17a9dd917ffba7c',
            dialog_title='嘻嘻~',
            dialog_content='密码不对哦~',
            dialog_button_text='再试试吧',
        )
        self.theme_color_mode_opt.value_changed.connect(self._on_theme_color_mode_changed)

        basic_group.addSettingCard(self.theme_color_mode_opt)

        self.background_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.BACKGROUND_FILL,
            title='主页背景类型',
            content='选择主页显示的背景',
            options_enum=BackgroundTypeEnum
        )
        self.background_type_opt.value_changed.connect(self._on_background_type_changed)
        basic_group.addSettingCard(self.background_type_opt)

        self.banner_select_btn = PrimaryPushButton(FluentIcon.EDIT, gt('选择'), self)
        self.banner_select_btn.clicked.connect(self._on_banner_select_clicked)
        self.custom_banner_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.PHOTO,
            title='自定义主页背景',
            extra_btn=self.banner_select_btn,
            password_hint='使用此功能需要密码哦~',
            password_hash='d678f04ece93caaa4d030696429101725cbf31657dd9ded4fdc3b71b3ee05c54',
            dialog_title='嘻嘻~',
            dialog_content='密码不对哦~',
            dialog_button_text='再试试吧',
        )
        self.custom_banner_opt.value_changed.connect(self.reload_banner)
        basic_group.addSettingCard(self.custom_banner_opt)

        return basic_group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.ui_language_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('ui_language'))
        self.theme_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme'))
        self.theme_color_mode_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('custom_theme_color'))
        self.custom_banner_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('custom_banner'))
        self.background_type_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('background_type'))

    def _on_ui_language_changed(self, index: int, value: str) -> None:
        language = self.ctx.custom_config.ui_language
        dialog = Dialog(gt("提示", "ui", language), gt("语言切换成功，需要重启应用程序以生效", "ui", language), self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText(gt("立即重启", "ui", language))
        dialog.cancelButton.setText(gt("稍后重启", "ui", language))

        if dialog.exec():
            app_utils.start_one_dragon(True)

    def _on_theme_changed(self, index: int, value: str) -> None:
        setTheme(Theme[self.ctx.custom_config.theme.upper()],lazy=True)

    def _on_theme_color_mode_changed(self, value: bool) -> None:
        if not value:
            self.ctx.signal.reload_banner = True

    def _on_custom_theme_color_clicked(self) -> None:
        _c = self.ctx.custom_config.theme_color
        _d = ColorDialog(QColor(_c[0], _c[1], _c[2]), gt('请选择主题色'), self)
        _d.colorChanged.connect(self._update_custom_theme_color)
        _d.yesButton.setText(gt('确定'))
        _d.cancelButton.setText(gt('取消'))
        _d.exec()

    def _update_custom_theme_color(self, color: QColor) -> None:
        _ct = (color.red(), color.green(), color.blue())
        self.ctx.custom_config.theme_color = _ct
        ThemeManager.set_theme_color(_ct)

    def _on_banner_select_clicked(self) -> None:
        _dp = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0027, None, 0, _dp)
        _fp, _ = QFileDialog.getOpenFileName(
            self,
            f"{gt('选择你的')}{gt('背景图片')}",
            _dp.value,
            filter="Images and Videos (*.png *.jpg *.jpeg *.webp *.bmp *.webm *.mp4 *.avi *.mov *.mkv);;Images (*.png *.jpg *.jpeg *.webp *.bmp);;Videos (*.webm *.mp4 *.avi *.mov *.mkv)"
        )
        if _fp is not None and _fp != '':
            _bp = os.path.join(os_utils.get_path_under_work_dir('custom', 'assets', 'ui'), 'banner')
            shutil.copyfile(_fp, _bp)
            self.reload_banner()

    def _on_background_type_changed(self, index: int, value: str) -> None:
        """背景类型改变时的回调"""
        self.reload_banner()

    def reload_banner(self) -> None:
        self.ctx.signal.reload_banner = True
