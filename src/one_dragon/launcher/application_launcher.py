import sys

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.operation.one_dragon_finalizer import (
    AfterDoneRequest,
    execute_after_done,
)
from one_dragon.launcher.launcher_base import LauncherBase
from one_dragon.utils.log_utils import log


class ApplicationLauncher(LauncherBase):
    """一条龙应用启动器基类"""

    def __init__(self):
        LauncherBase.__init__(self, "一条龙 应用启动器")
        self.ctx: OneDragonContext | None = None

    @staticmethod
    def parse_comma_separated_values(value: str, convert_func=None) -> list:
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

    def create_context(self) -> OneDragonContext:
        """创建上下文，子类实现"""
        pass

    def set_temp_instance_config(self, instance_indices: list[int]) -> bool:
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

    def init_context(self) -> None:
        """初始化上下文"""
        self.ctx = self.create_context()
        self.ctx.init_async()

    def process_arguments(self, args) -> None:
        """处理命令行参数"""
        if args.instance:
            instance_indices = self.parse_comma_separated_values(args.instance, int)
            if not self.set_temp_instance_config(instance_indices):
                log.error("未找到有效的实例")
                self.ctx.after_app_shutdown()
                sys.exit(1)

    def run_application(self, args) -> None:
        """运行应用"""
        try:
            # 执行一条龙应用
            run_result = self.ctx.run_context.run_application(
                app_id=application_const.ONE_DRAGON_APP_ID,
                instance_idx=self.ctx.current_instance_idx,
                group_id=application_const.DEFAULT_GROUP_ID,
            )
            execute_after_done(
                self.ctx,
                run_result,
                AfterDoneRequest(
                    close_game=args.close_game,
                    shutdown_seconds=args.shutdown,
                ),
            )
        finally:
            self.ctx.after_app_shutdown()

    def main(self, args) -> None:
        """执行主要逻辑"""
        self.init_context()
        self.process_arguments(args)
        self.run_application(args)
