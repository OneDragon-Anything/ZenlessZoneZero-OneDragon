from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Any, List

from .models import RunStatusEnum, RunStatusResponse


@dataclass
class RunEntry:
    run_id: str
    task: asyncio.Task
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    status: RunStatusEnum = RunStatusEnum.PENDING
    message: str | None = None
    result: dict | None = None
    error: dict | None = None


class RunRegistry:
    """
    线程安全的运行注册表。负责管理 runId -> asyncio.Task 映射及状态汇总。
    状态来源：
      - 任务生命周期（pending/running/done/cancelled）
      - 应用内部上下文（如 ctx.is_context_running / AppRunRecord）
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[str, RunEntry] = {}
        self._bridges: Dict[str, Callable[[], None]] = {}

    def create(self, task_factory: Callable[[], asyncio.Task]) -> str:
        run_id = str(uuid.uuid4())
        task = task_factory()
        entry = RunEntry(run_id=run_id, task=task)
        with self._lock:
            self._runs[run_id] = entry

        def _done_callback(t: asyncio.Task) -> None:
            with self._lock:
                entry.updated_at = time.time()
                if t.cancelled():
                    entry.status = RunStatusEnum.CANCELLED
                else:
                    exc = t.exception()
                    if exc is None:
                        entry.status = RunStatusEnum.SUCCEEDED
                        try:
                            entry.result = t.result()  # type: ignore[assignment]
                        except Exception:
                            entry.result = None
                    else:
                        entry.status = RunStatusEnum.FAILED
                        entry.error = {"code": exc.__class__.__name__, "message": str(exc)}
                # detach bridge when finished
                detach = self._bridges.pop(entry.run_id, None)
                if detach:
                    try:
                        detach()
                    except Exception:
                        pass

        try:
            loop = asyncio.get_running_loop()
            # attach callback in running loop context
            task.add_done_callback(_done_callback)
        except RuntimeError:
            # No running loop (sync thread). Schedule callback safely when loop runs.
            pass
        return run_id

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            entry = self._runs.get(run_id)
        if not entry:
            return False
        if not entry.task.done():
            entry.task.cancel()
            entry.status = RunStatusEnum.CANCELLED
            entry.updated_at = time.time()
            # detach bridge on cancel
            with self._lock:
                detach = self._bridges.pop(run_id, None)
            if detach:
                try:
                    detach()
                except Exception:
                    pass
            return True
        return False

    def get_status(self, run_id: str, *, message: Optional[str] = None) -> Optional[RunStatusResponse]:
        with self._lock:
            entry = self._runs.get(run_id)
        if not entry:
            return None
        status = entry.status
        if not entry.task.done() and not entry.task.cancelled():
            status = RunStatusEnum.RUNNING
        resp = RunStatusResponse(
            runId=run_id,
            status=status,
            progress=0.0,
            message=message or entry.message,
            startedAt=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry.created_at)),
            updatedAt=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry.updated_at)),
            result=entry.result,
            error=entry.error,
        )
        return resp

    def list_statuses(self) -> List[RunStatusResponse]:
        with self._lock:
            run_ids = list(self._runs.keys())
        results: List[RunStatusResponse] = []
        for rid in run_ids:
            status = self.get_status(rid)
            if status is not None:
                results.append(status)
        return results

    def remove(self, run_id: str) -> None:
        with self._lock:
            self._runs.pop(run_id, None)
            detach = self._bridges.pop(run_id, None)
        if detach:
            try:
                detach()
            except Exception:
                pass

    def set_bridge(self, run_id: str, detach_callback: Callable[[], None]) -> None:
        with self._lock:
            self._bridges[run_id] = detach_callback

    def update_message(self, run_id: str, message: Optional[str]) -> None:
        with self._lock:
            entry = self._runs.get(run_id)
            if entry is None:
                return
            entry.message = message
            entry.updated_at = time.time()

    def set_status(self, run_id: str, status: RunStatusEnum) -> None:
        with self._lock:
            entry = self._runs.get(run_id)
            if entry is None:
                return
            entry.status = status
            entry.updated_at = time.time()


_GLOBAL_REGISTRY: Optional[RunRegistry] = None


def get_global_run_registry() -> RunRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = RunRegistry()
    return _GLOBAL_REGISTRY


