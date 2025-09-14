from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_dispatch import \
    SuibianTempleAdventureDispatchDuration


class SuibianTempleConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(self, 'suibian_temple', instance_idx, group_id)

    @property
    def yum_cha_sin(self) -> bool:
        """饮茶仙-开关"""
        return self.get('yum_cha_sin', True)

    @yum_cha_sin.setter
    def yum_cha_sin(self, value: bool):
        self.update('yum_cha_sin', value)

    @property
    def yum_cha_sin_period_refresh(self) -> bool:
        """饮茶仙-定期采办-是否刷新"""
        return self.get('yum_cha_sin_period_refresh', True)

    @yum_cha_sin_period_refresh.setter
    def yum_cha_sin_period_refresh(self, value: bool):
        self.update('yum_cha_sin_period_refresh', value)

    @property
    def squad_duration(self) -> str:
        """游历-时间"""
        return self.get('squad_duration', SuibianTempleAdventureDispatchDuration.HOUR_20.name)

    @squad_duration.setter
    def squad_duration(self, value: str):
        self.update('squad_duration', value)