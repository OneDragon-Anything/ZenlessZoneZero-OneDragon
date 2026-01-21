from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from zzz_od.application.inventory_scan import inventory_scan_const
from zzz_od.application.inventory_scan.inventory_scan_app import InventoryScanApp
from zzz_od.application.inventory_scan.inventory_scan_config import InventoryScanConfig

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class InventoryScanAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=inventory_scan_const.APP_ID,
            app_name=inventory_scan_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return InventoryScanApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        return InventoryScanConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )
