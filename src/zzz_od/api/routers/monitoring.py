"""
监控和健康检查路由
提供系统监控指标和健康状态查询端点
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from zzz_od.api.monitoring import monitor
from zzz_od.api.security import get_api_key_dependency


router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"], dependencies=[Depends(get_api_key_dependency())])


@router.get("/health", summary="系统健康检查")
async def health_check() -> Dict[str, Any]:
    """
    获取系统整体健康状态，包括：
    - API调用统计
    - WebSocket连接状态
    - 模块运行状态
    - 详细指标数据
    """
    try:
        health_status = await monitor.get_health_status()
        return health_status
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )


@router.get("/metrics/api", summary="API调用指标")
async def get_api_metrics(endpoint: Optional[str] = Query(None, description="特定端点过滤器")) -> Dict[str, Any]:
    """
    获取API调用指标，包括：
    - 请求总数和成功/失败数
    - 响应时间统计
    - 错误率
    - 每分钟请求数
    """
    return {
        "metrics": monitor.get_api_metrics(endpoint),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/metrics/websocket", summary="WebSocket连接指标")
async def get_websocket_metrics(channel: Optional[str] = Query(None, description="特定通道过滤器")) -> Dict[str, Any]:
    """
    获取WebSocket连接指标，包括：
    - 连接总数和活跃连接数
    - 消息发送/接收统计
    - 连接错误数
    - 消息丢弃统计
    """
    return {
        "metrics": monitor.get_websocket_metrics(channel),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/metrics/modules", summary="模块运行指标")
async def get_module_metrics(module: Optional[str] = Query(None, description="特定模块过滤器")) -> Dict[str, Any]:
    """
    获取模块运行指标，包括：
    - 运行总数和成功/失败数
    - 活跃运行数
    - 平均运行时间
    - 最后运行时间
    """
    return {
        "metrics": monitor.get_module_metrics(module),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/status/modules", summary="模块状态概览")
async def get_modules_status() -> Dict[str, Any]:
    """
    获取所有模块的当前运行状态概览
    """
    from zzz_od.api.run_registry import get_global_run_registry

    registry = get_global_run_registry()

    # 获取所有活跃运行
    active_runs = {}
    for run_id, task in registry.runs.items():
        if registry.is_running(run_id):
            status = registry.get_status(run_id)
            module_name = getattr(task, 'module_name', 'unknown')
            active_runs[run_id] = {
                "module": module_name,
                "status": status.dict() if status else None,
                "is_running": True
            }

    # 获取模块运行统计
    module_stats = {}
    for module_name, metrics in monitor.module_metrics.items():
        module_stats[module_name] = {
            "active_runs": metrics.active_runs,
            "total_runs": metrics.total_runs,
            "success_rate": (metrics.successful_runs / metrics.total_runs * 100) if metrics.total_runs > 0 else 0,
            "last_run_time": metrics.last_run_time.isoformat() if metrics.last_run_time else None
        }

    return {
        "active_runs": active_runs,
        "module_statistics": module_stats,
        "total_active_runs": len(active_runs),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/status/websocket", summary="WebSocket连接状态")
async def get_websocket_status() -> Dict[str, Any]:
    """
    获取WebSocket连接的详细状态信息
    """
    from zzz_od.api.ws import manager as ws_manager

    # 获取连接管理器状态
    ws_health = await ws_manager.health_check()

    # 获取详细的通道统计
    channel_details = {}
    for channel, connections in ws_manager.active_connections.items():
        channel_details[channel] = {
            "active_connections": len(connections),
            "connection_objects": len([ws for ws in connections if ws is not None])
        }

    # 获取监控统计
    monitoring_stats = monitor.get_websocket_metrics()

    return {
        "manager_status": ws_health,
        "channel_details": channel_details,
        "monitoring_statistics": monitoring_stats,
        "rate_limiter_status": {
            "active_limiters": len(ws_manager.rate_limiters),
            "connection_filters": len(ws_manager.connection_filters)
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.post("/reset-metrics", summary="重置监控指标")
async def reset_metrics(
    api: bool = Query(False, description="重置API指标"),
    websocket: bool = Query(False, description="重置WebSocket指标"),
    modules: bool = Query(False, description="重置模块指标")
) -> Dict[str, Any]:
    """
    重置指定类型的监控指标（谨慎使用）
    """
    reset_count = 0

    if api:
        monitor.api_metrics.clear()
        monitor.request_timestamps.clear()
        reset_count += 1

    if websocket:
        monitor.websocket_metrics.clear()
        reset_count += 1

    if modules:
        monitor.module_metrics.clear()
        reset_count += 1

    return {
        "message": f"已重置 {reset_count} 类指标",
        "reset_api": api,
        "reset_websocket": websocket,
        "reset_modules": modules,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }