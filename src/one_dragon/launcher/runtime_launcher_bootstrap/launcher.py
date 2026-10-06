from __future__ import annotations

import argparse
import ctypes
import importlib
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pyuac

from one_dragon.launcher.runtime_launcher_bootstrap.builtin_source_validator import (
    BuiltinSourceValidator,
)
from one_dragon.launcher.runtime_launcher_bootstrap.profile import (
    RuntimeLauncherProfile,
)
from one_dragon.version import __version__

_SOURCE_ROOT_ENV = 'ONE_DRAGON_SOURCE_ROOT'
_SOURCE_MODE_ENV = 'ONE_DRAGON_RUNTIME_MODE'
_SOURCE_MODE_EXTERNAL = 'external'
_SOURCE_MODE_RECOVERY = 'recovery'


@dataclass(frozen=True, slots=True)
class LauncherOptions:
    show_version: bool
    onedragon: bool
    close_game: bool
    shutdown: int | None
    instance: str | None
    recovery: bool

    def build_onedragon_args(self) -> list[str]:
        """构造业务一条龙入口需要的参数。"""
        launch_args: list[str] = []
        if self.instance:
            launch_args.extend(['--instance', self.instance])
        if self.close_game:
            launch_args.append('--close-game')
        if self.shutdown is not None:
            launch_args.extend(['--shutdown', str(self.shutdown)])
        return launch_args


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    install_root: Path
    external_src: Path
    builtin_src: Path
    builtin_manifest: Path
    failure_log: Path

    @classmethod
    def from_executable(cls, executable: Path) -> RuntimePaths:
        """根据集成启动器路径建立三层源码位置。"""
        install_root = executable.resolve().parent
        builtin_root = install_root / '.runtime' / 'builtin_src'
        return cls(
            install_root=install_root,
            external_src=install_root / 'src',
            builtin_src=builtin_root / 'src',
            builtin_manifest=builtin_root / 'manifest.json',
            failure_log=install_root / '.log' / 'runtime_launcher_startup_error.log',
        )


class RuntimeLauncherSupervisor:
    """冻结启动内核，负责源码选择、ready 判定和进程级回退。"""

    def __init__(
        self,
        paths: RuntimePaths,
        version: str,
        profile: RuntimeLauncherProfile,
    ) -> None:
        self.paths: RuntimePaths = paths
        self.version: str = version
        self.profile: RuntimeLauncherProfile = profile
        self.ready: bool = False

    def run_normal(self, options: LauncherOptions) -> int:
        """使用安装目录外部源码启动正常应用。"""
        try:
            self._validate_external_source()
            self._activate_source(self.paths.external_src, _SOURCE_MODE_EXTERNAL)
            pre_modules = set(sys.modules)
            source_changed = bool(self.profile.sync_source(self.version))
            if source_changed:
                self._clear_source_modules(pre_modules, self.paths.external_src)
                importlib.invalidate_caches()

            runtime_entry = importlib.import_module(
                self.profile.runtime_entry_module
            )
            if options.onedragon:
                result = runtime_entry.run_onedragon(
                    options.build_onedragon_args(),
                    self.mark_ready,
                )
            else:
                self._hide_console()
                result = runtime_entry.run_gui(self.mark_ready)

            exit_code = int(result or 0)
            if not self.ready:
                if not options.onedragon and exit_code == 0:
                    return 0
                raise RuntimeError('应用在 ready 前退出')
            return exit_code
        except (Exception, SystemExit) as exc:
            error_info = self._format_failure(exc)
            if self.ready:
                self._show_fatal_error('运行失败', error_info)
                return 1
            return self._start_recovery_process(error_info)

    def run_recovery(self) -> int:
        """只使用内置源码启动轻量恢复界面。"""
        try:
            self._validate_builtin_source()
            self._activate_source(self.paths.builtin_src, _SOURCE_MODE_RECOVERY)
            self._hide_console()
            recovery_entry = importlib.import_module(
                self.profile.recovery_entry_module
            )
            failure_reason = self._read_failure_reason()
            return int(
                recovery_entry.main(
                    failure_reason=failure_reason,
                    launcher_version=self.version,
                )
                or 0
            )
        except (Exception, SystemExit) as exc:
            self._show_fatal_error(
                '恢复模式启动失败',
                self._format_failure(exc),
            )
            return 1

    def mark_ready(self) -> None:
        """记录业务应用已经越过自动回退边界。"""
        self.ready = True

    def _validate_external_source(self) -> None:
        """确认外部源码目录和项目入口文件存在。"""
        if not self.paths.external_src.is_dir():
            raise FileNotFoundError(
                f'缺少外部源码目录: {self.paths.external_src}'
            )
        missing = [
            relative_path
            for relative_path in self.profile.required_external_files
            if not (self.paths.external_src / relative_path).is_file()
        ]
        if missing:
            raise FileNotFoundError(
                f'外部源码入口不完整: {", ".join(missing)}'
            )

    def _validate_builtin_source(self) -> None:
        """确认内置源码清单与当前启动内核匹配。"""
        BuiltinSourceValidator(
            self.paths.builtin_src,
            self.paths.builtin_manifest,
            self.version,
            self.profile,
        ).validate()

    def _activate_source(self, source_root: Path, mode: str) -> None:
        """只激活选中的一棵业务源码树。"""
        selected = source_root.resolve()
        rejected = {
            self.paths.external_src.resolve(),
            self.paths.builtin_src.resolve(),
        }
        retained: list[str] = []
        for entry in sys.path:
            try:
                entry_path = Path(entry).resolve()
            except (OSError, RuntimeError, ValueError):
                retained.append(entry)
                continue
            if entry_path not in rejected:
                retained.append(entry)

        sys.path[:] = [str(selected), *retained]
        package_names = {
            'one_dragon',
            'one_dragon.launcher',
        }
        for entry_module in (
            self.profile.runtime_entry_module,
            self.profile.recovery_entry_module,
        ):
            module_parts = entry_module.split('.')
            package_names.update(
                '.'.join(module_parts[:index])
                for index in range(1, len(module_parts))
            )
        for package_name in sorted(package_names, key=lambda name: name.count('.')):
            relative_root = Path(*package_name.split('.'))
            package = sys.modules.get(package_name)
            selected_package_root = selected / relative_root
            if package is None or not selected_package_root.is_dir():
                continue
            rejected_package_roots = {
                (self.paths.external_src / relative_root).resolve(),
                (self.paths.builtin_src / relative_root).resolve(),
            }
            package.__path__ = [
                str(selected_package_root),
                *[
                    path
                    for path in getattr(package, '__path__', ())
                    if Path(path).resolve() not in rejected_package_roots
                ],
            ]
        if mode == _SOURCE_MODE_RECOVERY:
            sys.dont_write_bytecode = True
        os.environ[_SOURCE_ROOT_ENV] = str(selected)
        os.environ[_SOURCE_MODE_ENV] = mode

    @staticmethod
    def _clear_source_modules(
        pre_modules: set[str],
        source_root: Path,
    ) -> None:
        """源码更新后清除本轮从外部源码加载的模块。"""
        resolved_root = source_root.resolve()
        for name in set(sys.modules) - pre_modules:
            module: ModuleType | None = sys.modules.get(name)
            module_file = getattr(module, '__file__', None)
            if module_file is None:
                continue
            try:
                is_source_module = Path(module_file).resolve().is_relative_to(
                    resolved_root
                )
            except (OSError, RuntimeError, ValueError):
                is_source_module = False
            if is_source_module:
                del sys.modules[name]

    def _start_recovery_process(self, error_info: str) -> int:
        """记录启动失败原因，并拉起恢复模式进程。"""
        try:
            self.paths.failure_log.parent.mkdir(parents=True, exist_ok=True)
            self.paths.failure_log.write_text(error_info, encoding='utf-8')
            subprocess.Popen(
                [sys.executable, '--runtime-recovery'],
                cwd=self.paths.install_root,
                close_fds=True,
            )
        except Exception:
            fallback_error = (
                f'{error_info}\n\n拉起恢复模式失败:\n'
                f'{traceback.format_exc()}'
            )
            self._show_fatal_error('启动失败', fallback_error)
        return 1

    def _read_failure_reason(self) -> str:
        """读取上一次正常启动失败的原因。"""
        if not self.paths.failure_log.is_file():
            return '外部源码启动失败，未找到详细错误记录。'
        return self.paths.failure_log.read_text(
            encoding='utf-8',
            errors='replace',
        )

    @staticmethod
    def _format_failure(exc: BaseException) -> str:
        """把启动异常格式化成可写入日志的文本。"""
        if isinstance(exc, SystemExit):
            prefix = f'业务入口在 ready 前退出，退出码: {exc.code}\n'
        else:
            prefix = ''
        return prefix + ''.join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )

    @staticmethod
    def _hide_console() -> None:
        """隐藏当前控制台窗口。"""
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)

    def _show_fatal_error(self, title: str, error_info: str) -> None:
        """显示无法继续启动时的错误对话框。"""
        ctypes.windll.user32.MessageBoxW(
            None,
            f'{title}，报错信息如下:\n{error_info}',
            self.profile.application_name,
            0x10,
        )


def _parse_args(
    argv: list[str] | None = None,
    application_name: str = 'Application launcher',
) -> LauncherOptions:
    """解析集成启动器命令行参数。"""
    parser = argparse.ArgumentParser(
        description=application_name,
        add_help=False,
    )
    parser.add_argument('-h', '--help', action='help', help='显示帮助信息')
    parser.add_argument('-v', '--version', action='store_true', help='显示版本号')
    parser.add_argument('-o', '--onedragon', action='store_true', help='一条龙运行')
    parser.add_argument('-c', '--close-game', action='store_true', help='运行后关闭游戏')
    parser.add_argument(
        '-s',
        '--shutdown',
        type=int,
        nargs='?',
        const=60,
        help='运行后关机，可指定延迟秒数，默认60秒',
    )
    parser.add_argument(
        '-i',
        '--instance',
        type=str,
        help='指定运行的账号实例，多个用英文逗号分隔，如：1,2',
    )
    parser.add_argument(
        '--runtime-recovery',
        action='store_true',
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if not args.onedragon and (
        args.close_game or args.shutdown is not None or args.instance
    ):
        parser.error(
            '参数 --close-game, --shutdown, --instance 只能在指定 '
            '--onedragon 时使用'
        )
    return LauncherOptions(
        show_version=bool(args.version),
        onedragon=bool(args.onedragon),
        close_game=bool(args.close_game),
        shutdown=args.shutdown,
        instance=args.instance,
        recovery=bool(args.runtime_recovery),
    )


def main(
    profile: RuntimeLauncherProfile,
    argv: list[str] | None = None,
) -> int:
    """使用具体项目配置运行集成启动器。"""
    paths = RuntimePaths.from_executable(Path(sys.executable))
    options = _parse_args(argv, profile.application_name)
    if options.show_version:
        print(f'{profile.application_name} {__version__}')
        return 0

    if not pyuac.isUserAdmin():
        pyuac.runAsAdmin(sys.argv, wait=False)
        return 0

    supervisor = RuntimeLauncherSupervisor(paths, __version__, profile)
    if options.recovery:
        return supervisor.run_recovery()
    return supervisor.run_normal(options)
