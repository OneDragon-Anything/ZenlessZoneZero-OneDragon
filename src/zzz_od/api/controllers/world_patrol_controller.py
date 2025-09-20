from __future__ import annotations

from typing import Callable

from zzz_od.api.models import Capabilities
from zzz_od.api.unified_controller import UnifiedController
from zzz_od.api.deps import get_ctx
from zzz_od.application.world_patrol.world_patrol_app import WorldPatrolApp


class WorldPatrolController(UnifiedController):
    """锄大地模块统一控制器"""

    def __init__(self):
        super().__init__("world_patrol")

    def get_capabilities(self) -> Capabilities:
        """获取模块能力标识 - 锄大地支持暂停/恢复"""
        return Capabilities(
            canPause=True,
            canResume=True
        )

    def create_app_factory(self) -> Callable:
        """创建锄大地应用工厂函数"""
        def factory():
            ctx = get_ctx()
            return WorldPatrolApp(ctx)

        return factory