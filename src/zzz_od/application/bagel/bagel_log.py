from __future__ import annotations

import time
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult


class BagelRoundLog:
    """按操作实例合并连续相同的等待，保留次数与首末观察时间跨度。"""

    SUMMARY_INTERVAL: float = 5.0

    def __init__(self, operation_name: str) -> None:
        """一次操作执行使用一个记录器，不与父操作或其他实例共用。"""
        self.operation_name: str = operation_name
        self._wait_key: tuple[str, str, str, str] | None = None
        self._first_at: float = 0.0
        self._last_at: float = 0.0
        self._reported_at: float = 0.0
        self._total: int = 0
        self._pending: int = 0

    def record(
        self,
        from_node: str,
        node: str,
        status: str,
        result: OperationRoundResult,
        retry_times: int,
        retry_limit: int,
    ) -> None:
        """等待仅合并相同数据；重试、成功和失败每次都输出。"""
        now = time.monotonic()
        data = repr(result.data) if result.data is not None else ''
        key = (from_node, node, status, data)
        if result.result == OperationRoundResultEnum.WAIT and key == self._wait_key:
            self._last_at = now
            self._total += 1
            self._pending += 1
            if now - self._reported_at >= self.SUMMARY_INTERVAL:
                self.flush(continuing=True)
            return
        self.flush()
        self._wait_key = None
        arrow = f'{from_node} -> {node}' if from_node != 'none' else node
        detail = f'；数据={data}' if data else ''
        if result.result == OperationRoundResultEnum.RETRY:
            detail += f'；重试={retry_times + 1}/{retry_limit}'
        writer = log.warning if result.result == OperationRoundResultEnum.RETRY else (
            log.error if result.is_fail else log.info
        )
        writer('%s 节点 %s 返回状态 %s（%s）%s',
               self.operation_name, arrow, status, result.status_display, detail)
        if result.result == OperationRoundResultEnum.WAIT:
            self._wait_key = key
            self._first_at = self._last_at = self._reported_at = now
            self._total = 1
            self._pending = 0

    def flush(self, *, continuing: bool = False) -> None:
        """补齐遗漏次数；周期报告保留当前等待，状态切换或收尾结束计数。"""
        key = self._wait_key
        if not continuing:
            self._wait_key = None
        if key is None or self._pending == 0:
            return
        from_node, node, status, data = key
        arrow = f'{from_node} -> {node}' if from_node != 'none' else node
        log.info(
            '%s 等待汇总 %s：%s；新增相同观察=%s，累计=%s，首末跨度=%.2f秒%s',
            self.operation_name, arrow, status, self._pending, self._total,
            self._last_at - self._first_at, f'；数据={data}' if data else '',
        )
        self._pending = 0
        self._reported_at = self._last_at
