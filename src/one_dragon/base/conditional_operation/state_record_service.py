from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, Future
from typing import TYPE_CHECKING

from one_dragon.base.conditional_operation.state_recorder import StateRecorder, StateRecord
from one_dragon.utils import thread_utils

if TYPE_CHECKING:
    from one_dragon.base.conditional_operation.operator import ConditionalOperator


_state_record_service_executor = ThreadPoolExecutor(thread_name_prefix='od_state_record_service', max_workers=16)


class StateRecordService(ABC):

    def __init__(self):
        self.op_list: set[ConditionalOperator] = set()

    def register_operator(self, op: ConditionalOperator):
        """
        注册一个操作器

        Args:
            op: 操作器
        """
        self.op_list.add(op)

    def unregister_operator(self, op: ConditionalOperator):
        """
        注销一个操作器

        Args:
            op: 操作器
        """
        if op in self.op_list:
            self.op_list.remove(op)

    @abstractmethod
    def get_state_recorder(self, state_name: str) -> StateRecorder | None:
        """
        获取状态记录器

        Args:
            state_name: 状态名称

        Returns:
            状态记录器
        """
        pass

    def update_state(self, state_record: StateRecord) -> None:
        """
        更新一个状态
        更新后触发 操作器相应的动作
        """
        self.batch_update_states([state_record])

    def batch_update_states(self, state_records: list[StateRecord]) -> None:
        """
        批量更新多个状态
        更新后触发 操作器相应的动作
        """
        for state_record in state_records:
            self._update_state_recorder(state_record)

        for op in self.op_list:
            f: Future = _state_record_service_executor.submit(op.batch_update_states, state_records)
            f.add_done_callback(thread_utils.handle_future_result)

    def _update_state_recorder(self, new_record: StateRecord) -> StateRecorder | None:
        """
        更新一个状态记录

        Args:
            new_record: 新的状态记录

        Returns:
            更新后的状态记录器
        """
        recorder = self.get_state_recorder(new_record.state_name)
        if recorder is None:
            return None

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

    @staticmethod
    def after_app_shutdown() -> None:
        """
        整个脚本运行结束后的清理
        """
        _state_record_service_executor.shutdown(wait=False, cancel_futures=True)
