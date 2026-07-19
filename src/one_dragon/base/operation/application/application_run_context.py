from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar

from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.base.operation.notify_pool import NotifyPool
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.utils import thread_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.application.application_config import (
        ApplicationConfig,
    )
    from one_dragon.base.operation.application.application_factory import (
        ApplicationFactory,
    )
    from one_dragon.base.operation.application_base import Application
    from one_dragon.base.operation.application_run_record import AppRunRecord
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class RunFinishReason(StrEnum):
    """应用结束原因。"""

    COMPLETED = "COMPLETED"  # 正常完成
    STOPPED = "STOPPED"  # 用户、流程或程序停止
    FAILED = "FAILED"  # 执行失败或运行异常
    NOT_STARTED = "NOT_STARTED"  # 初始化失败、超时或未取得运行权


@dataclass(slots=True)
class ApplicationRunResult:
    """应用运行结果。"""

    finish_reason: RunFinishReason
    app_id: str
    instance_idx: int | None
    group_id: str | None


class ApplicationRunContextStateEnum(StrEnum):
    """应用运行上下文状态枚举。"""

    STOP = "STOP"  # 停止状态
    RUNNING = "RUNNING"  # 正在运行状态
    PAUSE = "PAUSE"  # 暂停状态


class ApplicationRunContextStateEventEnum(StrEnum):
    """应用运行上下文状态事件枚举。"""

    START = "start"  # 开始运行事件
    PAUSE = "pause"  # 暂停运行事件
    RESUME = "resume"  # 恢复运行事件
    STOP = "stop"  # 停止运行事件


CONFIG = TypeVar('CONFIG', bound="ApplicationConfig")
RECORD = TypeVar('RECORD', bound="AppRunRecord")

class ApplicationRunContext:
    """应用运行上下文管理类。

    负责管理应用的生命周期、状态转换、实例创建和运行调度。
    提供应用注册、状态查询、异步运行等功能，并维护当前运行的应用信息。

    Attributes:
        _application_factory_map: 应用工厂映射表，存储app_id到工厂的对应关系
        _run_state: 当前运行状态
        _executor: 线程池执行器，用于异步运行应用
        current_app_id: 当前运行的应用ID
        current_instance_idx: 当前运行的实例下标
        current_group_id: 当前运行的组ID
    """

    def __init__(
        self,
        ctx: OneDragonContext
    ):
        """
        初始化应用运行上下文。

        创建空的工厂映射表、设置初始状态为停止、初始化线程池和事件总线。
        """
        self.ctx: OneDragonContext = ctx
        self._application_factory_map: dict[str, ApplicationFactory] = {}
        self._run_state: ApplicationRunContextStateEnum = (
            ApplicationRunContextStateEnum.STOP
        )
        self._executor = ThreadPoolExecutor(
            thread_name_prefix="one_dragon_app_run_context", max_workers=1
        )
        self.event_bus: ContextEventBus = ContextEventBus()
        self.default_group_apps: list = []  # 默认应用组的应用ID列表

        # 当前运行的应用
        self.current_app_id: str | None = None
        self.current_instance_idx: int | None = None
        self.current_group_id: str | None = None
        self.current_application: Application | None = None
        self.last_run_result: ApplicationRunResult | None = None
        # 同步运行应用的最近一次结果，供 backend 运行槽固化终态使用。
        self.last_application_result: OperationResult | None = None

        # 通知池，应用开始时清空重用
        self.notify_pool: NotifyPool = NotifyPool()

    def registry_application(
        self,
        factory: ApplicationFactory | list[ApplicationFactory],
        default_group: bool = False,
    ):
        """
        注册应用工厂。

        将应用工厂或工厂列表注册到上下文中，后续可以通过app_id创建对应的应用实例。

        Args:
            factory: 应用工厂实例或工厂列表
            default_group: 应用是否属于默认应用组，默认为False
        """
        if isinstance(factory, list):
            for f in factory:
                self._application_factory_map[f.app_id] = f
                if default_group:
                    self.default_group_apps.append(f.app_id)
        else:
            self._application_factory_map[factory.app_id] = factory
            if default_group:
                self.default_group_apps.append(factory.app_id)

    def clear_applications(self) -> None:
        """清空所有已注册的应用工厂

        在刷新应用注册前调用，清空现有的注册信息。
        """
        self._application_factory_map.clear()
        self.default_group_apps.clear()

    def clear_application_cache(self) -> None:
        """清理已注册应用工厂缓存的配置和运行记录。

        外置 backend server 与 GUI 是不同进程；GUI 保存 YAML 后，本进程内
        已缓存的 ApplicationConfig / AppRunRecord 不会自动刷新，运行前通过
        这里清理缓存，让后续读取落到最新配置。
        """
        for factory in self._application_factory_map.values():
            factory.clear_cache()

    @property
    def notify_app_map(self) -> dict[str, str]:
        """返回需要通知的应用字典: {app_id: app_name}。

        说明:
            1. 通过工厂的 need_notify 标记判断是否需要通知。
            2. 若应用没有设置 app_name，则使用 app_id 作为值兜底。

        Returns:
            dict[str,str]: need_notify 为 True 的应用映射，按 app_id 排序。
        """
        tmp: list[tuple[str, str]] = []
        for app_id, factory in self._application_factory_map.items():
            if factory.need_notify:
                app_name = factory.app_name or app_id
                tmp.append((app_id, app_name))

        return dict(sorted(tmp, key=lambda x: x[0]))

    def is_app_registered(self, app_id: str) -> bool:
        """
        检查应用是否已注册。

        Args:
            app_id: 应用ID

        Returns:
            bool: 应用是否已注册
        """
        return app_id in self._application_factory_map

    def is_app_need_notify(self, app_id: str) -> bool:
        """
        检查应用是否需要通知。

        Args:
            app_id: 应用ID

        Returns:
            bool: 应用是否需要通知，如果应用未注册则返回False
        """
        factory = self._application_factory_map.get(app_id)
        return factory.need_notify if factory else False

    def get_application(
        self, app_id: str, instance_idx: int, group_id: str
    ) -> Application:
        """
        创建应用实例。

        通过已注册的工厂创建指定参数的应用实例。

        Args:
            app_id: 应用ID
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行

        Returns:
            Application: 创建的应用实例
        """
        if app_id not in self._application_factory_map:
            raise Exception(f"应用未注册 {app_id}")
        factory = self._application_factory_map[app_id]
        return factory.create_application(instance_idx=instance_idx, group_id=group_id)

    def get_application_name(self, app_id: str) -> str:
        """
        获取应用名称

        Args:
            app_id: 应用ID

        Returns:
            str: 应用名称
        """
        if app_id not in self._application_factory_map:
            raise Exception(f"应用未注册 {app_id}")

        return self._application_factory_map[app_id].app_name

    def get_config(
        self,
        app_id: str | None = None,
        instance_idx: int | None = None,
        group_id: str | None = None,
    ) -> CONFIG:
        """
        获取配置实例。

        通过已注册的工厂获取指定参数的应用配置。

        Args:
            app_id: 应用ID 为空时使用当前运行的
            instance_idx: 账号实例下标 为空时使用当前运行的
            group_id: 应用组ID 为空时使用当前运行的，不同应用组可以有不同的应用配置

        Returns:
            ApplicationConfig: 应用配置对象

        Raises:
            Exception: 如果注册应用无需配置(ApplicationFactory.create_config未实现)时，调用本方法会抛出异常
        """
        if app_id is None:
            app_id = self.current_app_id
        if instance_idx is None:
            instance_idx = self.current_instance_idx
        if group_id is None:
            group_id = self.current_group_id

        if app_id is None or instance_idx is None or group_id is None:
            raise Exception("参数不能为空")

        if app_id not in self._application_factory_map:
            raise Exception(f"应用未注册 {app_id}")

        factory = self._application_factory_map[app_id]
        return factory.get_config(instance_idx, group_id)

    def get_run_record(
        self,
        app_id: str | None = None,
        instance_idx: int | None = None,
    ) -> RECORD:
        """
        获取运行记录实例。

        通过已注册的工厂获取指定参数的应用运行记录。

        Args:
            app_id: 应用ID 为空时使用当前运行的
            instance_idx: 账号实例下标 为空时使用当前运行的

        Returns:
            AppRunRecord: 运行记录对象

        Raises:
            Exception: 如果子类应用无需配置(ApplicationFactory.create_run_record未实现)时，调用本方法会抛出异常
        """
        if app_id is None:
            app_id = self.current_app_id
        if instance_idx is None:
            instance_idx = self.current_instance_idx

        if app_id is None or instance_idx is None:
            raise Exception("参数不能为空")

        if app_id not in self._application_factory_map:
            raise Exception(f"应用未注册 {app_id}")

        factory = self._application_factory_map[app_id]
        return factory.get_run_record(instance_idx)

    @property
    def is_context_stop(self) -> bool:
        """
        检查上下文是否处于停止状态。

        Returns:
            bool: 是否处于停止状态
        """
        return self._run_state == ApplicationRunContextStateEnum.STOP

    @property
    def is_context_running(self) -> bool:
        """
        检查上下文是否处于运行状态。

        Returns:
            bool: 是否处于运行状态
        """
        return self._run_state == ApplicationRunContextStateEnum.RUNNING

    @property
    def is_context_pause(self) -> bool:
        """
        检查上下文是否处于暂停状态。

        Returns:
            bool: 是否处于暂停状态
        """
        return self._run_state == ApplicationRunContextStateEnum.PAUSE

    def _create_run_result(
        self,
        finish_reason: RunFinishReason,
        app_id: str | None = None,
        instance_idx: int | None = None,
        group_id: str | None = None,
    ) -> ApplicationRunResult:
        """创建运行结果对象。"""
        return ApplicationRunResult(
            finish_reason=finish_reason,
            app_id=(self.current_app_id if app_id is None else app_id) or "",
            instance_idx=self.current_instance_idx if instance_idx is None else instance_idx,
            group_id=self.current_group_id if group_id is None else group_id,
        )

    def _finish_running(
        self,
        result: ApplicationRunResult,
        dispatch_event: bool = True,
    ) -> ApplicationRunResult:
        """统一收口运行结束逻辑。"""
        if self.is_context_stop:
            if self.last_run_result is None:
                self.last_run_result = result
            return self.last_run_result

        self.last_run_result = result
        if self.is_context_running:
            self.switch_context_pause_and_run()

        self._run_state = ApplicationRunContextStateEnum.STOP
        if dispatch_event:
            self.event_bus.dispatch_event(
                ApplicationRunContextStateEventEnum.STOP, result
            )
        return result

    def start_running(self) -> bool:
        """
        开始运行。

        将上下文状态设置为运行，初始化控制器并发送开始事件。
        只有在停止状态下才能开始运行。

        Returns:
            bool: 是否成功开始运行
        """
        if not self.is_context_stop:
            log.error("请先结束其他运行中的功能 再启动")
            return False
        if self.ctx.controller is None:
            log.error("未初始化控制器")
            return False

        if self.ctx.controller.init_before_context_run():
            self.last_run_result = None
            self._run_state = ApplicationRunContextStateEnum.RUNNING
            self.event_bus.dispatch_event(
                ApplicationRunContextStateEventEnum.START, self._run_state
            )
            return True
        else:
            log.error("运行前初始化失败")
            return False

    def stop_running(self) -> ApplicationRunResult:
        """
        停止运行。

        将上下文状态设置为停止，如果正在运行则先暂停，然后发送停止事件。
        已经停止时返回首次收口结果，不重复发送停止事件或覆盖结束原因。
        """
        result = self._create_run_result(RunFinishReason.STOPPED)
        return self._finish_running(result)

    def switch_context_pause_and_run(self):
        """
        切换暂停和运行状态。

        根据当前状态在暂停和运行之间切换，并发送相应的事件。
        """
        if self._run_state == ApplicationRunContextStateEnum.RUNNING:
            log.info("暂停运行")
            self._run_state = ApplicationRunContextStateEnum.PAUSE
            self.event_bus.dispatch_event(
                ApplicationRunContextStateEventEnum.PAUSE, self._run_state
            )
        elif self._run_state == ApplicationRunContextStateEnum.PAUSE:
            log.info("恢复运行")
            self._run_state = ApplicationRunContextStateEnum.RUNNING
            self.event_bus.dispatch_event(
                ApplicationRunContextStateEventEnum.RESUME, self._run_state
            )

    @property
    def run_status_text(self) -> str:
        if self._run_state == ApplicationRunContextStateEnum.STOP:
            return gt('空闲')
        elif self._run_state == ApplicationRunContextStateEnum.RUNNING:
            return gt('运行中')
        elif self._run_state == ApplicationRunContextStateEnum.PAUSE:
            return gt('暂停中')
        else:
            return gt('未知')

    def run_application(
        self,
        app_id: str,
        instance_idx: int,
        group_id: str,
        init_timeout: int = 60,
    ) -> ApplicationRunResult:
        """
        同步运行指定的应用。

        设置当前运行信息，创建应用实例并执行，最后清理运行状态。

        Args:
            app_id: 应用ID
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行
            init_timeout: 等待初始化的超时时间(秒)

        Returns:
            ApplicationRunResult: 应用运行结束结果。
        """
        start_time = time.time()
        while not self.ctx.ready_for_application:
            now = time.time()
            if now - start_time >= init_timeout:
                log.error("等待应用 %s 初始化超时", app_id)
                return self._create_run_result(
                    RunFinishReason.NOT_STARTED, app_id, instance_idx, group_id
                )

            time.sleep(1)

        if not self.is_app_registered(app_id):
            log.error("应用 %s 未注册", app_id)
            return self._create_run_result(
                RunFinishReason.NOT_STARTED, app_id, instance_idx, group_id
            )

        if not self.start_running():
            return self._create_run_result(
                RunFinishReason.NOT_STARTED, app_id, instance_idx, group_id
            )

        self.last_application_result = None
        try:
            app = self.get_application(app_id, instance_idx, group_id)
        except Exception:
            log.error("创建应用 %s 失败", app_id, exc_info=True)
            return self._finish_running(
                self._create_run_result(
                    RunFinishReason.FAILED, app_id, instance_idx, group_id
                )
            )

        finish_reason: RunFinishReason
        try:
            self.current_app_id = app_id
            self.current_instance_idx = instance_idx
            self.current_group_id = group_id
            self.current_application = app

            self.last_application_result = app.execute()
            finish_reason = (
                RunFinishReason.COMPLETED
                if self.last_application_result.success
                else RunFinishReason.FAILED
            )
        except Exception as e:
            finish_reason = RunFinishReason.FAILED
            log.error("运行应用 %s 失败", app_id, exc_info=True)
            # 异常时固化失败终态，避免 last_application_result 留 None 被误判为成功。
            self.last_application_result = OperationResult(
                success=False, status=f'执行异常: {e}'
            )
        finally:
            if self.last_run_result is None:
                run_result = self._finish_running(
                    self._create_run_result(finish_reason)
                )
            else:
                run_result = self.last_run_result
            self.current_app_id = None
            self.current_instance_idx = None
            self.current_group_id = None
            self.current_application = None

        return run_result

    def run_application_async(
        self,
        app_id: str,
        instance_idx: int,
        group_id: str,
        init_timeout: int = 60,
    ) -> bool:
        """
        异步运行指定的应用。

        使用线程池在后台运行应用，不阻塞主线程。
        只有在上下文处于停止状态时才能启动异步运行。

        Args:
            app_id: 应用ID
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行
            init_timeout: 等待初始化的超时时间(秒)

        Returns:
            bool: 是否成功提交到线程池（不关心运行结果）
        """
        if not self.is_context_stop:
            return False

        if not self.is_app_registered(app_id):
            return False

        future = self._executor.submit(self.run_application, app_id, instance_idx, group_id, init_timeout)
        future.add_done_callback(thread_utils.handle_future_result)

        return True

    def check_and_update_all_run_record(self, instance_idx: int) -> None:
        """
        检查并刷新账号实例下的所有运行记录
        Args:
            instance_idx: 账号实例下标
        """
        for app_id in self._application_factory_map:
            try:
                run_record = self.get_run_record(app_id=app_id, instance_idx=instance_idx)
                run_record.check_and_update_status()
            except Exception:
                # 部分应用没有运行记录 跳过即可
                pass

    def after_app_shutdown(self) -> None:
        """
        整个脚本运行结束后的清理

        关闭应用运行上下文，包括停止当前运行任务、清除运行状态。
        """
        # 首先停止当前运行的应用，清除运行状态
        if not self.is_context_stop:
            self.stop_running()

        # 关闭执行器
        self._executor.shutdown(wait=False, cancel_futures=True)
