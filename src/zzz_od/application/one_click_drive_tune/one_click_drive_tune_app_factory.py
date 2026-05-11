from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord

from zzz_od.application.one_click_drive_tune import one_click_drive_tune_const
from zzz_od.application.one_click_drive_tune.one_click_drive_tune_app import (
    OneClickDriveTuneApp,
)
from zzz_od.application.one_click_drive_tune.one_click_drive_tune_config import (
    OneClickDriveTuneConfig,
)
from zzz_od.application.one_click_drive_tune.one_click_drive_tune_run_record import (
    OneClickDriveTuneRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class OneClickDriveTuneAppFactory(ApplicationFactory):
    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(self, one_click_drive_tune_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return OneClickDriveTuneApp(self.ctx)

    def create_config(self, instance_idx: int, group_id: str) -> ApplicationConfig:
        return OneClickDriveTuneConfig(instance_idx=instance_idx, group_id=group_id)

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return OneClickDriveTuneRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
