from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.application.notorious_hunt.notorious_hunt_app import NotoriousHuntApp
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig
from zzz_od.application.notorious_hunt.notorious_hunt_run_record import (
    NotoriousHuntRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class NotoriousHuntAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=notorious_hunt_const.APP_ID,
            app_name=notorious_hunt_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return NotoriousHuntApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return NotoriousHuntConfig(
            instance_idx=instance_idx,
            group_id=group_id
        )

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return NotoriousHuntRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )