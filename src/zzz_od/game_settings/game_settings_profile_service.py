from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.base.config.game_account_config import GameRegionEnum
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class GameSettingsProfileError(RuntimeError):
    """游戏画质配置切换失败。"""


class GameSettingsProfileService:
    """在最外层绝区零自动化前后切换注册表画质配置。"""

    _CN_REGISTRY_KEY: str = r'HKEY_CURRENT_USER\Software\miHoYo\绝区零'
    _GLOBAL_REGISTRY_KEY: str = r'HKEY_CURRENT_USER\Software\miHoYo\ZenlessZoneZero'
    _ALLOWED_REGISTRY_KEYS: tuple[str, ...] = (
        _CN_REGISTRY_KEY,
        _GLOBAL_REGISTRY_KEY,
    )
    _MAX_PROFILE_SIZE: int = 16 * 1024 * 1024
    _CLOSE_TIMEOUT_SECONDS: float = 30
    _CLOSE_POLL_SECONDS: float = 0.5
    _REGISTRY_FLUSH_SECONDS: float = 2

    def __init__(self, ctx: ZContext) -> None:
        self.ctx: ZContext = ctx
        self._action_lock: threading.Lock = threading.Lock()
        self._session_depth: int = 0
        self._normal_profile_path: Path | None = None

    @property
    def session_depth(self) -> int:
        """当前嵌套自动化层数。"""
        return self._session_depth

    def validate_profile(self, file_path: str) -> Path:
        """校验注册表文件只修改绝区零配置键。"""
        if not file_path.strip():
            raise GameSettingsProfileError('未选择注册表配置文件')

        try:
            profile_path = Path(file_path).expanduser().resolve()
            if profile_path.suffix.casefold() != '.reg':
                raise GameSettingsProfileError('画质配置必须是 .reg 文件')
            if not profile_path.is_file():
                raise GameSettingsProfileError(f'画质配置文件不存在: {profile_path}')
            if profile_path.stat().st_size > self._MAX_PROFILE_SIZE:
                raise GameSettingsProfileError('画质配置文件超过 16 MB')

            content = self._decode_profile(profile_path)
        except OSError as error:
            raise GameSettingsProfileError(f'无法读取画质配置文件: {error}') from error
        first_line = next(
            (line.strip() for line in content.splitlines() if line.strip()),
            '',
        )
        if first_line not in {
            'Windows Registry Editor Version 5.00',
            'REGEDIT4',
        }:
            raise GameSettingsProfileError('不是有效的 Windows 注册表文件')

        registry_keys = re.findall(r'^\s*\[([^\]\r\n]+)]\s*$', content, re.MULTILINE)
        if not registry_keys:
            raise GameSettingsProfileError('注册表文件只允许包含绝区零配置键')

        for registry_key in registry_keys:
            if not self._is_allowed_registry_key(registry_key):
                raise GameSettingsProfileError(
                    '注册表文件只允许包含绝区零国服或国际服配置键'
                )

        return profile_path

    def export_profile(self, file_path: str) -> Path:
        """关闭游戏后把当前实例的注册表配置导出到文件。"""
        with self._manual_action():
            if not file_path.strip():
                raise GameSettingsProfileError('未选择注册表配置保存位置')

            try:
                profile_path = Path(file_path).expanduser().resolve()
                if not profile_path.suffix:
                    profile_path = profile_path.with_suffix('.reg')
                elif profile_path.suffix.casefold() != '.reg':
                    raise GameSettingsProfileError('画质配置必须是 .reg 文件')
                if not profile_path.parent.is_dir():
                    raise GameSettingsProfileError(
                        f'画质配置保存目录不存在: {profile_path.parent}'
                    )
            except OSError as error:
                raise GameSettingsProfileError(
                    f'无法使用画质配置保存位置: {error}'
                ) from error

            registry_key = self._get_current_registry_key()
            self._close_game()
            self._export_registry_key(registry_key, profile_path)
            validated_path = self.validate_profile(str(profile_path))
            log.info(f'已保存当前游戏画质配置: {validated_path}')
            return validated_path

    def restore_normal_profile(self) -> Path:
        """关闭游戏后立即导入已配置的正常画质。"""
        with self._manual_action():
            normal_profile_path = self.validate_profile(
                self.ctx.one_dragon_config.game_settings_profile_normal_path
            )
            self._close_game()
            self._import_profile(normal_profile_path)
            log.info('已手动恢复正常游戏画质配置')
            return normal_profile_path

    def enter(self) -> bool:
        """进入一层自动化；最外层负责导入一条龙画质配置。"""
        with self._action_lock:
            return self._enter()

    def _enter(self) -> bool:
        """在互斥区内进入一层自动化。"""
        if self._session_depth > 0:
            self._session_depth += 1
            return True

        config = self.ctx.one_dragon_config
        if not config.game_settings_profile_enabled:
            self._session_depth = 1
            return True

        run_profile_path = self.validate_profile(config.game_settings_profile_run_path)
        normal_profile_path = self.validate_profile(
            config.game_settings_profile_normal_path
        )
        if run_profile_path == normal_profile_path:
            raise GameSettingsProfileError('一条龙画质和正常画质不能使用同一个文件')

        self._close_game()
        try:
            self._import_profile(run_profile_path)
        except GameSettingsProfileError as run_error:
            try:
                self._import_profile(normal_profile_path)
            except GameSettingsProfileError as normal_error:
                raise GameSettingsProfileError(
                    f'{run_error}；重新导入正常画质也失败: {normal_error}'
                ) from run_error
            raise

        self._normal_profile_path = normal_profile_path
        self._session_depth = 1
        log.info('已导入一条龙游戏画质配置')
        return True

    def exit(self) -> None:
        """退出一层自动化；最外层负责恢复正常画质配置。"""
        with self._action_lock:
            self._exit()

    def _exit(self) -> None:
        """在互斥区内退出一层自动化。"""
        if self._session_depth == 0:
            return

        self._session_depth -= 1
        if self._session_depth > 0:
            return

        normal_profile_path = self._normal_profile_path
        self._normal_profile_path = None
        if normal_profile_path is None:
            return

        self._close_game()
        self._import_profile(normal_profile_path)
        log.info('已恢复正常游戏画质配置')

    @staticmethod
    def _decode_profile(profile_path: Path) -> str:
        data = profile_path.read_bytes()
        encodings: tuple[str, ...]
        if data.startswith((b'\xff\xfe', b'\xfe\xff')):
            encodings = ('utf-16',)
        elif data.startswith(b'\xef\xbb\xbf'):
            encodings = ('utf-8-sig',)
        else:
            encodings = ('utf-8', 'utf-16-le')

        for encoding in encodings:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise GameSettingsProfileError('无法读取注册表文件编码')

    @classmethod
    def _is_allowed_registry_key(cls, registry_key: str) -> bool:
        normalized_key = registry_key.strip()
        if normalized_key.startswith('-'):
            return False

        normalized_key = normalized_key.casefold()
        for allowed_key in cls._ALLOWED_REGISTRY_KEYS:
            normalized_allowed_key = allowed_key.casefold()
            if normalized_key == normalized_allowed_key or normalized_key.startswith(
                f'{normalized_allowed_key}\\'
            ):
                return True
        return False

    def _close_game(self) -> None:
        controller = self.ctx.controller
        if controller is None:
            return

        controller.init_game_win()
        if not controller.is_game_window_ready:
            return

        log.info('切换游戏画质配置前关闭游戏')
        controller.close_game()
        deadline = time.monotonic() + self._CLOSE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(self._CLOSE_POLL_SECONDS)
            controller.init_game_win()
            if not controller.is_game_window_ready:
                time.sleep(self._REGISTRY_FLUSH_SECONDS)
                return

        raise GameSettingsProfileError('等待游戏正常关闭超时，未切换画质配置')

    def _ensure_manual_action_available(self) -> None:
        """防止手动保存或恢复中断正在运行的自动化。"""
        if self._session_depth > 0:
            raise GameSettingsProfileError('一条龙运行中不能手动保存或恢复画质配置')

    @contextmanager
    def _manual_action(self) -> Iterator[None]:
        """手动操作与自动切换互斥，并在冲突时立即返回。"""
        if not self._action_lock.acquire(blocking=False):
            raise GameSettingsProfileError('游戏画质配置正在切换，请稍后重试')
        try:
            self._ensure_manual_action_available()
            yield
        finally:
            self._action_lock.release()

    def _get_current_registry_key(self) -> str:
        """按当前实例的服务器类型选择绝区零注册表键。"""
        game_region = self.ctx.game_account_config.game_region
        if game_region in {
            GameRegionEnum.CN.value.value,
            GameRegionEnum.CNB.value.value,
        }:
            return self._CN_REGISTRY_KEY
        return self._GLOBAL_REGISTRY_KEY

    @staticmethod
    def _import_profile(profile_path: Path) -> None:
        GameSettingsProfileService._run_reg_command(
            ['import', str(profile_path), '/reg:64'],
            '导入注册表画质配置',
        )

    @staticmethod
    def _export_registry_key(registry_key: str, profile_path: Path) -> None:
        GameSettingsProfileService._run_reg_command(
            ['export', registry_key, str(profile_path), '/y', '/reg:64'],
            '导出注册表画质配置',
        )

    @staticmethod
    def _run_reg_command(arguments: list[str], action: str) -> None:
        """通过参数列表执行 Windows 注册表命令。"""
        reg_executable = shutil.which('reg.exe')
        if reg_executable is None:
            raise GameSettingsProfileError('找不到 Windows reg.exe')

        try:
            result = subprocess.run(
                [reg_executable, *arguments],
                capture_output=True,
                check=False,
                timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except subprocess.TimeoutExpired as error:
            raise GameSettingsProfileError(f'{action}超时') from error
        except OSError as error:
            raise GameSettingsProfileError(f'无法运行 reg.exe {action}') from error

        if result.returncode != 0:
            raise GameSettingsProfileError(
                f'{action}失败，reg.exe 返回 {result.returncode}'
            )
