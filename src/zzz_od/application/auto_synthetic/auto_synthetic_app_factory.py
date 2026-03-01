from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.auto_synthetic import auto_synthetic_const
from zzz_od.application.auto_synthetic.auto_synthetic_app import AutoSyntheticApp
from zzz_od.application.auto_synthetic.auto_synthetic_config import AutoSyntheticConfig
from zzz_od.application.auto_synthetic.auto_synthetic_run_record import AutoSyntheticRunRecord

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class AutoSyntheticAppFactory(ApplicationFactory):
    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=auto_synthetic_const.APP_ID,
            app_name=auto_synthetic_const.APP_NAME,
            default_group=auto_synthetic_const.DEFAULT_GROUP,
            need_notify=auto_synthetic_const.NEED_NOTIFY,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return AutoSyntheticApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        return AutoSyntheticConfig(
            instance_idx=instance_idx,
            group_id=group_id
        )

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return AutoSyntheticRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )