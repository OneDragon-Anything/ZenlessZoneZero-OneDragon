from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List, Any, Tuple, Dict, TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.conditional_operation.state_recorder import StateRecord
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle.target_state.target_state_checker import TargetStateChecker
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.target_state import DETECTION_TASKS, DetectionTask

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator


# 模块私有的独立线程池，用于并行处理状态检测任务
_target_context_executor = ThreadPoolExecutor(thread_name_prefix='od_target_context', max_workers=8)


class AutoBattleTargetContext:
    """
    一个由数据驱动的、通用的目标状态上下文。
    它加载一个检测任务列表，并根据每个任务的定义来自动调度、执行和更新状态。
    """

    def __init__(self, ctx: ZContext):
        """
        构造函数
        """
        self.ctx: ZContext = ctx
        self.checker: TargetStateChecker = TargetStateChecker(ctx)

        self._check_lock = threading.Lock()

        # 从数据定义加载所有启用的检测任务
        self.tasks: List[DetectionTask] = [task for task in DETECTION_TASKS if task.enabled]

        # 动态初始化计时器和间隔
        self._last_check_times: Dict[str, float] = {task.task_id: 0 for task in self.tasks}
        self._current_intervals: Dict[str, float] = {task.task_id: task.interval for task in self.tasks}

    def init_auto_op(
            self,
            auto_op: AutoBattleOperator,
    ) -> None:
        """
        加载自动战斗操作器时的动作
        """
        self._apply_config_intervals(
            auto_op.target_lock_interval,
            auto_op.abnormal_status_interval,
        )

    def _apply_config_intervals(self, target_lock_interval: float, abnormal_status_interval: float):
        """
        使用战斗配置文件中的值，覆盖任务的默认间隔
        """
        for task in self.tasks:
            if task.task_id == 'lock_on' and target_lock_interval > 0:
                task.interval = target_lock_interval
                # 同时更新动态间隔配置，以确保非锁定时使用新频率
                if 'interval_if_not_state' in task.dynamic_interval_config:
                    task.dynamic_interval_config['interval_if_not_state'] = target_lock_interval
                log.info(f"已从配置加载 [目标锁定] 检测间隔: {target_lock_interval}s")

            elif task.task_id == 'abnormal_statuses' and abnormal_status_interval > 0:
                task.interval = abnormal_status_interval
                log.info(f"已从配置加载 [异常状态] 检测间隔: {abnormal_status_interval}s")

        # 更新当前的计时器间隔
        self._current_intervals: Dict[str, float] = {task.task_id: task.interval for task in self.tasks}

    def run_all_checks(self, screen: MatLike, screenshot_time: float):
        """
        遍历所有检测任务，并执行到期的任务。
        这是模块的主入口，由外部的统一战斗循环在每一帧调用。
        """
        if not self._check_lock.acquire(blocking=False):
            return

        try:
            now = screenshot_time
            records_to_update: List[StateRecord] = []
            futures: Dict[Future, DetectionTask] = {}

            # 遍历并执行所有到期的任务
            for task in self.tasks:
                interval = self._current_intervals[task.task_id]
                if interval <= 0:  # 间隔为0或负数时，不执行此任务
                    continue

                if now - self._last_check_times[task.task_id] >= interval:
                    self._last_check_times[task.task_id] = now
                    if task.is_async:
                        future = _target_context_executor.submit(self.checker.run_task, screen, task)
                        futures[future] = task
                    else:
                        cv_ctx, sync_results = self.checker.run_task(screen, task)
                        self._handle_results(records_to_update, sync_results, screenshot_time, task)

            # 处理异步任务结果
            for future, task in futures.items():
                try:
                    _cv_ctx, async_results = future.result(timeout=1)
                    self._handle_results(records_to_update, async_results, screenshot_time, task)
                except Exception:
                    log.error(f"异步检测任务失败 [task_id={task.task_id}]", exc_info=True)

            # 批量提交状态更新
            if records_to_update:
                self.ctx.auto_battle_context.state_record_service.batch_update_states(records_to_update)

        finally:
            self._check_lock.release()

    def _handle_results(self, records_list: List[StateRecord],
                        results: List[Tuple[str, Any]],
                        screenshot_time: float,
                        task: DetectionTask):
        """
        处理同步或异步任务的结果，包括状态转换和动态间隔调整
        """
        if not results:
            return

        # 1. 添加状态记录
        for state_name, result in results:
            if isinstance(result, tuple) and len(result) == 2 and result[0] is True:
                # 更新时间和值: result is (True, value)
                records_list.append(StateRecord(state_name, screenshot_time, value=result[1]))
            elif result is True:
                # 只更新时间
                records_list.append(StateRecord(state_name, screenshot_time))
            elif result is None:
                # 清除状态
                records_list.append(StateRecord(state_name, is_clear=True))
            # elif result is False: 忽略，什么都不做

        # 2. 处理动态间隔
        dynamic_config = task.dynamic_interval_config
        if not dynamic_config:
            return

        state_to_watch = dynamic_config.get('state_to_watch')
        found_watched_state = False
        for state_name, result in results:
            if state_name == state_to_watch:
                # 检查是否是有效的命中结果
                if result is True or (isinstance(result, tuple) and result[0] is True):
                    self._current_intervals[task.task_id] = dynamic_config.get('interval_if_state', task.interval)
                    found_watched_state = True
                break  # 找到要观察的状态后就可以停止了

        if not found_watched_state:
            # 如果循环结束都没找到'hit'的被观察状态，则使用 not_state 的间隔
            self._current_intervals[task.task_id] = dynamic_config.get('interval_if_not_state', task.interval)

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        """
        _target_context_executor.shutdown(wait=False, cancel_futures=True)
