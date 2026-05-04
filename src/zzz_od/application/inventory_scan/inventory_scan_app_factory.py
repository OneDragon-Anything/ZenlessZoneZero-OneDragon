from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from zzz_od.application.inventory_scan import inventory_scan_const
from zzz_od.application.inventory_scan.inventory_scan_app import InventoryScanApp

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class InventoryScanAppFactory(ApplicationFactory):
    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(self, inventory_scan_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return InventoryScanApp(self.ctx)
