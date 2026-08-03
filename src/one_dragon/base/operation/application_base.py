from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from enum import Enum
from typing import TYPE_CHECKING

from one_dragon.base.config.notify_config import NotifyDetailMode
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_notify import send_application_notify

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext

_app_preheat_executor = ThreadPoolExecutor(thread_name_prefix='od_app_preheat', max_workers=1)


class ApplicationEventId(Enum):

    APPLICATION_START = '应用开始运行'
    APPLICATION_STOP = '应用停止运行'


class Application(Operation):

    def __init__(self, ctx: OneDragonContext, app_id: str,
                 node_max_retry_times: int = 1,
                 op_name: str | None = None,
                 timeout_seconds: float = -1,
                 op_callback: Callable[[OperationResult], None] | None = None,
                 need_check_game_win: bool = True,
                 op_to_enter_game: Operation | None = None,
                 run_record: AppRunRecord | None = None,
                 ) -> None:
        Operation.__init__(
            self,
            ctx,
            node_max_retry_times=node_max_retry_times,
            op_name=op_name,
            timeout_seconds=timeout_seconds,
            op_callback=op_callback,
            need_check_game_win=need_check_game_win,
            op_to_enter_game=op_to_enter_game,
        )

        # 应用唯一标识
        self.app_id: str = app_id

        # 运行记录
        self.run_record: AppRunRecord | None = run_record
        if run_record is None:
            # 部分应用没有运行记录 跳过即可
            with suppress(Exception):
                self.run_record = ctx.run_context.get_run_record(
                    app_id=self.app_id,
                    instance_idx=ctx.current_instance_idx,
                )

    def handle_init(self) -> None:
        """
        运行前初始化
        """
        Operation.handle_init(self)

        if self.run_record is not None:
            self.run_record.check_and_update_status()  # 先判断是否重置记录
            self.run_record.update_status(AppRunRecord.STATUS_RUNNING)

        if self.ctx.run_context.is_app_need_notify(self.app_id):
            send_application_notify(self, None)
            # 清空通知池，根据节点细节通知模式设置图片保留数量
            pool = self.ctx.run_context.notify_pool
            pool.clear()
            detail_mode = self.ctx.notify_config.get_app_detail_mode(self.app_id)
            pool.max_images = 10 if detail_mode == NotifyDetailMode.MERGE.value.value else 1

        self.ctx.dispatch_event(ApplicationEventId.APPLICATION_START.value, self.app_id)

    def execute(self) -> OperationResult:
        """
        执行应用，并确保异常路径也退出 screen scope。
        第三方插件应用执行期间设置 CV 流水线插件上下文，
        使裸名流水线解析优先自身插件目录（同名优先自身插件，其次主仓）。
        """
        self.ctx.screen_loader.enter_scope(self.app_id)
        token = None
        try:
            plugin_name = self._get_current_plugin_name()
            if plugin_name:
                token = self.ctx.cv_service.set_current_plugin(plugin_name)
            return Operation.execute(self)
        finally:
            if token is not None:
                self.ctx.cv_service.reset_current_plugin(token)
            self.ctx.screen_loader.exit_scope()

    def _get_current_plugin_name(self) -> str | None:
        """
        获取当前应用所属第三方插件的插件名（插件目录名）。
        内置应用返回 None，表示主仓上下文。
        """
        info = self.ctx.factory_manager.get_plugin_info(self.app_id)
        if info is not None and info.is_third_party and info.plugin_dir is not None:
            return info.plugin_dir.name
        return None

    def after_operation_done(self, result: OperationResult) -> None:
        """
        停止后的处理
        :return:
        """
        Operation.after_operation_done(self, result)

        self._update_record_after_stop(result)

        if self.ctx.run_context.is_app_need_notify(self.app_id):
            send_application_notify(self, result.success)
            # 清空通知池
            self.ctx.run_context.notify_pool.clear()

        self.ctx.dispatch_event(ApplicationEventId.APPLICATION_STOP.value, self.app_id)

    def _update_record_after_stop(self, result: OperationResult):
        """
        应用停止后的对运行记录的更新
        :param result: 运行结果
        :return:
        """
        if self.run_record is not None:
            if result.success:
                self.run_record.update_status(AppRunRecord.STATUS_SUCCESS)
            else:
                self.run_record.update_status(AppRunRecord.STATUS_FAIL)

    @property
    def current_execution_desc(self) -> str:
        """
        当前运行的描述 用于UI展示
        :return:
        """
        return ''

    @property
    def next_execution_desc(self) -> str:
        """
        下一步运行的描述 用于UI展示
        :return:
        """
        return ''

    @staticmethod
    def get_preheat_executor() -> ThreadPoolExecutor:
        return _app_preheat_executor

    @staticmethod
    def after_app_shutdown() -> None:
        """
        整个脚本运行结束后的清理
        """
        _app_preheat_executor.shutdown(wait=False, cancel_futures=True)
