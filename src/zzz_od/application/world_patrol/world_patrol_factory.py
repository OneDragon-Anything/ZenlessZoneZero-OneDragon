from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.world_patrol import world_patrol_const
from zzz_od.application.world_patrol.world_patrol_app import WorldPatrolApp
from zzz_od.application.world_patrol.world_patrol_config import WorldPatrolConfig
from zzz_od.application.world_patrol.world_patrol_run_record import WorldPatrolRunRecord

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class WorldPatrolAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=world_patrol_const.APP_ID,
            app_name=world_patrol_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return WorldPatrolApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return WorldPatrolConfig(
            instance_idx=instance_idx,
            group_id=group_id
        )

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return WorldPatrolRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
