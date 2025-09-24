from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from typing import Optional

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log


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


class ApplicationRunContext:
    """应用运行上下文管理类。

    负责管理应用的生命周期、状态转换、实例创建和运行调度。
    提供应用注册、状态查询、异步运行等功能，并维护当前运行的应用信息。

    Attributes:
        _application_factory_map: 应用工厂映射表，存储app_id到工厂的对应关系
        _run_state: 当前运行状态
        _executor: 线程池执行器，用于异步运行应用
        _controller: 游戏控制器，用于发送游戏指令
        _event_bus: 事件总线，用于状态变更通知
        current_app_id: 当前运行的应用ID
        current_instance_idx: 当前运行的实例下标
        current_group_id: 当前运行的组ID
    """

    def __init__(
        self,
    ):
        """
        初始化应用运行上下文。

        创建空的工厂映射表、设置初始状态为停止、初始化线程池和事件总线。
        """
        self._application_factory_map: dict[str, ApplicationFactory] = {}
        self._run_state: ApplicationRunContextStateEnum = (
            ApplicationRunContextStateEnum.STOP
        )
        self._executor = ThreadPoolExecutor(
            thread_name_prefix="one_dragon_app_run_context", max_workers=1
        )
        self._controller: Optional[ControllerBase] = None  # 这个在后续初始化后设置
        self._event_bus: ContextEventBus = ContextEventBus()

        # 当前运行的应用
        self.current_app_id: Optional[str] = None
        self.current_instance_idx: Optional[int] = None
        self.current_group_id: Optional[str] = None

    def set_controller(self, controller: ControllerBase):
        """
        设置游戏控制器。

        Args:
            controller: 游戏控制器实例，用于发送游戏指令
        """
        self._controller = controller

    def registry_application(
        self, factory: ApplicationFactory | list[ApplicationFactory]
    ):
        """
        注册应用工厂。

        将应用工厂或工厂列表注册到上下文中，后续可以通过app_id创建对应的应用实例。

        Args:
            factory: 应用工厂实例或工厂列表
        """
        if isinstance(factory, list):
            for f in factory:
                self._application_factory_map[f.app_id] = f
        else:
            self._application_factory_map[factory.app_id] = factory

    def is_app_registered(self, app_id: str) -> bool:
        """
        检查应用是否已注册。

        Args:
            app_id: 应用ID

        Returns:
            bool: 应用是否已注册
        """
        return app_id in self._application_factory_map

    def get_application(
        self, app_id: str, instance_idx: int, group_id: str
    ) -> Optional[Application]:
        """
        创建应用实例。

        通过已注册的工厂创建指定参数的应用实例。

        Args:
            app_id: 应用ID
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行

        Returns:
            Optional[Application]: 创建的应用实例，如果应用未注册则返回None
        """
        if app_id not in self._application_factory_map:
            return None
        factory = self._application_factory_map[app_id]
        return factory.create_application(instance_idx=instance_idx, group_id=group_id)

    def get_config(
        self,
        app_id: Optional[str] = None,
        instance_idx: Optional[int] = None,
        group_id: Optional[str] = None,
    ) -> Optional[ApplicationConfig]:
        """
        获取配置实例。

        通过已注册的工厂获取指定参数的应用配置。

        Args:
            app_id: 应用ID 为空时使用当前运行的
            instance_idx: 账号实例下标 为空时使用当前运行的
            group_id: 应用组ID 为空时使用当前运行的，不同应用组可以有不同的应用配置

        Returns:
            Optional[ApplicationConfig]: 应用配置对象，如果应用未注册则返回None
        """
        if app_id is None:
            app_id = self.current_app_id
        if instance_idx is None:
            instance_idx = self.current_instance_idx
        if group_id is None:
            group_id = self.current_group_id

        if app_id is None or instance_idx is None or group_id is None:
            return None

        if app_id not in self._application_factory_map:
            return None

        factory = self._application_factory_map[app_id]
        return factory.get_config(instance_idx, group_id)

    def get_run_record(
        self,
        app_id: Optional[str] = None,
        instance_idx: Optional[int] = None,
    ) -> Optional[AppRunRecord]:
        """
        获取运行记录实例。

        通过已注册的工厂获取指定参数的应用运行记录。

        Args:
            app_id: 应用ID 为空时使用当前运行的
            instance_idx: 账号实例下标 为空时使用当前运行的

        Returns:
            Optional[AppRunRecord]: 运行记录对象，如果应用未注册则返回None
        """
        if app_id is None:
            app_id = self.current_app_id
        if instance_idx is None:
            instance_idx = self.current_instance_idx

        if app_id is None or instance_idx is None:
            return None

        if app_id not in self._application_factory_map:
            return None

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
        if self._controller is None:
            log.error("未初始化控制器")
            return False

        if self._controller.init_before_context_run():
            self._run_state = ApplicationRunContextStateEnum.RUNNING
            self._event_bus.dispatch_event(
                ApplicationRunContextStateEventEnum.START, self._run_state
            )
            return True
        else:
            return False

    def stop_running(self):
        """
        停止运行。

        将上下文状态设置为停止，如果正在运行则先暂停，然后发送停止事件。
        """
        if self.is_context_stop:
            return
        if self.is_context_running:  # 先触发暂停 让执行中的指令停止
            self.switch_context_pause_and_run()
        self._run_state = ApplicationRunContextStateEnum.STOP
        log.info("停止运行")
        self._event_bus.dispatch_event(
            ApplicationRunContextStateEventEnum.STOP, self._run_state
        )

    def switch_context_pause_and_run(self):
        """
        切换暂停和运行状态。

        根据当前状态在暂停和运行之间切换，并发送相应的事件。
        """
        if self._run_state == ApplicationRunContextStateEnum.RUNNING:
            log.info("暂停运行")
            self._run_state = ApplicationRunContextStateEnum.PAUSE
            self._event_bus.dispatch_event(
                ApplicationRunContextStateEventEnum.PAUSE, self._run_state
            )
        elif self._run_state == ApplicationRunContextStateEnum.PAUSE:
            log.info("恢复运行")
            self._run_state = ApplicationRunContextStateEnum.RUNNING
            self._event_bus.dispatch_event(
                ApplicationRunContextStateEventEnum.RESUME, self._run_state
            )

    def run_application(self, app_id: str, instance_idx: int, group_id: str) -> bool:
        """
        同步运行指定的应用。

        设置当前运行信息，创建应用实例并执行，最后清理运行状态。

        Args:
            app_id: 应用ID
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行

        Returns:
            bool: 是否成功启动运行（不关心运行结果）
        """
        if not self.is_app_registered(app_id):
            log.error("应用 {} 未注册", app_id)
            return False

        if not self.start_running():
            return False

        app = self.get_application(app_id, instance_idx, group_id)
        if app is None:
            log.error("应用 {} 未注册", app_id)
            return False

        try:
            self.current_app_id = app_id
            self.current_instance_idx = instance_idx
            self.current_group_id = group_id

            op_result = app.execute()
        except Exception:
            log.error("运行应用 {} 失败", app_id)
        finally:
            self.stop_running()
            self.current_app_id = None
            self.current_instance_idx = None
            self.current_group_id = None

        return True

    def run_application_async(
        self, app_id: str, instance_idx: int, group_id: str
    ) -> bool:
        """
        异步运行指定的应用。

        使用线程池在后台运行应用，不阻塞主线程。
        只有在上下文处于停止状态时才能启动异步运行。

        Args:
            app_id: 应用ID
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行

        Returns:
            bool: 是否成功提交到线程池（不关心运行结果）
        """
        if not self.is_context_stop:
            return False

        if not self.is_app_registered(app_id):
            return False

        future = self._executor.submit(self.run_application, app_id, instance_idx, group_id)
        future.add_done_callback(thread_utils.handle_future_result)

        return True
