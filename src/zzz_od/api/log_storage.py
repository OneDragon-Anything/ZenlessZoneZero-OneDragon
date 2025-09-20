"""
运行日志存储系统

为统一API控制系统提供基于runId的日志存储和回放功能。
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Optional, Deque
from dataclasses import dataclass

from zzz_od.api.models import LogLevelEnum


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str  # UTC ISO8601格式
    level: LogLevelEnum
    message: str
    runId: str
    module: str
    seq: Optional[int] = None
    extra: Optional[Dict] = None


class RunLogStorage:
    """运行日志存储器"""

    def __init__(self, max_logs_per_run: int = 2000):
        self.max_logs_per_run = max_logs_per_run
        self._logs: Dict[str, Deque[LogEntry]] = defaultdict(lambda: deque(maxlen=max_logs_per_run))
        self._lock = threading.RLock()

    def add_log(self, runId: str, module: str, level: LogLevelEnum, message: str,
                seq: Optional[int] = None, extra: Optional[Dict] = None) -> None:
        """添加日志条目"""
        with self._lock:
            timestamp = datetime.utcnow().isoformat() + "Z"
            entry = LogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
                runId=runId,
                module=module,
                seq=seq,
                extra=extra
            )
            self._logs[runId].append(entry)

    def get_logs(self, runId: str, tail: Optional[int] = None) -> List[LogEntry]:
        """获取指定runId的日志"""
        with self._lock:
            if runId not in self._logs:
                return []

            logs = list(self._logs[runId])

            if tail is not None and tail > 0:
                # 返回最后tail条日志
                logs = logs[-tail:]

            return logs

    def cleanup_run(self, runId: str) -> None:
        """清理指定runId的日志（可选，用于内存管理）"""
        with self._lock:
            if runId in self._logs:
                del self._logs[runId]

    def get_run_count(self) -> int:
        """获取当前存储的运行数量"""
        with self._lock:
            return len(self._logs)

    def get_total_log_count(self) -> int:
        """获取总日志条数"""
        with self._lock:
            return sum(len(logs) for logs in self._logs.values())


# 全局日志存储实例
_global_log_storage: Optional[RunLogStorage] = None


def get_global_log_storage() -> RunLogStorage:
    """获取全局日志存储实例"""
    global _global_log_storage
    if _global_log_storage is None:
        _global_log_storage = RunLogStorage()
    return _global_log_storage