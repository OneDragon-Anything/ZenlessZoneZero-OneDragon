import ctypes
import importlib
import sys
from pathlib import Path

from one_dragon.launcher.exe_launcher import ExeLauncher
from one_dragon.version import __version__

# src/ 目录检查
_SRC_DIR = Path(sys.executable).parent / "src"
if not _SRC_DIR.is_dir():
    ctypes.windll.user32.MessageBoxW(
        None,
        f"缺少 src 目录：\n{_SRC_DIR}\n\n请重新解压完整的 WithRuntime 压缩包。",
        "OneDragon RuntimeLauncher",
        0x10,  # MB_ICONERROR
    )
    sys.exit(1)


class ZLauncher(ExeLauncher):
    """绝区零启动器"""

    def __init__(self):
        ExeLauncher.__init__(self, "绝区零 一条龙 启动器", __version__)

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

    def run_onedragon_mode(self, launch_args: list[str]) -> None:
        self._sync_code()
        from zzz_od.application.zzz_application_launcher import main
        main(launch_args)

    def run_gui_mode(self) -> None:
        self._sync_code()

        # 隐藏控制台窗口，避免 GUI 模式下出现黑窗口
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE

        from zzz_od.gui.app import main
        main()


if __name__ == '__main__':
    launcher = ZLauncher()
    launcher.run()
