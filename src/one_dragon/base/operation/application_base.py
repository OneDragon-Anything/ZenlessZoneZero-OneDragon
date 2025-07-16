from concurrent.futures import ThreadPoolExecutor

from enum import Enum
from typing import Optional, Callable
from io import BytesIO

from one_dragon.base.notify.push import Push
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.utils.i18_utils import gt

_app_preheat_executor = ThreadPoolExecutor(thread_name_prefix='od_app_preheat', max_workers=1)
_notify_executor = ThreadPoolExecutor(thread_name_prefix='od_app_notify', max_workers=1)


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
                 init_context_before_start: bool = True,
                 stop_context_after_stop: bool = True,
                 run_record: Optional[AppRunRecord] = None,
                 need_ocr: bool = True,
                 retry_in_od: bool = False,
                 need_notify: bool = False
                 ):
        super().__init__(ctx, node_max_retry_times=node_max_retry_times, op_name=op_name,
                         timeout_seconds=timeout_seconds,
                         op_callback=op_callback,
                         need_check_game_win=need_check_game_win,
                         op_to_enter_game=op_to_enter_game)

        self.app_id: str = app_id
        """应用唯一标识"""

        self.run_record: Optional[AppRunRecord] = run_record
        """运行记录"""

        self.init_context_before_start: bool = init_context_before_start
        """运行前是否初始化上下文 一条龙只有第一个应用需要"""

        self.stop_context_after_stop: bool = stop_context_after_stop
        """运行后是否停止上下文 一条龙只有最后一个应用需要"""

        self.need_ocr: bool = need_ocr
        """需要OCR"""

        self._retry_in_od: bool = retry_in_od  # 在一条龙中进行重试

        self.need_notify: bool = need_notify  # 节点运行结束后发送通知

        self.notify_screenshot: Optional[BytesIO] = None  # 发送通知的截图

    def _init_before_execute(self) -> None:
        Operation._init_before_execute(self)
        if self.run_record is not None:
            self.run_record.update_status(AppRunRecord.STATUS_RUNNING)
        if self.need_notify:
            self.notify(None)

        self.init_for_application()
        self.ctx.start_running()
        self.ctx.dispatch_event(ApplicationEventId.APPLICATION_START.value, self.app_id)

    def handle_resume(self) -> None:
        """
        恢复运行后的处理 由子类实现
        :return:
        """
        pass

    def after_operation_done(self, result: OperationResult):
        """
        停止后的处理
        :return:
        """
        Operation.after_operation_done(self, result)
        self._update_record_after_stop(result)
        if self.stop_context_after_stop:
            self.ctx.stop_running()
        self.ctx.dispatch_event(ApplicationEventId.APPLICATION_STOP.value, self.app_id)
        if self.need_notify:
            self.notify(result.success)

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

    def notify(self, is_success: Optional[bool] = True) -> None:
        """
        发送通知 应用开始或停止时调用 会在调用的时候截图
        :return:
        """
        if not hasattr(self.ctx, 'notify_config'):
            return
        if not getattr(self.ctx.notify_config, 'enable_notify', False):
            return
        if not getattr(self.ctx.notify_config, 'enable_before_notify', False) and is_success is None:
            return

        app_id = getattr(self, 'app_id', None)
        app_name = getattr(self, 'op_name', None)

        if not getattr(self.ctx.notify_config, app_id, False):
            return

        if is_success is True:
            status = gt('成功')
            image_source = self.notify_screenshot
        elif is_success is False:
            status = gt('失败')
            image_source = self.save_screenshot_bytes()
        elif is_success is None:
            status = gt('开始')
            image_source = None

        send_image = getattr(self.ctx.push_config, 'send_image', False)
        image = image_source if send_image else None

        message = f"{gt('任务「')}{app_name}{gt('」运行')}{status}\n"

        pusher = Push(self.ctx)
        _notify_executor.submit(pusher.send, message, image)

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

    def init_for_application(self) -> bool:
        """
        初始化
        """
        if self.need_ocr:
            self.ctx.init_ocr()
        return True
