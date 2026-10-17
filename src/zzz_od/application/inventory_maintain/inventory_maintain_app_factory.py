from typing import Any

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.application.inventory_maintain import inventory_maintain_app_const
from zzz_od.application.inventory_maintain.inventory_maintain_app import (
    InventoryMaintainApplication,
)


class InventoryMaintainAppFactory(ApplicationFactory):
    standalone_selectable = True

    def __init__(self, ctx: Any) -> None:
        super().__init__(inventory_maintain_app_const)
        self.ctx = ctx

    def create_application(self, instance_idx: Any, group_id: Any) -> Any:
        if instance_idx != self.ctx.current_instance_idx:
            raise ValueError('库存保持账号实例与当前助手不一致')
        return InventoryMaintainApplication(self.ctx)

    def create_config(self, instance_idx: Any, group_id: Any) -> Any:
        return None

    def create_run_record(self, instance_idx: Any) -> Any:
        return None
