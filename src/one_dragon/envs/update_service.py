import shutil
import sys
from pathlib import Path
from typing import Literal

from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.envs.env_config import DEFAULT_ENV_PATH, EnvConfig
from one_dragon.envs.git_service import GitService
from one_dragon.envs.launcher_asset_probe import probe_launcher_asset_urls
from one_dragon.envs.launcher_update_transaction import (
    RUNTIME_DIR,
    RUNTIME_LAUNCHER_EXE,
    LauncherUpdateTransaction,
)
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import app_utils, os_utils
from one_dragon.utils.log_utils import log

LauncherType = Literal['launcher', 'runtime']

# 原始启动器
LAUNCHER_EXE = 'OneDragon-Launcher.exe'
LAUNCHER_ZIP_SUFFIX = 'Launcher.zip'

# 集成启动器
RUNTIME_LAUNCHER_ZIP_SUFFIX = 'RuntimeLauncher.zip'


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
        self._launcher_transaction = LauncherUpdateTransaction()
        # 版本信息缓存：检查线程查询后填入，UI 构造下载项只读缓存，避免主线程网络请求
        self._launcher_version_cache: dict[str, tuple[str, str, str]] = {}

    @staticmethod
    def get_launcher_exe_name(launcher_type: LauncherType) -> str:
        """获取启动器类型对应的 exe 文件名。"""
        return LauncherUpdateTransaction.get_exe_name(launcher_type)

    @staticmethod
    def _get_launcher_zip_suffix(launcher_type: LauncherType) -> str:
        """获取启动器类型对应的压缩包后缀。"""
        return RUNTIME_LAUNCHER_ZIP_SUFFIX if launcher_type == 'runtime' else LAUNCHER_ZIP_SUFFIX

    def get_launcher_version_info(self, launcher_type: LauncherType) -> tuple[str, str, str]:
        """获取当前启动器版本、最新稳定版和最新测试版（带缓存，重复调用不重新请求网络）。"""
        cached = self._launcher_version_cache.get(launcher_type)
        if cached is not None:
            return cached
        exe_path = Path(os_utils.get_work_dir()) / self.get_launcher_exe_name(launcher_type)
        current_version = app_utils.get_exe_version(str(exe_path)) if exe_path.exists() else ''
        try:
            latest_stable, latest_beta = self.git_service.get_latest_tag()
        except Exception:
            log.error('获取最新启动器版本失败', exc_info=True)
            latest_stable, latest_beta = '', ''
        result = (current_version, latest_stable, latest_beta)
        self._launcher_version_cache[launcher_type] = result
        return result

    def is_launcher_update_available(self) -> bool:
        """检查当前启动器通道是否存在可用更新。"""
        launcher_type = self.detect_running_launcher_type() or 'launcher'
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
    def detect_running_launcher_type() -> LauncherType | None:
        """检测当前正在运行的启动器类型。

        集成启动器运行时当前进程是 OneDragon-RuntimeLauncher.exe；
        源码运行和原始启动器 exe 运行都属于原始启动器。
        """
        if not getattr(sys, 'frozen', False):
            return 'launcher'
        exe_name = Path(sys.executable).name
        if exe_name == RUNTIME_LAUNCHER_EXE:
            return 'runtime'
        if exe_name == LAUNCHER_EXE:
            return 'launcher'
        return None

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

    def get_launcher_asset_urls(
        self,
        launcher_type: LauncherType,
        target_version: str,
    ) -> dict[str, str]:
        """获取指定版本的启动器附件地址，不接受 latest。"""
        if not target_version or target_version == 'latest':
            raise ValueError('恢复模式必须使用具体启动器版本')
        zip_file_name = (
            f'{self.project_config.project_name}-{self._get_launcher_zip_suffix(launcher_type)}'
        )
        urls = self.env_config.repo_config.get_resource_asset_urls(
            'main',
            target_version,
            zip_file_name,
        )
        if not urls:
            raise RuntimeError('没有配置启动器下载源')
        return urls

    def check_launcher_asset(
        self,
        launcher_type: LauncherType,
        target_version: str,
    ) -> dict[str, str]:
        """确认指定版本的附件存在，并返回可用下载地址。"""
        urls = self.get_launcher_asset_urls(launcher_type, target_version)
        return probe_launcher_asset_urls(urls, self.env_config)

    def get_launcher_download_param(
        self,
        launcher_type: LauncherType,
        target_version: str = 'latest',
        staging: bool = False,
        download_urls: dict[str, str] | None = None,
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
        if download_urls is None:
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

    def validate_staged_launcher(self, launcher_type: LauncherType, staging_dir: Path) -> None:
        """检查暂存启动器的最小运行目录结构。"""
        staged_exe = staging_dir / self.get_launcher_exe_name(launcher_type)
        if not staged_exe.is_file() or staged_exe.stat().st_size == 0:
            raise RuntimeError('启动器更新包校验失败')
        if launcher_type != 'runtime':
            return
        staged_runtime = staging_dir / RUNTIME_DIR
        builtin_root = staged_runtime / 'builtin_src'
        if not staged_runtime.is_dir() or not (builtin_root / 'src').is_dir():
            raise RuntimeError('启动器运行环境缺少内置源码')
        if not (builtin_root / 'manifest.json').is_file():
            raise RuntimeError('启动器运行环境缺少内置清单')

    def apply_staged_launcher_update(
        self,
        launcher_type: LauncherType,
        staging_dir: Path,
    ) -> None:
        """校验临时目录后再备份并替换启动器，失败时自动回滚。"""
        self.validate_staged_launcher(launcher_type, staging_dir)
        staged_exe = staging_dir / self.get_launcher_exe_name(launcher_type)
        staged_runtime = staging_dir / RUNTIME_DIR
        work_dir = Path(os_utils.get_work_dir())
        backup_prepared = False
        try:
            self.prepare_launcher_update(launcher_type)
            backup_prepared = True
            staged_exe.replace(work_dir / staged_exe.name)
            if launcher_type == 'runtime':
                staged_runtime.rename(work_dir / RUNTIME_DIR)
            self._launcher_transaction.mark_cleanup(launcher_type)
            try:
                self.finish_launcher_update(launcher_type, True)
            except Exception:
                log.error("启动器更新已完成，但备份清理失败", exc_info=True)
                raise
            shutil.rmtree(staging_dir, ignore_errors=True)
        except Exception:
            if backup_prepared and (
                self._launcher_transaction._read_marker_state(launcher_type) != "cleanup"
            ):
                self._launcher_transaction.rollback_if_needed(launcher_type)
            raise

    def restore_interrupted_launcher_update(self) -> None:
        """启动时只处理有事务标记的备份，未知旧 bak 保留不动。"""
        self._launcher_transaction.restore_interrupted()

    def prepare_launcher_update(self, launcher_type: LauncherType) -> None:
        """为本次替换建立事务标记，再备份启动器。"""
        self._launcher_transaction.prepare(launcher_type)

    def finish_launcher_update(self, launcher_type: LauncherType, success: bool) -> None:
        """更新成功时安排清理备份，失败时回滚原启动器。"""
        self._launcher_transaction.finish(launcher_type, success)
