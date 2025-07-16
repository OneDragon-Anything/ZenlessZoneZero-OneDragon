import os
import shutil
import ctypes
from ctypes import wintypes

from PySide6.QtWidgets import QWidget, QFileDialog
from qfluentwidgets import Dialog, FluentIcon, PrimaryPushButton, SettingCardGroup, setTheme, Theme

from one_dragon.base.config.custom_config import ThemeEnum, UILanguageEnum
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.password_switch_setting_card import PasswordSwitchSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.i18_utils import gt

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

        self.notice_card_opt = SwitchSettingCard(icon=FluentIcon.PIN, title='主页公告', content='在主页显示游戏公告')
        self.notice_card_opt.value_changed.connect(lambda: setattr(self.ctx.signal, 'notice_card_config_changed', True))
        basic_group.addSettingCard(self.notice_card_opt)

        self.version_poster_opt = SwitchSettingCard(icon=FluentIcon.IMAGE_EXPORT, title='启用版本海报', content='版本活动海报持续整个版本')
        self.version_poster_opt.value_changed.connect(self._on_version_poster_changed)
        basic_group.addSettingCard(self.version_poster_opt)

        self.remote_banner_opt = SwitchSettingCard(icon=FluentIcon.CLOUD, title='启用官方启动器主页背景', content='关闭后仅用本地图片')
        self.remote_banner_opt.value_changed.connect(self._on_remote_banner_changed)
        basic_group.addSettingCard(self.remote_banner_opt)

        self.banner_select_btn = PrimaryPushButton(FluentIcon.EDIT, gt('选择'), self)
        self.banner_select_btn.clicked.connect(self._on_banner_select_clicked)
        self.custom_banner_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.PHOTO,
            title='自定义主页背景',
            extra_btn=self.banner_select_btn,
            password_hint='使用此功能需要密码哦~',
            password_hash='d7103a21d03b8b922c3af3d477a0adde1633053cde1a7574e8009293ca3b70f1',
            dialog_title='嘻嘻~',
            dialog_content='密码不对哦~',
            dialog_button_text='再试试吧',
        )
        self.custom_banner_opt.value_changed.connect(self.reload_banner)
        basic_group.addSettingCard(self.custom_banner_opt)

        return basic_group

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.ui_language_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('ui_language'))
        self.theme_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme'))
        self.notice_card_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('notice_card'))
        self.custom_banner_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('custom_banner'))
        self.remote_banner_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('remote_banner'))
        self.version_poster_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('version_poster'))

    def _on_ui_language_changed(self, index: int, value: str) -> None:
        """
        界面语言改变
        :param index: 选项下标
        :param value: 值
        :return:
        """
        language = self.ctx.custom_config.ui_language
        dialog = Dialog(gt("提示", "ui", language), gt("语言切换成功，需要重启应用程序以生效", "ui", language), self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText(gt("立即重启", "ui", language))
        dialog.cancelButton.setText(gt("稍后重启", "ui", language))

        if dialog.exec():
            app_utils.start_one_dragon(True)

    def _on_theme_changed(self, index: int, value: str) -> None:
        """
        主题类型改变
        :param index: 选项下标
        :param value: 值
        :return:
        """
        setTheme(Theme[self.ctx.custom_config.theme.upper()],lazy=True)

    def _on_banner_select_clicked(self) -> None:
        """
        选择背景图片并复制
        """
        # 将默认路径设为图片库路径
        default_path = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0027, None, 0, default_path)
        file_path, _ = QFileDialog.getOpenFileName(self, f"{gt('选择你的')}{gt('背景图片')}", default_path.value, filter="Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if file_path is not None and file_path != '':
            banner_path = os.path.join(
            os_utils.get_path_under_work_dir('custom', 'assets', 'ui'),
            'banner')
            shutil.copyfile(file_path, banner_path)
            self.reload_banner()

    def _on_version_poster_changed(self, value: bool) -> None:
        if value:
            self.remote_banner_opt.setValue(False)
        self.reload_banner()

    def _on_remote_banner_changed(self, value: bool) -> None:
        if value:
            self.version_poster_opt.setValue(False)
        self.reload_banner()

    def reload_banner(self) -> None:
        self.ctx.signal.reload_banner = True
