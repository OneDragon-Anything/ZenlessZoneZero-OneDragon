import time
from concurrent.futures import Future, ThreadPoolExecutor

import os
from typing import List, Optional, Tuple

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.operation_template import OperationTemplate
from one_dragon.base.conditional_operation.state_handler_template import StateHandlerTemplate
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.utils import os_utils, thread_utils
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle.atomic_op.btn_chain_left import AtomicBtnChainLeft
from zzz_od.auto_battle.atomic_op.btn_chain_right import AtomicBtnChainRight
from zzz_od.auto_battle.atomic_op.btn_common import AtomicBtnCommon
from zzz_od.auto_battle.atomic_op.btn_dodge import AtomicBtnDodge
from zzz_od.auto_battle.atomic_op.btn_lock import AtomicBtnLock
from zzz_od.auto_battle.atomic_op.btn_move_a import AtomicBtnMoveA
from zzz_od.auto_battle.atomic_op.btn_move_d import AtomicBtnMoveD
from zzz_od.auto_battle.atomic_op.btn_move_s import AtomicBtnMoveS
from zzz_od.auto_battle.atomic_op.btn_move_w import AtomicBtnMoveW
from zzz_od.auto_battle.atomic_op.btn_normal_attack import AtomicBtnNormalAttack
from zzz_od.auto_battle.atomic_op.btn_quick_assist import AtomicBtnQuickAssist
from zzz_od.auto_battle.atomic_op.btn_special_attack import AtomicBtnSpecialAttack
from zzz_od.auto_battle.atomic_op.btn_switch_agent import AtomicBtnSwitchAgent
from zzz_od.auto_battle.atomic_op.btn_switch_next import AtomicBtnSwitchNext
from zzz_od.auto_battle.atomic_op.btn_switch_prev import AtomicBtnSwitchPrev
from zzz_od.auto_battle.atomic_op.btn_ultimate import AtomicBtnUltimate
from zzz_od.auto_battle.atomic_op.state_clear import AtomicClearState
from zzz_od.auto_battle.atomic_op.state_set import AtomicSetState
from zzz_od.auto_battle.atomic_op.wait import AtomicWait
from zzz_od.auto_battle.auto_battle_context import AutoBattleContext
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum, CommonAgentStateEnum
from zzz_od.game_data.target_state import DETECTION_TASKS

_auto_battle_operator_executor = ThreadPoolExecutor(thread_name_prefix='_auto_battle_operator_executor', max_workers=1)

# 自动战斗配置的默认回退模板名
FALLBACK_TEMPLATE_NAME = '全配队通用'


class AutoBattleOperator(ConditionalOperator):

    def __init__(self, ctx: ZContext, sub_dir: str, template_name: str, is_mock: bool = False):
        self.ctx: ZContext = ctx

        # 初始化一个检查器 用于检查配置文件是否存在
        check_operator = ConditionalOperator(sub_dir, template_name)

        # 检查文件是否存在，如果不存在则使用回退配置
        if not check_operator.is_file_exists:
            log.warning(f'自动战斗配置 {template_name} 不存在，回退到 {FALLBACK_TEMPLATE_NAME}')
            template_name = FALLBACK_TEMPLATE_NAME

        # 显式释放临时检查器的资源，然后丢弃引用
        try:
            check_operator.dispose()
        finally:
            check_operator = None

        ConditionalOperator.__init__(
            self,
            sub_dir=sub_dir,
            template_name=template_name,
            is_mock=is_mock
        )

        self.state_recorders: dict[str, StateRecorder] = {}
        self._mutex_list: dict[str, List[str]] = {}

        self.auto_battle_context: AutoBattleContext = AutoBattleContext(ctx)
        self.async_init_future: Optional[Future[Tuple[bool, str]]] = None

        # 自动周期
        self.last_lock_time: float = 0  # 上一次锁定的时间
        self.last_turn_time: float = 0  # 上一次转动视角的时间

    def init_before_running(self) -> Tuple[bool, str]:
        """
        运行前进行初始化
        :return:
        """
        try:
            success, msg = self._init_operator()
            if not success:
                return success, msg

            self.auto_battle_context.init_battle_context(
                auto_op=self,
                use_gpu=self.ctx.model_config.flash_classifier_gpu,
                check_dodge_interval=self.get('check_dodge_interval', 0.02),
                check_agent_interval=self.get('check_agent_interval', 0.5),
                check_chain_interval=self.get('check_chain_interval', 1),
                check_quick_interval=self.get('check_quick_interval', 0.5),
                check_end_interval=self.get('check_end_interval', 5),
                target_lock_interval=self.get('target_lock_interval', 1),
                abnormal_status_interval=self.get('abnormal_status_interval', 0)
            )

            log.info(f'自动战斗配置加载成功 {self.module_name}')
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

        ConditionalOperator.init(
            self,
            op_getter=self.get_atomic_op,
            scene_handler_getter=AutoBattleOperator.get_state_handler_template,
            operation_template_getter=AutoBattleOperator.get_operation_template
        )
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
        :return:
        """
        op_name = op_def.op_name
        op_data = op_def.data
        # 有几个特殊参数 在这里统一提取
        press: bool = op_name.endswith('-按下')
        release: bool = op_name.endswith('-松开')
        if press:
            press_time = float(op_data[0]) if (op_data is not None and len(op_data) > 0) else None
        else:
            press_time = None

        if op_name == AtomicBtnSwitchAgent.OP_NAME or op_name == '切换角色':
            # 切换角色 只是一个兼容 后续删掉
            return AtomicBtnSwitchAgent(self.auto_battle_context, op_def)
        elif op_name == AtomicBtnQuickAssist.OP_NAME:
            return AtomicBtnQuickAssist(self.auto_battle_context, op_def)
        elif op_name.startswith('按键') and not op_name.endswith('按下') and not op_name.endswith('松开'):
            return AtomicBtnCommon(self.auto_battle_context, op_def)
        elif op_name.startswith(BattleStateEnum.BTN_DODGE.value):
            return AtomicBtnDodge(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_NEXT.value):
            return AtomicBtnSwitchNext(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_PREV.value):
            return AtomicBtnSwitchPrev(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_NORMAL_ATTACK.value):
            return AtomicBtnNormalAttack(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_SPECIAL_ATTACK.value):
            return AtomicBtnSpecialAttack(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_ULTIMATE.value):
            return AtomicBtnUltimate(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_CHAIN_LEFT.value):
            return AtomicBtnChainLeft(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_CHAIN_RIGHT.value):
            return AtomicBtnChainRight(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_W.value):
            return AtomicBtnMoveW(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_S.value):
            return AtomicBtnMoveS(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_A.value):
            return AtomicBtnMoveA(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_D.value):
            return AtomicBtnMoveD(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_LOCK.value):
            return AtomicBtnLock(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name == AtomicWait.OP_NAME:
            return AtomicWait(op_def)
        elif op_name == AtomicSetState.OP_NAME:
            return AtomicSetState(self.auto_battle_context.custom_context, op_def)
        elif op_name == AtomicClearState.OP_NAME:
            return AtomicClearState(self.auto_battle_context.custom_context, op_def)
        else:
            raise ValueError('非法的指令 %s' % op_name)

    @staticmethod
    def get_state_handler_template(target_template_name: str) -> Optional[StateHandlerTemplate]:
        """
        获取场景处理器模板
        :param target_template_name: 模板名称
        :return:
        """
        sub_dir = 'auto_battle_state_handler'
        template_dir = os_utils.get_path_under_work_dir('config', sub_dir)
        file_list = os.listdir(template_dir)

        for file_name in file_list:
            if file_name.endswith('.sample.yml'):
                template_name = file_name[0:-11]
            elif file_name.endswith('.yml'):
                template_name = file_name[0:-4]
            else:
                continue
            if template_name != target_template_name:
                continue

            return StateHandlerTemplate(sub_dir, template_name)

        return None

    @staticmethod
    def get_operation_template(target_template_name: str) -> Optional[OperationTemplate]:
        """
        获取操作模板，支持递归查找子目录
        :param target_template_name: 模板名称
        :return: OperationTemplate 对象或 None
        """
        sub_dir = 'auto_battle_operation'
        template_dir = os_utils.get_path_under_work_dir('config', sub_dir)

        # 递归查找模板文件
        for root, dirs, files in os.walk(template_dir):
            for file_name in files:
                if file_name.endswith('.sample.yml'):
                    template_name = file_name[0:-11]
                elif file_name.endswith('.yml'):
                    template_name = file_name[0:-4]
                else:
                    continue

                if target_template_name == template_name:
                    # 返回 OperationTemplate，包括子目录的路径信息
                    relative_sub_dir = os.path.relpath(root, os_utils.get_path_under_work_dir('config'))
                    return OperationTemplate(relative_sub_dir, template_name)

        # 如果未找到，返回 None
        return None

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

    def stop_running(self) -> None:
        """
        停止运行 要松开所有按钮
        """
        ConditionalOperator.stop_running(self)
        self.auto_battle_context.stop_context()

    def start_running_async(self) -> bool:
        success = ConditionalOperator.start_running_async(self)
        if success:
            self.auto_battle_context.start_context()
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
        auto_lock_interval = self.get('auto_lock_interval', 1)
        auto_turn_interval = self.get('auto_turn_interval', 2)
        if auto_lock_interval <= 0 and auto_turn_interval <= 0:  # 不开启自动锁定 和 自动转向
            return
        op = AtomicBtnLock(self.auto_battle_context)
        while self.is_running:
            now = time.time()

            if not self.auto_battle_context.last_check_in_battle:  # 当前画面不是战斗画面 就不运行了
                time.sleep(0.2)
                continue

            any_done: bool = False
            if auto_lock_interval > 0 and now - self.last_lock_time > auto_lock_interval:
                op.execute()
                self.last_lock_time = now
                any_done = True
            if auto_turn_interval > 0 and now - self.last_turn_time > auto_turn_interval:
                self.ctx.controller.turn_by_distance(100)
                self.last_turn_time = now
                any_done = True

            if not any_done:
                time.sleep(0.2)

    @property
    def team_list(self) -> List[List[str]]:
        return self.get('team_list', [])

    @property
    def author(self) -> str:
        return self.get('author', '')

    @property
    def homepage(self) -> str:
        return self.get('homepage', 'https://qm.qq.com/q/wuVRYuZzkA')

    @property
    def thanks(self) -> str:
        return self.get('thanks', '')

    @property
    def version(self) -> str:
        return self.get('version', '')

    @property
    def introduction(self) -> str:
        return self.get('introduction', '')


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    auto_op = AutoBattleOperator(ctx, 'auto_battle', '全配队通用')
    auto_op.init_before_running()
    # auto_op.start_running_async()
    # time.sleep(5)
    # auto_op.stop_running()


if __name__ == '__main__':
    __debug()
