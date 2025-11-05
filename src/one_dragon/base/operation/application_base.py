from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

from cv2.typing import MatLike

from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_notify import application_notify

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext

_app_preheat_executor = ThreadPoolExecutor(thread_name_prefix='od_app_preheat', max_workers=1)


class ApplicationEventId(Enum):

    APPLICATION_START: str = '应用开始运行'
    APPLICATION_STOP: str = '应用停止运行'


class Application(Operation):

    def __init__(self, ctx: OneDragonContext, app_id: str,
                 node_max_retry_times: int = 1,
                 op_name: str = None,
                 timeout_seconds: float = -1,
                 op_callback: Optional[Callable[[OperationResult], None]] = None,
                 need_check_game_win: bool = True,
                 op_to_enter_game: Optional[Operation] = None,
                 run_record: Optional[AppRunRecord] = None,
                 need_notify: bool = False,
                 ):
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

        self.app_id: str = app_id
        """应用唯一标识"""

        self.run_record: Optional[AppRunRecord] = run_record
        if run_record is None:
            try:
                self.run_record = ctx.run_context.get_run_record(
                    app_id=self.app_id,
                    instance_idx=ctx.current_instance_idx,
                )
            except Exception:  # 部分应用没有运行记录 跳过即可
                pass
        """运行记录"""

        self.need_notify: bool = need_notify  # 应用运行前后发送通知

    def _init_before_execute(self) -> None:
        Operation._init_before_execute(self)

    def handle_init(self) -> None:
        """
        运行前初始化
        """
        Operation.handle_init(self)
        if self.run_record is not None:
            self.run_record.check_and_update_status()  # 先判断是否重置记录
            self.run_record.update_status(AppRunRecord.STATUS_RUNNING)
        if self.need_notify:
            application_notify(self, None)

        self.ctx.dispatch_event(ApplicationEventId.APPLICATION_START.value, self.app_id)

    def after_operation_done(self, result: OperationResult):
        """
        停止后的处理
        :return:
        """
        Operation.after_operation_done(self, result)
        self._update_record_after_stop(result)

        if self.need_notify:
            application_notify(self, result.success)

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
