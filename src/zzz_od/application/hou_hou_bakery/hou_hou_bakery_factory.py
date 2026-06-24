from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.hou_hou_bakery import hou_hou_bakery_const
from zzz_od.application.hou_hou_bakery.hou_hou_bakery_app import HouHouBakeryApp
from zzz_od.application.hou_hou_bakery.hou_hou_bakery_run_record import (
    HouHouBakeryRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class HouHouBakeryFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(self, hou_hou_bakery_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return HouHouBakeryApp(self.ctx)

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return HouHouBakeryRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
