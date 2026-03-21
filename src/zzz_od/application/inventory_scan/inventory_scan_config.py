from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.inventory_scan import inventory_scan_const


class InventoryScanConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=inventory_scan_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )
