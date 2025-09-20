from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from typing import List


class OkResponse(BaseModel):
    ok: bool = True


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class RunIdResponse(BaseModel):
    runId: str = Field(..., description="唯一运行 ID")


class RunStatusEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ContextStateEnum(str, Enum):
    """上下文状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


class LogLevelEnum(str, Enum):
    """日志级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class RunStatusResponse(BaseModel):
    runId: str
    status: RunStatusEnum
    progress: float = 0.0
    message: Optional[str] = None
    startedAt: Optional[str] = None
    updatedAt: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[ErrorDetail] = None


class GameAccountConfigDTO(BaseModel):
    platform: Optional[str] = None
    gameRegion: Optional[str] = None
    gamePath: Optional[str] = None
    gameLanguage: Optional[str] = None
    useCustomWinTitle: Optional[bool] = None
    customWinTitle: Optional[str] = None
    account: Optional[str] = None
    password: Optional[str] = None


class TeamMemberDTO(BaseModel):
    agentId: str = Field(..., description="代理人ID")
    name: str = Field(..., description="代理人名称")


class TeamDTO(BaseModel):
    idx: int = Field(..., description="队伍索引")
    name: str = Field(..., description="队伍名称")
    members: List[TeamMemberDTO] = Field(..., description="队伍成员列表")
    autoBattle: str = Field(..., description="自动战斗配置")


class TeamListResponse(BaseModel):
    teams: List[TeamDTO] = Field(..., description="队伍列表")


class Capabilities(BaseModel):
    """模块能力标识"""
    canPause: bool = False
    canResume: bool = False


class ControlResponse(BaseModel):
    """统一控制响应"""
    ok: bool = True
    message: str
    runId: Optional[str] = None
    capabilities: Optional[Capabilities] = None


class StatusResponse(BaseModel):
    """统一状态响应"""
    is_running: bool
    context_state: ContextStateEnum = Field(..., description="上下文状态：idle | running | paused")
    running_tasks: Optional[int] = None
    message: Optional[str] = None
    runId: Optional[str] = None
    capabilities: Capabilities = Field(..., description="模块能力标识，必返字段避免前端判空")








# WebSocket事件相关模型
class WSEventType(str, Enum):
    """WebSocket事件类型枚举"""
    STATUS_UPDATE = "status_update"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    RUN_LOG = "run_log"


class WSEventData(BaseModel):
    """WebSocket事件数据"""
    # status_update事件字段
    is_running: Optional[bool] = None
    context_state: Optional[ContextStateEnum] = None
    running_tasks: Optional[int] = None
    message: Optional[str] = None

    # task事件字段
    taskName: Optional[str] = None
    error: Optional[str] = None

    # run_log事件字段
    level: Optional[LogLevelEnum] = None
    extra: Optional[Dict[str, Any]] = None


class WSEvent(BaseModel):
    """WebSocket事件模型"""
    type: WSEventType = Field(..., description="事件类型")
    module: str = Field(..., description="模块名称")
    runId: Optional[str] = Field(None, description="运行ID")
    timestamp: str = Field(..., description="时间戳，UTC ISO8601格式")
    data: WSEventData = Field(..., description="事件数据")
    seq: Optional[int] = Field(None, description="序列号，每个runId单调递增，辅助前端乱序重排")


# 日志回放相关模型
class LogReplayEntry(BaseModel):
    """日志回放条目"""
    timestamp: str = Field(..., description="时间戳，UTC ISO8601格式（2025-09-20T12:34:56.789Z）")
    level: LogLevelEnum = Field(..., description="日志级别")
    message: str = Field(..., description="日志消息")
    runId: str = Field(..., description="运行ID")
    module: str = Field(..., description="模块名称")
    seq: Optional[int] = Field(None, description="序列号")
    extra: Optional[Dict[str, Any]] = Field(None, description="额外信息")


class LogReplayResponse(BaseModel):
    """日志回放响应"""
    logs: List[LogReplayEntry] = Field(..., description="日志条目列表")
    total_count: int = Field(..., description="总条数")
    runId: str = Field(..., description="运行ID")
    module: str = Field(..., description="模块名称")
    has_more: bool = Field(False, description="是否还有更多日志（当前实现中始终为false）")
    message: Optional[str] = Field(None, description="响应消息")