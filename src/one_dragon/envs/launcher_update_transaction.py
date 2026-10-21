import gc
import importlib
import shutil
import time
from importlib import metadata
from pathlib import Path
from typing import Literal

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log

LauncherType = Literal['launcher', 'runtime']
LauncherUpdateMarkerState = Literal['rollback', 'cleanup']

LAUNCHER_EXE = 'OneDragon-Launcher.exe'
LAUNCHER_BACKUP = 'OneDragon-Launcher.bak.exe'
RUNTIME_LAUNCHER_EXE = 'OneDragon-RuntimeLauncher.exe'
RUNTIME_LAUNCHER_BACKUP = 'OneDragon-RuntimeLauncher.bak.exe'
RUNTIME_DIR = '.runtime'
RUNTIME_DIR_BACKUP = '.runtime.bak'
RUNTIME_UPDATE_MARKER = '.runtime.update.pending'


class LauncherUpdateTransaction:
    """管理一次启动器替换的备份、回滚和清理。"""

    @staticmethod
    def get_exe_name(launcher_type: LauncherType) -> str:
        """返回启动器类型对应的 exe 文件名。"""
        return RUNTIME_LAUNCHER_EXE if launcher_type == 'runtime' else LAUNCHER_EXE

    @staticmethod
    def _get_backup_name(launcher_type: LauncherType) -> str:
        """返回启动器类型对应的备份文件名。"""
        return RUNTIME_LAUNCHER_BACKUP if launcher_type == 'runtime' else LAUNCHER_BACKUP

    @staticmethod
    def _get_marker_path(launcher_type: LauncherType) -> Path:
        """返回本次替换事务的标记文件。"""
        name = (
            RUNTIME_UPDATE_MARKER
            if launcher_type == 'runtime'
            else '.launcher.update.pending'
        )
        return Path(os_utils.get_work_dir()) / name

    def _write_marker(
        self,
        launcher_type: LauncherType,
        state: LauncherUpdateMarkerState = 'rollback',
    ) -> None:
        """写入事务阶段，供下次启动决定回滚或清理。"""
        marker = self._get_marker_path(launcher_type)
        marker.write_text(f'{launcher_type}:{state}', encoding='utf-8')

    def _read_marker_state(
        self,
        launcher_type: LauncherType,
    ) -> LauncherUpdateMarkerState:
        """读取事务阶段；标记缺失或无法读取时按需要回滚处理。"""
        marker = self._get_marker_path(launcher_type)
        try:
            value = marker.read_text(encoding='utf-8').strip()
        except OSError:
            return 'rollback'
        return 'cleanup' if value == f'{launcher_type}:cleanup' else 'rollback'

    def _remove_marker(self, launcher_type: LauncherType) -> None:
        """删除本次替换事务的标记文件。"""
        self._get_marker_path(launcher_type).unlink(missing_ok=True)

    def _has_backup(self, launcher_type: LauncherType) -> bool:
        """返回当前是否存在属于该启动器类型的备份。"""
        work_dir = Path(os_utils.get_work_dir())
        backup_path = work_dir / self._get_backup_name(launcher_type)
        return backup_path.exists() or (
            launcher_type == 'runtime'
            and (work_dir / RUNTIME_DIR_BACKUP).exists()
        )

    def prepare(self, launcher_type: LauncherType) -> None:
        """为本次替换建立事务标记，再备份启动器。"""
        if self._has_backup(launcher_type):
            raise RuntimeError('发现未确认的旧启动器备份，请先处理后重试')
        self._write_marker(launcher_type)
        try:
            self._swap_backup(launcher_type, backup=True)
            self._delete_legacy_files()
        except Exception:
            if not self._has_backup(launcher_type):
                self._remove_marker(launcher_type)
            raise

    def mark_cleanup(self, launcher_type: LauncherType) -> None:
        """标记新启动器已经就位，下次启动只清理备份。"""
        self._write_marker(launcher_type, 'cleanup')

    def finish(self, launcher_type: LauncherType, success: bool) -> None:
        """更新成功时安排清理备份，失败时回滚原启动器。"""
        if not success:
            self._swap_backup(launcher_type, backup=False)
            self._remove_marker(launcher_type)
            return
        if launcher_type == 'runtime':
            # 当前进程可能仍占用已改名的 exe 和 .runtime 备份，Windows 无法立即删除。
            # 保留到下次启动，由事务标记证明这些备份属于本次更新。
            log.info('集成启动器更新完成，备份将在下次启动时清理')
            return
        self._cleanup_backup(launcher_type)
        self._remove_marker(launcher_type)

    def rollback_if_needed(self, launcher_type: LauncherType) -> None:
        """替换失败且备份还在时回滚；新文件已就位则留给下次启动清理。"""
        marker_state = self._read_marker_state(launcher_type)
        if marker_state == 'cleanup':
            log.error('启动器已替换，但备份清理未完成，将在下次启动重试')
        elif self._has_backup(launcher_type):
            self.finish(launcher_type, False)
        else:
            self._remove_marker(launcher_type)

    def restore_interrupted(self) -> None:
        """启动时只处理有事务标记的备份，未知旧 bak 保留不动。"""
        work_dir = Path(os_utils.get_work_dir())
        for launcher_type in ('launcher', 'runtime'):
            marker = self._get_marker_path(launcher_type)
            backup_path = work_dir / self._get_backup_name(launcher_type)
            runtime_backup = work_dir / RUNTIME_DIR_BACKUP
            has_backup = backup_path.exists() or (
                launcher_type == 'runtime' and runtime_backup.exists()
            )
            if not has_backup and not marker.exists():
                continue
            if not marker.exists():
                log.warning(
                    f'发现没有事务标记的旧启动器备份，保留现场: {backup_path.name}'
                )
                continue

            marker_state = self._read_marker_state(launcher_type)
            exe_path = work_dir / self.get_exe_name(launcher_type)
            current_valid = exe_path.is_file() and exe_path.stat().st_size > 0
            if launcher_type == 'runtime':
                current_valid = current_valid and (work_dir / RUNTIME_DIR).is_dir()
            try:
                if marker_state == 'cleanup' and current_valid:
                    self._cleanup_backup(launcher_type)
                else:
                    self._swap_backup(launcher_type, backup=False)
                self._remove_marker(launcher_type)
            except Exception:
                log.error(
                    f'启动器更新事务恢复未完成，将在下次启动重试: {launcher_type}',
                    exc_info=True,
                )

    @staticmethod
    def _release_runtime_dir_handles() -> None:
        """释放进程内可能挡住 .runtime 目录改名的文件句柄。

        importlib.metadata 扫描 sys.path 时会把 base_library.zip 用 zipfile 打开，
        并把 zipfile.Path 挂在被 lru_cache 缓存的 FastPath 上，句柄不再释放。
        Windows 下会让 .runtime 目录改名报 WinError 5。
        清掉该缓存并回收引用后，句柄才会真正关闭。
        """
        metadata.FastPath.__new__.cache_clear()
        importlib.invalidate_caches()
        gc.collect()

    def _rename_runtime_dir(self, src: Path, dst: Path) -> None:
        """重命名 .runtime 相关目录；失败时释放进程内句柄后重试。"""
        last_error: OSError | None = None
        for attempt in range(3):
            try:
                src.rename(dst)
                return
            except OSError as error:
                last_error = error
                if attempt == 0:
                    log.warning(
                        f'重命名目录失败，释放文件句柄后重试: {src.name} -> {dst.name} {error}'
                    )
                self._release_runtime_dir_handles()
                time.sleep(0.3)
        if last_error is not None:
            raise last_error

    def _swap_backup(self, launcher_type: LauncherType, backup: bool) -> None:
        """备份或回滚启动器文件。"""
        work_dir = Path(os_utils.get_work_dir())
        exe_path = work_dir / self.get_exe_name(launcher_type)
        backup_path = work_dir / self._get_backup_name(launcher_type)
        runtime_path = work_dir / RUNTIME_DIR
        runtime_backup_path = work_dir / RUNTIME_DIR_BACKUP

        if backup:
            # 未知旧备份不能被本次事务覆盖，否则失败时无法判断回滚来源。
            if backup_path.exists() or (
                launcher_type == 'runtime' and runtime_backup_path.exists()
            ):
                raise RuntimeError('发现未确认的旧启动器备份，请先处理后重试')

            exe_backed_up = False
            try:
                if exe_path.exists():
                    exe_path.replace(backup_path)
                    exe_backed_up = True
                    log.info(f'备份文件: {exe_path.name} -> {backup_path.name}')
                if launcher_type == 'runtime' and runtime_path.exists():
                    self._rename_runtime_dir(runtime_path, runtime_backup_path)
                    log.info(
                        f'备份目录: {runtime_path.name} -> {runtime_backup_path.name}'
                    )
            except Exception:
                log.error('备份启动器失败', exc_info=True)
                if exe_backed_up and backup_path.exists():
                    try:
                        backup_path.replace(exe_path)
                    except Exception:
                        log.error('恢复已备份的启动器文件失败', exc_info=True)
                raise
            return

        rollback_errors: list[Exception] = []
        if backup_path.exists():
            try:
                backup_path.replace(exe_path)
                log.info(f'回滚文件: {backup_path.name} -> {exe_path.name}')
            except Exception as error:
                rollback_errors.append(error)
                log.error(f'回滚文件失败 {backup_path.name}', exc_info=True)

        if launcher_type == 'runtime' and runtime_backup_path.exists():
            try:
                if runtime_path.exists():
                    shutil.rmtree(runtime_path)
                self._rename_runtime_dir(runtime_backup_path, runtime_path)
                log.info(
                    f'回滚目录: {runtime_backup_path.name} -> {runtime_path.name}'
                )
            except Exception as error:
                rollback_errors.append(error)
                log.error(f'回滚目录失败 {runtime_backup_path.name}', exc_info=True)

        if rollback_errors:
            raise RuntimeError('启动器回滚未完成') from rollback_errors[0]

    def _cleanup_backup(self, launcher_type: LauncherType) -> None:
        """删除启动器备份文件和集成启动器的运行时备份目录。"""
        work_dir = Path(os_utils.get_work_dir())
        cleanup_errors: list[Exception] = []
        backup_name = self._get_backup_name(launcher_type)
        backup_path = work_dir / backup_name
        if backup_path.exists():
            try:
                backup_path.unlink()
                log.info(f'删除备份文件: {backup_name}')
            except Exception as error:
                cleanup_errors.append(error)
                log.error(f'删除备份文件失败 {backup_name}: {error}')

        if launcher_type == 'runtime':
            runtime_backup_path = work_dir / RUNTIME_DIR_BACKUP
            if runtime_backup_path.exists():
                try:
                    shutil.rmtree(runtime_backup_path)
                    log.info(f'删除备份目录: {RUNTIME_DIR_BACKUP}')
                except Exception as error:
                    cleanup_errors.append(error)
                    log.error(f'删除备份目录失败 {RUNTIME_DIR_BACKUP}: {error}')

        if cleanup_errors:
            raise RuntimeError('启动器备份清理未完成') from cleanup_errors[0]

    @staticmethod
    def _delete_legacy_files() -> None:
        """删除旧版本遗留的启动器文件。"""
        work_dir = Path(os_utils.get_work_dir())
        legacy_files = [
            'OneDragon Installer.exe',
            'OneDragon Launcher.exe',
            'OneDragon Scheduler.exe',
        ]
        for legacy_file in legacy_files:
            legacy_path = work_dir / legacy_file
            if not legacy_path.exists():
                continue
            try:
                legacy_path.unlink()
                log.info(f'删除旧版本遗留文件: {legacy_file}')
            except Exception as error:
                log.error(f'删除旧版本遗留文件失败 {legacy_file}: {error}')
