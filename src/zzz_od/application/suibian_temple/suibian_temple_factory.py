from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.suibian_temple.suibian_temple_app import SuibianTempleApp
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.application.suibian_temple.suibian_temple_run_record import (
    SuibianTempleRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class SuibianTempleFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id="suibian_temple",
            app_name='随便观',
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return SuibianTempleApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return SuibianTempleConfig(instance_idx, group_id)

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return SuibianTempleRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )