import argparse


class LauncherBase:
    """基础启动器类"""

    def __init__(self, description: str = "应用启动器"):
        self.description = description
        self.parser = None
        self.args = None

    def setup_parser(self) -> None:
        """创建参数解析器"""
        self.parser = argparse.ArgumentParser(description=self.description, add_help=False)
        self.parser.add_argument("-h", "--help", action="help", help="显示帮助信息")
        self.add_custom_arguments(self.parser)
        self.add_common_arguments(self.parser)
        self.args = self.parser.parse_args()

    def add_custom_arguments(self, parser: argparse.ArgumentParser) -> None:
        """添加自定义参数，子类实现"""
        pass

    def add_common_arguments(self, parser: argparse.ArgumentParser) -> None:
        """添加通用参数"""
        parser.add_argument("-c", "--close-game", action="store_true", help="运行后关闭游戏")
        parser.add_argument("-s", "--shutdown", type=int, nargs='?', const=60, help="运行后关机，可指定延迟秒数，默认60秒")
        parser.add_argument("-i", "--instance", type=str, help="指定运行的账号实例，多个用英文逗号分隔，如：1,2")
        parser.add_argument("-a", "--app", type=str, help="指定运行的应用，多个用英文逗号分隔")

    def run(self) -> None:
        """运行启动器"""
        self.setup_parser()
        self.main(self.args)

    def main(self, args) -> None:
        """执行主要逻辑，子类实现"""
        pass
