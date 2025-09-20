from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

from fastapi import HTTPException

from zzz_od.api.models import ControlResponse, StatusResponse, Capabilities, LogReplayResponse, LogReplayEntry
from zzz_od.api.run_registry import RunRegistry, get_global_run_registry
from zzz_od.api.unified_event_bridge import attach_unified_event_bridge
from zzz_od.api.monitoring import monitor
from zzz_od.api.log_storage import get_global_log_storage


class UnifiedController(ABC):
    """统一控制器基类，提供标准的运行控制接口"""

    def __init__(self, module_name: str, registry: Optional[RunRegistry] = None):
        self.module_name = module_name
        self.registry = registry or get_global_run_registry()
        self.current_run_id: Optional[str] = None

    @abstractmethod
    def get_capabilities(self) -> Capabilities:
        """获取模块能力标识"""
        pass

    @abstractmethod
    def create_app_factory(self) -> Callable:
        """创建应用工厂函数"""
        pass

    async def start(self, ctx=None) -> ControlResponse:
        """启动模块运行"""
        start_time = time.time()

        # 检查是否已经在运行
        current_run_id = self.registry.get_current_run_id(self.module_name)
        if current_run_id and self.registry.is_running(current_run_id):
            # 幂等性处理：已运行时返回409或200+相同runId
            return ControlResponse(
                ok=True,
                message="模块已在运行中",
                runId=current_run_id,
                capabilities=self.get_capabilities()
            )

        try:
            # 获取上下文
            if ctx is None:
                from zzz_od.api.deps import get_ctx
                ctx = get_ctx()

            # 创建任务工厂
            app_factory = self.create_app_factory()

            def _factory() -> asyncio.Task:
                async def runner():
                    loop = asyncio.get_running_loop()

                    def _exec():
                        app = app_factory()
                        app.execute()

                    await loop.run_in_executor(None, _exec)

                return asyncio.create_task(runner())

            # 为模块创建运行实例
            run_id = self.registry.create_for_module(self.module_name, _factory)
            self.current_run_id = run_id

            # 附加统一事件桥接器
            attach_unified_event_bridge(ctx, run_id, self.module_name)

            # 记录模块启动事件
            monitor.record_module_event(self.module_name, "start", run_id=run_id)

            return ControlResponse(
                ok=True,
                message="模块启动成功",
                runId=run_id,
                capabilities=self.get_capabilities()
            )

        except Exception as e:
            # 记录启动失败事件
            monitor.record_module_event(
                self.module_name, "failed",
                error=str(e),
                duration=time.time() - start_time
            )
            raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")

    async def stop(self) -> ControlResponse:
        """停止模块运行"""
        current_run_id = self.registry.get_current_run_id(self.module_name)

        if not current_run_id or not self.registry.is_running(current_run_id):
            # 幂等性处理：stop在idle时返回200+容忍式消息
            return ControlResponse(
                ok=True,
                message="模块未在运行或已停止",
                capabilities=self.get_capabilities()
            )

        try:
            success = self.registry.cancel(current_run_id)
            if success:
                self.registry.cleanup_module_run(self.module_name)
                self.current_run_id = None

                # 记录模块停止事件
                monitor.record_module_event(self.module_name, "complete", run_id=current_run_id)

                return ControlResponse(
                    ok=True,
                    message="模块停止成功",
                    capabilities=self.get_capabilities()
                )
            else:
                # 记录停止失败事件
                monitor.record_module_event(
                    self.module_name, "failed",
                    run_id=current_run_id,
                    error="停止失败，任务可能已完成"
                )
                return ControlResponse(
                    ok=False,
                    message="停止失败，任务可能已完成",
                    capabilities=self.get_capabilities()
                )

        except Exception as e:
            # 记录停止异常事件
            monitor.record_module_event(
                self.module_name, "failed",
                run_id=current_run_id,
                error=str(e)
            )
            raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")

    async def pause(self) -> ControlResponse:
        """暂停模块运行"""
        capabilities = self.get_capabilities()
        if not capabilities.canPause:
            raise HTTPException(
                status_code=405,
                detail="该模块不支持暂停操作"
            )

        current_run_id = self.registry.get_current_run_id(self.module_name)
        if not current_run_id or not self.registry.is_running(current_run_id):
            return ControlResponse(
                ok=True,
                message="模块未在运行，无需暂停",
                capabilities=capabilities
            )

        try:
            # 获取上下文并调用暂停方法
            from zzz_od.api.deps import get_ctx
            ctx = get_ctx()

            if not ctx.is_context_running:
                return ControlResponse(
                    ok=True,
                    message="上下文未在运行，无需暂停",
                    capabilities=capabilities
                )

            # 调用上下文的暂停方法
            ctx.switch_context_pause_and_run()

            return ControlResponse(
                ok=True,
                message="模块暂停成功",
                runId=current_run_id,
                capabilities=capabilities
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"暂停失败: {str(e)}")

    async def resume(self) -> ControlResponse:
        """恢复模块运行"""
        capabilities = self.get_capabilities()
        if not capabilities.canResume:
            raise HTTPException(
                status_code=405,
                detail="该模块不支持恢复操作"
            )

        current_run_id = self.registry.get_current_run_id(self.module_name)
        if not current_run_id or not self.registry.is_running(current_run_id):
            return ControlResponse(
                ok=True,
                message="模块未在运行，无需恢复",
                capabilities=capabilities
            )

        try:
            # 获取上下文并调用恢复方法
            from zzz_od.api.deps import get_ctx
            ctx = get_ctx()

            if not ctx.is_context_pause:
                return ControlResponse(
                    ok=True,
                    message="上下文未暂停，无需恢复",
                    capabilities=capabilities
                )

            # 调用上下文的恢复方法
            ctx.switch_context_pause_and_run()

            return ControlResponse(
                ok=True,
                message="模块恢复成功",
                runId=current_run_id,
                capabilities=capabilities
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

    async def status(self) -> StatusResponse:
        """获取模块状态"""
        current_run_id = self.registry.get_current_run_id(self.module_name)
        is_running = False
        context_state = "idle"
        message = None
        running_tasks = None

        if current_run_id:
            is_running = self.registry.is_running(current_run_id)
            if is_running:
                context_state = "running"
                # 获取运行状态详情
                status_response = self.registry.get_status(current_run_id)
                if status_response:
                    message = status_response.message
                    # 可以根据需要设置running_tasks

        return StatusResponse(
            is_running=is_running,
            context_state=context_state,
            running_tasks=running_tasks,
            message=message,
            runId=current_run_id,
            capabilities=self.get_capabilities()
        )

    async def get_logs(self, runId: Optional[str] = None, tail: int = 1000) -> LogReplayResponse:
        """获取运行日志回放"""
        # 限制tail参数范围
        if tail <= 0:
            tail = 1000
        elif tail > 2000:
            tail = 2000

        # 确定要查询的runId
        target_run_id = runId
        if not target_run_id:
            target_run_id = self.registry.get_current_run_id(self.module_name)

        if not target_run_id:
            return LogReplayResponse(
                logs=[],
                total_count=0,
                runId="",
                module=self.module_name,
                has_more=False,
                message="未找到运行记录"
            )

        # 从日志存储中获取日志
        log_storage = get_global_log_storage()
        log_entries = log_storage.get_logs(target_run_id, tail)

        # 转换为响应格式
        replay_entries = [
            LogReplayEntry(
                timestamp=entry.timestamp,
                level=entry.level,
                message=entry.message,
                runId=entry.runId,
                module=entry.module,
                seq=entry.seq,
                extra=entry.extra
            )
            for entry in log_entries
        ]

        return LogReplayResponse(
            logs=replay_entries,
            total_count=len(replay_entries),
            runId=target_run_id,
            module=self.module_name,
            has_more=False,
            message=f"返回最近 {len(replay_entries)} 条日志" if replay_entries else "暂无日志记录"
        )