from __future__ import annotations

from functools import cached_property, lru_cache
from typing import Optional
from typing import TYPE_CHECKING

from one_dragon.base.conditional_operation.state_record_service import StateRecordService
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum
from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum, CommonAgentStateEnum
from zzz_od.game_data.target_state import DETECTION_TASKS

if TYPE_CHECKING:
    pass


class AutoBattleStateRecordService(StateRecordService):

    def __init__(self):
        super().__init__()

    @lru_cache(maxsize=None)
    def get_state_recorder(self, state_name: str) -> Optional[StateRecorder]:
        """
        获取状态记录器

        Args:
            state_name: 状态名称

        Returns:
            状态记录器
        """
        if self.is_valid_state(state_name):
            return StateRecorder(state_name, mutex_list=self.mutex_list.get(state_name, None))
        else:
            log.error(f'使用了不合法的状态 {state_name}')
            return None

    @lru_cache(maxsize=None)
    def is_valid_state(self, state_name: str) -> bool:
        """
        判断一个状态是否合法

        Args:
            state_name: 状态名称

        Returns:
            bool: 是否合法
        """
        if state_name in self.all_state_event_ids:
            return True
        elif state_name.startswith('自定义-'):
            return True
        else:
            return False

    @cached_property
    def all_state_event_ids(self) -> list[str]:
        """
        目前可用的状态事件ID
        """
        event_ids = []

        for event_enum in YoloStateEventEnum:
            event_ids.append(event_enum.value)

        for event_enum in BattleStateEnum:
            event_ids.append(event_enum.value)
            event_ids.append(event_enum.value + '-松开')
            event_ids.append(event_enum.value + '-按下')

        for agent_enum in AgentEnum:
            agent = agent_enum.value
            agent_name = agent.agent_name
            event_ids.append(f'前台-{agent_name}')
            event_ids.append(f'后台-{agent_name}')
            event_ids.append(f'后台-1-{agent_name}')
            event_ids.append(f'后台-2-{agent_name}')
            event_ids.append(f'连携技-1-{agent_name}')
            event_ids.append(f'连携技-2-{agent_name}')
            event_ids.append(f'快速支援-{agent_name}')
            event_ids.append(f'切换角色-{agent_name}')
            event_ids.append(f'{agent_name}-能量')
            event_ids.append(f'{agent_name}-特殊技可用')
            event_ids.append(f'{agent_name}-终结技可用')

            if agent.state_list is not None:
                for state in agent.state_list:
                    event_ids.append(state.state_name)

        for agent_type_enum in AgentTypeEnum:
            if agent_type_enum == AgentTypeEnum.UNKNOWN:
                continue
            event_ids.append('前台-' + agent_type_enum.value)
            event_ids.append('后台-1-' + agent_type_enum.value)
            event_ids.append('后台-2-' + agent_type_enum.value)
            event_ids.append('连携技-1-' + agent_type_enum.value)
            event_ids.append('连携技-2-' + agent_type_enum.value)
            event_ids.append('快速支援-' + agent_type_enum.value)
            event_ids.append('切换角色-' + agent_type_enum.value)

        for state_enum in CommonAgentStateEnum:
            common_agent_state = state_enum.value
            if common_agent_state.state_name not in event_ids:
                event_ids.append(common_agent_state.state_name)

        # 特殊处理邦布
        for i in range(1, 3):
            event_ids.append(f'连携技-{i}-邦布')

        # 添加目标状态 (V10: 从数据定义中动态获取)
        for task in DETECTION_TASKS:
            if not task.enabled:
                continue
            for state_def in task.state_definitions:
                if state_def.state_name not in event_ids:
                    event_ids.append(state_def.state_name)

        # 这是一个旧的状态 等待后续删除或者恢复识别
        event_ids.append('格挡-破碎')

        return event_ids

    @cached_property
    def mutex_list(self) -> dict[str, list[str]]:
        """
        初始化状态互斥列表
        """
        all_mutex_list: dict[str, list[str]] = {}

        for agent_enum in AgentEnum:
            mutex_list: list[str] = []
            for mutex_agent_enum in AgentEnum:
                if mutex_agent_enum == agent_enum:
                    continue
                mutex_list.append(mutex_agent_enum.value.agent_name)

            agent_name = agent_enum.value.agent_name
            all_mutex_list[f'前台-{agent_name}'] = [f'前台-{i}' for i in mutex_list] + [f'后台-1-{agent_name}', f'后台-2-{agent_name}', f'后台-{agent_name}']
            all_mutex_list[f'后台-{agent_name}'] = [f'前台-{agent_name}']
            all_mutex_list[f'后台-1-{agent_name}'] = [f'后台-1-{i}' for i in mutex_list] + [f'后台-2-{agent_name}', f'前台-{agent_name}']
            all_mutex_list[f'后台-2-{agent_name}'] = [f'后台-2-{i}' for i in mutex_list] + [f'后台-1-{agent_name}', f'前台-{agent_name}']
            all_mutex_list[f'连携技-1-{agent_name}'] = [f'连携技-1-{i}' for i in (mutex_list + ['邦布'])]
            all_mutex_list[f'连携技-2-{agent_name}'] = [f'连携技-2-{i}' for i in (mutex_list + ['邦布'])]
            all_mutex_list[f'快速支援-{agent_name}'] = [f'快速支援-{i}' for i in mutex_list]
            all_mutex_list[f'切换角色-{agent_name}'] = [f'切换角色-{i}' for i in mutex_list]

        for agent_type_enum in AgentTypeEnum:
            if agent_type_enum == AgentTypeEnum.UNKNOWN:
                continue
            mutex_list: list[str] = []
            for mutex_agent_type_enum in AgentTypeEnum:
                if mutex_agent_type_enum == AgentTypeEnum.UNKNOWN:
                    continue
                if mutex_agent_type_enum == agent_type_enum:
                    continue
                mutex_list.append(mutex_agent_type_enum.value)

            all_mutex_list['前台-' + agent_type_enum.value] = ['前台-' + i for i in mutex_list]
            all_mutex_list['后台-1-' + agent_type_enum.value] = ['后台-1-' + i for i in mutex_list]
            all_mutex_list['后台-2-' + agent_type_enum.value] = ['后台-2-' + i for i in mutex_list]
            all_mutex_list['连携技-1-' + agent_type_enum.value] = ['连携技-1-' + i for i in mutex_list]
            all_mutex_list['连携技-2-' + agent_type_enum.value] = ['连携技-2-' + i for i in mutex_list]
            all_mutex_list['快速支援-' + agent_type_enum.value] = ['快速支援-' + i for i in mutex_list]
            all_mutex_list['切换角色-' + agent_type_enum.value] = ['切换角色-' + i for i in mutex_list]

        # 特殊处理连携技的互斥
        for i in range(1, 3):
            all_mutex_list[f'连携技-{i}-邦布'] = [f'连携技-{i}-{agent_enum.value.agent_name}' for agent_enum in AgentEnum]

        return all_mutex_list
