from __future__ import annotations

import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import List, Optional, Tuple, Any, TYPE_CHECKING

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.loader import ConditionalOperatorLoader
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.operator import ConditionalOperator
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle.atomic_op.btn_lock import AtomicBtnLock
from zzz_od.auto_battle.atomic_op.turn import AtomicTurn
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum, CommonAgentStateEnum
from zzz_od.game_data.target_state import DETECTION_TASKS

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext

_auto_battle_operator_executor = ThreadPoolExecutor(thread_name_prefix='_auto_battle_operator_executor', max_workers=1)

# 自动战斗配置的默认回退模板名
FALLBACK_TEMPLATE_NAME = '全配队通用'


class AutoBattleOperator(ConditionalOperator):

    def __init__(
        self,
        ctx: AutoBattleContext,
        sub_dir: str,
        template_name: str,
        read_from_merged: bool = True,
    ):
        original_file_path = ConditionalOperatorLoader.get_yaml_file_path(
            sub_dir=[sub_dir],
            template_name=template_name,
            read_from_merged=read_from_merged,
        )
        if not os.path.exists(original_file_path):
            log.warning(f'自动战斗配置 {original_file_path} 不存在，回退到 {FALLBACK_TEMPLATE_NAME}')
            template_name = FALLBACK_TEMPLATE_NAME

        ConditionalOperator.__init__(
            self,
            sub_dir=[sub_dir],
            template_name=template_name,
            operation_template_sub_dir=['auto_battle_operation'],
            state_handler_template_sub_dir=['auto_battle_state_handler'],
            read_from_merged=read_from_merged,
        )

        # 配置文件的zzz定制内容
        self.author: str = ''  #  作者
        self.homepage: str = ''
        self.thanks: str = ''
        self.version: str = ''
        self.introduction: str = ''
        self.team_list: list[list[str]] = []  # 配队信息

        self._check_dodge_interval: float = 0.02  # 检测闪避的间隔
        self._check_agent_interval: float = 0.5  # 检测代理人的间隔
        self._check_chain_interval: float = 1  # 检测连携技的间隔
        self._check_quick_interval: float = 0.5  # 检测快速支援的间隔
        self._check_end_interval: float = 5  # 检测战斗结束的间隔
        self._target_lock_interval: float = 1  # 检测锁定目标的间隔
        self._abnormal_status_interval: float = 0  # 检测异常状态的间隔
        self._auto_lock_interval = 1  # 自动锁定的间隔
        self._auto_turn_interval = 2  # 自动转向的间隔

        self.ctx: AutoBattleContext = ctx

        self.state_recorders: dict[str, StateRecorder] = {}
        self._mutex_list: dict[str, List[str]] = {}

        self.async_init_future: Optional[Future[Tuple[bool, str]]] = None

        # 自动周期
        self.last_lock_time: float = 0  # 上一次锁定的时间
        self.last_turn_time: float = 0  # 上一次转动视角的时间

    def load_other_info(self, data: dict[str, Any]) -> None:
        """
        加载其他所需的信息

        Args:
            data: 配置文件内容
        """
        self.author = data.get('author', '')
        self.homepage = data.get('homepage', 'https://qm.qq.com/q/wuVRYuZzkA')
        self.thanks = data.get('thanks', '')
        self.version = data.get('version', '')
        self.introduction = data.get('introduction', '')
        self.team_list = data.get('team_list', [])

        self._check_dodge_interval = data.get('check_dodge_interval', 0.02)
        self._check_agent_interval = data.get('check_agent_interval', 0.5)
        self._check_chain_interval = data.get('check_chain_interval', 1)
        self._check_quick_interval = data.get('check_quick_interval', 0.5)
        self._check_end_interval = data.get('check_end_interval', 5)
        self._target_lock_interval = data.get('target_lock_interval', 1)
        self._abnormal_status_interval = data.get('abnormal_status_interval', 0)

    def init_before_running(self) -> Tuple[bool, str]:
        """
        运行前进行初始化
        :return:
        """
        try:
            success, msg = self._init_operator()
            if not success:
                return success, msg

            self.ctx.init_battle_context(
                auto_op=self,
                check_dodge_interval=self._check_dodge_interval,
                check_agent_interval=self._check_agent_interval,
                check_chain_interval=self._check_chain_interval,
                check_quick_interval=self._check_quick_interval,
                check_end_interval=self._check_end_interval,
                target_lock_interval=self._target_lock_interval,
                abnormal_status_interval=self._abnormal_status_interval,
            )

            log.info(f'自动战斗配置加载成功 {self.get_template_name()}')
            return True, ''
        except Exception as e:
            log.error('自动战斗初始化失败 共享配队文件请在群内提醒对应作者修复', exc_info=True)
            return False, '初始化失败'

    def init_before_running_async(self) -> Future[Tuple[bool, str]]:
        """
        异步初始化
        """
        self.async_init_future = _auto_battle_operator_executor.submit(self.init_before_running)
        return self.async_init_future

    def _init_operator(self) -> Tuple[bool, str]:
        self._mutex_list: dict[str, List[str]] = {}

        for agent_enum in AgentEnum:
            mutex_list: List[str] = []
            for mutex_agent_enum in AgentEnum:
                if mutex_agent_enum == agent_enum:
                    continue
                mutex_list.append(mutex_agent_enum.value.agent_name)

            agent_name = agent_enum.value.agent_name
            self._mutex_list[f'前台-{agent_name}'] = [f'前台-{i}' for i in mutex_list] + [f'后台-1-{agent_name}', f'后台-2-{agent_name}', f'后台-{agent_name}']
            self._mutex_list[f'后台-{agent_name}'] = [f'前台-{agent_name}']
            self._mutex_list[f'后台-1-{agent_name}'] = [f'后台-1-{i}' for i in mutex_list] + [f'后台-2-{agent_name}', f'前台-{agent_name}']
            self._mutex_list[f'后台-2-{agent_name}'] = [f'后台-2-{i}' for i in mutex_list] + [f'后台-1-{agent_name}', f'前台-{agent_name}']
            self._mutex_list[f'连携技-1-{agent_name}'] = [f'连携技-1-{i}' for i in (mutex_list + ['邦布'])]
            self._mutex_list[f'连携技-2-{agent_name}'] = [f'连携技-2-{i}' for i in (mutex_list + ['邦布'])]
            self._mutex_list[f'快速支援-{agent_name}'] = [f'快速支援-{i}' for i in mutex_list]
            self._mutex_list[f'切换角色-{agent_name}'] = [f'切换角色-{i}' for i in mutex_list]

        for agent_type_enum in AgentTypeEnum:
            if agent_type_enum == AgentTypeEnum.UNKNOWN:
                continue
            mutex_list: List[str] = []
            for mutex_agent_type_enum in AgentTypeEnum:
                if mutex_agent_type_enum == AgentTypeEnum.UNKNOWN:
                    continue
                if mutex_agent_type_enum == agent_type_enum:
                    continue
                mutex_list.append(mutex_agent_type_enum.value)

            self._mutex_list['前台-' + agent_type_enum.value] = ['前台-' + i for i in mutex_list]
            self._mutex_list['后台-1-' + agent_type_enum.value] = ['后台-1-' + i for i in mutex_list]
            self._mutex_list['后台-2-' + agent_type_enum.value] = ['后台-2-' + i for i in mutex_list]
            self._mutex_list['连携技-1-' + agent_type_enum.value] = ['连携技-1-' + i for i in mutex_list]
            self._mutex_list['连携技-2-' + agent_type_enum.value] = ['连携技-2-' + i for i in mutex_list]
            self._mutex_list['快速支援-' + agent_type_enum.value] = ['快速支援-' + i for i in mutex_list]
            self._mutex_list['切换角色-' + agent_type_enum.value] = ['切换角色-' + i for i in mutex_list]

        # 特殊处理连携技的互斥
        for i in range(1, 3):
            self._mutex_list[f'连携技-{i}-邦布'] = [f'连携技-{i}-{agent_enum.value.agent_name}' for agent_enum in AgentEnum]

        ConditionalOperator.init(self)
        return True, ''

    @staticmethod
    def get_all_state_event_ids() -> List[str]:
        """
        目前可用的状态事件ID
        :return:
        """
        event_ids = []

        for event_enum in YoloStateEventEnum:
            event_ids.append(event_enum.value)

        for event_enum in BattleStateEnum:
            event_ids.append(event_enum.value)

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

        return event_ids

    def get_state_recorder(self, state_name: str) -> Optional[StateRecorder]:
        """
        获取状态记录器
        :param state_name:
        :return:
        """
        if AutoBattleOperator.is_valid_state(state_name):
            if state_name in self.state_recorders:
                return self.state_recorders[state_name]
            else:
                r = StateRecorder(state_name, mutex_list=self._mutex_list.get(state_name, None))
                self.state_recorders[state_name] = r
                return r
        else:
            return None

    @staticmethod
    def is_valid_state(state_name: str) -> bool:
        """
        判断一个状态是否合法
        :param state_name:
        :return:
        """
        if state_name in AutoBattleOperator.get_all_state_event_ids():
            return True
        elif state_name.startswith('自定义-'):
            return True
        else:
            return False

    def get_atomic_op(self, op_def: OperationDef) -> AtomicOp:
        """
        获取一个原子操作

        Args:
            op_def: 操作定义

        Returns:
            AtomicOp: 原子操作
        """
        return self.ctx.atomic_op_factory.get_atomic_op(op_def)

    def dispose(self) -> None:
        """
        销毁 注意要解绑各种事件监听
        :return:
        """
        if self.async_init_future is not None:
            try:
                self.async_init_future.result(10)
            except Exception as e:
                pass
        ConditionalOperator.dispose(self)
        self.async_init_future = None
        for sr in self.state_recorders.values():
            sr.dispose()
        self.state_recorders.clear()

    def start_running_async(self) -> bool:
        success = ConditionalOperator.start_running_async(self)
        if success:
            lock_f = _auto_battle_operator_executor.submit(self.operate_periodically)
            lock_f.add_done_callback(thread_utils.handle_future_result)

        return success

    def operate_periodically(self) -> None:
        """
        周期性完成动作

        1. 锁定敌人
        2. 转向 - 有机会找到后方太远的敌人；迷失之地可以转动下层入口
        :return:
        """
        if self._auto_lock_interval <= 0 and self._auto_turn_interval <= 0:  # 不开启自动锁定 和 自动转向
            return
        lock_op = AtomicBtnLock(self.ctx)
        turn_op = AtomicTurn(self.ctx, 100)
        while self.is_running:
            now = time.time()

            if not self.ctx.last_check_in_battle:  # 当前画面不是战斗画面 就不运行了
                time.sleep(0.2)
                continue

            any_done: bool = False
            if self._auto_lock_interval > 0 and now - self.last_lock_time > self._auto_lock_interval:
                lock_op.execute()
                self.last_lock_time = now
                any_done = True
            if self._auto_turn_interval > 0 and now - self.last_turn_time > self._auto_turn_interval:
                turn_op.execute()
                self.last_turn_time = now
                any_done = True

            if not any_done:
                time.sleep(0.2)


def __debug():
    ctx = ZContext()
    ctx.init()
    auto_op = AutoBattleOperator(ctx.auto_battle_context, 'auto_battle', '全配队通用')
    auto_op.init_before_running()
    # auto_op.start_running_async()
    # time.sleep(5)
    # auto_op.stop_running()


if __name__ == '__main__':
    __debug()
