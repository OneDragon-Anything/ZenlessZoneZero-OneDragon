import argparse
import sys
from typing import List
from one_dragon.launcher.launcher_base import LauncherBase


class ExeLauncher(LauncherBase):
    """EXE启动器基类"""

    def __init__(self, description: str, version: str):
        LauncherBase.__init__(self, description)
        self.version = version

    def add_custom_arguments(self, parser: argparse.ArgumentParser) -> None:
        """添加自定义参数"""
        parser.add_argument("-v", "--version", action="store_true", help="显示版本号")
        parser.add_argument("-o", "--onedragon", action="store_true", help="一条龙运行")

    def show_version(self) -> None:
        """显示版本信息"""
        print(f"{self.description} {self.version}")
        sys.exit(0)

    def build_launch_args(self, args) -> List[str]:
        """构建启动参数列表"""
        launch_args = []
        if args.instance:
            launch_args.extend(["--instance", args.instance])
        if args.app:
            launch_args.extend(["--app", args.app])
        if args.close_game:
            launch_args.append("--close-game")
        if args.shutdown:
            launch_args.extend(["--shutdown", str(args.shutdown)])
        return launch_args

    def run_onedragon_mode(self, launch_args) -> None:
        """运行一条龙模式，子类实现"""
        pass

    def run_gui_mode(self) -> None:
        """运行GUI模式，子类实现"""
        pass

    def main(self, args) -> None:
        """执行主要逻辑"""
        if args.version:
            self.show_version()

        if not args.onedragon and (args.close_game or args.shutdown or args.instance or args.app):
            print("错误：参数 --close-game, --shutdown, --instance, --app 只能在指定 --onedragon 时使用")
            sys.exit(1)

        if args.onedragon:
            launch_args = self.build_launch_args(args)
            self.run_onedragon_mode(launch_args)
        else:
            self.run_gui_mode()
