import shutil
from contextlib import suppress
from pathlib import Path

from packaging import version
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from qfluentwidgets import ComboBox, FluentIcon, FluentThemeColor

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.envs.env_config import (
    DEFAULT_ENV_PATH,
    RuntimeUpdateSourceEnum,
)
from one_dragon.envs.runtime_update_service import RuntimeUpdateCheckResult
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

# 集成启动器
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


class RuntimeLauncherUpdateChecker(QThread):
    check_finished = Signal(object, str)

    def __init__(self, ctx: OneDragonEnvContext, channel: str, source: str):
        super().__init__()
        self.ctx = ctx
        self.channel = channel
        self.source = source

    def run(self) -> None:
        try:
            result = self.ctx.runtime_update_service.check_for_updates(self.channel, self.source)
            self.check_finished.emit(result, "")
        except Exception as e:
            self.check_finished.emit(None, str(e))


class RuntimeLauncherUpdateRunner(QThread):
    progress_changed = Signal(str)
    finished = Signal(bool, str, object)

    def __init__(self, ctx: OneDragonEnvContext):
        super().__init__()
        self.ctx = ctx
        self.check_result: RuntimeUpdateCheckResult | None = None
        self.source_mode: str = RuntimeUpdateSourceEnum.AUTO.value.value
        self.progress_signal: dict[str, str | None] = {"signal": None}

    def run(self) -> None:
        if self.check_result is None:
            self.finished.emit(False, "未找到可用更新", None)
            return

        try:
            prepared = self._download_preferred_update(self.check_result)
            self.finished.emit(True, "准备更新完成，即将重启应用", prepared)
        except Exception as e:
            if self.progress_signal.get("signal") == "cancel":
                self.finished.emit(False, "下载已取消", None)
            else:
                self.finished.emit(False, str(e), None)

    def cancel(self) -> None:
        self.progress_signal["signal"] = "cancel"

    def _download_preferred_update(self, check_result: RuntimeUpdateCheckResult):
        try:
            return self.ctx.runtime_update_service.download_and_prepare_update(
                check_result,
                progress_signal=self.progress_signal,
                progress_callback=lambda _progress, msg: self.progress_changed.emit(msg),
            )
        except Exception as e:
            if self.source_mode != RuntimeUpdateSourceEnum.AUTO.value.value:
                raise
            if check_result.selected_source != RuntimeUpdateSourceEnum.S3.value.value:
                raise

            self.progress_changed.emit(f"{gt('S3/CDN 下载失败，回退到 GitHub')}: {e}")
            fallback_check = self.ctx.runtime_update_service.check_for_updates(
                check_result.channel,
                RuntimeUpdateSourceEnum.GITHUB.value.value,
            )
            return self.ctx.runtime_update_service.download_and_prepare_update(
                fallback_check,
                progress_signal=self.progress_signal,
                progress_callback=lambda _progress, msg: self.progress_changed.emit(msg),
            )


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
        self.runtime_update_result: RuntimeUpdateCheckResult | None = None
        self.runtime_update_error: str = ""
        self.runtime_update_runner = RuntimeLauncherUpdateRunner(ctx)
        self.runtime_update_runner.progress_changed.connect(self._on_runtime_update_progress)
        self.runtime_update_runner.finished.connect(self._on_runtime_update_finish)
        self.runtime_checker: RuntimeLauncherUpdateChecker | None = None

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
        self.type_combo.addItem(gt('集成启动器'), userData='runtime')
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.btn_layout.insertWidget(1, self.type_combo, alignment=Qt.AlignmentFlag.AlignRight)

        self.source_combo = ComboBox()
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.btn_layout.insertWidget(2, self.source_combo, alignment=Qt.AlignmentFlag.AlignRight)

        # 通道选项：稳定版 / 测试版
        self.set_options_by_list([
            ConfigItem('稳定版', 'stable'),
            ConfigItem('测试版', 'beta')
        ])
        self._reload_runtime_source_options()
        self._update_runtime_control_visibility()

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
        self._update_runtime_control_visibility()
        # 断开旧检查器信号，避免竞态覆盖
        old_checker = self.version_checker
        old_checker.check_finished.disconnect(self._on_version_check_finished)
        # 重建版本检查器（指向不同 exe）
        self.version_checker = LauncherVersionChecker(self.ctx, self._exe_name)
        self.version_checker.check_finished.connect(self._on_version_check_finished)
        # 重置版本状态，触发重新检查
        self.current_version = None
        self.latest_stable = None
        self.latest_beta = None
        self.runtime_update_result = None
        self.runtime_update_error = ""
        self.check_and_update_display()

    def _reload_runtime_source_options(self) -> None:
        selected = self.ctx.env_config.runtime_update_source
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        source_names = {
            RuntimeUpdateSourceEnum.AUTO.value.value: gt("自动"),
            RuntimeUpdateSourceEnum.S3.value.value: gt("S3/CDN"),
            RuntimeUpdateSourceEnum.GITHUB.value.value: gt("GitHub"),
            RuntimeUpdateSourceEnum.MIRROR.value.value: gt("Mirror酱"),
        }
        options = self.ctx.runtime_update_service.get_available_sources()
        for value, label in options:
            self.source_combo.addItem(source_names.get(value, label), userData=value)
        for idx in range(self.source_combo.count()):
            if self.source_combo.itemData(idx) == selected:
                self.source_combo.setCurrentIndex(idx)
                break
        else:
            self.source_combo.setCurrentIndex(0)
        self.source_combo.blockSignals(False)

    def _update_runtime_control_visibility(self) -> None:
        is_runtime = self._is_runtime
        self.source_combo.setVisible(is_runtime)

    def _on_source_changed(self, _index: int) -> None:
        if not self._is_runtime:
            return
        source = self.source_combo.currentData()
        if source:
            self.ctx.env_config.runtime_update_source = source
        self.runtime_update_result = None
        self.runtime_update_error = ""
        self.check_and_update_display()

    def _get_downloader_param(self, _idx = None) -> CommonDownloaderParam:
        zip_file_name = f'{self.ctx.project_config.project_name}-{self._zip_suffix}'
        exe_path = str(Path(os_utils.get_work_dir()) / self._exe_name)

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

    def _update_runtime_ui(self) -> None:
        if self.runtime_update_error:
            self._update_ui_state(
                icon=FluentIcon.INFO.icon(color=FluentThemeColor.RED.value),
                message=f"{gt('更新检查失败')}: {self.runtime_update_error}",
                button_text=gt('重试'),
                button_enabled=True,
            )
            return

        if self.runtime_update_result is None:
            self._update_ui_state(
                icon=FluentIcon.INFO,
                message=gt('正在检查版本...'),
                button_text=gt('检查中...'),
                button_enabled=False,
            )
            return

        result = self.runtime_update_result
        if not result.has_update:
            self._update_ui_state(
                icon=FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value),
                message=f"{gt('已安装')} {result.current_version or result.target_version}",
                button_text=gt('已安装'),
                button_enabled=False,
            )
            return

        source_name = {
            RuntimeUpdateSourceEnum.AUTO.value.value: gt("自动"),
            RuntimeUpdateSourceEnum.S3.value.value: gt("S3/CDN"),
            RuntimeUpdateSourceEnum.GITHUB.value.value: gt("GitHub"),
            RuntimeUpdateSourceEnum.MIRROR.value.value: gt("Mirror酱"),
        }.get(result.selected_source, result.selected_source)
        item_size = result.selected_item.get("size", 0) or 0
        size_text = f"{item_size / 1024 / 1024:.2f} MB" if item_size else gt("未知大小")
        note = result.release_notes.strip().replace("\n", " ")
        note_text = f"; {gt('更新说明')}: {note[:80]}" if note else ""
        self._update_ui_state(
            icon=FluentIcon.INFO.icon(color=FluentThemeColor.GOLD.value),
            message=(
                f"{gt('可下载')} {gt('当前版本')}: {result.current_version or gt('未安装')}; "
                f"{gt('目标版本')}: {result.target_version}; "
                f"{gt('更新方式')}: {result.selected_kind}; "
                f"{gt('更新源')}: {source_name}; "
                f"{gt('下载大小')}: {size_text}"
                f"{note_text}"
            ),
            button_text=gt('更新'),
            button_enabled=True,
        )

    def check_and_update_display(self) -> None:
        """
        检查启动器状态并更新显示
        重写父类方法以实现启动器特有的逻辑
        :return:
        """
        if self._is_runtime:
            self._check_and_update_runtime_display()
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

    def _check_and_update_runtime_display(self) -> None:
        is_running = self.runtime_update_runner.isRunning()
        self.cancel_btn.setVisible(is_running)
        self.cancel_btn.setEnabled(is_running)

        if is_running:
            self.download_btn.setText(gt('下载中'))
            self.download_btn.setDisabled(True)
            self.combo_box.setDisabled(True)
            self.type_combo.setDisabled(True)
            self.source_combo.setDisabled(True)
            return

        self.combo_box.setEnabled(True)
        self.type_combo.setEnabled(True)
        self.source_combo.setEnabled(True)

        if self.runtime_checker is not None and self.runtime_checker.isRunning():
            self._update_ui_state(
                icon=FluentIcon.INFO,
                message=gt('正在检查版本...'),
                button_text=gt('检查中...'),
                button_enabled=False,
            )
            return

        need_check = self.runtime_update_result is None and not self.runtime_update_error
        if need_check:
            channel = self.combo_box.currentData() or "stable"
            source = self.source_combo.currentData() or self.ctx.env_config.runtime_update_source
            self.runtime_checker = RuntimeLauncherUpdateChecker(self.ctx, channel, source)
            self.runtime_checker.check_finished.connect(self._on_runtime_check_finished)
            self.runtime_checker.start()
            self._update_ui_state(
                icon=FluentIcon.INFO,
                message=gt('正在检查版本...'),
                button_text=gt('检查中...'),
                button_enabled=False,
            )
            return

        self._update_runtime_ui()

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

    def on_index_changed(self, index: int) -> None:
        if self._is_runtime:
            if index == self.last_index:
                return
            self.last_index = index
            self.runtime_update_result = None
            self.runtime_update_error = ""
            self.check_and_update_display()
            self.value_changed.emit(index, self.combo_box.itemData(index))
            return
        ZipDownloaderSettingCard.on_index_changed(self, index)

    def _on_download_click(self) -> None:
        if self._is_runtime:
            if self.runtime_update_result is None or not self.runtime_update_result.has_update:
                self.runtime_update_error = ""
                self.runtime_update_result = None
                self.check_and_update_display()
                return
            self.runtime_update_runner.check_result = self.runtime_update_result
            self.runtime_update_runner.source_mode = self.source_combo.currentData() or self.ctx.env_config.runtime_update_source
            self.runtime_update_runner.progress_signal["signal"] = None
            self.runtime_update_runner.start()
            self.check_and_update_display()
            return
        self._swap_backup(backup=True)
        self._delete_legacy_files()
        ZipDownloaderSettingCard._on_download_click(self)

    def _on_cancel_click(self) -> None:
        if self._is_runtime:
            if self.runtime_update_runner.isRunning():
                self.runtime_update_runner.cancel()
                self.download_btn.setText(gt('取消中'))
                self.cancel_btn.setDisabled(True)
            return
        ZipDownloaderSettingCard._on_cancel_click(self)

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
                src.replace(dst)
                log.info(f'{action}文件: {src.name} -> {dst.name}')
            except Exception as e:
                log.error(f'{action}文件失败 {src.name}: {e}')

        # 集成启动器额外处理 .runtime 目录
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
        """删除备份的启动器文件（以及集成启动器的 .runtime.bak 目录）。"""
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

    def _on_runtime_check_finished(self, result: object, error: str) -> None:
        self.runtime_update_result = result if isinstance(result, RuntimeUpdateCheckResult) else None
        self.runtime_update_error = error
        self.check_and_update_display()

    def _on_runtime_update_progress(self, message: str) -> None:
        self.contentLabel.setText(message)

    def _on_runtime_update_finish(self, success: bool, message: str, prepared: object) -> None:
        if not success:
            log.error(message)
            self.runtime_update_error = message
            self.runtime_update_result = None
            self.check_and_update_display()
            return

        self.contentLabel.setText(gt('正在应用更新并重启...'))
        self.ctx.runtime_update_service.launch_apply_script(prepared)
        app = QApplication.instance()
        if app is not None:
            app.quit()
