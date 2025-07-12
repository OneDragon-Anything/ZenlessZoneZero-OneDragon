from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout
from qfluentwidgets import FluentIcon, SettingCardGroup, TitleLabel, PrimaryPushButton

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import CpythonSourceEnum, EnvSourceEnum, ProxyTypeEnum, PipSourceEnum, RegionEnum, RepositoryTypeEnum
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.horizontal_setting_card_group import HorizontalSettingCardGroup
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard


class SourceConfigInterface(VerticalScrollInterface):
    """源配置界面"""

    finished = Signal(bool)

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='source_config_interface',
            parent=parent,
            nav_text_cn='源配置',
            nav_icon=FluentIcon.GLOBE
        )
        self.ctx = ctx

    def get_content_widget(self) -> QWidget:
        """获取内容组件"""
        content_widget = Column()
        content_widget.v_layout.setContentsMargins(40, 40, 40, 40)
        content_widget.v_layout.setSpacing(10)

        # 标题
        title_label = TitleLabel(gt('配置源'))
        content_widget.add_widget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 地区选择和确认按钮的水平布局
        region_confirm_widget = QWidget()
        region_confirm_layout = QHBoxLayout(region_confirm_widget)
        region_confirm_layout.setContentsMargins(0, 0, 0, 0)
        region_confirm_layout.setSpacing(10)

        self.region_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='地区选择',
            options_enum=RegionEnum
        )
        self.region_opt.value_changed.connect(self._on_region_changed)

        self.confirm_btn = PrimaryPushButton(gt('确认配置'))
        self.confirm_btn.setFixedSize(120, 40)
        self.confirm_btn.clicked.connect(lambda: self.finished.emit(True))
        self.confirm_btn.clicked.connect(self._init_proxy)

        region_confirm_layout.addWidget(self.region_opt, 1)
        region_confirm_layout.addWidget(self.confirm_btn, 0)

        content_widget.add_widget(region_confirm_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # 高级配置组
        self.advanced_group = self.get_advanced_group()
        content_widget.add_widget(self.advanced_group)

        return content_widget

    def get_advanced_group(self) -> QWidget:
        advanced_group = SettingCardGroup(gt('配置源'))
        advanced_group.titleLabel.setVisible(False)

        # 源
        source_group = SettingCardGroup(gt('源'))

        self.repository_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.CODE,
            title='代码仓库',
            options_enum=RepositoryTypeEnum
        )
        self.repository_type_opt.value_changed.connect(lambda: self.ctx.git_service.update_git_remote())

        self.env_source_opt = ComboBoxSettingCard(
            icon=FluentIcon.CLOUD_DOWNLOAD,
            title='环境下载源',
            options_enum=EnvSourceEnum
        )

        self.cpython_source_opt = ComboBoxSettingCard(
            icon=FluentIcon.DOWNLOAD,
            title='Python下载源',
            options_enum=CpythonSourceEnum
        )

        self.pip_source_opt = ComboBoxSettingCard(
            icon=FluentIcon.APPLICATION,
            title='Pip源',
            options_enum=PipSourceEnum
        )

        # 创建横向布局组件
        first_row = HorizontalSettingCardGroup([self.repository_type_opt, self.cpython_source_opt])
        second_row = HorizontalSettingCardGroup([self.env_source_opt, self.pip_source_opt])

        # 将横向布局组件添加到源组
        source_group.addSettingCard(first_row)
        source_group.addSettingCard(second_row)
        advanced_group.addSettingCard(source_group)

        # 网络代理设置
        proxy_group = SettingCardGroup(gt('网络代理设置'))

        self.proxy_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='代理类型',
            options_enum=ProxyTypeEnum
        )
        self.proxy_type_opt.value_changed.connect(self._update_proxy_ui)

        self.proxy_url_input = TextSettingCard(icon=FluentIcon.WIFI, title='代理地址')

        proxy_group.addSettingCards([self.proxy_type_opt, self.proxy_url_input])
        advanced_group.addSettingCard(proxy_group)

        return advanced_group

    def _on_region_changed(self, index: int, value: str):
        if index == 0:
            self.ctx.env_config.repository_type = RepositoryTypeEnum.GITEE.value.value
            self.ctx.env_config.env_source = EnvSourceEnum.GITEE.value.value
            self.ctx.env_config.cpython_source = CpythonSourceEnum.GITEE.value.value
            self.ctx.env_config.pip_source = PipSourceEnum.ALIBABA.value.value
            self.ctx.env_config.proxy_type = ProxyTypeEnum.GHPROXY.value.value
            self.ctx.async_update_gh_proxy()
        elif index == 1:
            self.ctx.env_config.repository_type = RepositoryTypeEnum.GITHUB.value.value
            self.ctx.env_config.env_source = EnvSourceEnum.GITHUB.value.value
            self.ctx.env_config.cpython_source = CpythonSourceEnum.GITHUB.value.value
            self.ctx.env_config.pip_source = PipSourceEnum.PYPI.value.value
            self.ctx.env_config.proxy_type = ProxyTypeEnum.NONE.value.value
        self._init_config_values()

    def _init_config_values(self):
        """初始化配置值显示"""
        self.repository_type_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('repository_type'))
        self.env_source_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('env_source'))
        self.cpython_source_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('cpython_source'))
        self.pip_source_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('pip_source'))
        self.proxy_type_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('proxy_type'))

        self._update_proxy_ui()

    def _update_proxy_ui(self):
        """更新代理界面显示"""
        current_proxy_type = self.ctx.env_config.proxy_type
        if current_proxy_type == ProxyTypeEnum.PERSONAL.value.value:
            self.proxy_url_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('personal_proxy'))
            self.proxy_url_input.titleLabel.setText(gt('个人代理地址'))
            self.proxy_url_input.line_edit.setPlaceholderText('http://127.0.0.1:8080')
            self.proxy_url_input.setVisible(True)
        elif current_proxy_type == ProxyTypeEnum.GHPROXY.value.value:
            self.proxy_url_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('gh_proxy_url'))
            self.proxy_url_input.titleLabel.setText(gt('免费代理地址'))
            self.proxy_url_input.line_edit.setPlaceholderText('https://ghproxy.link/')
            self.proxy_url_input.setVisible(True)
        else:
            self.proxy_url_input.setVisible(False)

    def _init_proxy(self):
        """初始化代理设置"""
        self.ctx.env_config.init_system_proxy()
        self.ctx.git_service.is_proxy_set = False
        self.ctx.git_service.init_git_proxy()

    def on_interface_shown(self):
        VerticalScrollInterface.on_interface_shown(self)
        self._init_config_values()
