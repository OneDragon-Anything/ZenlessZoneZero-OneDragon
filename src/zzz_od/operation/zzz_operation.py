from typing import Optional, Callable

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
from zzz_od.telemetry.auto_telemetry import TelemetryOperationMixin


class ZOperation(Operation, TelemetryOperationMixin):

    def __init__(self, ctx: ZContext,
                 node_max_retry_times: int = 3,
                 op_name: str = '',
                 timeout_seconds: float = -1,
                 op_callback: Optional[Callable[[OperationResult], None]] = None,
                 need_check_game_win: bool = True
                 ):
        self.ctx: ZContext = ctx
        op_to_enter_game = OpenAndEnterGame(ctx)
        Operation.__init__(self,
                           ctx=ctx,
                           node_max_retry_times=node_max_retry_times,
                           op_name=op_name,
                           timeout_seconds=timeout_seconds,
                           op_callback=op_callback,
                           need_check_game_win=need_check_game_win,
                           op_to_enter_game=op_to_enter_game)

        self._telemetry_start_time = None
        self._telemetry_operation_name = self.__class__.__name__

    def execute(self) -> OperationResult:

        telemetry = getattr(self.ctx, 'telemetry', None)
        if not telemetry:
            return super().execute()

        import time

        # 记录操作开始
        self._telemetry_start_time = time.time()
        operation_name = self._telemetry_operation_name

        try:
            # 添加面包屑
            telemetry.add_breadcrumb(
                f"开始执行操作: {operation_name}",
                "operation",
                "info",
                {
                    'operation_class': self.__class__.__name__,
                    'operation_name': getattr(self, 'op_name', ''),
                    'timeout_seconds': getattr(self, 'timeout_seconds', -1)
                }
            )

            # 跟踪操作开始
            telemetry.track_operation_start(operation_name, {
                'operation_class': self.__class__.__name__,
                'operation_name': getattr(self, 'op_name', ''),
                'need_check_game_win': getattr(self, 'need_check_game_win', True)
            })

            # 执行原始操作
            result = super().execute()

            # 计算执行时间
            duration = time.time() - self._telemetry_start_time

            # 记录操作结果
            success = result.success if result else False

            # 添加结果面包屑
            telemetry.add_breadcrumb(
                f"操作完成: {operation_name} ({'成功' if success else '失败'})",
                "operation",
                "info" if success else "error",
                {
                    'success': success,
                    'duration': duration,
                    'status': result.status if result else 'unknown'
                }
            )

            # 跟踪操作结束
            telemetry.track_operation_end(operation_name, success, duration, {
                'status': result.status if result else 'unknown',
                'data': result.data if result and hasattr(result, 'data') else None
            })

            # 跟踪操作时间性能
            telemetry.track_operation_time(operation_name, duration, success, {
                'operation_class': self.__class__.__name__,
                'status': result.status if result else 'unknown'
            })

            return result

        except Exception as e:
            # 计算执行时间
            duration = time.time() - self._telemetry_start_time if self._telemetry_start_time else 0

            # 记录错误
            telemetry.capture_error(e, {
                'operation_name': operation_name,
                'operation_class': self.__class__.__name__,
                'duration': duration,
                'context': 'operation_execution'
            })

            # 添加错误面包屑
            telemetry.add_breadcrumb(
                f"操作异常: {operation_name} - {str(e)}",
                "operation",
                "error",
                {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'duration': duration
                }
            )

            # 跟踪操作结束（失败）
            telemetry.track_operation_end(operation_name, False, duration, {
                'error_type': type(e).__name__,
                'error_message': str(e)
            })

            # 重新抛出异常
            raise
