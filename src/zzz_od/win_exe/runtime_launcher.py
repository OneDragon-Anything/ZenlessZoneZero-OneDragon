import ctypes
import importlib
import os
import sys

from one_dragon.launcher.exe_launcher import ExeLauncher
from one_dragon.version import __version__

# src/ 目录检查 — 仅 PyInstaller 打包环境下检查
if getattr(sys, 'frozen', False):
    _SRC_DIR = os.path.join(os.path.dirname(sys.executable), "src")
    if not os.path.isdir(_SRC_DIR):
        print(f"错误: 缺少 src 目录 ({_SRC_DIR})，请重新解压完整的 RuntimeLauncher 压缩包。")
        input("按 Enter 退出...")
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

        env_config = EnvConfig()
        git_service = GitService(ProjectConfig(), env_config)
        first_run = not git_service.check_repo_exists()

        if not first_run and not env_config.auto_update:
            print("未开启代码自动更新，跳过")
            return

        print("首次运行，正在同步代码仓库..." if first_run else "正在检查代码更新...")
        success, msg = git_service.fetch_latest_code(
            progress_callback=lambda p, m: print(f"  [{p:.0%}] {m}")
        )

        if success:
            print("代码同步完成" if first_run else "代码已是最新")
            # 清除同步过程中加载的模块，避免主程序使用旧版本
            for name in set(sys.modules) - pre_modules:
                del sys.modules[name]
            importlib.invalidate_caches()
        elif first_run:
            print(f"代码同步失败: {msg}")
            sys.exit(1)
        else:
            print(f"代码更新失败: {msg}")

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
