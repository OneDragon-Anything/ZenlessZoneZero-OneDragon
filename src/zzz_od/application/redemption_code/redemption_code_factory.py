from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.redemption_code.redemption_code_app import RedemptionCodeApp
from zzz_od.application.redemption_code.redemption_code_run_record import (
    RedemptionCodeRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class RedemptionCodeFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id="redemption_code",
            app_name="兑换码",
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return RedemptionCodeApp(self.ctx)

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return RedemptionCodeRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
