from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.random_play.random_play_app import RandomPlayApp
from zzz_od.application.random_play.random_play_config import RandomPlayConfig
from zzz_od.application.random_play.random_play_run_record import (
    RandomPlayRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class RandomPlayFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id="random_play",
            app_name="录像店营业"
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return RandomPlayApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return RandomPlayConfig(
            instance_idx=instance_idx,
            group_id=group_id
        )

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return RandomPlayRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )