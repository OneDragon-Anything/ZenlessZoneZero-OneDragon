"""
通用上下文控制API
"""

from __future__ import annotations

import asyncio
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.context.zzz_context import ZContext


router = APIRouter(
    prefix="/api/v1/context",
    tags=["上下文控制 Context Control"],
    dependencies=[Depends(get_api_key_dependency())],
)

_registry = get_global_run_registry()


class ContextStatusResponse(BaseModel):
    """上下文状态响应"""
    is_running: bool
    status: str  # "running", "idle", "paused", "error"
    message: str
    progress: float = 0.0
    running_tasks: int = 0
    pending_tasks: int = 0


class ContextOperationResponse(BaseModel):
    """上下文操作响应"""
    success: bool
    message: str
    details: Dict[str, Any] = {}


@router.post("/start", response_model=ContextOperationResponse, summary="启动上下文")
async def start_context(ctx: ZContext = Depends(get_ctx)):
    """
    启动当前上下文的主要任务

    ## 功能描述
    启动一条龙主任务，类似PySide GUI中的启动按钮功能。

    ## 返回数据
    - **success**: 操作是否成功
    - **message**: 操作结果消息
    - **details**: 额外的详细信息

    ## 错误码
    - **ALREADY_RUNNING**: 任务已在运行中
    - **START_FAILED**: 启动失败

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/context/start")
    result = response.json()
    if result['success']:
        print("启动成功")
    else:
        print(f"启动失败: {result['message']}")
    ```
    """
    try:
        # 检查是否已在运行
        if getattr(ctx, 'is_context_running', False):
            return ContextOperationResponse(
                success=False,
                message="上下文已在运行中",
                details={"error_code": "ALREADY_RUNNING"}
            )

        # 启动一条龙任务
        def _factory() -> asyncio.Task:
            async def runner():
                loop = asyncio.get_running_loop()

                def _exec():
                    from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
                    app = ZOneDragonApp(ctx)
                    app.execute()

                return await loop.run_in_executor(None, _exec)

            return asyncio.create_task(runner())

        # 创建任务
        run_id = _registry.create(_factory)

        # 附加事件桥接
        attach_run_event_bridge(ctx, run_id)

        return ContextOperationResponse(
            success=True,
            message="上下文启动成功",
            details={"run_id": run_id}
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "START_FAILED",
                    "message": f"启动上下文失败: {str(e)}"
                }
            }
        )


@router.post("/stop", response_model=ContextOperationResponse, summary="停止上下文")
def stop_context(ctx: ZContext = Depends(get_ctx)):
    """
    停止当前上下文的所有任务

    ## 功能描述
    停止当前运行的所有任务，类似PySide GUI中的停止按钮功能。

    ## 返回数据
    - **success**: 操作是否成功
    - **message**: 操作结果消息
    - **details**: 包含取消的任务数量等信息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/context/stop")
    result = response.json()
    print(f"停止结果: {result['message']}")
    print(f"取消任务数: {result['details']['cancelled_tasks']}")
    ```
    """
    try:
        # 停止上下文运行（类似PySide GUI的实现）
        if hasattr(ctx, 'stop_running'):
            ctx.stop_running()

        # 取消所有相关任务
        statuses = _registry.list_statuses()
        cancelled_count = 0

        for status in statuses:
            if status.status.value in ["pending", "running"]:
                if _registry.cancel(status.runId):
                    cancelled_count += 1

        return ContextOperationResponse(
            success=True,
            message=f"上下文已停止，取消了 {cancelled_count} 个任务",
            details={
                "cancelled_tasks": cancelled_count,
                "stopped_context": True
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "STOP_FAILED",
                    "message": f"停止上下文失败: {str(e)}"
                }
            }
        )


@router.post("/pause", response_model=ContextOperationResponse, summary="暂停上下文")
def pause_context(ctx: ZContext = Depends(get_ctx)):
    """
    暂停当前上下文的执行

    ## 功能描述
    暂停当前正在执行的任务，保持状态以便后续继续。

    ## 返回数据
    - **success**: 操作是否成功
    - **message**: 操作结果消息

    ## 注意事项
    - 暂停功能依赖于具体应用的实现
    - 某些任务可能无法暂停

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/context/pause")
    result = response.json()
    if result['success']:
        print("暂停成功")
    else:
        print(f"暂停失败: {result['message']}")
    ```
    """
    try:
        # 检查是否有暂停方法
        if hasattr(ctx, 'pause_running'):
            ctx.pause_running()
            return ContextOperationResponse(
                success=True,
                message="上下文已暂停",
                details={"paused": True}
            )
        else:
            return ContextOperationResponse(
                success=False,
                message="当前版本不支持暂停功能",
                details={"error_code": "PAUSE_NOT_SUPPORTED"}
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "PAUSE_FAILED",
                    "message": f"暂停上下文失败: {str(e)}"
                }
            }
        )


@router.post("/resume", response_model=ContextOperationResponse, summary="继续上下文")
def resume_context(ctx: ZContext = Depends(get_ctx)):
    """
    继续已暂停的上下文执行

    ## 功能描述
    恢复之前暂停的任务执行。

    ## 返回数据
    - **success**: 操作是否成功
    - **message**: 操作结果消息

    ## 注意事项
    - 继续功能依赖于具体应用的实现
    - 只能继续之前暂停的任务

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/context/resume")
    result = response.json()
    if result['success']:
        print("继续成功")
    else:
        print(f"继续失败: {result['message']}")
    ```
    """
    try:
        # 检查是否有继续方法
        if hasattr(ctx, 'resume_running'):
            ctx.resume_running()
            return ContextOperationResponse(
                success=True,
                message="上下文已继续",
                details={"resumed": True}
            )
        else:
            return ContextOperationResponse(
                success=False,
                message="当前版本不支持继续功能",
                details={"error_code": "RESUME_NOT_SUPPORTED"}
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RESUME_FAILED",
                    "message": f"继续上下文失败: {str(e)}"
                }
            }
        )


@router.get("/status", response_model=ContextStatusResponse, summary="获取上下文状态")
def get_context_status(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前上下文的运行状态

    ## 功能描述
    返回上下文的详细运行状态，类似PySide GUI中的状态检查。

    ## 返回数据
    - **is_running**: 是否有任务在运行
    - **status**: 当前状态（running/idle/paused/error）
    - **message**: 状态描述信息
    - **progress**: 整体进度（0.0-1.0）
    - **running_tasks**: 正在运行的任务数量
    - **pending_tasks**: 等待中的任务数量

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/context/status")
    status = response.json()
    print(f"运行状态: {status['status']}")
    print(f"进度: {status['progress']*100:.1f}%")
    print(f"运行任务数: {status['running_tasks']}")
    ```
    """
    try:
        # 检查上下文运行状态（类似PySide GUI的检查方式）
        is_running = getattr(ctx, 'is_context_running', False)

        # 获取状态文本
        status_text = getattr(ctx, 'context_running_status_text', '')

        # 获取任务统计
        statuses = _registry.list_statuses()
        running_count = sum(1 for s in statuses if s.status.value == "running")
        pending_count = sum(1 for s in statuses if s.status.value == "pending")

        # 判断整体状态
        if is_running or running_count > 0:
            status = "running"
            message = status_text or "上下文运行中"

            # 尝试获取进度信息
            progress = 0.0
            try:
                from zzz_od.api.status_builder import build_onedragon_aggregate
                agg = build_onedragon_aggregate(ctx)
                progress = agg.get('progress', 0.0)
                if progress > 0:
                    message = f"{message} ({int(progress*100)}%)"
            except Exception:
                pass

        elif pending_count > 0:
            status = "pending"
            message = "任务等待中"
            progress = 0.0
        else:
            status = "idle"
            message = "上下文空闲"
            progress = 0.0

        return ContextStatusResponse(
            is_running=is_running or running_count > 0,
            status=status,
            message=message,
            progress=progress,
            running_tasks=running_count,
            pending_tasks=pending_count
        )

    except Exception as e:
        return ContextStatusResponse(
            is_running=False,
            status="error",
            message=f"获取状态失败: {str(e)}",
            progress=0.0,
            running_tasks=0,
            pending_tasks=0
        )
