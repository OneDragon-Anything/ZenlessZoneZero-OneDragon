from PySide6.QtGui import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup, VBoxLayout, PushButton, HyperlinkButton

from one_dragon.base.config.config_item import get_config_item_from_enum
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import RepositoryTypeEnum, GitMethodEnum, ProxyTypeEnum, PipSourceEnum
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon.utils.i18_utils import gt


class SettingEnvInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        self.ctx: OneDragonEnvContext = ctx

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
        content_layout.addWidget(self._init_web_group())
        content_layout.addWidget(self._init_key_group())

        return content_widget

    def _init_basic_group(self) -> SettingCardGroup:
        basic_group = SettingCardGroup(gt('基础', 'ui'))

        self.debug_opt = SwitchSettingCard(
            icon=FluentIcon.SEARCH, title='调试模式', content='正常无需开启'
        )
        self.debug_opt.value_changed.connect(self._on_debug_changed)
        basic_group.addSettingCard(self.debug_opt)

        return basic_group

    def _init_code_group(self) -> SettingCardGroup:
        code_group = SettingCardGroup(gt('Git相关', 'ui'))

        self.repository_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.APPLICATION, title='代码源', content='国内无法访问Github则选择Gitee',
            options_enum=RepositoryTypeEnum
        )
        self.repository_type_opt.value_changed.connect(self._on_repo_type_changed)
        code_group.addSettingCard(self.repository_type_opt)

        self.git_method_opt = ComboBoxSettingCard(
            icon=FluentIcon.SYNC, title='拉取方式', content='不懂什么是ssh就选https',
            options_enum=GitMethodEnum
        )
        self.git_method_opt.value_changed.connect(self._on_git_method_changed)
        code_group.addSettingCard(self.git_method_opt)

        self.force_update_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='强制更新', content='不懂代码请开启，会将脚本更新到最新并将你的改动覆盖，不会使你的配置失效',
        )
        self.force_update_opt.value_changed.connect(self._on_force_update_changed)
        code_group.addSettingCard(self.force_update_opt)

        self.auto_update_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='自动更新', content='脚本启动时，自动检测并更新代码',
        )
        self.auto_update_opt.value_changed.connect(self._on_auto_update_changed)
        code_group.addSettingCard(self.auto_update_opt)

        self.pip_source_opt = ComboBoxSettingCard(icon=FluentIcon.GLOBE, title='Pip源', options_enum=PipSourceEnum)
        self.pip_choose_best_btn = PushButton('自动测速选择', self)
        self.pip_choose_best_btn.clicked.connect(self.on_pip_choose_best_clicked)
        self.pip_source_opt.hBoxLayout.addWidget(self.pip_choose_best_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.pip_source_opt.hBoxLayout.addSpacing(16)
        code_group.addSettingCard(self.pip_source_opt)

        return code_group

    def _init_web_group(self) -> SettingCardGroup:
        web_group = SettingCardGroup(gt('网络相关', 'ui'))

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
        self.personal_proxy_input.value_changed.connect(self._on_personal_proxy_changed)
        web_group.addSettingCard(self.personal_proxy_input)

        self.gh_proxy_url_opt = TextSettingCard(
            icon=FluentIcon.GLOBE, title='免费代理'
        )
        web_group.addSettingCard(self.gh_proxy_url_opt)

        self.auto_fetch_gh_proxy_url_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='自动获取免费代理地址', content='获取失败时 可前往 https://ghproxy.link/ 查看自行更新'
        )
        self.fetch_gh_proxy_url_btn = PushButton('获取', self)
        self.fetch_gh_proxy_url_btn.clicked.connect(self.on_fetch_gh_proxy_url_clicked)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addWidget(self.fetch_gh_proxy_url_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addSpacing(16)

        self.goto_gh_proxy_link_btn = HyperlinkButton('https://ghproxy.link', '前往', self)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addWidget(self.goto_gh_proxy_link_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addSpacing(16)

        web_group.addSettingCard(self.auto_fetch_gh_proxy_url_opt)

        return web_group

    def _init_key_group(self) -> SettingCardGroup:
        key_group = SettingCardGroup(gt('脚本按键', 'ui'))

        self.key_start_running_input = KeySettingCard(
            icon=FluentIcon.PLAY, title='开始运行', content='开始、暂停、恢复某个应用',
        )
        self.key_start_running_input.value_changed.connect(self._on_key_start_running_changed)
        key_group.addSettingCard(self.key_start_running_input)

        self.key_stop_running_input = KeySettingCard(
            icon=FluentIcon.CLOSE, title='停止运行', content='停止正在运行的应用，不能恢复'
        )
        self.key_stop_running_input.value_changed.connect(self._on_key_stop_running_changed)
        key_group.addSettingCard(self.key_stop_running_input)

        self.key_screenshot_input = KeySettingCard(
            icon=FluentIcon.CAMERA, title='游戏截图', content='用于开发、提交bug。会自动对UID打码，保存在 .debug/images/ 文件夹中'
        )
        self.key_screenshot_input.value_changed.connect(self._on_key_screenshot_changed)
        key_group.addSettingCard(self.key_screenshot_input)

        self.key_debug_input = KeySettingCard(
            icon=FluentIcon.MOVE, title='调试按钮', content='用于开发，部分应用开始调试'
        )
        self.key_debug_input.value_changed.connect(self._on_key_debug_changed)
        key_group.addSettingCard(self.key_debug_input)

        return key_group

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)

        self.debug_opt.setValue(self.ctx.env_config.is_debug)

        self.key_start_running_input.setValue(self.ctx.env_config.key_start_running)
        self.key_stop_running_input.setValue(self.ctx.env_config.key_stop_running)
        self.key_screenshot_input.setValue(self.ctx.env_config.key_screenshot)
        self.key_debug_input.setValue(self.ctx.env_config.key_debug)

        repo_type = get_config_item_from_enum(RepositoryTypeEnum, self.ctx.env_config.repository_type)
        if repo_type is not None:
            self.repository_type_opt.setValue(repo_type.value)

        git_method = get_config_item_from_enum(GitMethodEnum, self.ctx.env_config.git_method)
        if git_method is not None:
            self.git_method_opt.setValue(git_method.value)

        self.force_update_opt.setValue(self.ctx.env_config.force_update)
        self.auto_update_opt.setValue(self.ctx.env_config.auto_update)
        self.pip_source_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('pip_source'))

        proxy_type = get_config_item_from_enum(ProxyTypeEnum, self.ctx.env_config.proxy_type)
        if proxy_type is not None:
            self.proxy_type_opt.setValue(proxy_type.value)
        self.update_proxy_ui()

        self.personal_proxy_input.setValue(self.ctx.env_config.personal_proxy)

        self.gh_proxy_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('gh_proxy_url'))
        self.auto_fetch_gh_proxy_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('auto_fetch_gh_proxy_url'))

    def _on_debug_changed(self, value: bool):
        """
        调试模式改变
        :param value:
        :return:
        """
        self.ctx.env_config.is_debug = value
        self.ctx.init_by_config()

    def _on_repo_type_changed(self, index: int, value: str) -> None:
        """
        仓库类型改变
        :param index: 选项下标
        :param value: 值
        :return:
        """
        config_item = get_config_item_from_enum(RepositoryTypeEnum, value)
        self.ctx.env_config.repository_type = config_item.value
        self.ctx.git_service.update_git_remote()

    def _on_git_method_changed(self, index: int, value: str) -> None:
        """
        拉取方式改变
        :param index: 选项下标
        :param value: 值
        :return:
        """
        config_item = get_config_item_from_enum(GitMethodEnum, value)
        self.ctx.env_config.git_method = config_item.value
        self.ctx.git_service.update_git_remote()

    def _on_force_update_changed(self, value: bool) -> None:
        """
        强制更新改变
        """
        self.ctx.env_config.force_update = value

    def _on_auto_update_changed(self, value: bool) -> None:
        self.ctx.env_config.auto_update = value

    def _on_proxy_type_changed(self, index: int, value: str) -> None:
        """
        拉取方式改变
        :param index: 选项下标
        :param value: 值
        :return:
        """
        config_item = get_config_item_from_enum(ProxyTypeEnum, value)
        self.ctx.env_config.proxy_type = config_item.value
        self.update_proxy_ui()
        self._on_proxy_changed()

    def _on_personal_proxy_changed(self, value: str) -> None:
        """
        个人代理改变
        :param value: 值
        :return:
        """
        self.ctx.env_config.personal_proxy = value
        self._on_proxy_changed()

    def _on_proxy_changed(self) -> None:
        """
        代理发生改变
        :return:
        """
        # 清除当前代理设置的状态
        self.ctx.git_service.is_proxy_set = False

        # 调用 init_git_proxy 同步更新 Git 的代理设置
        self.ctx.git_service.init_git_proxy()

    def _on_key_start_running_changed(self, value: str) -> None:
        self.ctx.env_config.key_start_running = value

    def _on_key_stop_running_changed(self, value: str) -> None:
        self.ctx.env_config.key_stop_running = value

    def _on_key_screenshot_changed(self, value: str) -> None:
        self.ctx.env_config.key_screenshot = value

    def _on_key_debug_changed(self, value: str) -> None:
        self.ctx.env_config.key_debug = value

    def on_fetch_gh_proxy_url_clicked(self) -> None:
        self.ctx.gh_proxy_service.update_proxy_url()
        self.gh_proxy_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('gh_proxy_url'))

    def on_pip_choose_best_clicked(self) -> None:
        self.ctx.python_service.choose_best_pip_source()
        self.pip_source_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('pip_source'))

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