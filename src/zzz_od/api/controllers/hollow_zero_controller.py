from __future__ import annotations

from typing import Callable

from zzz_od.api.models import Capabilities
from zzz_od.api.unified_controller import UnifiedController
from zzz_od.api.deps import get_ctx


class HollowZeroController(UnifiedController):
    """空洞零号（枯萎之都）统一控制器"""

    def __init__(self):
        super().__init__("hollow_zero")

    def get_capabilities(self) -> Capabilities:
        """空洞零号支持暂停/恢复功能"""
        return Capabilities(
            canPause=True,
            canResume=True
        )

    def create_app_factory(self) -> Callable:
        """创建空洞零号应用工厂函数"""
        def factory():
            ctx = get_ctx()
            # 设置临时运行清单为空洞零号
            ctx.one_dragon_app_config.set_temp_app_run_list(["hollow_zero"])

            from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
            return ZOneDragonApp(ctx)

        return factory


class LostVoidController(UnifiedController):
    """迷失之地统一控制器"""

    def __init__(self):
        super().__init__("lost_void")

    def get_capabilities(self) -> Capabilities:
        """迷失之地支持暂停/恢复功能"""
        return Capabilities(
            canPause=True,
            canResume=True
        )

    def create_app_factory(self) -> Callable:
        """创建迷失之地应用工厂函数"""
        def factory():
            ctx = get_ctx()
            # 设置临时运行清单为迷失之地
            ctx.one_dragon_app_config.set_temp_app_run_list(["lost_void"])

            from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
            return ZOneDragonApp(ctx)

        return factory