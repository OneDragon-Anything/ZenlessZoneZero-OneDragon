import time
from concurrent.futures import ThreadPoolExecutor, Future

from threading import Lock
from typing import Optional, Callable, List

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.operation_task import OperationTask
from one_dragon.base.conditional_operation.operation_template import OperationTemplate
from one_dragon.base.conditional_operation.scene_handler import SceneHandler
from one_dragon.base.conditional_operation.state_handler_template import StateHandlerTemplate
from one_dragon.base.conditional_operation.state_recorder import StateRecorder, StateRecord
from one_dragon.base.conditional_operation.utils import construct_scene_handler
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.thread.atomic_int import AtomicInt
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log

_od_conditional_op_executor = ThreadPoolExecutor(thread_name_prefix='od_conditional_op', max_workers=32)


class ConditionalOperator(YamlConfig):

    def __init__(self, sub_dir: str, template_name: str,
                 instance_idx: Optional[int] = None, is_mock: bool = False):
        YamlConfig.__init__(
            self,
            module_name=template_name,
            sub_dir=[sub_dir],
            instance_idx=instance_idx,
            sample=True, copy_from_sample=False, is_mock=is_mock
        )

        self._inited: bool = False  # 是否已经完成初始化

        self.trigger_scene_handler: dict[str, SceneHandler] = {}  # 需要状态触发的场景处理
        self.last_trigger_time: dict[int, float] = {}  # 各handler最后一次的触发时间
        self.normal_scene_handler: Optional[SceneHandler] = None  # 不需要状态触发的场景处理
        self.is_running: bool = False  # 整体是否正在运行

        self._task_lock: Lock = Lock()
        self.running_task: Optional[OperationTask] = None  # 正在运行的任务
        self.running_task_cnt: AtomicInt = AtomicInt()

    def init(
            self,
            op_getter: Callable[[OperationDef], AtomicOp],
            scene_handler_getter: Callable[[str], StateHandlerTemplate],
            operation_template_getter: Callable[[str], OperationTemplate],
    ) -> None:
        """
        初始化 在需要执行之前再使用
        """
        self._inited = False

        self.dispose()  # 先把旧的清除掉
        self.trigger_scene_handler: dict[str, SceneHandler] = {}
        self.normal_scene_handler = None
        self.last_trigger_time = {}

        scenes = self.get('scenes', [])

        usage_states = []  # 已经监听的状态变更

        for scene_data in scenes:
            handler = construct_scene_handler(scene_data, self.get_state_recorder,
                                              op_getter, scene_handler_getter, operation_template_getter)
            states = scene_data.get('triggers', [])
            if len(states) > 0:
                for state in states:
                    if state in usage_states:
                        raise ValueError('状态监听 %s 出现在多个场景中' % state)
                    self.trigger_scene_handler[state] = handler
                    usage_states.append(state)  # 修复bug：将状态添加到已使用状态列表中
            elif self.normal_scene_handler is not None:
                raise ValueError('存在多个无状态监听的场景')
            else:
                self.normal_scene_handler = handler

        self._inited = True

    def dispose(self) -> None:
        """
        销毁 要对子模块进行完全销毁
        :return:
        """
        self.stop_running()  # 在这里强制停止运行
        if self.trigger_scene_handler is not None:
            for _, handler in self.trigger_scene_handler.items():
                handler.dispose()
        if self.normal_scene_handler is not None:
            self.normal_scene_handler.dispose()

    def start_running_async(self) -> bool:
        """
        异步开始运行
        :return:
        """
        if not self._inited:
            log.error('自动指令 [ %s ] 未完成初始化 无法运行', self.module_name)
            return False
        if self.is_running:
            return False

        self.is_running = True
        self.running_task_cnt.set(0)  # 每次重置计数器 防止有bug导致无法正常运行

        if self.normal_scene_handler is not None:
            future: Future = _od_conditional_op_executor.submit(self._normal_scene_loop)
            future.add_done_callback(thread_utils.handle_future_result)

        return True

    def _normal_scene_loop(self) -> None:
        """
        主循环
        :return:
        """
        normal_handler_id = id(self.normal_scene_handler)
        while self.is_running:
            if self.running_task_cnt.get() > 0:
                # 有其它场景在运行 等待
                time.sleep(0.02)
            else:
                # log.debug('开始等待新的主循环')
                to_sleep: Optional[float] = None

                # 上锁后确保运行状态不会被篡改
                with self._task_lock:
                    if not self.is_running:
                        # 已经被stop_running中断了 不继续
                        break

                    trigger_time = time.time()
                    last_trigger_time = self.last_trigger_time.get(normal_handler_id, 0)
                    past_time = trigger_time - last_trigger_time
                    if past_time < self.normal_scene_handler.interval_seconds:
                        to_sleep = self.normal_scene_handler.interval_seconds - past_time
                    else:
                        new_task = self.normal_scene_handler.get_operations(trigger_time)
                        if new_task is not None:
                            log.debug(f'当前场景 主循环 当前条件 {new_task.expr_display}')
                            self.running_task = new_task
                            self.last_trigger_time[normal_handler_id] = trigger_time
                            self.running_task_cnt.inc()
                            future = self.running_task.run_async()
                            future.add_done_callback(self._on_task_done)

                if to_sleep is not None:
                    # 等待时间不能写在锁里 要尽快释放锁
                    time.sleep(to_sleep)
                else:  # 没有命中的状态 或者 提交执行了 那就自旋等待
                    time.sleep(0.02)

    def _trigger_scene(self, state_name: str) -> None:
        """
        触发对应的场景
        :param state_name: 触发的状态
        :return:
        """
        if state_name not in self.trigger_scene_handler:
            return
        handler = self.trigger_scene_handler[state_name]
        trigger_handler_id = id(handler)

        # 上锁后确保运行状态不会被篡改
        with self._task_lock:
            if not self.is_running:
                # 已经被stop_running中断了 不继续
                return

            trigger_time: float = time.time()  # 这里不应该使用事件发生时间 而是应该使用当前的实际操作时间
            last_trigger_time = self.last_trigger_time.get(trigger_handler_id, 0)
            if trigger_time - last_trigger_time < handler.interval_seconds:  # 冷却时间没过 不触发
                return

            new_task = handler.get_operations(trigger_time)
            # 若new_task为空，即无匹配state，则不打断当前task
            if new_task is None:
                return

            can_interrupt: bool = False
            if self.running_task is not None:
                old_priority = self.running_task.priority
                new_priority = new_task.priority
                if old_priority is None:  # 当前运行场景可随意打断
                    can_interrupt = True
                elif new_priority is not None and new_priority > old_priority:  # 新触发场景优先级更高
                    can_interrupt = True
            else:
                can_interrupt = True

            if not can_interrupt:  # 当前运行场景无法被打断
                return

            # 必须要先增加计算器 避免无触发场景的循环进行
            self.running_task_cnt.inc()
            # 停止已有的操作
            self._stop_running_task()

            log.debug(f'当前场景 {state_name} 当前条件 {new_task.expr_display}')

            new_task.set_trigger(state_name)
            self.running_task = new_task
            self.last_trigger_time[trigger_handler_id] = trigger_time
            future = self.running_task.run_async()
            future.add_done_callback(self._on_task_done)

    def stop_running(self) -> None:
        """
        停止执行
        :return:
        """
        # 上锁后停止 上锁后确保运行状态不会被篡改
        with self._task_lock:
            self.is_running = False
            self._stop_running_task()

    def _stop_running_task(self) -> None:
        """
        停止正在运行的任务
        调用这个函数的地方都使用了 self._task_lock 锁
        :return:
        """
        if self.running_task is not None:
            finish = self.running_task.stop()  # stop之前是否已经完成所有op
            if not finish:
                # 如果 finish=True 则计数器已经在 _on_task_done 减少了 这里就不减了
                # 如果 finish=False 则代表还有操作在继续。在这里要减少计数器而不是等_on_task_done 让无触发器场景尽早运行
                self.running_task_cnt.dec()

    def _on_task_done(self, future: Future) -> None:
        """
        一系列指令任务完成后
        """
        with self._task_lock:  # 上锁 保证_running_trigger_cnt安全
            try:
                result = future.result()
                if result:  # 顺利执行完毕
                    self.running_task_cnt.dec()
                    self.running_task.priority = None
            except Exception:  # run_async里有callback打印日志
                pass

    def get_usage_states(self) -> set[str]:
        """
        获取使用的状态 需要init之后使用
        :return:
        """
        states: set[str] = set()
        if self.normal_scene_handler is not None:
            states = states.union(self.normal_scene_handler.get_usage_states())
        if self.trigger_scene_handler is not None:
            for event_id, handler in self.trigger_scene_handler.items():
                states.add(event_id)
                states = states.union(handler.get_usage_states())
        return states

    def get_state_recorder(self, state_name: str) -> Optional[StateRecorder]:
        """
        如何获取状态记录器 由具体子类实现
        """
        return None

    def update_state(self, state_record: StateRecord) -> None:
        """
        更新一个状态
        然后看是否需要触发对应的场景 清除状态的不进行触发
        :param state_record: 状态记录
        :return:
        """
        # 先统一更新状态值
        state_recorder = self._update_state_recorder(state_record)
        if state_recorder is None:
            return

        # 再去触发具体的场景 由自己的线程处理
        if not state_record.is_clear:
            future: Future = _od_conditional_op_executor.submit(self._trigger_scene, state_recorder.state_name)
            future.add_done_callback(thread_utils.handle_future_result)

    def batch_update_states(self, state_records: List[StateRecord]) -> None:
        """
        批量更新多个状态
        然后看是否需要触发对应的场景 清除状态的不进行触发
        只触发优先级最高的一个
        多个相同优先级时 随机触发一个
        没有场景需要触发时 判断是否符合当前运行指令的打断 如果符合 则打断
        :param state_records: 状态记录列表
        :return:
        """
        top_priority_handler: Optional[SceneHandler] = None
        top_priority_state: Optional[str] = None

        for state_record in state_records:
            state_name = state_record.state_name
            state_recorder = self._update_state_recorder(state_record)
            if state_recorder is None:
                continue
            if state_record.is_clear:
                continue

            # 找优先级最高的场景
            handler = self.trigger_scene_handler.get(state_name)
            if handler is None:
                continue

            replace = False
            if top_priority_handler is None:
                replace = True
            elif top_priority_handler.priority is None:  # 可随意打断
                replace = True
            elif handler.priority is None:  # 可随意打断
                pass
            elif handler.priority > top_priority_handler.priority:  # 新触发场景优先级更高
                replace = True

            if replace:
                top_priority_handler = handler
                top_priority_state = state_name

        # 触发具体的场景 由自己的线程处理
        if top_priority_state is not None:
            future: Future = _od_conditional_op_executor.submit(self._trigger_scene, top_priority_state)
            future.add_done_callback(thread_utils.handle_future_result)
        else:
            # 没有场景需要触发 看是否需要打断当前操作
            with self._task_lock:
                interrupt: bool = False
                if (self.running_task is not None and self.running_task.running
                        and self.running_task.interrupt_cal_tree is not None):
                    now = time.time()
                    if self.running_task.interrupt_cal_tree.in_time_range(now):
                        interrupt = True
                        log.debug('复合中断条件满足，执行中断')
                if interrupt:
                    self._stop_running_task()

    def _update_state_recorder(self, new_record: StateRecord) -> Optional[StateRecorder]:
        """
        更新一个状态记录
        :param new_record: 新的状态记录
        :return:
        """
        recorder = self.get_state_recorder(new_record.state_name)
        if recorder is None:
            return

        if new_record.is_clear:
            recorder.clear_state_record()
        else:
            recorder.update_state_record(new_record)
            if recorder.mutex_list is not None:
                for mutex_state in recorder.mutex_list:
                    mutex_recorder = self.get_state_recorder(mutex_state)
                    if mutex_recorder is None:
                        continue
                    mutex_recorder.clear_state_record()

        return recorder
