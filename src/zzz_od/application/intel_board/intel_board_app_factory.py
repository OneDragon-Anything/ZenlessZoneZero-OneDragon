from __future__ import annotations

from typing import TYPE_CHECKING, cast

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.intel_board import intel_board_const
from zzz_od.application.intel_board.intel_board_app import (
    IntelBoardApp,
)
from zzz_od.application.intel_board.intel_board_config import (
    IntelBoardConfig,
)
from zzz_od.application.intel_board.intel_board_run_record import (
    IntelBoardRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class IntelBoardAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=intel_board_const.APP_ID,
            app_name=intel_board_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return IntelBoardApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        return IntelBoardConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return IntelBoardRunRecord(
            config=cast(IntelBoardConfig, self.get_config(
                instance_idx=instance_idx,
                group_id=application_const.DEFAULT_GROUP_ID
            )),
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
