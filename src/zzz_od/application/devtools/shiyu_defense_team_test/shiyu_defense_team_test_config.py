from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.game_data.agent import DmgTypeEnum

if TYPE_CHECKING:
    from zzz_od.application.shiyu_defense.shiyu_defense_team_utils import (
        DefensePhaseTeamInfo,
    )


class ShiyuDefenseTeamTestConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id='shiyu_defense_team_test',
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def target_count(self) -> int:
        return self.get('target_count', 1)

    @target_count.setter
    def target_count(self, new_value: int) -> None:
        self.update('target_count', new_value)

    def get_target_dmg_type(
        self,
        target_idx: int,
        is_weakness: bool,
        type_idx: int,
    ) -> str:
        key = self._get_target_dmg_type_key(target_idx, is_weakness, type_idx)
        return self.get(key, '')

    def set_target_dmg_type(
        self,
        target_idx: int,
        is_weakness: bool,
        type_idx: int,
        new_value: str,
    ) -> None:
        key = self._get_target_dmg_type_key(target_idx, is_weakness, type_idx)
        self.update(key, new_value)

    def get_target_list(self) -> list['DefensePhaseTeamInfo']:
        from zzz_od.application.shiyu_defense.shiyu_defense_team_utils import (
            DefensePhaseTeamInfo,
        )

        target_list: list[DefensePhaseTeamInfo] = []
        for target_idx in range(min(max(self.target_count, 1), 3)):
            weakness_list = self._get_target_dmg_type_list(target_idx, True)
            resistance_list = self._get_target_dmg_type_list(target_idx, False)
            target_list.append(DefensePhaseTeamInfo(weakness_list, resistance_list))
        return target_list

    def _get_target_dmg_type_list(
        self,
        target_idx: int,
        is_weakness: bool,
    ) -> list[DmgTypeEnum]:
        result: list[DmgTypeEnum] = []
        for type_idx in range(2):
            dmg_type = DmgTypeEnum.from_name(
                self.get_target_dmg_type(target_idx, is_weakness, type_idx)
            )
            if dmg_type != DmgTypeEnum.UNKNOWN:
                result.append(dmg_type)
        return result

    @staticmethod
    def _get_target_dmg_type_key(
        target_idx: int,
        is_weakness: bool,
        type_idx: int,
    ) -> str:
        type_name = 'weakness' if is_weakness else 'resistance'
        return f'target_{target_idx + 1}_{type_name}_{type_idx + 1}'
