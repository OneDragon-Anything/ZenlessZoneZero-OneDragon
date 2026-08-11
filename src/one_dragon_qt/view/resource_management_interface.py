from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QSizePolicy, QTableWidgetItem, QWidget
from qfluentwidgets import (
    Dialog,
    FluentIcon,
    LineEdit,
    MessageBoxBase,
    PipsPager,
    PushButton,
    SettingCardGroup,
    SubtitleLabel,
    TableWidget,
    ToolButton,
)

from one_dragon.base.config.basic_model_config import (
    get_ocr_opts,
)
from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.envs.env_config import ProxyTypeEnum
from one_dragon.envs.git_service import GitLog, GitSyncStatus
from one_dragon.envs.repo_config import ModelResourceDefinition
from one_dragon.envs.update_service import LauncherType
from one_dragon.utils.app_utils import start_one_dragon
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.download_queue_service import (
    DownloadQueueService,
    ResourceDownloadSpec,
)
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.download_card.launcher_download_card import (
    LauncherDownloadCard,
)
from one_dragon_qt.widgets.download_card.onnx_model_download_card import (
    OnnxModelDownloadCard,
)
from one_dragon_qt.widgets.install_card.code_install_card import CodeInstallCard
from one_dragon_qt.widgets.resource_download_dialog import (
    build_resource_source_options,
)
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.expand_setting_card_group import (
    ExpandSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.password_switch_setting_card import (
    PasswordSwitchSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class FetchTotalRunner(QThread):

    finished = Signal(int)

    def __init__(self, method: Callable[[], int]):
        super().__init__()
        self.method: Callable[[], int] = method

    def run(self) -> None:
        self.finished.emit(self.method())


class FetchPageRunner(QThread):

    finished = Signal(list)

    def __init__(self, method: Callable[[], list[GitLog]]):
        super().__init__()
        self.method: Callable[[], list[GitLog]] = method

    def run(self) -> None:
        self.finished.emit(self.method())


class OcrReloadRunner(QThread):
    """后台重新初始化 OCR 模型 避免下载与加载阻塞界面线程。"""

    def __init__(self, ctx: OneDragonContext):
        super().__init__()
        self.ctx: OneDragonContext = ctx

    def run(self) -> None:
        try:
            self.ctx.init_ocr()
        except Exception:
            log.error('后台重新加载 OCR 模型失败', exc_info=True)


class ResourceManagementInterface(VerticalScrollInterface):

    def __init__(
        self,
        ctx: OneDragonContext,
        download_queue: DownloadQueueService,
        parent: QWidget | None = None,
    ) -> None:
        self.page_num: int = -1
        self.page_size: int = 10
        self.ctx: OneDragonContext = ctx
        self.download_queue: DownloadQueueService = download_queue

        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='resource_management_interface',
            parent=parent,
            nav_text_cn='资源管理', nav_icon=FluentIcon.SYNC
        )

        self.fetch_total_runner = FetchTotalRunner(ctx.git_service.fetch_total_commit)
        self.fetch_total_runner.finished.connect(self.update_total)
        self.fetch_page_runner = FetchPageRunner(self.fetch_page)
        self.fetch_page_runner.finished.connect(self.update_page)

    def get_content_widget(self) -> Column:
        content_widget = Column(spacing=20)
        content_widget.v_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.code_card = CodeInstallCard(self.ctx)
        self.code_card.titleLabel.setText(gt('代码同步'))
        self.code_card.iconLabel.setIcon(FluentIcon.CODE)
        self.code_card.git_branch_opt.hide()
        self.code_card.finished.connect(self.on_code_updated)
        self.code_card.finished.connect(self._show_dialog_after_code_updated)
        self.code_card.install_btn.clicked.disconnect()
        self.code_card.install_btn.clicked.connect(self._start_code_sync)

        self.history_button = PushButton(FluentIcon.HISTORY, gt('版本记录'))
        self.history_button.clicked.connect(self._show_history_dialog)
        self.settings_button = PushButton(FluentIcon.SETTING, gt('设置'))
        self.settings_button.clicked.connect(self._show_code_settings_dialog)
        self.code_card.btn_layout.insertWidget(
            1,
            self.history_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        self.code_card.btn_layout.insertWidget(
            2,
            self.settings_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        self.repository_url_opt = ComboBoxSettingCard(
            icon=FluentIcon.APPLICATION,
            title='代码源',
            content='自动模式优先使用上次成功源',
            options_list=self.ctx.repo_config.repository_options,
        )
        self.repository_url_opt.value_changed.connect(lambda: self.ctx.git_service.update_remote())

        self.git_branch_opt = ComboBoxSettingCard(
            icon=FluentIcon.GITHUB,
            title='代码分支',
            content='主分支用于稳定版本，测试分支用于提前体验新功能',
            options_list=self.ctx.repo_config.branch_options,
        )
        self.git_branch_opt.value_changed.connect(self._on_git_branch_changed)

        self.auto_update_code_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.SYNC, title='自动更新', content='使用exe启动时，自动检测并更新代码',
            password_hash='69fec7ebc9c57ba044c55deb4e30aa1a6d6788f1da67b824ef96a590f526d20a',
            reverse_mode=True
        )

        self.force_update_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC, title='强制更新', content='不懂代码请开启，会将脚本更新到最新并将你的改动覆盖，不会使你的配置失效',
        )

        self.custom_git_branch_lineedit = LineEdit()
        self.custom_git_branch_lineedit.setPlaceholderText(gt('自定义分支'))
        self.custom_git_branch_lineedit.editingFinished.connect(self._on_custom_branch_edited)
        self.custom_git_branch_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.EDIT,
            title='自定义分支',
            extra_btn=self.custom_git_branch_lineedit,
            password_hash='9eccbf284f363f3a5f416e879aa9bcb2c8d8445997f97740270fccc98d360a33'
        )

        self.code_settings_group = SettingCardGroup(gt('代码设置'))
        self.code_settings_group.addSettingCard(self.repository_url_opt)
        self.code_settings_group.addSettingCard(self.git_branch_opt)
        self.code_settings_group.addSettingCard(self.force_update_opt)

        self.developer_code_group = SettingCardGroup(gt('开发者选项'))
        self.developer_code_group.addSettingCard(self.auto_update_code_opt)
        self.developer_code_group.addSettingCard(self.custom_git_branch_opt)

        self.code_settings_content = Column(spacing=12)
        self.code_settings_content.v_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )
        self.code_settings_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.code_settings_content.add_widget(self.code_settings_group)
        self.code_settings_content.add_widget(self.developer_code_group)

        self.log_table = TableWidget()
        self.log_table.setMinimumHeight(self.page_size * 42)

        self.log_table.setBorderVisible(True)
        self.log_table.setBorderRadius(8)

        self.log_table.setWordWrap(True)
        self.log_table.setColumnCount(5)
        self.log_table.setColumnWidth(0, 50)
        self.log_table.setColumnWidth(1, 100)
        self.log_table.setColumnWidth(2, 150)
        self.log_table.setColumnWidth(3, 200)
        # 设置最后一列占用剩余空间
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.verticalHeader().hide()
        self.log_table.setHorizontalHeaderLabels([
            gt('回滚'),
            gt('ID'),
            gt('作者'),
            gt('时间'),
            gt('内容')
        ])
        self.pager = PipsPager()
        self.pager.setPageNumber(1)
        self.pager.setVisibleNumber(5)
        self.pager.currentIndexChanged.connect(self.on_page_changed)
        self.pager.setItemAlignment(Qt.AlignmentFlag.AlignCenter)
        self._add_resource_content(content_widget)

        return content_widget

    def _add_resource_content(self, content_widget: Column) -> None:
        """添加框架通用资源和项目资源。"""
        self.download_settings_group = SettingCardGroup('下载设置')
        self.resource_source_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='下载源',
            content='自动模式优先使用上次成功源，失败后继续尝试其他源',
            options_list=build_resource_source_options(self.ctx.env_config),
        )
        self.download_settings_group.addSettingCard(self.resource_source_opt)

        self.proxy_group = ExpandSettingCardGroup(
            icon=FluentIcon.WIFI,
            title='代理设置',
            content='为代码和资源下载配置网络代理',
        )
        self.proxy_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='代理类型',
            options_enum=ProxyTypeEnum,
        )
        self.proxy_type_opt.value_changed.connect(
            self._on_proxy_type_changed
        )
        self.proxy_group.addHeaderWidget(self.proxy_type_opt.combo_box)

        self.proxy_url_input = TextSettingCard(
            icon=FluentIcon.WIFI,
            title='代理地址',
        )
        self.proxy_url_input.value_changed.connect(
            lambda _value: self.ctx.env_config.init_system_proxy()
        )
        self.proxy_group.addSettingCard(self.proxy_url_input)

        self.auto_fetch_proxy_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC,
            title='自动获取免费代理地址',
            content='仅在使用 GitHub 代理时生效',
        )
        self.fetch_proxy_btn = PushButton(gt('立即获取'), self)
        self.fetch_proxy_btn.clicked.connect(self._fetch_proxy_url)
        self.auto_fetch_proxy_opt.hBoxLayout.addWidget(
            self.fetch_proxy_btn,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        self.auto_fetch_proxy_opt.hBoxLayout.addSpacing(16)
        self.proxy_group.addSettingCard(self.auto_fetch_proxy_opt)
        self.download_settings_group.addSettingCard(self.proxy_group)

        self.auto_download_opt = SwitchSettingCard(
            icon=FluentIcon.DOWNLOAD,
            title='资源自动下载',
            content='发现资源缺失或有新版本时，跳过确认并自动下载',
        )
        self.download_settings_group.addSettingCard(self.auto_download_opt)
        content_widget.add_widget(self.download_settings_group)

        self.download_items_group = SettingCardGroup('更新与下载')
        self.download_items_group.addSettingCard(self.code_card)
        self.launcher_opt = LauncherDownloadCard(self.ctx)
        self.launcher_opt.use_download_queue(
            self.download_queue,
            self._build_launcher_spec,
        )
        self.download_items_group.addSettingCard(self.launcher_opt)

        self.ocr_opt = self._create_model_card(
            title='OCR识别',
            options=get_ocr_opts(),
            current_getter=lambda: self.ctx.model_config.ocr,
            config_key='ocr',
            resource_id='ocr',
        )
        self.ocr_opt.gpu_changed.connect(self._on_ocr_gpu_changed)
        self.download_items_group.addSettingCard(self.ocr_opt)

        self._add_model_resource_cards(self.download_items_group)
        content_widget.add_widget(self.download_items_group)

    def _add_model_resource_cards(
        self,
        group: SettingCardGroup,
    ) -> None:
        """按项目模型配置声明自动创建全部模型卡片。"""
        self.model_resource_cards: dict[str, OnnxModelDownloadCard] = {}
        for resource in self.ctx.model_config.get_model_resources():
            def current_getter(
                selected: ModelResourceDefinition = resource,
            ) -> str:
                return self.ctx.model_config.get_model_current(selected)

            card = self._create_model_card(
                title=resource.display_name,
                options=self.ctx.model_config.get_model_options(resource),
                current_getter=current_getter,
                config_key=resource.config_key,
                resource_id=resource.config_key,
            )
            self._bind_model_gpu_option(card, resource)
            self.model_resource_cards[resource.config_key] = card
            group.addSettingCard(card)

    def _bind_model_gpu_option(
        self,
        card: OnnxModelDownloadCard,
        resource: ModelResourceDefinition,
    ) -> None:
        """按声明绑定模型 GPU 配置；未声明时隐藏开关。"""
        if resource.gpu_config_key is None:
            card.gpu_opt.hide()
            return
        card.gpu_changed.connect(
            lambda value, key=resource.gpu_config_key: (
                self.ctx.model_config.update(key, value)
            )
        )

    def _on_proxy_type_changed(
        self,
        _index: int,
        _value: str,
    ) -> None:
        """代理类型变化后刷新输入项并应用系统代理。"""
        self._update_proxy_ui()
        self.ctx.env_config.init_system_proxy()

    def _update_proxy_ui(self) -> None:
        """按后端代理类型绑定对应地址配置。"""
        proxy_type = self.ctx.env_config.proxy_type
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
        self.ctx.env_config.init_system_proxy()

    def _create_model_card(
        self,
        title: str,
        options: list[ConfigItem],
        current_getter: Callable[[], str],
        config_key: str,
        resource_id: str,
    ) -> OnnxModelDownloadCard:
        """创建接入下载队列的模型卡片。"""
        card = OnnxModelDownloadCard(
            ctx=self.ctx,
            icon=FluentIcon.GLOBE,
            title=title,
        )
        card.set_options_by_list(options)
        card.set_active_value_getter(current_getter)
        card.set_value_by_save_file_name(f'{current_getter()}.zip')
        card.value_changed.connect(
            lambda _index, param, key=config_key: self._switch_existing_model(
                key,
                param,
            )
        )
        card.use_download_queue(
            self.download_queue,
            lambda c=card, key=config_key, rid=resource_id, name=title: (
                self._build_model_spec(c, key, rid, name)
            ),
        )
        return card

    def _build_model_spec(
        self,
        card: OnnxModelDownloadCard,
        config_key: str,
        resource_id: str,
        title: str,
    ) -> ResourceDownloadSpec:
        """根据模型卡片当前选项构造队列任务。"""
        param: CommonDownloaderParam = card.getValue()
        target = param.save_file_name.removesuffix('.zip')
        current = str(self.ctx.model_config.get(config_key, ''))
        return ResourceDownloadSpec(
            resource_id=resource_id,
            resource_type='model',
            title=title,
            current_version=current,
            target_version=target,
            downloader_factory=lambda selected=param: ZipDownloader(selected),
            after_download=(
                lambda success, key=config_key, value=target: (
                    self._after_model_download(success, key, value)
                )
            ),
        )

    def _build_launcher_spec(self) -> ResourceDownloadSpec:
        """根据启动器卡片当前通道构造队列任务。"""
        launcher_type = self.launcher_opt._launcher_type
        target_version = self.launcher_opt.target_version
        current_version = self.launcher_opt.current_version or ''
        param = self.ctx.update_service.get_launcher_download_param(
            launcher_type,
            target_version,
            staging=True,
        )
        staging_dir = self.ctx.update_service.get_launcher_staging_dir(
            launcher_type,
            target_version,
        )
        return ResourceDownloadSpec(
            resource_id=f'launcher_{launcher_type}',
            resource_type='launcher',
            title='启动器',
            current_version=current_version,
            target_version=target_version,
            downloader_factory=lambda selected=param: ZipDownloader(selected),
            after_download=lambda success: self._after_launcher_download(
                launcher_type,
                staging_dir,
                success,
            ),
        )

    def _after_launcher_download(
        self,
        launcher_type: LauncherType,
        staging_dir: Path,
        success: bool,
    ) -> None:
        """下载完成后执行启动器事务替换。"""
        if success:
            self.ctx.update_service.apply_staged_launcher_update(
                launcher_type,
                staging_dir,
            )

    def _switch_existing_model(
        self,
        config_key: str,
        param: CommonDownloaderParam,
    ) -> None:
        """仅在模型已经存在时立即切换配置。"""
        downloader = ZipDownloader(param)
        if downloader.is_file_existed():
            self.ctx.model_config.update(
                config_key,
                param.save_file_name.removesuffix('.zip'),
            )

    def _after_model_download(
        self,
        success: bool,
        config_key: str,
        target: str,
    ) -> None:
        """模型下载成功后切换配置。"""
        if success:
            self.ctx.model_config.update(config_key, target)
            if config_key == 'ocr':
                self.ctx.init_ocr()

    def _on_ocr_gpu_changed(self, value: bool) -> None:
        """更新 OCR GPU 配置。"""
        previous = self.ctx.model_config.ocr_use_gpu
        self.ctx.model_config.ocr_use_gpu = value
        # 重新初始化 OCR 可能触发下载和模型加载 放到后台避免卡住界面
        self._ocr_reload_runner = OcrReloadRunner(self.ctx)
        self._ocr_reload_runner.finished.connect(
            lambda: self._on_ocr_reload_finished(previous, value)
        )
        self._ocr_reload_runner.start()

    def _on_ocr_reload_finished(self, previous: bool, requested: bool) -> None:
        """OCR 后台重载结束后恢复界面状态。"""
        ocr = self.ctx.ocr
        if ocr is None or ocr._model is None:
            # 加载失败 回滚开关和配置 避免界面显示与实际引擎不一致
            if previous != requested:
                self.ctx.model_config.ocr_use_gpu = previous
                self.ocr_opt.gpu_opt.setChecked(previous)

    def _show_history_dialog(self) -> None:
        """按需加载并展示代码版本记录。"""
        if not hasattr(self, 'history_dialog'):
            self.history_dialog = MessageBoxBase(self.window())
            self.history_dialog.yesButton.setText(gt('关闭'))
            self.history_dialog.cancelButton.hide()
            self.history_dialog.viewLayout.addWidget(self.log_table)
            self.history_dialog.viewLayout.addWidget(self.pager)
            self.history_dialog.widget.setMinimumWidth(850)
        self.page_num = -1
        self.start_fetch_total()
        self.history_dialog.exec()

    def _show_code_settings_dialog(self) -> None:
        """打开代码同步设置弹窗。"""
        self._refresh_code_settings()
        if not hasattr(self, 'code_settings_dialog'):
            self.code_settings_dialog = MessageBoxBase(self.window())
            self.code_settings_dialog.yesButton.setText(gt('关闭'))
            self.code_settings_dialog.cancelButton.hide()
            self.code_settings_dialog.viewLayout.addWidget(
                SubtitleLabel(gt('代码设置'))
            )
            self.code_settings_dialog.viewLayout.addWidget(
                self.code_settings_content
            )
            self.code_settings_dialog.widget.setMinimumWidth(720)
        self.code_settings_dialog.exec()

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self._refresh_code_settings()
        self.code_card.git_branch_opt.init_with_value(
            self.ctx.env_config.git_branch
        )
        self.code_card.check_and_update_display()
        self.resource_source_opt.init_with_adapter(
            self.ctx.env_config.get_prop_adapter('resource_source')
        )
        self.proxy_type_opt.init_with_adapter(
            self.ctx.env_config.get_prop_adapter('proxy_type')
        )
        self.auto_fetch_proxy_opt.init_with_adapter(
            self.ctx.env_config.get_prop_adapter(
                'auto_fetch_gh_proxy_url'
            )
        )
        self._update_proxy_ui()
        self.auto_download_opt.init_with_adapter(
            self.ctx.env_config.get_prop_adapter(
                'resource_download_no_confirm'
            )
        )
        self.ocr_opt.gpu_opt.setChecked(self.ctx.model_config.ocr_use_gpu)
        for resource in self.ctx.model_config.get_model_resources():
            if resource.gpu_config_key is None:
                continue
            card = self.model_resource_cards.get(resource.config_key)
            if card is not None:
                card.gpu_opt.setChecked(
                    bool(
                        self.ctx.model_config.get(
                            resource.gpu_config_key,
                            False,
                        )
                    )
                )

    def _refresh_code_settings(self) -> None:
        """刷新代码设置控件及开发者选项可见性。"""
        self.auto_update_code_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('auto_update_code'))
        self.force_update_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('force_update'))
        self.custom_git_branch_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('custom_git_branch'))
        self.repository_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('repository_url'))
        self.git_branch_opt.init_with_adapter(
            self.ctx.env_config.get_prop_adapter('git_branch')
        )
        self.custom_git_branch_lineedit.setText(self.ctx.env_config.git_branch)
        self._update_developer_visibility()

    def _start_code_sync(self) -> None:
        """从摘要卡片开始代码同步。"""
        self._update_code_header(gt('同步中'))
        self.code_card.start_progress()

    def _update_code_header(self, status: str) -> None:
        """刷新摘要卡片中的分支和同步状态。"""
        self.code_card.setContent(
            f'{gt("当前分支")} {self.ctx.env_config.git_branch} · {status}'
        )

    def _update_developer_visibility(self) -> None:
        """按开发者模式显示代码高级选项。"""
        if not self._init:
            return
        developer_mode = self.ctx.env_config.developer_mode
        self.developer_code_group.setVisible(developer_mode)

    def start_fetch_total(self) -> None:
        """
        开始获取总数
        :return:
        """
        if self.fetch_total_runner.isRunning():
            return
        self.fetch_total_runner.start()

    def update_total(self, total: int) -> None:
        """
        更新总数
        :param total:
        :return:
        """
        self.pager.setPageNumber((total + self.page_size - 1) // self.page_size)
        if self.page_num == -1:  # 还没有加载过任何分页
            self.page_num = 0
            self.start_fetch_page()

    def start_fetch_page(self) -> None:
        """
        开始获取分页内容
        :return:
        """
        if self.fetch_page_runner.isRunning():
            return
        self.fetch_page_runner.start()

    def fetch_page(self) -> list[GitLog]:
        """
        获取分页数据
        :return:
        """
        return self.ctx.git_service.fetch_page_commit(self.page_num, self.page_size)

    def update_page(self, log_list: list[GitLog]) -> None:
        """
        更新分页内容
        :param log_list:
        :return:
        """
        page_size = len(log_list)
        self.log_table.setRowCount(page_size)

        for i in range(page_size):
            reset_btn = ToolButton(FluentIcon.LEFT_ARROW, parent=None)
            reset_btn.setFixedSize(32, 32)
            reset_btn.setProperty('commit', log_list[i].commit_id)
            reset_btn.clicked.connect(self.on_reset_commit_clicked)

            self.log_table.setCellWidget(i, 0, reset_btn)
            self.log_table.setItem(i, 1, QTableWidgetItem(log_list[i].commit_id))

            author_item = QTableWidgetItem(log_list[i].author)
            author_item.setFlags(author_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 2, author_item)

            time_item = QTableWidgetItem(log_list[i].commit_time)
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 3, time_item)

            content_item = QTableWidgetItem(log_list[i].commit_message)
            content_item.setFlags(content_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 4, content_item)

    def on_page_changed(self, page: int) -> None:
        """
        翻页
        :param page:
        :return:
        """
        if page == self.page_num:
            return
        self.page_num = page
        self.start_fetch_page()

    def on_code_updated(self, success: bool) -> None:
        """
        代码同步后更新显示
        :param success: 是否成功
        :return:
        """
        self._update_code_header(gt('同步完成') if success else gt('同步失败'))
        if not success:
            return

        self.pager.setCurrentIndex(0)
        self.page_num = -1
        self.start_fetch_total()

    def on_reset_commit_clicked(self) -> None:
        """
        回滚到特定的commit
        """
        btn = self.sender()
        commit_id = btn.property('commit')
        success, msg = self.ctx.git_service.reset_to_commit(commit_id)
        if success:
            self.code_card.updated = True
            self.code_card.check_and_update_display()
            self.page_num = -1
            self.start_fetch_total()
        elif msg:
            dialog = Dialog(gt('回滚失败'), msg, self)
            dialog.setTitleBarVisible(False)
            dialog.cancelButton.hide()
            dialog.exec()

    def _on_git_branch_changed(self, _index: int, value: object) -> None:
        """切换标准代码分支并刷新同步状态。"""
        branch = str(value)
        self.ctx.env_config.git_branch = branch
        self.code_card.git_branch_opt.init_with_value(branch)
        self.custom_git_branch_lineedit.setText(branch)
        self.code_card.check_and_update_display()

    def _on_custom_branch_edited(self) -> None:
        text = self.custom_git_branch_lineedit.text()
        fallback = self.git_branch_opt.getValue()
        if fallback is None:
            fallback = self.ctx.repo_config.primary_branch
        self.ctx.env_config.git_branch = text if text else str(fallback)
        self.code_card.check_and_update_display()

    def _show_dialog_after_code_updated(self, success: bool) -> None:
        """仅在代码实际更新后显示重启对话框。"""
        if not success or self.code_card.last_sync_status is not GitSyncStatus.SUCCESS:
            return
        dialog = Dialog(gt('更新完成'), gt('代码已更新，重启以应用更改'), self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText(gt('立即重启'))
        dialog.cancelButton.setText(gt('稍后重启'))
        if dialog.exec():
            start_one_dragon(restart=True)
