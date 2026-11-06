import os
import sys
import time

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

    @staticmethod
    def _consume_single_app_flag() -> str | None:
        """读取并删除一次性单应用标志文件（工作目录 .single_app_run，内容为 app_id）。

        用途：计划任务等固定命令行的提权场景无法追加 -a 参数，预先放置标志文件
        即可让本次启动进入单应用模式。读取后立即删除，保证一次性语义，不影响
        后续正常启动。文件缺失、为空或读取异常都返回 None（走默认全链）。
        """
        flag_path = os.path.join(os.getcwd(), '.single_app_run')
        try:
            if not os.path.isfile(flag_path):
                return None
            with open(flag_path, encoding='utf-8-sig') as f:
                app_id = f.read().strip()
            os.remove(flag_path)
            if app_id:
                log.info('检测到一次性单应用标志文件: %s', app_id)
                return app_id
        except Exception:
            log.error('读取单应用标志文件失败', exc_info=True)
        return None

    def get_target_app_id(self, args) -> str:
        """根据参数获取要运行的应用ID，-a 指定单应用时校验其已注册"""
        app_id = getattr(args, 'app', None) or self._consume_single_app_flag()
        if not app_id:
            return application_const.ONE_DRAGON_APP_ID

        run_context = self.ctx.run_context
        if not run_context.is_app_registered(app_id):
            registered = sorted(getattr(run_context, '_application_factory_map', {}).keys())
            log.error("应用 %s 未注册。可用应用: %s", app_id, ', '.join(registered))
            self.ctx.after_app_shutdown()
            sys.exit(1)

        log.info("单应用运行模式: %s", app_id)
        return app_id

    def wait_context_ready(self, timeout: float = 180.0) -> None:
        """等待异步初始化完成（init_async 在线程池执行 init，含应用注册与 OCR）。

        直跑模式（-a 单应用）会在启动后立即校验应用注册，GUI 模式下初始化早已完成，
        此处补齐时序：轮询 ready_for_application，超时则带警告继续。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if getattr(self.ctx, 'ready_for_application', False):
                log.info('上下文初始化完成')
                return
            time.sleep(0.5)
        log.warning('等待上下文初始化超时（%s 秒），继续尝试运行', timeout)

    def run_application(self, args) -> None:
        """运行应用"""
        try:
            # 执行一条龙应用（-a 指定时只运行该应用）
            self.wait_context_ready()
            run_result = self.ctx.run_context.run_application(
                app_id=self.get_target_app_id(args),
                instance_idx=self.ctx.current_instance_idx,
                group_id=application_const.DEFAULT_GROUP_ID,
            )
            execute_after_done(
                self.ctx,
                run_result,
                AfterDoneRequest(
                    close_game=args.close_game,
                    shutdown_seconds=args.shutdown,
                    hibernate=args.hibernate,
                    sleep=args.sleep,
                ),
            )
        finally:
            self.ctx.after_app_shutdown()

    def main(self, args) -> None:
        """执行主要逻辑"""
        self.init_context()
        self.process_arguments(args)
        self.run_application(args)
