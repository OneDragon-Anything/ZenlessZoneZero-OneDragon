import os
import shutil
from contextlib import suppress
from pathlib import Path

from packaging import version
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import ComboBox, FluentIcon, FluentThemeColor

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

# 原始启动器
LAUNCHER_EXE = 'OneDragon-Launcher.exe'
LAUNCHER_BACKUP = 'OneDragon-Launcher.bak.exe'
LAUNCHER_ZIP_SUFFIX = 'Launcher.zip'

# RuntimeLauncher
RUNTIME_LAUNCHER_EXE = 'OneDragon-RuntimeLauncher.exe'
RUNTIME_LAUNCHER_BACKUP = 'OneDragon-RuntimeLauncher.bak.exe'
RUNTIME_LAUNCHER_ZIP_SUFFIX = 'RuntimeLauncher.zip'
RUNTIME_DIR = '.runtime'
RUNTIME_DIR_BACKUP = '.runtime.bak'


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

    def __init__(self, ctx: OneDragonEnvContext, exe_name: str):
        super().__init__()
        self.ctx = ctx
        self.exe_name = exe_name

    def run(self) -> None:
        exe_path = Path(os_utils.get_work_dir()) / self.exe_name
        current_version = app_utils.get_exe_version(str(exe_path)) if exe_path.exists() else ""
        latest_stable, latest_beta = self.ctx.git_service.get_latest_tag()
        self.check_finished.emit(current_version, latest_stable, latest_beta)


class LauncherDownloadCard(ZipDownloaderSettingCard):

    def __init__(self, ctx: OneDragonEnvContext):
        self.ctx: OneDragonEnvContext = ctx
        self._launcher_type: str = 'launcher'  # 'launcher' | 'runtime'
        self.version_checker = LauncherVersionChecker(ctx, LAUNCHER_EXE)
        self.version_checker.check_finished.connect(self._on_version_check_finished)
        self.target_version = "latest"
        self.current_version: str | None = None
        self.latest_stable: str | None = None
        self.latest_beta: str | None = None

        ZipDownloaderSettingCard.__init__(
            self,
            ctx=ctx,
            icon=FluentIcon.INFO,
            title=gt('启动器'),
            content=gt('检查中...'),
        )

        # 启动器类型下拉框
        self.type_combo = ComboBox()
        self.type_combo.addItem(gt('原始启动器'), userData='launcher')
        self.type_combo.addItem('RuntimeLauncher', userData='runtime')
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.btn_layout.insertWidget(1, self.type_combo, alignment=Qt.AlignmentFlag.AlignRight)

        # 通道选项：稳定版 / 测试版
        self.set_options_by_list([
            ConfigItem('稳定版', 'stable'),
            ConfigItem('测试版', 'beta')
        ])

    # ---- 启动器类型 ----

    @property
    def _exe_name(self) -> str:
        return RUNTIME_LAUNCHER_EXE if self._launcher_type == 'runtime' else LAUNCHER_EXE

    @property
    def _backup_name(self) -> str:
        return RUNTIME_LAUNCHER_BACKUP if self._launcher_type == 'runtime' else LAUNCHER_BACKUP

    @property
    def _zip_suffix(self) -> str:
        return RUNTIME_LAUNCHER_ZIP_SUFFIX if self._launcher_type == 'runtime' else LAUNCHER_ZIP_SUFFIX

    @property
    def _is_runtime(self) -> bool:
        return self._launcher_type == 'runtime'

    def _on_type_changed(self, _index: int) -> None:
        self._launcher_type = self.type_combo.currentData()
        # 重建版本检查器（指向不同 exe）
        self.version_checker = LauncherVersionChecker(self.ctx, self._exe_name)
        self.version_checker.check_finished.connect(self._on_version_check_finished)
        # 重置版本状态，触发重新检查
        self.current_version = None
        self.latest_stable = None
        self.latest_beta = None
        self.check_and_update_display()

    def _get_downloader_param(self, _idx = None) -> CommonDownloaderParam:
        zip_file_name = f'{self.ctx.project_config.project_name}-{self._zip_suffix}'
        exe_path = os.path.join(os_utils.get_work_dir(), self._exe_name)

        base = (
            'latest/download'
            if self.target_version == 'latest'
            else f'download/{self.target_version}'
        )
        download_url = f'{self.ctx.project_config.github_homepage}/releases/{base}/{zip_file_name}'

        return CommonDownloaderParam(
            save_file_path=DEFAULT_ENV_PATH,
            save_file_name=zip_file_name,
            github_release_download_url=download_url,
            check_existed_list=[exe_path],
            unzip_dir_path=os_utils.get_work_dir()
        )

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
            # 稳定版通道
            self.target_version = self.latest_stable or 'latest'
        else:
            # 测试版通道：优先测试版，其次稳定版，最后兜底
            self.target_version = self.latest_beta or self.latest_stable or 'latest'

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
            self.type_combo.setDisabled(True)
            return

        # 启用下拉框
        self.combo_box.setEnabled(True)
        self.type_combo.setEnabled(True)

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
        self._swap_backup(backup=True)
        self._delete_legacy_files()
        ZipDownloaderSettingCard._on_download_click(self)

    def _swap_backup(self, backup: bool) -> None:
        """备份或回滚启动器文件。"""
        work_dir = Path(os_utils.get_work_dir())
        action = '备份' if backup else '回滚'

        # exe
        exe_path = work_dir / self._exe_name
        bak_path = work_dir / self._backup_name
        src, dst = (exe_path, bak_path) if backup else (bak_path, exe_path)
        if src.exists():
            try:
                if backup and dst.exists():
                    dst.unlink()
                os.replace(str(src), str(dst))
                log.info(f'{action}文件: {src.name} -> {dst.name}')
            except Exception as e:
                log.error(f'{action}文件失败 {src.name}: {e}')

        # RuntimeLauncher 额外处理 .runtime 目录
        if self._is_runtime:
            rt_path = work_dir / RUNTIME_DIR
            rt_bak = work_dir / RUNTIME_DIR_BACKUP
            src_d, dst_d = (rt_path, rt_bak) if backup else (rt_bak, rt_path)
            if src_d.exists():
                try:
                    if dst_d.exists():
                        shutil.rmtree(dst_d)
                    src_d.rename(dst_d)
                    log.info(f'{action}目录: {src_d.name} -> {dst_d.name}')
                except Exception as e:
                    log.error(f'{action}目录失败 {src_d.name}: {e}')

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

    def _cleanup_backup(self) -> None:
        """删除备份的启动器文件（以及 RuntimeLauncher 的 .runtime.bak 目录）。"""
        work_dir = Path(os_utils.get_work_dir())

        bak_path = work_dir / self._backup_name
        if bak_path.exists():
            try:
                bak_path.unlink()
                log.info(f'删除备份文件: {self._backup_name}')
            except Exception as e:
                log.error(f'删除备份文件失败 {self._backup_name}: {e}')

        if self._is_runtime:
            rt_bak = work_dir / RUNTIME_DIR_BACKUP
            if rt_bak.exists():
                try:
                    shutil.rmtree(rt_bak)
                    log.info(f'删除备份目录: {RUNTIME_DIR_BACKUP}')
                except Exception as e:
                    log.error(f'删除备份目录失败 {RUNTIME_DIR_BACKUP}: {e}')

    def _on_download_finish(self, success: bool, message: str) -> None:
        """下载完成后处理备份：成功则删除备份，失败则回滚。"""
        if success:
            self._cleanup_backup()

            if not self.version_checker.isRunning():
                self.version_checker.start()
        else:
            self._swap_backup(backup=False)

        ZipDownloaderSettingCard._on_download_finish(self, success, message)
