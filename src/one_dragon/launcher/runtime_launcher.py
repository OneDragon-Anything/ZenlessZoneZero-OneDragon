import ctypes
import importlib
import sys
from pathlib import Path

from one_dragon.launcher.exe_launcher import ExeLauncher


class RuntimeLauncher(ExeLauncher):
    """集成启动器基类

    将 Python 运行时嵌入到应用目录中的启动器。
    提供代码同步、控制台隐藏等通用功能。
    """

    def __init__(self, description: str, version: str) -> None:
        ExeLauncher.__init__(self, description, version)

    def _sync_code(self) -> None:
        """同步代码：首次运行时克隆，后续运行时自动更新"""
        pre_modules = set(sys.modules)

        from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
        from one_dragon.envs.git_service import GitSyncStatus
        from one_dragon.utils.i18_utils import gt
        from one_dragon.utils.log_utils import log
        from one_dragon.version import __version__
        log.info(f"OneDragon 集成启动器 {__version__}")

        env_context = OneDragonEnvContext()
        env_config = env_context.env_config
        git_service = env_context.git_service
        first_run = git_service.is_initial_checkout_pending()

        if not first_run and not env_config.auto_update_code:
            log.info(gt('未开启代码自动更新，跳过'))
            return

        last_progress_printed = False

        def log_progress(_progress: float, message: str) -> None:
            nonlocal last_progress_printed
            refresh = '%' in message and 'done' not in message.lower()
            if refresh:
                print(message, end='\r', flush=True)
                last_progress_printed = True
                return

            if last_progress_printed:
                print(' ' * 120, end='\r', flush=True)
                last_progress_printed = False

            log.info(message)

        log.info(gt('首次运行，正在同步代码仓库...') if first_run else gt('正在检查代码更新...'))
        initial_tag = __version__ if first_run and __version__.startswith('v') and __version__ != 'v0.0.0' else None
        status, message = git_service.fetch_latest_code(log_progress, initial_tag=initial_tag)

        if status is GitSyncStatus.SUCCESS:
            log.info(message)
            # 清除同步过程中加载的源码模块，避免主程序使用旧版本
            self._clear_src_modules(pre_modules)
            importlib.invalidate_caches()
        elif status is GitSyncStatus.UP_TO_DATE:
            log.info(message)
        elif status is GitSyncStatus.RUNTIME_INCOMPATIBLE:
            log.warning(f'{message}, {gt("继续使用当前版本")}')
        elif status is GitSyncStatus.BUILTIN_TAG_UNAVAILABLE:
            log.warning(f'{message}, {gt("继续使用内置版本")}')
        elif status is GitSyncStatus.REMOTE_UNAVAILABLE:
            if first_run:
                log.error(f'{message}, {gt("请稍后重试或切换代码源")}')
                sys.exit(1)
                return
            log.warning(f'{message}, {gt("继续使用当前版本")}')
        elif status is GitSyncStatus.LOCAL_CHANGES:
            log.warning(f'{message}, {gt("继续使用当前版本")}')
        elif status is GitSyncStatus.LOCAL_UPDATE_FAILED:
            log.error(f'{message}, {gt("请重新运行启动器；仍然失败时请重新安装")}')
            sys.exit(1)
        else:
            log.error(f'{message}, {gt("请查看日志后重试")}')
            sys.exit(1)

    @staticmethod
    def _clear_src_modules(pre_modules: set[str]) -> None:
        """清除同步期间加载的源码模块，不清除运行时和第三方模块。"""
        src_dir = (Path(sys.executable).parent / 'src').resolve()
        if not src_dir.is_dir():
            return

        for name in set(sys.modules) - pre_modules:
            module = sys.modules.get(name)
            module_file = getattr(module, '__file__', None)
            if module_file is None or not Path(module_file).resolve().is_relative_to(src_dir):
                continue

            del sys.modules[name]

    @staticmethod
    def _hide_console() -> None:
        """隐藏控制台窗口，用于 GUI 模式"""
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE

    @staticmethod
    def _show_fatal_error(error_info: str) -> None:
        """显示致命错误对话框并退出"""
        ctypes.windll.user32.MessageBoxW(
            None,
            f"启动失败，报错信息如下:\n{error_info}",
            "OneDragon 集成启动器",
            0x10,  # MB_ICONERROR
        )
        sys.exit(1)

    def run_onedragon_mode(self, launch_args: list[str]) -> None:
        try:
            self._sync_code()
            self._do_run_onedragon(launch_args)
        except Exception:
            import traceback
            self._show_fatal_error(traceback.format_exc())

    def run_gui_mode(self) -> None:
        try:
            self._sync_code()
            self._hide_console()
            self._do_run_gui()
        except Exception:
            import traceback
            self._show_fatal_error(traceback.format_exc())

    def _do_run_onedragon(self, launch_args: list[str]) -> None:
        """运行一条龙模式，子类实现"""
        pass

    def _do_run_gui(self) -> None:
        """运行GUI模式，子类实现"""
        pass
