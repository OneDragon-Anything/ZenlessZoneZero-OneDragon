from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.logistics_shop import logistics_shop_const
from zzz_od.application.logistics_shop.logistics_shop_app import LogisticsShopApp
from zzz_od.application.logistics_shop.logistics_shop_config import LogisticsShopConfig
from zzz_od.application.logistics_shop.logistics_shop_run_record import (
    LogisticsShopRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class LogisticsShopFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(self, logistics_shop_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return LogisticsShopApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        return LogisticsShopConfig(instance_idx, group_id)

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return LogisticsShopRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
