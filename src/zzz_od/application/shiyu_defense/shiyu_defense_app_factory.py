from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.shiyu_defense import shiyu_defense_const
from zzz_od.application.shiyu_defense.shiyu_defense_app import ShiyuDefenseApp
from zzz_od.application.shiyu_defense.shiyu_defense_config import ShiyuDefenseConfig
from zzz_od.application.shiyu_defense.shiyu_defense_run_record import (
    ShiyuDefenseRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ShiyuDefenseAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=shiyu_defense_const.APP_ID,
            app_name=shiyu_defense_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return ShiyuDefenseApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return ShiyuDefenseConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return ShiyuDefenseRunRecord(
            config=self.get_config(
                instance_idx=instance_idx,
                group_id=application_const.DEFAULT_GROUP_ID,
            ),
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )