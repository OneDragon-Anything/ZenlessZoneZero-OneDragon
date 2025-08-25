from __future__ import annotations

from fastapi import APIRouter, Depends

from zzz_od.api.deps import get_ctx
from typing import List

from zzz_od.api.models import RunStatusResponse, RunStatusEnum
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.security import get_api_key_dependency


router = APIRouter(
    prefix="/api/v1/runs",
    tags=["runs"],
    dependencies=[Depends(get_api_key_dependency())],
)

_registry = get_global_run_registry()


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str) -> RunStatusResponse:
    ctx = get_ctx()
    status = _registry.get_status(run_id, message=ctx.context_running_status_text)
    if status is None:
        return RunStatusResponse(runId=run_id, status=RunStatusEnum.FAILED, message="Run not found", progress=0.0)
    return status


@router.post("/{run_id}:cancel")
async def cancel_run(run_id: str):
    _registry.cancel(run_id)
    ctx = get_ctx()
    ctx.stop_running()
    return {"ok": True}


@router.get("/", response_model=List[RunStatusResponse])
async def list_runs() -> List[RunStatusResponse]:
    return _registry.list_statuses()


