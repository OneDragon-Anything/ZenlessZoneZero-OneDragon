"""Native opt-in discovery factory; calibration never enabled by discovery."""

from typing import Any

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.application.inventory_inspection import inventory_inspection_app_const
from zzz_od.application.inventory_inspection.inventory_inspection_app import (
    InventoryInspectionApplication,
)


class InventoryInspectionAppFactory(ApplicationFactory):
    standalone_selectable = True

    def __init__(self, ctx: Any) -> None:
        super().__init__(inventory_inspection_app_const)
        self.ctx = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Any:
        if instance_idx != self.ctx.current_instance_idx:
            raise ValueError('仓库检查账号实例与当前助手不一致')
        return InventoryInspectionApplication(self.ctx)

    def create_config(self, instance_idx: int, group_id: str) -> Any:
        return None

    def create_run_record(self, instance_idx: int) -> Any:
        return None
