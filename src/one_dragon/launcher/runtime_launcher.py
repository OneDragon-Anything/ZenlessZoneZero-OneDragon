import ctypes
import importlib
import sys

from one_dragon.launcher.exe_launcher import ExeLauncher


class RuntimeLauncher(ExeLauncher):
    """Runtime模式启动器基类

    用于将 Python 运行时嵌入到应用目录中的启动器。
    提供代码同步、控制台隐藏等通用功能。
    """

    def __init__(self, description: str, version: str):
        ExeLauncher.__init__(self, description, version)

    def _sync_code(self) -> None:
        """同步代码：首次运行时克隆，后续运行时自动更新"""
        pre_modules = set(sys.modules)

        from one_dragon.envs.env_config import EnvConfig
        from one_dragon.envs.git_service import GitService
        from one_dragon.envs.project_config import ProjectConfig
        from one_dragon.utils.log_utils import log

        env_config = EnvConfig()
        git_service = GitService(ProjectConfig(), env_config)
        first_run = not git_service.check_repo_exists()

        if not first_run and not env_config.auto_update:
            log.info("未开启代码自动更新，跳过")
            return

        log.info("首次运行，正在同步代码仓库..." if first_run else "正在检查代码更新...")
        success, msg = git_service.fetch_latest_code()

        if success:
            log.info("代码同步完成" if first_run else "代码已是最新")
            # 清除同步过程中加载的模块，避免主程序使用旧版本
            for name in set(sys.modules) - pre_modules:
                del sys.modules[name]
            importlib.invalidate_caches()
        elif first_run:
            log.info(f"代码同步失败: {msg}")
            sys.exit(1)
        else:
            log.info(f"代码更新失败: {msg}")

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
            "OneDragon RuntimeLauncher",
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
