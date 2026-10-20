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

    @property
    def scan_drive_disk(self) -> bool:
        """是否扫描驱动盘"""
        return self.get('scan_drive_disk', True)

    @scan_drive_disk.setter
    def scan_drive_disk(self, new_value: bool) -> None:
        self.update('scan_drive_disk', new_value)

    @property
    def scan_wengine(self) -> bool:
        """是否扫描音擎"""
        return self.get('scan_wengine', True)

    @scan_wengine.setter
    def scan_wengine(self, new_value: bool) -> None:
        self.update('scan_wengine', new_value)

    @property
    def scan_agent(self) -> bool:
        """是否扫描代理人"""
        return self.get('scan_agent', True)

    @scan_agent.setter
    def scan_agent(self, new_value: bool) -> None:
        self.update('scan_agent', new_value)
