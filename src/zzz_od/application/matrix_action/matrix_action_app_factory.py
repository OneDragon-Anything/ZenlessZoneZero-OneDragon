from __future__ import annotations

from typing import TYPE_CHECKING, cast

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.matrix_action import matrix_action_const
from zzz_od.application.matrix_action.matrix_action_app import MatrixActionApp
from zzz_od.application.matrix_action.matrix_action_config import MatrixActionConfig
from zzz_od.application.matrix_action.matrix_action_run_record import (
    MatrixActionRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class MatrixActionAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=matrix_action_const.APP_ID,
            app_name=matrix_action_const.APP_NAME,
            default_group=matrix_action_const.DEFAULT_GROUP,
            need_notify=matrix_action_const.NEED_NOTIFY,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return MatrixActionApp(self.ctx)

    def create_config(
        self,
        instance_idx: int,
        group_id: str,
    ) -> ApplicationConfig:
        return MatrixActionConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return MatrixActionRunRecord(
            config=cast(
                MatrixActionConfig,
                self.get_config(
                    instance_idx=instance_idx,
                    group_id=application_const.DEFAULT_GROUP_ID,
                ),
            ),
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
