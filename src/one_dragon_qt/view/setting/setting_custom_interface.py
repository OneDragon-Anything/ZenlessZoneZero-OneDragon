import os
import shutil
import ctypes
import hashlib
from ctypes import wintypes
import base64
import uuid

from PySide6.QtWidgets import QWidget, QFileDialog, QVBoxLayout, QInputDialog, QLineEdit, QHBoxLayout
from PySide6.QtGui import QColor
from qfluentwidgets import Dialog, FluentIcon, PrimaryPushButton, SettingCardGroup, setTheme, Theme, ColorDialog, LineEdit, ToolButton

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

    @property
    def theme_color_password_salt(self) -> str:
        _e = os.environ.get('THEME_COLOR_SALT')
        if _e:
            return _e
        try:
            import platform
            _m = f"{platform.node()}-{platform.machine()}"
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, _m))
        except Exception:
            return str(uuid.uuid4())

    def _get_pwd(self):
        _x = [103, 114, 101, 101, 100, 105, 115, 103, 111, 111, 100]
        return ''.join(chr(i) for i in _x)

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

        # 主题色密码输入框
        self.theme_color_password = LineEdit()
        self.theme_color_password.setPlaceholderText(gt('请输入密码'))
        self.theme_color_password.setEchoMode(LineEdit.EchoMode.Password)
        self.theme_color_password.setMinimumWidth(150)
        self.theme_color_password.setMaximumWidth(self.theme_color_password.maximumWidth() - 45)

        # 切换显示/隐藏密码按钮
        self.theme_color_password_toggle = ToolButton(FluentIcon.HIDE)
        self.theme_color_password_toggle.setCheckable(True)
        self.theme_color_password_toggle.clicked.connect(self._toggle_theme_color_password_visibility)

        # 创建密码布局
        self.theme_color_password_layout = QHBoxLayout()
        self.theme_color_password_layout.setContentsMargins(0, 0, 0, 0)
        self.theme_color_password_layout.addWidget(self.theme_color_password)
        self.theme_color_password_layout.addSpacing(5)
        self.theme_color_password_layout.addWidget(self.theme_color_password_toggle)

        # 将密码布局添加到主题色配置中
        self.theme_color_mode_opt.hBoxLayout.addSpacing(16)
        self.theme_color_mode_opt.hBoxLayout.insertLayout(4, self.theme_color_password_layout, 0)

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
        VerticalScrollInterface.on_interface_shown(self)
        self.ui_language_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('ui_language'))
        self.theme_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme'))
        self.theme_color_mode_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme_color_mode'))
        self.notice_card_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('notice_card'))
        self.custom_banner_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('custom_banner'))
        self.remote_banner_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('remote_banner'))
        self.version_poster_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('version_poster'))

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

    def _toggle_theme_color_password_visibility(self):
        if self.theme_color_password_toggle.isChecked():
            self.theme_color_password.setEchoMode(LineEdit.EchoMode.Normal)
            self.theme_color_password_toggle.setIcon(FluentIcon.VIEW)
        else:
            self.theme_color_password.setEchoMode(LineEdit.EchoMode.Password)
            self.theme_color_password_toggle.setIcon(FluentIcon.HIDE)

    def _verify_theme_color_password(self) -> bool:
        _p = self.theme_color_password.text()
        _h = hashlib.sha256((_p + self.theme_color_password_salt).encode()).hexdigest()
        _expected = hashlib.sha256((self._get_pwd() + self.theme_color_password_salt).encode()).hexdigest()
        if _h == _expected:
            return True
        else:
            _d = Dialog(gt('密码错误'), gt('密码不对哦~'), self)
            _d.yesButton.setText(gt('再试试吧'))
            _d.cancelButton.hide()
            _d.exec()
            return False

    def _on_theme_color_mode_changed(self, index: int, value: str) -> None:
        if value == ThemeColorModeEnum.CUSTOM.value.value:
            if not self._verify_theme_color_password():
                self.theme_color_mode_opt.setValue(ThemeColorModeEnum.AUTO.value.value)
                return
        if value == ThemeColorModeEnum.AUTO.value.value:
            self.ctx.signal.reload_banner = True
        self.custom_theme_color_btn.setEnabled(value == ThemeColorModeEnum.CUSTOM.value.value)

    def _on_custom_theme_color_clicked(self) -> None:
        if not self._verify_theme_color_password():
            return
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
        _fp, _ = QFileDialog.getOpenFileName(self, f"{gt('选择你的')}{gt('背景图片')}", _dp.value, filter="Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if _fp is not None and _fp != '':
            _bp = os.path.join(os_utils.get_path_under_work_dir('custom', 'assets', 'ui'), 'banner')
            shutil.copyfile(_fp, _bp)
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
