from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from zzz_od.application.commission_processing import commission_processing_const
from zzz_od.application.commission_processing.commission_processing_app import (
    CommissionProcessingApp,
)
from zzz_od.application.commission_processing.commission_processing_config import (
    CommissionProcessingConfig,
)
from zzz_od.application.commission_processing.commission_processing_run_record import (
    CommissionProcessingRunRecord,
)
from one_dragon.base.operation.application_run_record import AppRunRecord

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class CommissionProcessingAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=commission_processing_const.APP_ID,
            app_name=commission_processing_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return CommissionProcessingApp(
            self.ctx,
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset
        )

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        return CommissionProcessingConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return CommissionProcessingRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
