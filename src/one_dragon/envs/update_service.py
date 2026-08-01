import shutil
from pathlib import Path
from typing import Literal

from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.envs.env_config import DEFAULT_ENV_PATH, EnvConfig
from one_dragon.envs.git_service import GitService
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.log_utils import log

LauncherType = Literal['launcher', 'runtime']

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


class UpdateService:
    """统一处理资源更新相关的版本检查、下载参数和文件替换。"""

    def __init__(
        self,
        project_config: ProjectConfig,
        env_config: EnvConfig,
        git_service: GitService,
    ) -> None:
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config
        self.git_service: GitService = git_service

    @staticmethod
    def get_launcher_exe_name(launcher_type: LauncherType) -> str:
        """获取启动器类型对应的 exe 文件名。"""
        return RUNTIME_LAUNCHER_EXE if launcher_type == 'runtime' else LAUNCHER_EXE

    @staticmethod
    def _get_launcher_backup_name(launcher_type: LauncherType) -> str:
        """获取启动器类型对应的备份文件名。"""
        return RUNTIME_LAUNCHER_BACKUP if launcher_type == 'runtime' else LAUNCHER_BACKUP

    @staticmethod
    def _get_launcher_zip_suffix(launcher_type: LauncherType) -> str:
        """获取启动器类型对应的压缩包后缀。"""
        return RUNTIME_LAUNCHER_ZIP_SUFFIX if launcher_type == 'runtime' else LAUNCHER_ZIP_SUFFIX

    def get_launcher_version_info(self, launcher_type: LauncherType) -> tuple[str, str, str]:
        """获取当前启动器版本、最新稳定版和最新测试版。"""
        exe_path = Path(os_utils.get_work_dir()) / self.get_launcher_exe_name(launcher_type)
        current_version = app_utils.get_exe_version(str(exe_path)) if exe_path.exists() else ''
        latest_stable, latest_beta = self.git_service.get_latest_tag()
        return current_version, latest_stable, latest_beta

    def is_launcher_update_available(self) -> bool:
        """检查当前启动器通道是否存在可用更新。"""
        launcher_type = self.detect_installed_launcher_type() or 'launcher'
        current_version, latest_stable, latest_beta = (
            self.get_launcher_version_info(launcher_type)
        )
        target_latest = self.get_launcher_target_version(
            current_version,
            latest_stable,
            latest_beta,
        )
        return current_version != target_latest

    @staticmethod
    def get_launcher_target_version(
        current_version: str,
        latest_stable: str,
        latest_beta: str,
    ) -> str:
        """按当前启动器通道返回目标版本。

        Args:
            current_version: 当前启动器版本。
            latest_stable: 最新稳定版。
            latest_beta: 最新测试版。

        Returns:
            应保持或更新到的目标版本。
        """
        if current_version and '-beta' in current_version:
            return latest_beta or latest_stable or current_version
        return latest_stable or current_version

    @staticmethod
    def detect_installed_launcher_type() -> LauncherType | None:
        """检测当前已安装的启动器类型，优先返回集成启动器。"""
        work_dir = Path(os_utils.get_work_dir())
        if (work_dir / RUNTIME_LAUNCHER_EXE).exists():
            return 'runtime'
        if (work_dir / LAUNCHER_EXE).exists():
            return 'launcher'
        return None

    @staticmethod
    def is_launcher_installed(launcher_type: LauncherType) -> bool:
        """检查指定类型的启动器是否已安装。"""
        launcher_path = Path(os_utils.get_work_dir()) / UpdateService.get_launcher_exe_name(
            launcher_type
        )
        return launcher_path.exists()

    def get_launcher_download_param(
        self,
        launcher_type: LauncherType,
        target_version: str = 'latest',
        staging: bool = False,
    ) -> CommonDownloaderParam:
        """构造启动器更新包的下载参数。"""
        zip_file_name = (
            f'{self.project_config.project_name}-{self._get_launcher_zip_suffix(launcher_type)}'
        )
        target_dir = (
            self.get_launcher_staging_dir(launcher_type, target_version)
            if staging
            else Path(os_utils.get_work_dir())
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        exe_path = str(target_dir / self.get_launcher_exe_name(launcher_type))

        tag = '' if target_version == 'latest' else target_version
        download_urls = self.env_config.repo_config.get_resource_asset_urls(
            'main',
            tag,
            zip_file_name,
        )
        if not download_urls:
            base = 'latest/download' if tag == '' else f'download/{tag}'
            download_urls = {
                'github': (
                    f'{self.project_config.github_homepage}/releases/{base}/{zip_file_name}'
                ),
            }

        return CommonDownloaderParam(
            save_file_path=str(target_dir if staging else Path(DEFAULT_ENV_PATH)),
            save_file_name=zip_file_name,
            download_urls=download_urls,
            check_existed_list=[exe_path],
            unzip_dir_path=str(target_dir),
        )

    @staticmethod
    def get_launcher_staging_dir(
        launcher_type: LauncherType,
        target_version: str,
    ) -> Path:
        """返回启动器临时下载目录。"""
        safe_version = target_version.replace('/', '_').replace('\\', '_')
        return Path(DEFAULT_ENV_PATH) / 'launcher_update' / launcher_type / safe_version

    def apply_staged_launcher_update(
        self,
        launcher_type: LauncherType,
        staging_dir: Path,
    ) -> None:
        """校验临时目录后再备份并替换启动器，失败时自动回滚。"""
        staged_exe = staging_dir / self.get_launcher_exe_name(launcher_type)
        if not staged_exe.is_file() or staged_exe.stat().st_size == 0:
            raise RuntimeError('启动器更新包校验失败')
        staged_runtime = staging_dir / RUNTIME_DIR
        if launcher_type == 'runtime' and not staged_runtime.is_dir():
            raise RuntimeError('启动器运行环境缺失')

        work_dir = Path(os_utils.get_work_dir())
        try:
            self.prepare_launcher_update(launcher_type)
            staged_exe.replace(work_dir / staged_exe.name)
            if launcher_type == 'runtime':
                staged_runtime.rename(work_dir / RUNTIME_DIR)
            self.finish_launcher_update(launcher_type, True)
            shutil.rmtree(staging_dir, ignore_errors=True)
        except Exception:
            self.finish_launcher_update(launcher_type, False)
            raise

    def restore_interrupted_launcher_update(self) -> None:
        """启动时恢复上次替换中断留下的启动器备份。"""
        work_dir = Path(os_utils.get_work_dir())
        for launcher_type in ('launcher', 'runtime'):
            exe_path = work_dir / self.get_launcher_exe_name(launcher_type)
            backup_path = work_dir / self._get_launcher_backup_name(launcher_type)
            current_valid = exe_path.is_file() and exe_path.stat().st_size > 0
            if launcher_type == 'runtime':
                current_valid = current_valid and (work_dir / RUNTIME_DIR).is_dir()
            if backup_path.exists() and not current_valid:
                self._swap_launcher_backup(launcher_type, backup=False)
            elif backup_path.exists() and current_valid:
                self._cleanup_launcher_backup(launcher_type)

    def prepare_launcher_update(self, launcher_type: LauncherType) -> None:
        """备份现有启动器并清理旧版本遗留文件。"""
        self._swap_launcher_backup(launcher_type, backup=True)
        self._delete_legacy_launcher_files()

    def finish_launcher_update(self, launcher_type: LauncherType, success: bool) -> None:
        """更新成功时清理备份，失败时回滚原启动器。"""
        if success:
            self._cleanup_launcher_backup(launcher_type)
        else:
            self._swap_launcher_backup(launcher_type, backup=False)

    def _swap_launcher_backup(self, launcher_type: LauncherType, backup: bool) -> None:
        """备份或回滚启动器文件。"""
        work_dir = Path(os_utils.get_work_dir())
        action = '备份' if backup else '回滚'

        exe_path = work_dir / self.get_launcher_exe_name(launcher_type)
        backup_path = work_dir / self._get_launcher_backup_name(launcher_type)
        source_path, target_path = (exe_path, backup_path) if backup else (backup_path, exe_path)
        if source_path.exists():
            try:
                if backup and target_path.exists():
                    target_path.unlink()
                source_path.replace(target_path)
                log.info(f'{action}文件: {source_path.name} -> {target_path.name}')
            except Exception as e:
                log.error(f'{action}文件失败 {source_path.name}: {e}')

        if launcher_type == 'runtime':
            runtime_path = work_dir / RUNTIME_DIR
            runtime_backup_path = work_dir / RUNTIME_DIR_BACKUP
            source_dir, target_dir = (
                (runtime_path, runtime_backup_path)
                if backup
                else (runtime_backup_path, runtime_path)
            )
            if source_dir.exists():
                try:
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    source_dir.rename(target_dir)
                    log.info(f'{action}目录: {source_dir.name} -> {target_dir.name}')
                except Exception as e:
                    log.error(f'{action}目录失败 {source_dir.name}: {e}')

    def _cleanup_launcher_backup(self, launcher_type: LauncherType) -> None:
        """删除启动器备份文件和集成启动器的运行时备份目录。"""
        work_dir = Path(os_utils.get_work_dir())

        backup_name = self._get_launcher_backup_name(launcher_type)
        backup_path = work_dir / backup_name
        if backup_path.exists():
            try:
                backup_path.unlink()
                log.info(f'删除备份文件: {backup_name}')
            except Exception as e:
                log.error(f'删除备份文件失败 {backup_name}: {e}')

        if launcher_type == 'runtime':
            runtime_backup_path = work_dir / RUNTIME_DIR_BACKUP
            if runtime_backup_path.exists():
                try:
                    shutil.rmtree(runtime_backup_path)
                    log.info(f'删除备份目录: {RUNTIME_DIR_BACKUP}')
                except Exception as e:
                    log.error(f'删除备份目录失败 {RUNTIME_DIR_BACKUP}: {e}')

    @staticmethod
    def _delete_legacy_launcher_files() -> None:
        """删除旧版本遗留的启动器文件。"""
        work_dir = Path(os_utils.get_work_dir())
        legacy_files = [
            'OneDragon Installer.exe',
            'OneDragon Launcher.exe',
            'OneDragon Scheduler.exe',
        ]

        for legacy_file in legacy_files:
            legacy_path = work_dir / legacy_file
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                    log.info(f'删除旧版本遗留文件: {legacy_file}')
                except Exception as e:
                    log.error(f'删除旧版本遗留文件失败 {legacy_file}: {e}')
