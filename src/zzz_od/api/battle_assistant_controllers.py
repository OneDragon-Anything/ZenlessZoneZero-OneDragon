"""
战斗助手模块的统一控制器实现
"""
from typing import Callable

from zzz_od.api.unified_controller import UnifiedController
from zzz_od.api.models import Capabilities


class AutoBattleController(UnifiedController):
    """自动战斗控制器"""

    def __init__(self):
        super().__init__("battle-assistant-auto-battle")

    def get_capabilities(self) -> Capabilities:
        """自动战斗支持暂停和恢复"""
        return Capabilities(
            canPause=True,
            canResume=True
        )

    def create_app_factory(self) -> Callable:
        """创建自动战斗应用工厂"""
        def factory():
            from zzz_od.application.battle_assistant.auto_battle_app import AutoBattleApp
            from zzz_od.api.deps import get_ctx
            ctx = get_ctx()
            return AutoBattleApp(ctx)
        return factory


class DodgeController(UnifiedController):
    """闪避助手控制器"""

    def __init__(self):
        super().__init__("battle-assistant-dodge")

    def get_capabilities(self) -> Capabilities:
        """闪避助手支持暂停和恢复"""
        return Capabilities(
            canPause=True,
            canResume=True
        )

    def create_app_factory(self) -> Callable:
        """创建闪避助手应用工厂"""
        def factory():
            from zzz_od.application.battle_assistant.dodge_assitant.dodge_assistant_app import DodgeAssistantApp
            from zzz_od.api.deps import get_ctx
            ctx = get_ctx()
            return DodgeAssistantApp(ctx)
        return factory


class OperationDebugController(UnifiedController):
    """指令调试控制器"""

    def __init__(self):
        super().__init__("battle-assistant-operation-debug")

    def get_capabilities(self) -> Capabilities:
        """指令调试支持暂停和恢复"""
        return Capabilities(
            canPause=True,
            canResume=True
        )

    def create_app_factory(self) -> Callable:
        """创建指令调试应用工厂"""
        def factory():
            from zzz_od.application.battle_assistant.operation_debug_app import OperationDebugApp
            from zzz_od.api.deps import get_ctx
            ctx = get_ctx()
            return OperationDebugApp(ctx)
        return factory


# 全局控制器实例
auto_battle_controller = AutoBattleController()
dodge_controller = DodgeController()
operation_debug_controller = OperationDebugController()