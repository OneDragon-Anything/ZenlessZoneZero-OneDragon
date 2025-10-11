from __future__ import annotations

from typing import Callable

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import Capabilities
from zzz_od.api.unified_controller import UnifiedController


class OneDragonController(UnifiedController):
    """一条龙模块的统一控制器"""

    def __init__(self):
        super().__init__("onedragon")

    def get_capabilities(self) -> Capabilities:
        """一条龙模块支持暂停/恢复"""
        return Capabilities(
            canPause=True,
            canResume=True
        )

    def create_app_factory(self) -> Callable:
        """创建一条龙应用工厂函数"""
        def factory():
            from zzz_od.application.one_dragon_app.zzz_one_dragon_app import ZOneDragonApp
            ctx = get_ctx()
            return ZOneDragonApp(ctx)

        return factory
