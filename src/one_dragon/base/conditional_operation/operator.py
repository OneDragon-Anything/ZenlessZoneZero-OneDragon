import time
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import List, Optional

from one_dragon.base.conditional_operation.state_recorder import StateRecord
from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.execution_info import ExecutionInfo
from one_dragon.base.conditional_operation.loader import ConditionalOperatorLoader
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.operation_executor import (
    OperationExecutor,
)
from one_dragon.base.conditional_operation.scene import Scene
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.thread.atomic_int import AtomicInt
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log

# 当前运行的场景一个 打断的新场景一个 处理事件更新状态一个
_od_conditional_op_executor = ThreadPoolExecutor(thread_name_prefix='od_conditional_op', max_workers=4)


class ConditionalOperator(ConditionalOperatorLoader):

    def __init__(
        self,
        sub_dir: list[str],
        template_name: str,
        operation_template_sub_dir: list[str],
        state_handler_template_sub_dir: list[str],
        read_from_merged: bool = True,
    ):
        ConditionalOperatorLoader.__init__(
            self,
            sub_dir=sub_dir,
            template_name=template_name,
            operation_template_sub_dir=operation_template_sub_dir,
            state_handler_template_sub_dir=state_handler_template_sub_dir,
            read_from_merged=read_from_merged,
        )

        self.trigger_2_scene: dict[str, Scene] = {}  # 需要状态触发的场景处理
        self.normal_scene: Scene | None = None  # 不需要状态触发的场景处理
        self.last_trigger_time: dict[int, float] = {}  # 各场景最后一次的触发时间

        self.is_running: bool = False  # 整体是否正在运行
        self.current_execution_info: ExecutionInfo | None = None  # 当前的执行信息
        self.running_executor: OperationExecutor | None = None  # 正在运行的任务
        self.running_executor_cnt: AtomicInt = AtomicInt()  # 统计有
        
        self._inited: bool = False
        self._task_lock: Lock = Lock()

    def init(self) -> None:
        """
        完整的初始化流程 可重复调用
        """
        self._inited = False

        self.dispose()
        self.load()
        self.build()

        self._inited = True

    def build(self) -> None:
        """
        根据配置数据 构建操作器
        需要先调用  self.load() 加载配置文件
        """
        self.dispose()  # 先把旧的清除掉
        self.trigger_2_scene = {}
        self.normal_scene = None
        self.last_trigger_time = {}

        for scene in self.scenes:
            scene.build(
                state_recorder_getter=self.get_state_recorder,
                op_getter=self.get_atomic_op,
            )
            if len(scene.triggers) > 0:
                for trigger in scene.triggers:
                    self.trigger_2_scene[trigger] = scene
            else:
                self.normal_scene = scene

    def dispose(self) -> None:
        """
        销毁操作器
        """
        pass

    @abstractmethod
    def get_state_recorder(self, state_name: str) -> StateRecorder | None:
        """
        如何获取状态记录器 由具体子类实现
        """
        pass

    @abstractmethod
    def get_atomic_op(self, op_def: OperationDef) -> AtomicOp:
        """
        获取原子操作 由具体子类实现
        """
        pass

    def start_running_async(self) -> bool:
        """
        异步开始运行
        :return:
        """
        if not self._inited:
            log.error('未完成初始化 无法运行')
            return False
        if self.is_running:
            return False

        self.is_running = True
        self.running_executor_cnt.set(0)  # 每次重置计数器 防止有bug导致无法正常运行

        if self.normal_scene is not None:
            future: Future = _od_conditional_op_executor.submit(self._normal_scene_loop)
            future.add_done_callback(thread_utils.handle_future_result)

        return True

    def _normal_scene_loop(self) -> None:
        """
        主循环
        :return:
        """
        normal_handler_id = id(self.normal_scene)
        while self.is_running:
            if self.running_executor_cnt.get() > 0:
                # 有其它场景在运行 等待
                time.sleep(0.02)
                continue

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
                if past_time < self.normal_scene.interval_seconds:
                    to_sleep = self.normal_scene.interval_seconds - past_time
                else:
                    new_execution_info = self.normal_scene.match_execution(trigger_time)
                    if new_execution_info is not None:
                        log.debug(f'当前场景 主循环 当前条件 {new_execution_info.expr_display}')
                        new_execution_info.handler_id = normal_handler_id
                        self.current_execution_info = new_execution_info
                        self.running_executor = OperationExecutor(
                            op_list=new_execution_info.op_list,
                            trigger_time=trigger_time,
                        )
                        self.last_trigger_time[normal_handler_id] = trigger_time
                        self.running_executor_cnt.inc()
                        future = self.running_executor.run_async()
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
        if state_name not in self.trigger_2_scene:
            return
        handler = self.trigger_2_scene[state_name]
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

            new_execution_info = handler.match_execution(trigger_time)
            # 若new_execution_info为空，即无匹配state，则不打断当前运行
            if new_execution_info is None:
                return

            can_interrupt: bool = False
            if self.running_executor is not None:
                old_priority = self.current_execution_info.priority
                new_priority = new_execution_info.priority
                if old_priority is None:  # 当前运行场景可随意打断
                    can_interrupt = True
                elif new_priority is not None and new_priority > old_priority:  # 新触发场景优先级更高
                    can_interrupt = True
            else:
                can_interrupt = True

            if not can_interrupt:  # 当前运行场景无法被打断
                return

            # 必须要先增加计算器 避免无触发场景的循环进行
            self.running_executor_cnt.inc()
            # 停止已有的操作
            self._stop_running_task()

            log.debug(f'当前场景 {state_name} 当前条件 {new_execution_info.expr_display}')

            new_execution_info.trigger = state_name
            new_execution_info.handler_id = trigger_handler_id
            self.running_executor = OperationExecutor(new_execution_info.op_list, trigger_time)
            self.last_trigger_time[trigger_handler_id] = trigger_time
            future = self.running_executor.run_async()
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
        if self.running_executor is not None:
            finish = self.running_executor.stop()  # stop之前是否已经完成所有op
            if not finish:
                # 如果 finish=True 则计数器已经在 _on_task_done 减少了 这里就不减了
                # 如果 finish=False 则代表还有操作在继续。在这里要减少计数器而不是等_on_task_done 让无触发器场景尽早运行
                self.running_executor_cnt.dec()
            self.running_executor = None

    def _on_task_done(self, future: Future) -> None:
        """
        一系列指令任务完成后
        """
        with self._task_lock:  # 上锁 保证_running_trigger_cnt安全
            try:
                result = future.result()
                if result:  # 顺利执行完毕
                    self.running_executor_cnt.dec()
                    self.running_executor.priority = None
            except Exception:  # run_async里有callback打印日志
                pass

    def get_usage_states(self) -> set[str]:
        """
        获取使用的状态 需要init之后使用
        Returns:
            set[str]: 当前操作器所用到的全部状态
        """
        states: set[str] = set()
        if self.normal_scene is not None:
            states = states.union(self.normal_scene.usage_states)
        if self.trigger_2_scene is not None:
            for event_id, handler in self.trigger_2_scene.items():
                states.add(event_id)
                states = states.union(handler.usage_states)
        return states

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
        top_priority_scene: Optional[Scene] = None
        top_priority_state: Optional[str] = None

        for state_record in state_records:
            state_name = state_record.state_name
            state_recorder = self._update_state_recorder(state_record)
            if state_recorder is None:
                continue
            if state_record.is_clear:
                continue

            # 找优先级最高的场景
            handler = self.trigger_2_scene.get(state_name)
            if handler is None:
                continue

            replace = False
            if top_priority_scene is None:
                replace = True
            elif top_priority_scene.priority is None:  # 可随意打断
                replace = True
            elif handler.priority is None:  # 可随意打断
                pass
            elif handler.priority > top_priority_scene.priority:  # 新触发场景优先级更高
                replace = True

            if replace:
                top_priority_scene = handler
                top_priority_state = state_name

        # 触发具体的场景 由自己的线程处理
        if top_priority_state is not None:
            future: Future = _od_conditional_op_executor.submit(self._trigger_scene, top_priority_state)
            future.add_done_callback(thread_utils.handle_future_result)
        else:
            # 没有场景需要触发 看是否需要打断当前操作
            with self._task_lock:
                interrupt: bool = False
                if (self.running_executor is not None and self.running_executor.running
                        and self.current_execution_info.interrupt_cal_tree is not None):
                    now = time.time()
                    if self.current_execution_info.interrupt_cal_tree.in_time_range(now):
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
