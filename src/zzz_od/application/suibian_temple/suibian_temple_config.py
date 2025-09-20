from enum import StrEnum

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
    def adventure_duration(self) -> str:
        """游历-时间"""
        return self.get('adventure_duration', SuibianTempleAdventureDispatchDuration.HOUR_20.name)

    @adventure_duration.setter
    def adventure_duration(self, value: str):
        self.update('adventure_duration', value)

    @property
    def adventure_mission_1(self) -> str:
        """游历-任务1"""
        return self.get('adventure_mission', SuibianTempleAdventureMission.RESEARCH_3_4.name)

    @adventure_mission_1.setter
    def adventure_mission_1(self, value: str):
        self.update('adventure_mission', value)

    @property
    def adventure_mission_2(self) -> str:
        """游历-任务2"""
        return self.get('adventure_mission', SuibianTempleAdventureMission.RESEARCH_2_4.name)

    @adventure_mission_2.setter
    def adventure_mission_2(self, value: str):
        self.update('adventure_mission', value)

    @property
    def adventure_mission_3(self) -> str:
        """游历-任务3"""
        return self.get('adventure_mission', SuibianTempleAdventureMission.RESEARCH_1_4.name)

    @adventure_mission_3.setter
    def adventure_mission_3(self, value: str):
        self.update('adventure_mission', value)

    @property
    def adventure_mission_4(self) -> str:
        """游历-任务4"""
        return self.get('adventure_mission', SuibianTempleAdventureMission.COMMUNITY_3_4.name)

    @adventure_mission_4.setter
    def adventure_mission_4(self, value: str):
        self.update('adventure_mission', value)


class SuibianTempleAdventureMission(StrEnum):

    CRAFT_1_1 = '制造区1-1'
    CRAFT_1_2 = '制造区1-2'
    CRAFT_1_3 = '制造区1-3'
    CRAFT_1_4 = "制造区1-4"

    CRAFT_2_1 = '制造区2-1'
    CRAFT_2_2 = '制造区2-2'
    CRAFT_2_3 = '制造区2-3'
    CRAFT_2_4 = "制造区2-4"

    CRAFT_3_1 = '制造区3-1'
    CRAFT_3_2 = '制造区3-2'
    CRAFT_3_3 = '制造区3-3'
    CRAFT_3_4 = "制造区3-4"

    COMMUNITY_1_1 = '社区旧址1-1'
    COMMUNITY_1_2 = '社区旧址1-2'
    COMMUNITY_1_3 = '社区旧址1-3'
    COMMUNITY_1_4 = "社区旧址1-4"

    COMMUNITY_2_1 = '社区旧址2-1'
    COMMUNITY_2_2 = '社区旧址2-2'
    COMMUNITY_2_3 = '社区旧址2-3'
    COMMUNITY_2_4 = "社区旧址2-4"

    COMMUNITY_3_1 = '社区旧址3-1'
    COMMUNITY_3_2 = '社区旧址3-2'
    COMMUNITY_3_3 = '社区旧址3-3'
    COMMUNITY_3_4 = "社区旧址3-4"

    RESEARCH_1_1 = '科研院旧址1-1'
    RESEARCH_1_2 = '科研院旧址1-2'
    RESEARCH_1_3 = '科研院旧址1-3'
    RESEARCH_1_4 = "科研院旧址1-4"

    RESEARCH_2_1 = '科研院旧址2-1'
    RESEARCH_2_2 = '科研院旧址2-2'
    RESEARCH_2_3 = '科研院旧址2-3'
    RESEARCH_2_4 = "科研院旧址2-4"

    RESEARCH_3_1 = '科研院旧址3-1'
    RESEARCH_3_2 = '科研院旧址3-2'
    RESEARCH_3_3 = '科研院旧址3-3'
    RESEARCH_3_4 = "科研院旧址3-4"
