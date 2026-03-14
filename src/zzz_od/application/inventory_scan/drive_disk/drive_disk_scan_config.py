from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.inventory_scan.drive_disk import drive_disk_scan_const


class DriveDiskScanConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=drive_disk_scan_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )