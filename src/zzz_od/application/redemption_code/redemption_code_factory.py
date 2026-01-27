from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.redemption_code import redemption_code_const
from zzz_od.application.redemption_code.redemption_code_app import RedemptionCodeApp
from zzz_od.application.redemption_code.redemption_code_config import RedemptionCodeConfig
from zzz_od.application.redemption_code.redemption_code_run_record import (
    RedemptionCodeRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class RedemptionCodeFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=redemption_code_const.APP_ID,
            app_name=redemption_code_const.APP_NAME,
            need_notify=redemption_code_const.NEED_NOTIFY,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return RedemptionCodeApp(self.ctx)

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return RedemptionCodeRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )

    def create_config(self, instance_idx: int, group_id: str) -> RedemptionCodeConfig:
        """创建兑换码配置

        注意：兑换码配置是全局配置，不依赖于instance_idx和group_id
        这里的参数只是为了符合ApplicationFactory的接口要求
        """
        return RedemptionCodeConfig()
