from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    FluentIcon,
    HyperlinkButton,
    InfoBar,
    InfoBarPosition,
    PushButton,
    SettingCardGroup,
    VBoxLayout,
)

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.envs.env_config import (
    CpythonSourceEnum,
    PipSourceEnum,
    ProxyTypeEnum,
    RepositoryTypeEnum,
    ScreenshotMethodEnum,
)
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class SettingEnvInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, parent=None):
        self.ctx: OneDragonContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='setting_env_interface',
            content_widget=None, parent=parent,
            nav_text_cn='脚本环境'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        content_layout = VBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        content_layout.addWidget(self._init_basic_group())
        content_layout.addWidget(self._init_code_group())
        content_layout.addWidget(self._init_python_group())
        content_layout.addWidget(self._init_web_group())
        content_layout.addWidget(self._init_key_group())

        return content_widget

    def _init_basic_group(self) -> SettingCardGroup:
        basic_group = SettingCardGroup(gt('基础'))

        self.debug_opt = SwitchSettingCard(
            icon=FluentIcon.SEARCH, title='调试模式', content='正常无需开启'
        )
        self.debug_opt.value_changed.connect(lambda: self.ctx.init_async())
        basic_group.addSettingCard(self.debug_opt)

        self.copy_screenshot_opt = SwitchSettingCard(
            icon=FluentIcon.CAMERA, title='复制截图到剪贴板',
            content='按下截图按键时，自动将截图复制到剪贴板'
        )
        basic_group.addSettingCard(self.copy_screenshot_opt)

        self.ocr_cache_opt = SwitchSettingCard(
            icon=FluentIcon.SEARCH, title='OCR缓存模式', content='降低CPU占用(测试中)'
        )
        basic_group.addSettingCard(self.ocr_cache_opt)

        self.screenshot_method_opt = ComboBoxSettingCard(
            icon=FluentIcon.CAMERA, title='截图方法',
            options_enum=ScreenshotMethodEnum
        )
        self.screenshot_method_opt.value_changed.connect(lambda: self.ctx.init_controller())
        basic_group.addSettingCard(self.screenshot_method_opt)

        return basic_group

    def _init_code_group(self) -> SettingCardGroup:
        code_group = SettingCardGroup(gt('Git相关'))

        self.repository_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.APPLICATION, title='代码源', content='国内无法访问GitHub则选择Gitee',
            options_enum=RepositoryTypeEnum
        )
        self.repository_type_opt.value_changed.connect(lambda: self.ctx.git_service.update_remote())
        code_group.addSettingCard(self.repository_type_opt)

        self.auto_update_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='自动更新', content='使用exe启动时，自动检测并更新代码',
        )
        code_group.addSettingCard(self.auto_update_opt)

        self.force_update_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='强制更新', content='不懂代码请开启，会将脚本更新到最新并将你的改动覆盖，不会使你的配置失效',
        )
        code_group.addSettingCard(self.force_update_opt)

        return code_group

    def _init_python_group(self) -> SettingCardGroup:
        python_group = SettingCardGroup(gt('Python相关'))

        self.cpython_source_opt = ComboBoxSettingCard(icon=FluentIcon.GLOBE, title='Python下载源', options_enum=CpythonSourceEnum)
        self.cpython_build_choose_best_btn = PushButton(gt('自动测速选择'), self)
        self.cpython_build_choose_best_btn.clicked.connect(self.on_cpython_build_choose_best_clicked)
        self.cpython_source_opt.hBoxLayout.addWidget(self.cpython_build_choose_best_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.cpython_source_opt.hBoxLayout.addSpacing(16)
        python_group.addSettingCard(self.cpython_source_opt)

        self.pip_source_opt = ComboBoxSettingCard(icon=FluentIcon.GLOBE, title='Pip源', options_enum=PipSourceEnum)
        self.pip_choose_best_btn = PushButton(gt('自动测速选择'), self)
        self.pip_choose_best_btn.clicked.connect(self.on_pip_choose_best_clicked)
        self.pip_source_opt.hBoxLayout.addWidget(self.pip_choose_best_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.pip_source_opt.hBoxLayout.addSpacing(16)
        python_group.addSettingCard(self.pip_source_opt)

        return python_group

    def _init_web_group(self) -> SettingCardGroup:
        web_group = SettingCardGroup(gt('网络相关'))

        self.proxy_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE, title='网络代理', content='免费代理仅能加速工具和模型下载，无法加速代码同步',
            options_enum=ProxyTypeEnum
        )
        self.proxy_type_opt.value_changed.connect(self._on_proxy_type_changed)
        web_group.addSettingCard(self.proxy_type_opt)

        self.personal_proxy_input = TextSettingCard(
            icon=FluentIcon.WIFI, title='个人代理',
            input_placeholder='http://127.0.0.1:8080'
        )
        self.personal_proxy_input.value_changed.connect(lambda: self._on_proxy_changed())
        web_group.addSettingCard(self.personal_proxy_input)

        self.gh_proxy_url_opt = TextSettingCard(
            icon=FluentIcon.GLOBE, title='免费代理'
        )
        web_group.addSettingCard(self.gh_proxy_url_opt)

        self.auto_fetch_gh_proxy_url_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='自动获取免费代理地址', content='获取失败时 可前往 https://ghproxy.link/ 查看自行更新'
        )
        self.fetch_gh_proxy_url_btn = PushButton(gt('获取'), self)
        self.fetch_gh_proxy_url_btn.clicked.connect(self.on_fetch_gh_proxy_url_clicked)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addWidget(self.fetch_gh_proxy_url_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addSpacing(16)

        self.goto_gh_proxy_link_btn = HyperlinkButton('https://ghproxy.link', gt('前往'), self)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addWidget(self.goto_gh_proxy_link_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addSpacing(16)

        web_group.addSettingCard(self.auto_fetch_gh_proxy_url_opt)

        return web_group

    def _init_key_group(self) -> SettingCardGroup:
        key_group = SettingCardGroup(gt('脚本按键'))

        self.key_start_running_input = KeySettingCard(
            icon=FluentIcon.PLAY, title='开始运行', content='开始、暂停、恢复某个应用',
        )
        key_group.addSettingCard(self.key_start_running_input)

        self.key_stop_running_input = KeySettingCard(
            icon=FluentIcon.CLOSE, title='停止运行', content='停止正在运行的应用，不能恢复'
        )
        key_group.addSettingCard(self.key_stop_running_input)

        self.key_screenshot_input = KeySettingCard(
            icon=FluentIcon.CAMERA, title='游戏截图', content='用于开发、提交bug。会自动对UID打码，保存在 .debug/images/ 文件夹中'
        )
        key_group.addSettingCard(self.key_screenshot_input)

        self.key_debug_input = KeySettingCard(
            icon=FluentIcon.MOVE, title='调试按钮', content='用于开发，部分应用开始调试'
        )
        key_group.addSettingCard(self.key_debug_input)

        return key_group

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)

        self.debug_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('is_debug'))
        self.copy_screenshot_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('copy_screenshot'))
        self.ocr_cache_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('ocr_cache'))
        self.screenshot_method_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('screenshot_method'))

        self.key_start_running_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('key_start_running'))
        self.key_stop_running_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('key_stop_running'))
        self.key_screenshot_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('key_screenshot'))
        self.key_debug_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('key_debug'))

        self.repository_type_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('repository_type'))

        self.force_update_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('force_update'))
        self.auto_update_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('auto_update'))
        self.pip_source_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('pip_source'))
        self.cpython_source_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('cpython_source'))

        self.proxy_type_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('proxy_type'))
        self.personal_proxy_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('personal_proxy'))
        self.gh_proxy_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('gh_proxy_url'))
        self.auto_fetch_gh_proxy_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('auto_fetch_gh_proxy_url'))
        self.update_proxy_ui()

    def _on_proxy_type_changed(self, index: int, value: str) -> None:
        self.update_proxy_ui()
        self._on_proxy_changed()

    def _on_proxy_changed(self) -> None:
        """
        代理发生改变
        :return:
        """
        self.ctx.env_config.init_system_proxy()

    def on_fetch_gh_proxy_url_clicked(self) -> None:
        self.ctx.gh_proxy_service.update_proxy_url()
        self.gh_proxy_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('gh_proxy_url'))

    def _show_info_bar(self, title: str, content: str, duration: int = 20000):
        """显示信息条"""
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=duration,
            parent=self,
        ).setCustomBackgroundColor("white", "#202020")

    def on_pip_choose_best_clicked(self) -> None:
        # 异步测速pip源，toast显示日志和结果
        self._pip_speed_thread = PipSourceSpeedTestThread(self.ctx)
        self._pip_speed_thread.log_signal.connect(lambda label, ms: self._show_info_bar(
            title=f"测速：{label}",
            content=f"耗时 {ms}ms",
            duration=2000
        ))
        def pip_result(label, ms, value):
            self.ctx.env_config.pip_source = value
            self.pip_source_opt.setValue(value)
            self._show_info_bar(
                title="测速结果",
                content=f"已选择最快的Pip源：{label}（{ms}ms）",
                duration=3000
            )
        self._pip_speed_thread.result_signal.connect(pip_result)
        self._pip_speed_thread.start()

    def on_cpython_build_choose_best_clicked(self) -> None:
        # 异步测速python-build镜像源，toast显示日志和结果
        self._python_speed_thread = PythonSourceSpeedTestThread(self.ctx)
        self._python_speed_thread.log_signal.connect(lambda label, ms: self._show_info_bar(
            title=f"测速：{label}",
            content=f"耗时 {ms}ms",
            duration=2000
        ))
        def python_result(label, ms, value):
            self.ctx.env_config.cpython_source = value
            self.cpython_source_opt.setValue(value)
            self._show_info_bar(
                title="测速结果",
                content=f"已选择最快的Python下载源：{label}（{ms}ms）",
                duration=3000
            )
        self._python_speed_thread.result_signal.connect(python_result)
        self._python_speed_thread.start()

    def update_proxy_ui(self) -> None:
        """
        更新代理设置的UI
        :return:
        """
        if self.ctx.env_config.proxy_type == ProxyTypeEnum.GHPROXY.value.value:
            self.personal_proxy_input.hide()
            self.gh_proxy_url_opt.show()
            self.auto_fetch_gh_proxy_url_opt.show()
        elif self.ctx.env_config.proxy_type == ProxyTypeEnum.PERSONAL.value.value:
            self.personal_proxy_input.show()
            self.gh_proxy_url_opt.hide()
            self.auto_fetch_gh_proxy_url_opt.hide()
        elif self.ctx.env_config.proxy_type == ProxyTypeEnum.NONE.value.value:
            self.personal_proxy_input.hide()
            self.gh_proxy_url_opt.hide()
            self.auto_fetch_gh_proxy_url_opt.hide()


class SpeedTestRunnerBase(QThread):
    log_signal = Signal(str, int)
    result_signal = Signal(str, int, str)

    def __init__(self, ctx: OneDragonContext, parent=None):
        self.ctx: OneDragonContext = ctx
        super().__init__(parent)


class PythonSourceSpeedTestThread(SpeedTestRunnerBase):
    def __init__(self, ctx, parent=None):
        SpeedTestRunnerBase.__init__(self, ctx, parent)

    def run(self):
        result = self.ctx.python_service.choose_best_cpython_source()

        if result:
            best_label, best_ms = result
            best_source_value = self.ctx.env_config.cpython_source
            self.result_signal.emit(best_label, best_ms, best_source_value)
        else:
            self.result_signal.emit("Error", 9999, "")


class PipSourceSpeedTestThread(SpeedTestRunnerBase):
    def __init__(self, ctx, parent=None):
        SpeedTestRunnerBase.__init__(self, ctx, parent)

    def run(self):
        result = self.ctx.python_service.choose_best_pip_source()

        if result:
            best_label, best_ms = result
            best_source_value = self.ctx.env_config.pip_source
            self.result_signal.emit(best_label, best_ms, best_source_value)
        else:
            self.result_signal.emit("Error", 9999, "")
