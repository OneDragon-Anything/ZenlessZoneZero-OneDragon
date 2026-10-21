from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, PushButton, SettingCardGroup

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import ProxyTypeEnum
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.resource_download_dialog import build_resource_source_options
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.expand_setting_card_group import (
    ExpandSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard


class DownloadSourceSettingsGroup(SettingCardGroup):
    """下载源和代理设置，资源页与恢复页共用。"""

    def __init__(
        self,
        ctx: OneDragonEnvContext,
        parent: QWidget | None = None,
        proxy_content: str = '为代码和资源下载配置网络代理',
        show_fetch_button: bool = False,
        fetch_proxy: Callable[[], None] | None = None,
    ) -> None:
        """创建下载源、代理类型和代理地址设置。

        Args:
            ctx: 提供环境配置的上下文。
            parent: 父组件。
            proxy_content: 代理分组的说明文字。
            show_fetch_button: 是否显示立即获取免费代理的按钮。
            fetch_proxy: 点击立即获取时执行的操作。
        """
        super().__init__(gt('下载设置'), parent)
        self.ctx: OneDragonEnvContext = ctx
        self._last_proxy_type: str = ctx.env_config.proxy_type

        self.resource_source_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='下载源',
            content='自动模式优先使用上次成功源，失败后继续尝试其他源',
            options_list=build_resource_source_options(ctx.env_config),
        )
        self.resource_source_opt.combo_box.setFixedWidth(160)
        self.addSettingCard(self.resource_source_opt)

        self.proxy_group = ExpandSettingCardGroup(
            icon=FluentIcon.WIFI,
            title='代理设置',
            content=proxy_content,
        )
        self.proxy_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='代理类型',
            options_enum=ProxyTypeEnum,
        )
        self.proxy_type_opt.value_changed.connect(self._on_proxy_type_changed)
        self.proxy_group.addHeaderWidget(self.proxy_type_opt.combo_box)

        self.proxy_url_input = TextSettingCard(
            icon=FluentIcon.WIFI,
            title='代理地址',
            input_max_width=300,
        )
        self.proxy_url_input.line_edit.setFixedWidth(300)
        self.proxy_url_input.value_changed.connect(self._apply_system_proxy)
        self.proxy_group.addSettingCard(self.proxy_url_input)

        self.auto_fetch_proxy_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC,
            title='自动获取免费代理地址',
            content='仅在使用 GitHub 代理时生效',
            on_text_cn='',
            off_text_cn='',
        )
        if show_fetch_button:
            self.fetch_proxy_btn = PushButton(gt('立即获取'), self)
            self.fetch_proxy_btn.setFixedWidth(112)
            self.fetch_proxy_btn.clicked.connect(
                fetch_proxy or self._fetch_proxy_url
            )
            self.auto_fetch_proxy_opt.hBoxLayout.addWidget(
                self.fetch_proxy_btn,
                0,
                Qt.AlignmentFlag.AlignRight,
            )
            self.auto_fetch_proxy_opt.hBoxLayout.addSpacing(16)
        self.proxy_group.addSettingCard(self.auto_fetch_proxy_opt)
        self.addSettingCard(self.proxy_group)

    def init_adapters(self) -> None:
        """把下载源和代理选项绑定到当前环境配置。"""
        env_config = self.ctx.env_config
        self.resource_source_opt.init_with_adapter(
            env_config.get_prop_adapter('resource_source')
        )
        self.proxy_type_opt.init_with_adapter(
            env_config.get_prop_adapter('proxy_type')
        )
        self.auto_fetch_proxy_opt.init_with_adapter(
            env_config.get_prop_adapter('auto_fetch_gh_proxy_url')
        )
        self._update_proxy_ui()

    def _on_proxy_type_changed(self, _index: int, _value: str) -> None:
        """代理类型变化后刷新输入项；从无代理切到有代理时展开分组。"""
        proxy_type = self.ctx.env_config.proxy_type
        self._update_proxy_ui()
        if (
            self._last_proxy_type == ProxyTypeEnum.NONE.value.value
            and proxy_type != ProxyTypeEnum.NONE.value.value
        ):
            self.proxy_group.setExpand(True)
        self._last_proxy_type = proxy_type
        self._apply_system_proxy()

    def _update_proxy_ui(self) -> None:
        """按当前代理类型显示对应地址输入。"""
        proxy_type = self.ctx.env_config.proxy_type
        proxy_enabled = proxy_type != ProxyTypeEnum.NONE.value.value
        if not proxy_enabled:
            self.proxy_group.setExpand(False)
        self.proxy_group.card.expandButton.setEnabled(proxy_enabled)

        if proxy_type == ProxyTypeEnum.PERSONAL.value.value:
            self.proxy_url_input.init_with_adapter(
                self.ctx.env_config.get_prop_adapter('personal_proxy')
            )
            self.proxy_url_input.titleLabel.setText(gt('个人代理地址'))
            self.proxy_url_input.line_edit.setPlaceholderText(
                'http://127.0.0.1:7890'
            )
            self.proxy_url_input.setVisible(True)
            self.auto_fetch_proxy_opt.setVisible(False)
        elif proxy_type == ProxyTypeEnum.GHPROXY.value.value:
            self.proxy_url_input.init_with_adapter(
                self.ctx.env_config.get_prop_adapter('gh_proxy_url')
            )
            self.proxy_url_input.titleLabel.setText(gt('免费代理地址'))
            self.proxy_url_input.line_edit.setPlaceholderText(
                'https://ghproxy.link/'
            )
            self.proxy_url_input.setVisible(True)
            self.auto_fetch_proxy_opt.setVisible(True)
        else:
            self.proxy_url_input.setVisible(False)
            self.auto_fetch_proxy_opt.setVisible(False)

    def _fetch_proxy_url(self) -> None:
        """立即获取免费代理地址并刷新输入框。"""
        self.ctx.gh_proxy_service.update_proxy_url()
        self.proxy_url_input.init_with_adapter(
            self.ctx.env_config.get_prop_adapter('gh_proxy_url')
        )
        self._apply_system_proxy()

    def _apply_system_proxy(self, _value: str = '') -> None:
        """把当前代理配置应用到系统代理。"""
        self.ctx.env_config.init_system_proxy()
