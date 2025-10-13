import time
from typing import Callable, Optional

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
from zzz_od.telemetry.auto_telemetry import (
    TelemetryApplicationMixin,
    auto_telemetry_method,
)


class ZApplication(Application, TelemetryApplicationMixin):

    def __init__(self, ctx: ZContext, app_id: str,
                 node_max_retry_times: int = 1,
                 op_name: str = None,
                 timeout_seconds: float = -1,
                 op_callback: Optional[Callable[[OperationResult], None]] = None,
                 need_check_game_win: bool = True,
                 op_to_enter_game: Optional[Operation] = None,
                 run_record: Optional[AppRunRecord] = None,
                 need_notify: bool = False
                 ):
        self.ctx: ZContext = ctx
        if op_to_enter_game is None:
            op_to_enter_game = OpenAndEnterGame(ctx)
        Application.__init__(
            self,
            ctx=ctx,
            app_id=app_id,
            node_max_retry_times=node_max_retry_times,
            op_name=op_name,
            timeout_seconds=timeout_seconds,
            op_callback=op_callback,
            need_check_game_win=need_check_game_win,
            op_to_enter_game=op_to_enter_game,
            run_record=run_record,
            need_notify=need_notify,
        )

        self._telemetry_start_time = None
        self._telemetry_end_time = None

    @auto_telemetry_method("application_resume")
    def handle_resume(self) -> None:
        self.ctx.controller.active_window()
        Application.handle_resume(self)

    def execute(self) -> OperationResult:
        # 记录开始时间
        start_time = time.time()

        # 手动触发应用执行事件
        telemetry = getattr(self, '_get_telemetry', lambda: None)()
        if telemetry:
            try:
                # 记录应用执行开始
                telemetry.capture_event('application_execute', {
                    'app_id': getattr(self, 'app_id', 'unknown'),
                    'app_class': self.__class__.__name__,
                    'op_name': getattr(self, 'op_name', 'unknown'),
                    'action': 'start'
                })
            except Exception:
                pass

        # 执行原始方法
        result = super().execute()

        # 计算执行时长
        duration = time.time() - start_time

        # 记录应用执行结束（包含执行时长）
        if telemetry:
            try:
                telemetry.capture_event('application_execute', {
                    'app_id': getattr(self, 'app_id', 'unknown'),
                    'app_class': self.__class__.__name__,
                    'op_name': getattr(self, 'op_name', 'unknown'),
                    'action': 'end',
                    'success': result.success if result else False,
                    'status': result.status if result else 'unknown',
                    'duration_seconds': round(duration, 2),
                    'duration_minutes': round(duration / 60, 2),
                    'event_category': 'app_performance'
                })
            except Exception:
                pass

        return result

    @auto_telemetry_method("application_stop")
    def stop(self) -> None:
        super().stop()
