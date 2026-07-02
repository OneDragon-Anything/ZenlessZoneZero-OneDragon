from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RunFinishReason(StrEnum):
    """应用结束原因。"""

    COMPLETED = "COMPLETED"  # 正常完成
    STOPPED_BY_USER = "STOPPED_BY_USER"  # 用户主动停止
    STOPPED_BY_FLOW = "STOPPED_BY_FLOW"  # 流程主动停止
    FAILED = "FAILED"  # 运行异常结束
    INIT_FAILED = "INIT_FAILED"  # 启动前初始化失败
    INIT_TIMEOUT = "INIT_TIMEOUT"  # 等待初始化超时
    APP_SHUTDOWN = "APP_SHUTDOWN"  # 程序退出清理


@dataclass(slots=True)
class ApplicationRunResult:
    """应用运行结果。"""

    finish_reason: RunFinishReason
    app_id: str
    instance_idx: int | None
    group_id: str | None
