from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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






