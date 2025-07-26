from concurrent.futures import ThreadPoolExecutor, Future

import threading
from cv2.typing import MatLike
from typing import Optional, List, Union, Tuple, Callable

from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator
from one_dragon.base.conditional_operation.state_recorder import StateRecord, StateRecorder
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import cv2_utils, cal_utils
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle.agent_state import agent_state_checker
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent, AgentEnum, AgentStateCheckWay, CommonAgentStateEnum, AgentStateDef

_battle_agent_context_executor = ThreadPoolExecutor(thread_name_prefix='od_battle_agent_context', max_workers=16)
_agent_state_check_method: dict[AgentStateCheckWay, Callable] = {
    AgentStateCheckWay.COLOR_RANGE_CONNECT: agent_state_checker.check_cnt_by_color_range,
    AgentStateCheckWay.COLOR_RANGE_EXIST: agent_state_checker.check_exist_by_color_range,
    AgentStateCheckWay.BACKGROUND_GRAY_RANGE_LENGTH: agent_state_checker.check_length_by_background_gray,
    AgentStateCheckWay.FOREGROUND_GRAY_RANGE_LENGTH: agent_state_checker.check_length_by_foreground_gray,
    AgentStateCheckWay.FOREGROUND_COLOR_RANGE_LENGTH: agent_state_checker.check_length_by_foreground_color,
    AgentStateCheckWay.TEMPLATE_NOT_FOUND: agent_state_checker.check_template_not_found,
    AgentStateCheckWay.TEMPLATE_FOUND: agent_state_checker.check_template_found,
    AgentStateCheckWay.COLOR_CHANNEL_MAX_RANGE_EXIST: agent_state_checker.check_exist_by_color_channel_max_range,
    AgentStateCheckWay.COLOR_CHANNEL_EQUAL_RANGE_CONNECT: agent_state_checker.check_cnt_by_color_channel_equal_range,
}


class AgentInfo:

    def __init__(self, agent: Optional[Agent], energy: int = 0,
                 special_ready: bool = False,
                 ultimate_ready: bool = False,
                 matched_template_id: Optional[str] = None):
        self.agent: Agent = agent
        self.matched_template_id: Optional[str] = matched_template_id  # 上次成功匹配的模板ID
        self.energy: int = energy  # 能量
        self.special_ready: bool = special_ready  # 特殊技
        self.ultimate_ready: bool = ultimate_ready  # 终结技


class TeamInfo:

    def __init__(self, agent_names: Optional[List[str]] = None):
        self.agent_list: List[AgentInfo] = []

        self.should_check_all_agents: bool = agent_names is None  # 是否应该检查所有角色
        self.check_agent_same_times: int = 0  # 识别角色的相同次数
        self.check_agent_diff_times: int = 0  # 识别角色的不同次数
        self.update_agent_lock = threading.Lock()
        self.agent_update_time: float = 0  # 识别角色的更新时间

        if agent_names is not None:
            for agent_name in agent_names:
                for agent_enum in AgentEnum:
                    if agent_name == agent_enum.value.agent_name:
                        self.agent_list.append(AgentInfo(agent_enum.value))
                        break

    def update_agent_list(self,
                          current_agent_list: List[Tuple[Agent, Optional[str]]],
                          energy_list: List[int],
                          special_list: List[int],
                          ultimate_list: List[int],
                          update_time: float,) -> bool:
        """
        更新角色列表
        :param current_agent_list: 新的角色列表及匹配的模板ID
        :param energy_list: 能量列表
        :param special_list: 特殊技列表
        :param ultimate_list: 终结技列表
        :param update_time: 更新时间
        :return: 本次是否更新了
        """
        with self.update_agent_lock:

            if self.should_check_all_agents:
                if self.is_same_agent_list(current_agent_list):
                    self.check_agent_diff_times = 0
                    self.check_agent_same_times += 1

                    if self.check_agent_same_times >= 5:  # 连续5次一致时 就不验证了
                        self.should_check_all_agents = False
                        log.debug("停止识别新角色")
                else:
                    self.check_agent_diff_times += 1
                    self.check_agent_same_times = 0
            else:
                if not self.is_same_agent_list(current_agent_list):
                    self.check_agent_diff_times += 1
                    self.check_agent_same_times = 0

                    if self.check_agent_diff_times >= 250:  # 0.02秒1次 大概5s不一致就重新识别 除了减员情况外基本不可能出现
                        self.should_check_all_agents = True
                        log.debug("重新识别新角色")
                else:
                    self.check_agent_diff_times = 0
                    self.check_agent_same_times += 0

            if not self.should_check_all_agents and not self.is_same_agent_list(current_agent_list):
                # 如果已经确定角色列表了 那识别出来的应该是一样的
                # 不一样的话 就不更新了
                return False

            all_none: bool = True
            for agent, _ in current_agent_list:
                if agent is not None:
                    all_none = False
                    break
            # 没有一个能识别到的话 也不更新
            if all_none:
                return False

            if update_time < self.agent_update_time:  # 可能是过时的截图 这时候不更新
                return False
            self.agent_update_time = update_time

            # log.debug('当前角色列表 %s', [
            #     i.agent.agent_name if i.agent is not None else 'none'
            #     for i in self.agent_list
            # ])

            self.agent_list = []
            for i in range(len(current_agent_list)):
                agent, matched_template_id = current_agent_list[i]
                energy = energy_list[i] if i < len(energy_list) else 0
                special_ready = (special_list[i] if i < len(special_list) else 0) > 0
                ultimate_ready = (ultimate_list[i] if i < len(ultimate_list) else 0) > 0
                self.agent_list.append(AgentInfo(agent, energy, special_ready, ultimate_ready, matched_template_id))

            # log.debug('更新后角色列表 %s 更新时间 %.4f',
            #           [i.agent.agent_name if i.agent is not None else 'none' for i in self.agent_list],
            #           update_time)

            return True

    def is_same_agent_list(self, current_agent_list: List[Tuple[Optional[Agent], Optional[str]]]) -> bool:
        """
        是否跟原来的角色列表一致 忽略顺序
        :param current_agent_list:
        :return:
        """
        if self.agent_list is None or current_agent_list is None:
            return False
        if len(self.agent_list) != len(current_agent_list):
            return False
        old_agent_ids = [i.agent.agent_id for i in self.agent_list if i.agent is not None]
        new_agent_ids = [agent.agent_id for agent, _ in current_agent_list if agent is not None]
        if len(old_agent_ids) != len(new_agent_ids):
            return False

        for old_agent_id in old_agent_ids:
            if old_agent_id not in new_agent_ids:
                return False

        return True

    def switch_next_agent(self, update_time: float) -> bool:
        """
        切换到下一个代理人
        :param update_time: 更新时间
        :return: 是否更新了代理人列表
        """
        with self.update_agent_lock:
            if update_time < self.agent_update_time:
                return False

            if self.agent_list is None or len(self.agent_list) == 0:
                return False
            self.agent_update_time = update_time

            not_none_agent_list = []
            none_cnt: int = 0
            for i in self.agent_list:
                if i.agent is None:
                    none_cnt += 1
                else:
                    not_none_agent_list.append(i)

            next_agent_list = []
            if len(not_none_agent_list) > 0:
                for i in range(1, len(not_none_agent_list)):
                    next_agent_list.append(not_none_agent_list[i])
                next_agent_list.append(not_none_agent_list[0])

            for i in range(none_cnt):
                next_agent_list.append(AgentInfo(None, 0))

            self.agent_list = next_agent_list

            # log.debug('切换下一个 更新后角色列表 %s 更新时间 %.4f',
            #           [ i.agent.agent_name if i.agent is not None else 'none' for i in self.agent_list],
            #           update_time)

            return True

    def switch_prev_agent(self, update_time: float) -> bool:
        """
        切换到上一个代理人
        :param update_time: 更新时间
        :return: 是否更新了代理人列表
        """
        with self.update_agent_lock:
            if update_time < self.agent_update_time:
                return False

            if self.agent_list is None or len(self.agent_list) == 0:
                return False
            self.agent_update_time = update_time

            not_none_agent_list = []
            none_cnt: int = 0
            for i in self.agent_list:
                if i.agent is None:
                    none_cnt += 1
                else:
                    not_none_agent_list.append(i)

            next_agent_list = []
            if len(not_none_agent_list) > 0:
                next_agent_list.append(not_none_agent_list[-1])
                for i in range(0, len(not_none_agent_list)-1):
                    next_agent_list.append(not_none_agent_list[i])

            for i in range(none_cnt):
                next_agent_list.append(AgentInfo(None, 0))
            self.agent_list = next_agent_list

            # log.debug('切换上一个 更新后角色列表 %s 更新时间 %.4f',
            #           [ i.agent.agent_name if i.agent is not None else 'none' for i in self.agent_list],
            #           update_time)

            return True

    def get_agent_pos(self, agent: Agent) -> int:
        """
        获取指定代理人在队伍当前的位置
        :return: 如果存在就返回1~3 不存在就返回0
        """
        for i in range(len(self.agent_list)):
            if self.agent_list[i].agent is None:
                continue
            if self.agent_list[i].agent.agent_id == agent.agent_id:
                return i + 1
        return 0

    def get_agent_pos_by_name(self, agent_name: str) -> int:
        """
        根据代理人名称 获取指定代理人在队伍当前的位置
        :return: 如果存在就返回1~3 不存在就返回0
        """
        switch_agent = None
        for agent_enum in AgentEnum:
            if agent_enum.value.agent_name == agent_name:
                switch_agent = agent_enum.value
                break
        if switch_agent is None:
            return 0

        return self.get_agent_pos(switch_agent)


class CheckAgentState:

    def __init__(self, state: AgentStateDef, total: Optional[int] = None, pos: Optional[int] = None):
        self.state: AgentStateDef = state
        self.total: int = total
        self.pos: int = pos


class AutoBattleAgentContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        self.auto_op: ConditionalOperator = ConditionalOperator('', '', is_mock=True)
        self.team_info: TeamInfo = TeamInfo()

        # 识别锁 保证每种类型只有1实例在进行识别
        self._check_agent_lock = threading.Lock()

    def init_battle_agent_context(
            self,
            auto_op: ConditionalOperator,
            agent_names: Optional[List[str]] = None,
            to_check_state_list: Optional[List[str]] = None,
            check_agent_interval: Union[float, List[float]] = 0,) -> None:
        """
        自动战斗前的初始化
        :return:
        """
        self.auto_op: ConditionalOperator = auto_op
        self.team_info: TeamInfo = TeamInfo(agent_names)

        # 识别区域 先读取出来 不要每次用的时候再读取
        self.area_agent_3_1: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '头像-3-1')
        self.area_agent_3_2: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '头像-3-2')
        self.area_agent_3_3: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '头像-3-3')
        self.area_agent_2_2: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '头像-2-2')

        # 识别间隔
        self._check_agent_interval = check_agent_interval

        # 上一次识别的时间
        self._last_check_agent_time: float = 0
        self._last_switch_agent_time: float = 0

        # 初始化需要检测的状态
        for agent_enum in AgentEnum:
            agent = agent_enum.value
            if agent.state_list is None:
                continue
            for state in agent.state_list:
                if to_check_state_list is not None:
                    state.should_check_in_battle = state.state_name in to_check_state_list
                else:
                    state.should_check_in_battle = True

        for state_enum in CommonAgentStateEnum:
            state = state_enum.value
            if to_check_state_list is not None:
                state.should_check_in_battle = state.state_name in to_check_state_list
            else:
                state.should_check_in_battle = True

    def get_possible_agent_list(self) -> Optional[List[Tuple[Agent, Optional[str]]]]:
        """
        获取用于匹配的候选角色列表
        """
        all: bool = False
        if self.team_info.should_check_all_agents:
            all = True
        elif self.team_info.agent_list is None or len(self.team_info.agent_list) == 0:
            all = True
        else:
            for i in self.team_info.agent_list:
                if i.agent is None:
                    all = True
                    break
        if all:
            return [(agent_enum.value, None) for agent_enum in AgentEnum]
        else:
            return [(i.agent, i.matched_template_id) for i in self.team_info.agent_list if i.agent is not None]

    def check_agent_related(self, screen: MatLike, screenshot_time: float) -> None:
        """
        判断角色相关内容 并发送事件
        :return:
        """
        if not self._check_agent_lock.acquire(blocking=False):
            return

        try:
            if screenshot_time - self._last_check_agent_time < cal_utils.random_in_range(self._check_agent_interval):
                # 还没有达到识别间隔
                return
            self._last_check_agent_time = screenshot_time

            screen_agent_list = self._check_agent_in_parallel(screen)
            energy_state_list, special_state_list, ultimate_state_list, other_state_list = self._check_all_agent_state(screen, screenshot_time, screen_agent_list)

            update_state_record_list = []
            # 尝试更新代理人列表 成功的话 更新状态记录
            if self.team_info.update_agent_list(
                    screen_agent_list,
                    [(i.value if i is not None else 0) for i in energy_state_list],
                    [(i.value if i is not None else 0) for i in special_state_list],
                    [(i.value if i is not None else 0) for i in ultimate_state_list],
                    screenshot_time):

                for i in self._get_agent_state_records(screenshot_time):
                    update_state_record_list.append(i)

                # 只有代理人列表更新成功 本次识别的状态才可用
                for i in other_state_list:
                    update_state_record_list.append(i)

            self.auto_op.batch_update_states(update_state_record_list)
        except Exception:
            log.error('识别画面角色失败', exc_info=True)
        finally:
            self._check_agent_lock.release()

    def _check_agent_in_parallel(self, screen: MatLike) -> List[Tuple[Agent, Optional[str]]]:
        """
        并发识别角色
        :return:
        """
        area_img = [
            cv2_utils.crop_image_only(screen, self.area_agent_3_1.rect),
            cv2_utils.crop_image_only(screen, self.area_agent_3_2.rect),
            cv2_utils.crop_image_only(screen, self.area_agent_3_3.rect),
            cv2_utils.crop_image_only(screen, self.area_agent_2_2.rect)
        ]

        possible_agents = self.get_possible_agent_list()

        result_agent_list: List[Tuple[Optional[Agent], Optional[str]]] = []
        future_list: List[Optional[Future]] = []
        should_check: List[bool] = [True, False, False, False]

        if not self.team_info.should_check_all_agents:
            if len(self.team_info.agent_list) == 3:
                should_check[1] = True
                should_check[2] = True
            elif len(self.team_info.agent_list) == 2:
                should_check[3] = True
        else:
            for i in range(4):
                should_check[i] = True

        for i in range(4):
            if should_check[i]:
                future_list.append(_battle_agent_context_executor.submit(self._match_agent_in, area_img[i], i == 0, possible_agents))
            else:
                future_list.append(None)

        for future in future_list:
            if future is None:
                result_agent_list.append((None, None))
                continue
            try:
                result_agent, result_template_id = future.result()
                result_agent_list.append((result_agent, result_template_id))
            except Exception:
                log.error('识别角色头像失败', exc_info=True)
                result_agent_list.append((None, None))

        if result_agent_list[1][0] is not None and result_agent_list[2][0] is not None:  # 3人
            current_agent_list = result_agent_list[:3]
        elif result_agent_list[3][0] is not None:  # 2人
            current_agent_list = [result_agent_list[0], result_agent_list[3]]
        else:  # 1人
            current_agent_list = [result_agent_list[0]]

        return current_agent_list

    def _match_agent_in(self, img: MatLike, is_front: bool,
                        possible_agents: Optional[List[Tuple[Agent, Optional[str]]]] = None) -> Tuple[Optional[Agent], Optional[str]]:
        """
        在候选列表重匹配角色
        :return:
        """
        prefix = 'avatar_1_' if is_front else 'avatar_2_'
        for agent, specific_template_id in possible_agents:
            # 上次识别过的模板 ID，接着用
            if specific_template_id:
                template_to_check = prefix + specific_template_id
                mrl = self.ctx.tm.match_template(img, 'battle', template_to_check, threshold=0.8)
                if mrl.max is not None:
                    return agent, specific_template_id
            # 没有上次识别过的模板 ID，匹配所有可能的模板 ID
            else:
                for template_id in agent.template_id_list:
                    template_to_check = prefix + template_id
                    mrl = self.ctx.tm.match_template(img, 'battle', template_to_check, threshold=0.8)
                    if mrl.max is not None:
                        return agent, template_id

        return None, None

    def _check_agent_state_in_parallel(self, screen: MatLike, screenshot_time: float, agent_state_list: List[CheckAgentState]) -> List[StateRecord]:
        """
        并行识别多个角色状态
        :param screen: 游戏画面
        :param screenshot_time: 截图时间
        :param agent_state_list: 需要识别的状态列表
        :return:
        """
        future_list: List[Future] = []
        for state in agent_state_list:
            if not state.state.should_check_in_battle:
                continue
            future_list.append(_battle_agent_context_executor.submit(self._check_agent_state, screen, screenshot_time, state))

        result_list: List[Optional[StateRecord]] = []
        for future in future_list:
            try:
                record = future.result()
                if record is not None:
                    result_list.append(record)
            except Exception:
                log.error('识别角色状态失败', exc_info=True)

        return result_list

    def _check_agent_state(self, screen: MatLike, screenshot_time: float, to_check: CheckAgentState) -> Optional[StateRecord]:
        """
        识别一个角色状态
        :param screen:
        :param screenshot_time:
        :param to_check: 需要识别的状态
        :return:
        """
        value: int = -1
        state = to_check.state
        check_method = _agent_state_check_method[state.check_way]
        value = check_method(ctx=self.ctx, screen=screen, state_def=state, total=to_check.total, pos=to_check.pos)

        if value > -1 and value >= state.min_value_trigger_state:
            return StateRecord(state.state_name, screenshot_time, value)

    def _check_all_agent_state(self, screen: MatLike, screenshot_time: float,
                               screen_agent_list: List[Tuple[Agent, Optional[str]]]
                               ) -> Tuple[List[StateRecord], List[StateRecord], List[StateRecord], List[StateRecord]]:
        """
        识别所有需要的角色状态
        - 能量条
        - 角色独有状态
        - 血量扣减
        :param screen: 游戏画面
        :param screenshot_time: 截图时间
        :param screen_agent_list: 当前截图的角色列表
        :return: 三个状态记录 能量、终结技、角色状态
        """

        if screen_agent_list is None or len(screen_agent_list) == 0:
            return [], [], [], []

        total = len(screen_agent_list)
        to_check_list: List[CheckAgentState] = []

        # 能量、特殊技、终结技
        if total == 3:
            energy_state_list = [
                CommonAgentStateEnum.ENERGY_31.value,
                CommonAgentStateEnum.ENERGY_32.value,
                CommonAgentStateEnum.ENERGY_33.value,
            ]
            special_state_list = [
                CommonAgentStateEnum.SPECIAL_31.value,
                CommonAgentStateEnum.SPECIAL_32.value,
                CommonAgentStateEnum.SPECIAL_33.value,
            ]
            ultimate_state_list = [
                CommonAgentStateEnum.ULTIMATE_31.value,
                CommonAgentStateEnum.ULTIMATE_32.value,
                CommonAgentStateEnum.ULTIMATE_33.value,
            ]
        elif len(screen_agent_list) == 2:
            energy_state_list = [
                CommonAgentStateEnum.ENERGY_21.value,
                CommonAgentStateEnum.ENERGY_22.value,
            ]
            special_state_list = [
                CommonAgentStateEnum.SPECIAL_21.value,
                CommonAgentStateEnum.SPECIAL_22.value,
            ]
            ultimate_state_list = [
                CommonAgentStateEnum.ULTIMATE_21.value,
                CommonAgentStateEnum.ULTIMATE_22.value,
            ]
        else:
            energy_state_list = [CommonAgentStateEnum.ENERGY_21.value]
            special_state_list = [CommonAgentStateEnum.SPECIAL_31.value]
            ultimate_state_list = [CommonAgentStateEnum.ULTIMATE_31.value]

        for energy_state in energy_state_list:
            to_check_list.append(CheckAgentState(energy_state))

        for special_state in special_state_list:
            to_check_list.append(CheckAgentState(special_state))

        for ultimate_state in ultimate_state_list:
            to_check_list.append(CheckAgentState(ultimate_state))

        # 角色独有状态
        for idx in range(total):
            agent, _ = screen_agent_list[idx]
            if agent is None:
                continue
            if agent.state_list is None or len(agent.state_list) == 0:
                continue
            for state in agent.state_list:
                to_check_list.append(CheckAgentState(state, total, idx + 1))

        # 格挡破碎
        to_check_list.append(CheckAgentState(CommonAgentStateEnum.GUARD_BREAK.value))

        # 血量扣减
        if len(screen_agent_list) == 3:
            state = CommonAgentStateEnum.LIFE_DEDUCTION_31.value
        else:
            state = CommonAgentStateEnum.LIFE_DEDUCTION_21.value
        to_check_list.append(CheckAgentState(state))

        all_state_result_list = self._check_agent_state_in_parallel(screen, screenshot_time, to_check_list)
        energy_len = len(energy_state_list)
        special_len = len(special_state_list)
        ultimate_len = len(ultimate_state_list)

        energy_result_list = all_state_result_list[:energy_len]
        special_result_list = all_state_result_list[energy_len:energy_len + special_len]
        ultimate_result_list = all_state_result_list[energy_len + special_len:energy_len + special_len + ultimate_len]
        other_result_list = all_state_result_list[energy_len + special_len + ultimate_len:]

        return energy_result_list, special_result_list, ultimate_result_list, other_result_list

    def switch_next_agent(self, update_time: float, update_state: bool = True, check_agent: bool = False) -> List[StateRecord]:
        """
        代理人列表 切换下一个
        :param update_time: 更新时间
        :param update_state: 是否更新状态
        :param check_agent: 下一次截图是否需要识别代理人。普通切人场景可能会切错人（目标代理人还没有离场 没法再次切上场） 需要尽量快识别截图来更正代理人
        """
        if self.team_info.switch_next_agent(update_time):
            if check_agent:
                self._last_check_agent_time = 0
            records = self._get_agent_state_records(update_time, switch=True)
            if update_state:
                self.auto_op.batch_update_states(records)
            return records
        return []

    def switch_prev_agent(self, update_time: float, update_state: bool = True, check_agent: bool = False) -> List[StateRecord]:
        """
        代理人列表 切换上一个
        :param update_time: 更新时间
        :param update_state: 是否更新状态
        :param check_agent: 下一次截图是否需要识别代理人。普通切人场景可能会切错人（目标代理人还没有离场 没法再次切上场） 需要尽量快识别截图来更正代理人
        """
        if self.team_info.switch_prev_agent(update_time):
            if check_agent:
                self._last_check_agent_time = 0
            records = self._get_agent_state_records(update_time, switch=True)
            if update_state:
                self.auto_op.batch_update_states(records)
            return records
        return []

    def switch_quick_assist(self, update_time: float, update_state: bool = True) -> Tuple[int, List[StateRecord]]:
        """
        切换到快速支援的角色
        :param update_time: 更新时间
        :param update_state: 是否更新状态
        :return:
        """
        # 由于快速支援没法固定是上一个或者下一个 因此要靠快速支援的识别结果来判断是哪个角色
        switch_agent: Optional[Agent] = None
        latest_recorder: Optional[StateRecorder] = None
        for agent_enum in AgentEnum:
            agent = agent_enum.value
            state_name = f'快速支援-{agent.agent_name}'
            state_recorder = self.auto_op.get_state_recorder(state_name)
            if state_recorder is None or state_recorder.last_record_time <= 0:
                continue

            if latest_recorder is None or state_recorder.last_record_time > latest_recorder.last_record_time:
                latest_recorder = state_recorder
                switch_agent = agent

        if switch_agent is None:
            return 0, []

        target_agent_pos = self.team_info.get_agent_pos(switch_agent)
        if target_agent_pos == 2:  # 在下一个
            return target_agent_pos, self.switch_next_agent(update_time, update_state=update_state)
        elif target_agent_pos == 3:  # 在上一个
            return target_agent_pos, self.switch_prev_agent(update_time, update_state=update_state)
        else:
            return 0, []

    def chain_left(self, update_time: float, update_state: bool = True) -> List[StateRecord]:
        """
        连携技-左
        :return:
        """
        # 由于连携有邦布的存在 因此要特殊判断切换的角色
        chain_name_list = self.get_chain_name()

        # 没有识别到的情况 就默认使用上一个
        if len(chain_name_list) < 1:
            return self.switch_prev_agent(update_time, update_state=update_state)

        if chain_name_list[0] == '邦布':
            agent_name = chain_name_list[1]
        else:
            agent_name = chain_name_list[0]

        _, states = self.switch_by_agent_name(agent_name, update_time, update_state=update_state)
        return states

    def chain_right(self, update_time: float, update_state: bool = True) -> List[StateRecord]:
        """
        连携技-右
        :return:
        """
        # 由于连携有邦布的存在 因此要特殊判断切换的角色
        chain_name_list = self.get_chain_name()

        # 有识别到的情况 就默认使用上一个
        if len(chain_name_list) < 2:
            return self.switch_next_agent(update_time, update_state=update_state)

        if chain_name_list[1] == '邦布':
            agent_name = chain_name_list[0]
        else:
            agent_name = chain_name_list[1]

        _, states = self.switch_by_agent_name(agent_name, update_time, update_state=update_state)
        return states

    def get_chain_name(self) -> List[str]:
        """
        获取连携的名称
        :return:
        """
        result = []
        all_name_list = ['邦布'] + [agent_enum.value.agent_name for agent_enum in AgentEnum]
        for i in range(1, 3):
            target_name: Optional[str] = None
            latest_recorder: Optional[StateRecorder] = None
            for name in all_name_list:
                state_name = f'连携技-{i}-{name}'
                state_recorder = self.auto_op.get_state_recorder(state_name)
                if state_recorder is None or state_recorder.last_record_time <= 0:
                    continue

                if latest_recorder is None or state_recorder.last_record_time > latest_recorder.last_record_time:
                    latest_recorder = state_recorder
                    target_name = name

            result.append(target_name)

        return result

    def switch_by_agent_name(self, agent_name: str, update_time: float, update_state: bool = True) -> Tuple[int, List[StateRecord]]:
        """
        根据代理人名称进行切换
        :param agent_name:
        :param update_time:
        :param update_state:
        :return: 目标代理人的位置 切换导致的状态更新
        """
        switch_agent = None
        for agent_enum in AgentEnum:
            if agent_enum.value.agent_name == agent_name:
                switch_agent = agent_enum.value
                break
        if switch_agent is None:
            return 0, []

        target_agent_pos = self.team_info.get_agent_pos(switch_agent)
        if target_agent_pos == 2:  # 在下一个
            return target_agent_pos, self.switch_next_agent(update_time, update_state=update_state, check_agent=True)
        elif target_agent_pos == 3:  # 在上一个
            return target_agent_pos, self.switch_prev_agent(update_time, update_state=update_state, check_agent=True)
        else:
            return 0, []

    def _get_agent_state_records(self, update_time: float, switch: bool = False) -> List[StateRecord]:
        """
        获取代理人相关的状态
        :param update_time:
        :param switch: 是否切换角色
        :return:
        """
        state_records = []
        for i in range(len(self.team_info.agent_list)):
            prefix = '前台-' if i == 0 else ('后台-%d-' % i)
            agent_info = self.team_info.agent_list[i]

            # 需要识别到角色的状态
            agent = agent_info.agent
            if agent is not None:
                state_records.append(StateRecord(prefix + agent.agent_name, update_time))
                state_records.append(StateRecord(prefix + agent.agent_type.value, update_time))

                if i > 0:
                    state_records.append(StateRecord(f'后台-{agent.agent_name}', update_time))
                if i == 0 and switch:
                    state_records.append(StateRecord(f'切换角色-{agent.agent_name}', update_time))
                    state_records.append(StateRecord(f'切换角色-{agent.agent_type.value}', update_time))
                    self._last_switch_agent_time = update_time

                state_records.append(StateRecord(f'{agent.agent_name}-能量', update_time, agent_info.energy))
                state_records.append(StateRecord(f'{agent.agent_name}-特殊技可用', update_time, is_clear=not agent_info.special_ready))

                # 只有距离上次切换超过1秒才更新终结技状态
                if update_time - self._last_switch_agent_time >= 1.0:
                    state_records.append(StateRecord(f'{agent.agent_name}-终结技可用', update_time, is_clear=not agent_info.ultimate_ready))

            # 特殊技和终结技的按钮
            if i == 0:
                state_records.append(StateRecord(BattleStateEnum.STATUS_SPECIAL_READY.value, update_time, is_clear=not agent_info.special_ready))
                state_records.append(StateRecord(BattleStateEnum.STATUS_ULTIMATE_READY.value, update_time, is_clear=not agent_info.ultimate_ready))

            state_records.append(StateRecord(f'{prefix}能量', update_time, agent_info.energy))
            state_records.append(StateRecord(f'{prefix}特殊技可用', update_time, is_clear=not agent_info.special_ready))
            state_records.append(StateRecord(f'{prefix}终结技可用', update_time, is_clear=not agent_info.ultimate_ready))

        return state_records


def __debug_agent():
    ctx = ZContext()
    ctx.init_by_config()
    from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
    op = AutoBattleOperator(ctx, '' , '', is_mock=True)
    agent_ctx = AutoBattleAgentContext(ctx)
    agent_ctx.init_battle_agent_context(op)

    from one_dragon.utils import debug_utils
    import time
    screen = debug_utils.get_debug_image('1')
    agent_ctx.check_agent_related(screen, time.time())
    for i in agent_ctx.team_info.agent_list:
        print('角色 %s 能量 %d' % (i.agent.agent_name if i.agent is not None else 'none', i.energy))


if __name__ == '__main__':
    __debug_agent()