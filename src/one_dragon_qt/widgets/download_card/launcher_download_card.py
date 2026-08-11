from contextlib import suppress

from packaging import version
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.envs.update_service import LauncherType, UpdateService
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.download_queue_service import (
    ResourceDownloadTask,
    ResourceDownloadTaskState,
)
from one_dragon_qt.widgets.setting_card.common_download_card import (
    ZipDownloaderSettingCard,
)


class LauncherVersionChecker(QThread):
    """启动器版本信息检查器。

    该线程在后台获取当前启动器版本号和最新版本信息。
    运行结束后通过 check_finished 信号发出三个字符串：
        (current_version, latest_stable, latest_beta)
        - current_version: 当前启动器版本号，如果不存在则为空字符串
        - latest_stable: 最新稳定版标签
        - latest_beta: 最新测试版标签
    """
    check_finished = Signal(str, str, str)

    def __init__(self, update_service: UpdateService, launcher_type: LauncherType) -> None:
        super().__init__()
        self.update_service: UpdateService = update_service
        self.launcher_type: LauncherType = launcher_type

    def run(self) -> None:
        try:
            current_version, latest_stable, latest_beta = (
                self.update_service.fetch_launcher_version_info(self.launcher_type)
            )
        except Exception:
            # 检查失败也要发出信号 否则界面会永远停在检查中且按钮不可用
            log.error('获取启动器版本信息失败', exc_info=True)
            current_version, latest_stable, latest_beta = '', '', ''
        self.check_finished.emit(current_version, latest_stable, latest_beta)


class LauncherDownloadCard(ZipDownloaderSettingCard):

    def __init__(self, ctx: OneDragonEnvContext) -> None:
        self.ctx: OneDragonEnvContext = ctx
        # 只处理当前正在运行的启动器类型 另一种类型不提供下载入口
        self._launcher_type: LauncherType = (
            ctx.update_service.detect_running_launcher_type() or 'launcher'
        )
        self.version_checker = LauncherVersionChecker(ctx.update_service, self._launcher_type)
        self.version_checker.check_finished.connect(self._on_version_check_finished)
        self.target_version = "latest"
        self.current_version: str | None = None
        self.latest_stable: str | None = None
        self.latest_beta: str | None = None

        launcher_title = (
            gt('集成启动器')
            if self._launcher_type == 'runtime'
            else gt('原始启动器')
        )
        ZipDownloaderSettingCard.__init__(
            self,
            ctx=ctx,
            icon=FluentIcon.INFO,
            title=launcher_title,
            content=gt('检查中...'),
        )

        # 通道选项：稳定版 / 测试版
        self.set_options_by_list([
            ConfigItem('稳定版', 'stable'),
            ConfigItem('测试版', 'beta')
        ])

    def _get_downloader_param(self, _idx: int | None = None) -> CommonDownloaderParam:
        return self.ctx.update_service.get_launcher_download_param(
            self._launcher_type,
            self.target_version,
        )

    def _on_queue_task_changed(self, task: ResourceDownloadTask) -> None:
        """启动器更新成功后重新读取已安装版本。"""
        if (
            task.task_key == self._queue_task_key
            and task.state == ResourceDownloadTaskState.SUCCEEDED
        ):
            self.current_version = None
            self.latest_stable = None
            self.latest_beta = None
        super()._on_queue_task_changed(task)

    def _on_version_check_finished(self, current_version: str, latest_stable: str, latest_beta: str) -> None:
        """
        版本检查完成后的回调（空字符串表示不存在）

        Args:
            current_version: 当前启动器版本号
            latest_stable: 最新稳定版标签
            latest_beta: 最新测试版标签
        """
        # 保存版本信息
        self.current_version = current_version
        self.latest_stable = latest_stable
        self.latest_beta = latest_beta

        # 尝试更新标题栏版本号
        if self.current_version:
            with suppress(Exception):
                self.window().titleBar.setLauncherVersion(self.current_version)

        # 根据当前版本初始化下拉框的值
        self._select_channel_by_version()

        # 更新UI显示
        self.check_and_update_display()

    def _update_ui_by_version(self) -> None:
        """
        根据版本信息更新UI显示
        :return:
        """
        # 根据下拉框选择的通道决定目标版本
        selected_channel = self.combo_box.currentData()
        if selected_channel == 'stable':
            # 稳定版通道 远端标签获取失败时保持当前已安装版本
            self.target_version = self.latest_stable or self.current_version or 'latest'
        else:
            # 测试版通道：优先测试版，其次稳定版，再保持当前版本
            self.target_version = (
                self.latest_beta
                or self.latest_stable
                or self.current_version
                or 'latest'
            )

        self._refresh_queue_task_key()
        self._update_downloader_and_runner()

        # 更新UI显示
        if self.current_version and self.current_version == self.target_version:
            # 版本一致：已安装
            self._update_ui_state(
                icon=FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value),
                message=f"{gt('已安装')} {self.current_version}",
                button_text=gt('已安装'),
                button_enabled=False
            )
        elif self.current_version:
            # 有新版本：可下载
            self._update_ui_state(
                icon=FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value),
                message=f"{gt('可下载')} {gt('当前版本')}: {self.current_version}; {gt('目标版本')}: {self.target_version}",
                button_text=gt('下载'),
                button_enabled=True
            )
        else:
            # 未安装：可下载
            self._update_ui_state(
                icon=FluentIcon.INFO.icon(color=FluentThemeColor.RED.value),
                message=f"{gt('未安装')} {gt('目标版本')}: {self.target_version}",
                button_text=gt('下载'),
                button_enabled=True
            )

    def check_and_update_display(self) -> None:
        """
        检查启动器状态并更新显示
        重写父类方法以实现启动器特有的逻辑
        :return:
        """
        if self.download_queue is not None and self._apply_queue_display_state():
            self.combo_box.setEnabled(True)
            self.cancel_btn.setVisible(False)
            return

        # 检查是否正在下载
        is_running = self.download_runner is not None and self.download_runner.isRunning()

        # 更新取消按钮的显示状态
        self.cancel_btn.setVisible(is_running)
        self.cancel_btn.setEnabled(is_running)

        # 如果正在下载，设置下载按钮状态并返回
        if is_running:
            self.download_btn.setText(gt('下载中'))
            self.download_btn.setDisabled(True)
            self.combo_box.setDisabled(True)
            return

        # 启用下拉框
        self.combo_box.setEnabled(True)

        # 检查版本检查线程状态
        is_checking = self.version_checker.isRunning()

        # 检查是否需要启动版本检查
        need_check = (
            self.current_version is None  # 当前版本未检查
            or self.latest_stable is None  # 稳定版未检查
            or self.latest_beta is None  # 测试版未检查
        )

        # 启动检查（如果需要且未在检查）
        if need_check and not is_checking:
            self.version_checker.start()
            is_checking = True  # 标记为检查中

        # 根据检查状态更新UI
        if is_checking or need_check:
            # 正在检查或刚启动检查，显示检查中状态
            self._update_ui_state(
                icon=FluentIcon.INFO,
                message=gt('正在检查版本...'),
                button_text=gt('检查中...'),
                button_enabled=False
            )
        else:
            # 所有信息已获取，更新UI
            self._update_ui_by_version()

    def _update_ui_state(
        self,
        icon: QIcon,
        message: str,
        button_text: str,
        button_enabled: bool
    ) -> None:
        """
        统一更新UI状态的方法
        :param icon: 图标
        :param message: 提示消息
        :param button_text: 按钮文本
        :param button_enabled: 按钮是否启用
        :return:
        """
        self.iconLabel.setIcon(icon)
        self.contentLabel.setText(message)
        self.download_btn.setText(button_text)
        self.download_btn.setEnabled(button_enabled)

    def _select_channel_by_version(self) -> None:
        """
        根据当前版本自动选择通道(稳定版/测试版)
        :return:
        """
        try:
            is_beta = (self.current_version and version.parse(self.current_version).is_prerelease)
        except Exception:
            is_beta = False

        if is_beta:
            # 设置为测试版
            self.combo_box.setCurrentIndex(1)
        else:
            # 设置为稳定版（包括未安装、未检查或稳定版的情况）
            self.combo_box.setCurrentIndex(0)

    def _on_download_click(self) -> None:
        if self.download_queue is not None:
            ZipDownloaderSettingCard._on_download_click(self)
            return
        self.ctx.update_service.prepare_launcher_update(self._launcher_type)
        ZipDownloaderSettingCard._on_download_click(self)

    def _on_download_finish(self, success: bool, message: str) -> None:
        """下载完成后处理备份：成功则删除备份，失败则回滚。"""
        self.ctx.update_service.finish_launcher_update(self._launcher_type, success)
        if success and not self.version_checker.isRunning():
            self.version_checker.start()

        ZipDownloaderSettingCard._on_download_finish(self, success, message)
