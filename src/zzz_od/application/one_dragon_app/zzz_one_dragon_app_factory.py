from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from zzz_od.application.one_dragon_app.zzz_one_dragon_app import ZOneDragonApp

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ZzzOneDragonAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=application_const.ONE_DRAGON_APP_ID,
            app_name=application_const.ONE_DRAGON_APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return ZOneDragonApp(self.ctx)
