from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.scratch_card.scratch_card_app import ScratchCardApp
from zzz_od.application.scratch_card.scratch_card_run_record import ScratchCardRunRecord

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ScratchCardFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id="scratch_card",
            app_name="刮刮卡"
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return ScratchCardApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return None

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return ScratchCardRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
