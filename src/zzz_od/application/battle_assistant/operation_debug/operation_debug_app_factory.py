from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from zzz_od.application.battle_assistant.operation_debug import operation_debug_const
from zzz_od.application.battle_assistant.operation_debug.operation_debug_app import (
    OperationDebugApp,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class OperationDebugAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=operation_debug_const.APP_ID,
            app_name=operation_debug_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return OperationDebugApp(self.ctx)