import sys
from typing import List

from one_dragon.utils import cmd_utils
from one_dragon.utils.log_utils import log
from one_dragon.launcher.launcher_base import LauncherBase


class ApplicationLauncher(LauncherBase):
    """一条龙应用启动器基类"""

    def __init__(self):
        LauncherBase.__init__(self, "一条龙 应用启动器")
        self.ctx = None

    @staticmethod
    def parse_comma_separated_values(value: str, convert_func=None) -> List:
        """解析逗号分隔的值"""
        if not value:
            return []
        items = [item.strip() for item in value.split(',') if item.strip()]

        if convert_func is None:
            return items

        try:
            return [convert_func(item) for item in items]
        except ValueError:
            log.error(f"无效的参数值: {value}")
            return []

    def create_context(self):
        """创建上下文，子类实现"""
        pass

    def get_app_class(self):
        """获取应用类，子类实现"""
        pass

    def set_temp_instance_config(self, instance_indices: List[int]) -> bool:
        """设置临时实例配置"""
        if not instance_indices:
            return False

        self.ctx.one_dragon_config.set_temp_instance_indices(instance_indices)

        # 验证有效实例
        valid_instances = [idx for idx in instance_indices
                           if any(instance.idx == idx for instance in self.ctx.one_dragon_config.instance_list)]

        if valid_instances:
            log.info(f"指定运行实例: {valid_instances}")
            return True
        else:
            self.ctx.one_dragon_config.clear_temp_instance_indices()
            return False

    def set_temp_app_config(self, app_names: List[str]) -> bool:
        """设置临时应用配置"""
        if not app_names:
            return False

        # 获取所有可用应用
        app_class = self.get_app_class()
        temp_app = app_class(self.ctx)
        all_apps = temp_app.get_app_list()

        # 构建应用名称到ID的映射
        app_name_to_id = {}
        for app in all_apps:
            # 使用应用ID作为名称
            app_name_to_id[app.app_id] = app.app_id
            # 如果有中文名称，也加入映射
            if hasattr(app, 'op_name') and app.op_name:
                app_name_to_id[app.op_name] = app.app_id

        # 查找匹配的应用ID
        valid_app_ids = []
        for app_name in app_names:
            if app_name in app_name_to_id:
                valid_app_ids.append(app_name_to_id[app_name])
            else:
                log.warning(f"未找到应用: {app_name}")

        if valid_app_ids:
            self.ctx.one_dragon_app_config.set_temp_app_run_list(valid_app_ids)
            log.info(f"指定运行应用: {valid_app_ids}")
            return True
        else:
            return False

    def init_context(self) -> None:
        """初始化上下文"""
        self.ctx = self.create_context()
        self.ctx.init_by_config()

        # 异步加载OCR
        self.ctx.async_init_ocr()

    def process_arguments(self, args) -> None:
        """处理命令行参数"""
        if args.instance:
            instance_indices = self.parse_comma_separated_values(args.instance, int)
            if not self.set_temp_instance_config(instance_indices):
                log.error("未找到有效的实例")
                self.ctx.after_app_shutdown()
                sys.exit(1)

        if args.app:
            app_names = self.parse_comma_separated_values(args.app)
            if not self.set_temp_app_config(app_names):
                log.error("未找到有效的应用")
                self.ctx.after_app_shutdown()
                sys.exit(1)

    def run_application(self, args) -> None:
        """运行应用"""
        try:
            # 执行一条龙应用
            app_class = self.get_app_class()
            app = app_class(self.ctx)
            app.execute()

            # 运行后操作
            if args.close_game:
                self.ctx.controller.close_game()
            if args.shutdown:
                cmd_utils.shutdown_sys(args.shutdown)
        finally:
            self.ctx.after_app_shutdown()

    def main(self, args) -> None:
        """执行主要逻辑"""
        self.init_context()
        self.process_arguments(args)
        self.run_application(args)
