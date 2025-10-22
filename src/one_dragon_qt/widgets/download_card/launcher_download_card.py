import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.envs.env_config import DEFAULT_ENV_PATH
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.setting_card.common_download_card import (
    ZipDownloaderSettingCard,
)

LAUNCHER_EXE_NAME = 'OneDragon-Launcher.exe'
LAUNCHER_BACKUP_NAME = LAUNCHER_EXE_NAME + '.bak'


class LauncherVersionChecker(QThread):
    """启动器版本号检查器。

    该线程在后台获取最新的稳定版和测试版标签，并读取当前本地启动器版本。
    运行结束后通过 check_finished 信号发出两个字符串参数：
        latest_stable: 最新稳定版标签（或空字符串）
        latest_beta: 最新测试版标签（或空字符串）
    """
    check_finished = Signal(str, str)

    def __init__(self, ctx: OneDragonEnvContext):
        super().__init__()
        self.ctx = ctx

    def run(self):
        latest_stable, latest_beta = self.ctx.git_service.get_latest_tag()
        self.check_finished.emit(latest_stable or '', latest_beta or '')


class LauncherDownloadCard(ZipDownloaderSettingCard):

    def __init__(self, ctx: OneDragonEnvContext):
        self.ctx: OneDragonEnvContext = ctx
        self.version_checker = LauncherVersionChecker(ctx)
        self.version_checker.check_finished.connect(self._on_version_check_finished)
        self.latest_version = "latest"
        self.current_version = ""
        self.latest_stable = ""
        self.latest_beta = ""

        ZipDownloaderSettingCard.__init__(
            self,
            ctx=ctx,
            icon=FluentIcon.INFO,
            title=gt('启动器'),
            content=gt('未安装'),
            parent=None
        )

        # 设置下拉框选项：稳定版和测试版
        self.set_options_by_list([
            ConfigItem('稳定版', 'stable'),
            ConfigItem('测试版', 'beta')
        ])

    def _get_downloader_param(self, index) -> CommonDownloaderParam:
        """
        动态生成下载器参数
        :param index: 选择的下标（未使用，因为 LauncherInstallCard 不依赖 combo_box 数据）
        :return: CommonDownloaderParam
        """
        zip_file_name = f'{self.ctx.project_config.project_name}-Launcher.zip'
        launcher_path = os.path.join(os_utils.get_work_dir(), LAUNCHER_EXE_NAME)

        base = (
            'latest/download'
            if self.latest_version == 'latest'
            else f'download/{self.latest_version}'
        )
        download_url = f'{self.ctx.project_config.github_homepage}/releases/{base}/{zip_file_name}'

        return CommonDownloaderParam(
            save_file_path=DEFAULT_ENV_PATH,
            save_file_name=zip_file_name,
            github_release_download_url=download_url,
            check_existed_list=[launcher_path],
            unzip_dir_path=os_utils.get_work_dir()
        )

    def _check_launcher_exist(self) -> bool:
        """
        检查启动器是否存在
        :return: 是否存在
        """
        launcher_path = Path(os_utils.get_work_dir()) / LAUNCHER_EXE_NAME
        return launcher_path.exists()

    def _on_version_check_finished(self, latest_stable: str, latest_beta: str) -> None:
        """
        版本检查完成后的回调
        :param latest_stable: 最新稳定版
        :param latest_beta: 最新测试版
        :return:
        """
        # 更新实例变量
        self.latest_stable = latest_stable
        self.latest_beta = latest_beta

        # 根据下拉框选择的通道决定检查哪个版本
        selected_channel = self.combo_box.currentData()
        if selected_channel == 'stable':
            # 稳定版通道：与最新稳定版比较；若不存在稳定版，则视为已最新
            self.latest_version = self.latest_stable or self.current_version
        else:
            # 测试版通道：与最新测试版比较；若不存在测试版，则视为已最新
            self.latest_version = self.latest_beta or self.current_version

        self._update_downloader_and_runner()

        # 在主线程中更新UI
        if self.current_version == self.latest_version:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            msg = f"{gt('已安装')} {self.current_version}"
            self._update_display(icon, msg)
            self.download_btn.setText(gt('已安装'))
            self.download_btn.setDisabled(True)
        else:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value)
            msg = f"{gt('需更新')} {gt('当前版本')}: {self.current_version}; {gt('最新版本')}: {self.latest_version}"
            self._update_display(icon, msg)
            self.download_btn.setText(gt('更新'))
            self.download_btn.setDisabled(False)

    def check_and_update_display(self) -> None:
        """
        检查启动器状态并更新显示
        重写父类方法以实现启动器特有的逻辑
        :return:
        """
        # 先更新UI为检查中状态
        self.download_btn.setText(gt('检查中...'))
        self.download_btn.setDisabled(True)

        # 获取当前版本和启动器存在状态
        launcher_exist = self._check_launcher_exist()
        if launcher_exist:
            self.current_version = app_utils.get_launcher_version()

        # 如果启动器不存在，直接更新UI，不需要后台检查
        if not launcher_exist:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('需下载')
            self._update_display(icon, msg)
            self.download_btn.setText(gt('下载'))
            self.download_btn.setDisabled(False)
            return

        is_version_checked = (self.latest_stable or self.latest_beta)
        if not self.version_checker.isRunning() and not is_version_checked:
            self.version_checker.start()
        else:
            # 如果版本号已经检查过，直接调用回调更新UI
            self._on_version_check_finished(self.latest_stable, self.latest_beta)

    def _update_display(self, icon: QIcon, msg: str) -> None:
        """
        更新显示内容
        :param icon: 图标
        :param msg: 消息
        :return:
        """
        self.iconLabel.setIcon(icon)
        self.contentLabel.setText(msg)

    def _on_download_click(self) -> None:
        """
        备份旧启动器文件并删除遗留文件
        :return:
        """
        # 备份需要更新的启动器文件
        self._swap_launcher_and_backup(backup=True)

        # 删除旧版本遗留的文件
        self._delete_legacy_files()

        ZipDownloaderSettingCard._on_download_click(self)

    def _swap_launcher_and_backup(self, backup: bool) -> None:
        """
        在启动器文件和备份文件之间进行交换
        :param backup: True=备份，False=回滚
        """
        work_dir = Path(os_utils.get_work_dir())
        launcher_path = work_dir / LAUNCHER_EXE_NAME
        backup_path = work_dir / LAUNCHER_BACKUP_NAME
        src, dst, action = (
            (launcher_path, backup_path, '备份')
            if backup else
            (backup_path, launcher_path, '回滚')
        )

        if not src.exists():
            return  # 没有可操作文件，直接返回

        try:
            # 仅在备份时需要清理旧备份
            if backup and dst.exists():
                dst.unlink()
            os.replace(str(src), str(dst))
            log.info(f'{action}文件: {src.name} -> {dst.name}')
        except Exception as e:
            log.error(f'{action}文件失败 {src.name}: {e}')

    def _delete_legacy_files(self) -> None:
        """
        删除旧版本遗留的文件
        :return:
        """
        work_dir = os_utils.get_work_dir()
        legacy_files = [
            'OneDragon Installer.exe',
            'OneDragon Launcher.exe',
            'OneDragon Scheduler.exe'
        ]

        for legacy_file in legacy_files:
            legacy_path = Path(work_dir) / legacy_file
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                    log.info(f'删除旧版本遗留文件: {legacy_file}')
                except Exception as e:
                    log.error(f'删除旧版本遗留文件失败 {legacy_file}: {e}')

    def _cleanup_backup_launcher(self) -> None:
        """
        删除备份的启动器文件
        :return:
        """
        work_dir = os_utils.get_work_dir()
        backup_path = Path(work_dir) / LAUNCHER_BACKUP_NAME

        if backup_path.exists():
            try:
                backup_path.unlink()
                log.info(f'删除备份文件: {LAUNCHER_BACKUP_NAME}')
            except Exception as e:
                log.error(f'删除备份文件失败 {LAUNCHER_BACKUP_NAME}: {e}')

    def _on_download_finish(self, success: bool, message: str) -> None:
        """
        下载完成后处理备份：成功则删除备份，失败则回滚
        :param success: 是否成功
        :param message: 消息
        :return:
        """
        if success:
            # 下载成功，删除备份文件
            self._cleanup_backup_launcher()

            # 更新标题栏版本号
            self.current_version = app_utils.get_launcher_version()
            try:
                self.window().titleBar.setLauncherVersion(self.current_version)
            except Exception:
                pass
        else:
            # 下载失败，回滚到备份文件
            self._swap_launcher_and_backup(backup=False)

        ZipDownloaderSettingCard._on_download_finish(self, success, message)
