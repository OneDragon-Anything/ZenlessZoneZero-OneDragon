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






