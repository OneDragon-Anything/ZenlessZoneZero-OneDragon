import os
import shutil
import ctypes
from ctypes import wintypes

from PySide6.QtWidgets import QWidget, QFileDialog
from PySide6.QtGui import QColor
from qfluentwidgets import Dialog, FluentIcon, PrimaryPushButton, SettingCardGroup, setTheme, Theme, ColorDialog

from one_dragon.base.config.custom_config import ThemeEnum, UILanguageEnum, ThemeColorModeEnum
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon_qt.services.theme_manager import ThemeManager
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

        # 主题色模式选择
        self.theme_color_mode_opt = ComboBoxSettingCard(
            icon=FluentIcon.PALETTE,
            title='主题色模式',
            content='选择主题色的获取方式',
            options_enum=ThemeColorModeEnum
        )
        self.theme_color_mode_opt.value_changed.connect(self._on_theme_color_mode_changed)

        # 自定义主题色按钮
        self.custom_theme_color_btn = PrimaryPushButton(icon=FluentIcon.PALETTE, text=gt('自定义主题色'))
        self.custom_theme_color_btn.clicked.connect(self._on_custom_theme_color_clicked)
        self.theme_color_mode_opt.hBoxLayout.addWidget(self.custom_theme_color_btn, 0)
        self.theme_color_mode_opt.hBoxLayout.addSpacing(16)
        self.custom_theme_color_btn.setEnabled(self.ctx.custom_config.is_custom_theme_color)
        basic_group.addSettingCard(self.theme_color_mode_opt)

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
            password_hash='d678f04ece93caaa4d030696429101725cbf31657dd9ded4fdc3b71b3ee05c54',
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
        self.theme_color_mode_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme_color_mode'))
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

    def _on_theme_color_mode_changed(self, index: int, value: str) -> None:
        """
        主题色模式改变
        :param index: 选项下标
        :param value: 值
        :return:
        """
        # 如果切换到从背景提取，触发banner重载
        if value == ThemeColorModeEnum.AUTO.value.value:
            self.ctx.signal.reload_banner = True
        self.custom_theme_color_btn.setEnabled(value == ThemeColorModeEnum.CUSTOM.value.value)

    def _on_custom_theme_color_clicked(self) -> None:
        """
        点击自定义主题色按钮
        """
        color = self.ctx.custom_config.theme_color
        dialog = ColorDialog(QColor(color[0], color[1], color[2]), gt('请选择主题色'), self)
        dialog.colorChanged.connect(self._update_custom_theme_color)
        dialog.yesButton.setText(gt('确定'))
        dialog.cancelButton.setText(gt('取消'))
        dialog.exec()

    def _update_custom_theme_color(self, color: QColor) -> None:
        """
        更新自定义主题色
        :param color: QColor对象
        """
        color_tuple = (color.red(), color.green(), color.blue())
        self.ctx.custom_config.theme_color = color_tuple
        ThemeManager.set_theme_color(color_tuple)

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
