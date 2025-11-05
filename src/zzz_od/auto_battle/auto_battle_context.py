import time
from concurrent.futures import ThreadPoolExecutor, Future

import threading
from cv2.typing import MatLike
from typing import Optional, List, Union, Tuple

from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator
from one_dragon.base.conditional_operation.state_recorder import StateRecord
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from one_dragon.utils import cv2_utils, thread_utils, cal_utils, str_utils
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle.auto_battle_agent_context import AutoBattleAgentContext
from zzz_od.auto_battle.auto_battle_custom_context import AutoBattleCustomContext
from zzz_od.auto_battle.auto_battle_dodge_context import AutoBattleDodgeContext
from zzz_od.auto_battle.auto_battle_target_context import AutoBattleTargetContext
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent

_battle_state_check_executor = ThreadPoolExecutor(thread_name_prefix='od_battle_state_check', max_workers=16)


class AutoBattleContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        self.agent_context: AutoBattleAgentContext = AutoBattleAgentContext(self.ctx)
        self.dodge_context: AutoBattleDodgeContext = AutoBattleDodgeContext(self.ctx)
        self.custom_context: AutoBattleCustomContext = AutoBattleCustomContext(self.ctx)
        self.target_context: AutoBattleTargetContext = AutoBattleTargetContext(self.ctx)
        self.auto_op: ConditionalOperator = ConditionalOperator('', '', is_mock=True)

        # 识别区域
        self._check_distance_area: Optional[ScreenArea] = None

        # 识别锁 保证每种类型只有1实例在进行识别
        self._check_chain_lock = threading.Lock()
        self._check_quick_lock = threading.Lock()
        self._check_end_lock = threading.Lock()
        self._check_distance_lock = threading.Lock()

        # 识别间隔
        self._check_chain_interval: Union[float, List[float]] = 0
        self._check_quick_interval: Union[float, List[float]] = 0
        self._check_end_interval: Union[float, List[float]] = 5
        self._check_distance_interval: Union[float, List[float]] = 5

        # 上一次识别的时间
        self._last_check_chain_time: float = 0
        self._last_check_quick_time: float = 0
        self._last_check_end_time: float = 0
        self._last_check_distance_time: float = 0

        # 识别结果
        self.last_check_in_battle: bool = False  # 是否在战斗画面
        self.last_check_end_result: Optional[str] = None
        self.last_check_distance: float = -1  # 最后一次识别的距离
        self.without_distance_times: int = 0  # 没有显示距离的次数
        self.with_distance_times: int = 0  # 有显示距离的次数

    def dodge(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_DODGE.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_DODGE.value + '-松开'
        else:
            e = BattleStateEnum.BTN_DODGE.value

        self.ctx.controller.dodge(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def switch_next(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        update_agent = False
        if press:
            e = BattleStateEnum.BTN_SWITCH_NEXT.value + '-按下'
            update_agent = True
        elif release:
            e = BattleStateEnum.BTN_SWITCH_NEXT.value + '-松开'
        else:
            e = BattleStateEnum.BTN_SWITCH_NEXT.value
            update_agent = True

        start_time = time.time()
        self.ctx.controller.switch_next(press=press, press_time=press_time, release=release)

        finish_time = time.time()
        state_records = [StateRecord(e, finish_time)]
        if update_agent:
            # 切换角色的状态时间应该是按键开始时间
            agent_records = self.agent_context.switch_next_agent(start_time, False, check_agent=True)
            for i in agent_records:
                state_records.append(i)
        self.auto_op.batch_update_states(state_records)

    def switch_prev(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        update_agent = False
        if press:
            e = BattleStateEnum.BTN_SWITCH_PREV.value + '-按下'
            update_agent = True
        elif release:
            e = BattleStateEnum.BTN_SWITCH_PREV.value + '-松开'
        else:
            e = BattleStateEnum.BTN_SWITCH_PREV.value
            update_agent = True

        start_time = time.time()
        self.ctx.controller.switch_prev(press=press, press_time=press_time, release=release)

        finish_time = time.time()
        state_records = [StateRecord(e, finish_time)]
        if update_agent:
            # 切换角色的状态时间应该是按键开始时间
            agent_records = self.agent_context.switch_prev_agent(start_time, False, check_agent=True)
            for i in agent_records:
                state_records.append(i)
        self.auto_op.batch_update_states(state_records)

    def normal_attack(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_SWITCH_NORMAL_ATTACK.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_SWITCH_NORMAL_ATTACK.value + '-松开'
        else:
            e = BattleStateEnum.BTN_SWITCH_NORMAL_ATTACK.value

        self.ctx.controller.normal_attack(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def special_attack(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_SWITCH_SPECIAL_ATTACK.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_SWITCH_SPECIAL_ATTACK.value + '-松开'
        else:
            e = BattleStateEnum.BTN_SWITCH_SPECIAL_ATTACK.value

        self.ctx.controller.special_attack(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def ultimate(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_ULTIMATE.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_ULTIMATE.value + '-松开'
        else:
            e = BattleStateEnum.BTN_ULTIMATE.value

        self.ctx.controller.ultimate(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def chain_left(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        update_agent = False
        if press:
            e = BattleStateEnum.BTN_CHAIN_LEFT.value + '-按下'
            update_agent = True
        elif release:
            e = BattleStateEnum.BTN_CHAIN_LEFT.value + '-松开'
        else:
            e = BattleStateEnum.BTN_CHAIN_LEFT.value
            update_agent = True

        start_time = time.time()
        self.ctx.controller.chain_left(press=press, press_time=press_time, release=release)

        finish_time = time.time()
        state_records = [StateRecord(e, finish_time)]
        if update_agent:
            # 切换角色的状态时间应该是按键开始时间
            # 使用正确的连携技逻辑，而不是简单的切换到上一个角色
            agent_records = self.agent_context.chain_left(start_time, False)
            for i in agent_records:
                state_records.append(i)
        self.auto_op.batch_update_states(state_records)

    def chain_right(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        update_agent = False
        if press:
            e = BattleStateEnum.BTN_CHAIN_RIGHT.value + '-按下'
            update_agent = True
        elif release:
            e = BattleStateEnum.BTN_CHAIN_RIGHT.value + '-松开'
        else:
            e = BattleStateEnum.BTN_CHAIN_RIGHT.value
            update_agent = True

        start_time = time.time()
        self.ctx.controller.chain_right(press=press, press_time=press_time, release=release)

        finish_time = time.time()
        state_records = [StateRecord(e, finish_time)]
        if update_agent:
            # 切换角色的状态时间应该是按键开始时间
            # 使用正确的连携技逻辑，而不是简单的切换到下一个角色
            agent_records = self.agent_context.chain_right(start_time, False)
            for i in agent_records:
                state_records.append(i)
        self.auto_op.batch_update_states(state_records)

    def move_w(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_MOVE_W.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_MOVE_W.value + '-松开'
        else:
            e = BattleStateEnum.BTN_MOVE_W.value

        self.ctx.controller.move_w(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def move_s(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_MOVE_S.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_MOVE_S.value + '-松开'
        else:
            e = BattleStateEnum.BTN_MOVE_S.value

        self.ctx.controller.move_s(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def move_a(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_MOVE_A.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_MOVE_A.value + '-松开'
        else:
            e = BattleStateEnum.BTN_MOVE_A.value

        self.ctx.controller.move_a(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def move_d(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_MOVE_D.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_MOVE_D.value + '-松开'
        else:
            e = BattleStateEnum.BTN_MOVE_D.value

        self.ctx.controller.move_d(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def lock(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_LOCK.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_LOCK.value + '-松开'
        else:
            e = BattleStateEnum.BTN_LOCK.value

        self.ctx.controller.lock(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def chain_cancel(self, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            e = BattleStateEnum.BTN_CHAIN_CANCEL.value + '-按下'
        elif release:
            e = BattleStateEnum.BTN_CHAIN_CANCEL.value + '-松开'
        else:
            e = BattleStateEnum.BTN_CHAIN_CANCEL.value

        self.ctx.controller.chain_cancel(press=press, press_time=press_time, release=release)
        finish_time = time.time()
        self.auto_op.update_state(StateRecord(e, finish_time))

    def quick_assist(self):
        # 切换角色的状态时间应该是按键开始时间
        start_time = time.time()
        pos, state_records = self.agent_context.switch_quick_assist(start_time, False)

        if pos == 2:
            self.ctx.controller.switch_next()
            btn_name = BattleStateEnum.BTN_SWITCH_NEXT.value
        elif pos == 3:
            self.ctx.controller.switch_prev()
            btn_name = BattleStateEnum.BTN_SWITCH_PREV.value
        else:
            return

        finish_time = time.time()
        state_records.append(StateRecord(btn_name, finish_time))
        self.auto_op.batch_update_states(state_records)

    def switch_by_name(self, agent_name: str) -> None:
        """
        根据代理人名称 切换到指定的代理人
        :param agent_name: 代理人名称
        :return:
        """
        # 切换角色的状态时间应该是按键开始时间
        start_time = time.time()
        pos, state_records = self.agent_context.switch_by_agent_name(agent_name, update_time=start_time, update_state=False)

        if pos == 2:
            self.ctx.controller.switch_next()
            btn_name = BattleStateEnum.BTN_SWITCH_NEXT.value
        elif pos == 3:
            self.ctx.controller.switch_prev()
            btn_name = BattleStateEnum.BTN_SWITCH_PREV.value
        else:
            return

        finish_time = time.time()
        state_records.append(StateRecord(btn_name, finish_time))
        self.auto_op.batch_update_states(state_records)

    def init_battle_context(
            self,
            auto_op: ConditionalOperator,
            use_gpu: bool = True,
            check_dodge_interval: Union[float, List[float]] = 0,
            agent_names: Optional[List[str]] = None,
            to_check_state_list: Optional[List[str]] = None,
            check_agent_interval: Union[float, List[float]] = 0,
            check_chain_interval: Union[float, List[float]] = 0,
            check_quick_interval: Union[float, List[float]] = 0,
            check_end_interval: Union[float, List[float]] = 5,
            target_lock_interval: float = 0,
            abnormal_status_interval: float = 0,
    ) -> None:
        """
        自动战斗前的初始化
        :return:
        """
        self.auto_op: ConditionalOperator = auto_op
        self.agent_context.init_battle_agent_context(
            auto_op,
            agent_names,
            to_check_state_list,
            check_agent_interval,
        )
        self.dodge_context.init_battle_dodge_context(
            auto_op=auto_op,
            use_gpu=use_gpu,
            check_dodge_interval=check_dodge_interval
        )
        self.custom_context.init_battle_custom_context(auto_op)
        self.target_context.init_battle_target_context(
            auto_op=auto_op,
            target_lock_interval=target_lock_interval,
            abnormal_status_interval=abnormal_status_interval
        )

        self._to_check_states: set[str] = set(to_check_state_list) if to_check_state_list is not None else None

        # 识别区域 先读取出来 不要每次用的时候再读取
        self._check_distance_area = self.ctx.screen_loader.get_area('战斗画面', '距离显示区域')

        self.area_btn_normal: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '按键-普通攻击')
        self.area_btn_special: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '按键-特殊攻击')
        self.area_btn_ultimate: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '按键-终结技')
        self.area_btn_switch: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '按键-切换角色')

        self.area_chain_1: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '连携技-1')
        self.area_chain_2: ScreenArea = self.ctx.screen_loader.get_area('战斗画面', '连携技-2')

        # 识别间隔
        self._check_chain_interval = check_chain_interval
        self._check_quick_interval = check_quick_interval
        self._check_end_interval = check_end_interval
        self._check_distance_interval = 5

        # 上一次识别的时间
        self._last_check_chain_time: float = 0
        self._last_check_quick_time: float = 0
        self._last_check_end_time: float = 0
        self._last_check_distance_time: float = 0

        # 识别结果
        self.last_check_end_result: Optional[str] = None  # 识别战斗结束的结果
        self.without_distance_times: int = 0  # 没有显示距离的次数
        self.with_distance_times: int = 0  # 有显示距离的次数
        self.last_check_distance = -1

    def check_battle_state(
            self, screen: MatLike, screenshot_time: float,
            check_battle_end_normal_result: bool = False,
            check_battle_end_hollow_result: bool = False,
            check_battle_end_defense_result: bool = False,
            check_distance: bool = False,
            sync: bool = False
    ) -> bool:
        """
        识别战斗状态的总入口
        :return: 当前是否在战斗画面
        """
        in_battle = self.is_normal_attack_btn_available(screen)
        self.last_check_in_battle = in_battle

        future_list: List[Future] = []

        # 统一提交检测任务
        if in_battle:
            # 闪避相关
            audio_future = _battle_state_check_executor.submit(self.dodge_context.check_dodge_audio, screenshot_time)
            future_list.append(audio_future)
            future_list.append(_battle_state_check_executor.submit(self.dodge_context.check_dodge_flash, screen, screenshot_time, audio_future))

            # 角色状态
            future_list.append(_battle_state_check_executor.submit(self.agent_context.check_agent_related, screen, screenshot_time))

            # 目标状态
            future_list.append(_battle_state_check_executor.submit(self.target_context.run_all_checks, screen, screenshot_time))

            # 快速支援
            future_list.append(_battle_state_check_executor.submit(self.check_quick_assist, screen, screenshot_time))

            # 距离
            if check_distance:
                future_list.append(_battle_state_check_executor.submit(self._check_distance_with_lock, screen, screenshot_time))
        else:
            # 连携
            future_list.append(_battle_state_check_executor.submit(self.check_chain_attack, screen, screenshot_time))

            # 战斗结束
            check_battle_end = check_battle_end_normal_result or check_battle_end_hollow_result or check_battle_end_defense_result
            if check_battle_end:
                future_list.append(_battle_state_check_executor.submit(
                    self._check_battle_end, screen, screenshot_time,
                    check_battle_end_normal_result, check_battle_end_hollow_result, check_battle_end_defense_result
                ))

        # 统一处理结果
        for future in future_list:
            future.add_done_callback(thread_utils.handle_future_result)

        if sync:
            for future in future_list:
                future.result()

        return in_battle

    def check_chain_attack(self, screen: MatLike, screenshot_time: float) -> None:
        """
        识别连携技
        """
        if not self._check_chain_lock.acquire(blocking=False):
            return

        try:
            if screenshot_time - self._last_check_chain_time < cal_utils.random_in_range(self._check_chain_interval):
                # 还没有达到识别间隔
                return
            self._last_check_chain_time = screenshot_time

            self._check_chain_attack_in_parallel(screen, screenshot_time)
        except Exception:
            log.error('识别连携技出错', exc_info=True)
        finally:
            self._check_chain_lock.release()

    def _check_chain_attack_in_parallel(self, screen: MatLike, screenshot_time: float):
        """
        并行识别连携技角色
        """
        c1 = cv2_utils.crop_image_only(screen, self.area_chain_1.rect)
        c2 = cv2_utils.crop_image_only(screen, self.area_chain_2.rect)

        possible_agents = self.agent_context.get_possible_agent_list()

        result_agent_list: List[Optional[Agent]] = []
        future_list: List[Future] = []
        future_list.append(_battle_state_check_executor.submit(self._match_chain_agent_in, c1, possible_agents))
        future_list.append(_battle_state_check_executor.submit(self._match_chain_agent_in, c2, possible_agents))

        for future in future_list:
            try:
                future.add_done_callback(thread_utils.handle_future_result)
                result = future.result()
                result_agent_list.append(result)
            except Exception:
                log.error('识别连携技角色头像失败', exc_info=True)
                result_agent_list.append(None)

        state_records: List[StateRecord] = []
        for i in range(len(result_agent_list)):
            if result_agent_list[i] is None:
                continue
            state_records.append(StateRecord(f'连携技-{i + 1}-{result_agent_list[i].agent_name}', screenshot_time))
            state_records.append(StateRecord(f'连携技-{i + 1}-{result_agent_list[i].agent_type.value}', screenshot_time))

        if len(state_records) > 0:
            # 有其中一个能识别时 另一个不能识别的就是邦布
            for i in range(len(result_agent_list)):
                if result_agent_list[i] is not None:
                    continue
                state_records.append(StateRecord(f'连携技-{i + 1}-邦布', screenshot_time))

            state_records.append(StateRecord(BattleStateEnum.STATUS_CHAIN_READY.value, screenshot_time))
            self.auto_op.batch_update_states(state_records)

    def _match_chain_agent_in(self, img: MatLike, possible_agents: Optional[List[Tuple[Agent, Optional[str]]]]) -> Optional[Agent]:
        """
        在候选列表重匹配角色
        :return:
        """
        prefix = 'avatar_chain_'
        for agent, specific_template_id in possible_agents:
            # 上次识别过的模板 ID，接着用
            if specific_template_id:
                template_to_check = prefix + specific_template_id
                mrl = self.ctx.tm.match_template(img, 'battle', template_to_check, threshold=0.8)
                if mrl.max is not None:
                    return agent
            # 没有上次识别过的模板 ID，匹配所有可能的模板 ID
            else:
                for template_id in agent.template_id_list:
                    template_to_check = prefix + template_id
                    mrl = self.ctx.tm.match_template(img, 'battle', template_to_check, threshold=0.8)
                    if mrl.max is not None:
                        return agent

        return None

    def check_quick_assist(self, screen: MatLike, screenshot_time: float) -> None:
        """
        识别快速支援
        """
        if not self._check_quick_lock.acquire(blocking=False):
            return

        try:
            if screenshot_time - self._last_check_quick_time < cal_utils.random_in_range(self._check_quick_interval):
                # 还没有达到识别间隔
                return
            self._last_check_quick_time = screenshot_time

            part = cv2_utils.crop_image_only(screen, self.area_btn_switch.rect)

            possible_agents = self.agent_context.get_possible_agent_list()

            agent = self._match_quick_assist_agent_in(part, possible_agents)

            if agent is not None:
                state_records: List[StateRecord] = [
                    StateRecord(f'快速支援-{agent.agent_name}', screenshot_time),
                    StateRecord(f'快速支援-{agent.agent_type.value}', screenshot_time),
                    StateRecord(BattleStateEnum.STATUS_QUICK_ASSIST_READY.value, screenshot_time),
                ]
                self.auto_op.batch_update_states(state_records)
        except Exception:
            log.error('识别快速支援失败', exc_info=True)
        finally:
            self._check_quick_lock.release()

    def _match_quick_assist_agent_in(self, img: MatLike, possible_agents: Optional[List[Tuple[Agent, Optional[str]]]]) -> Optional[Agent]:
        """
        在候选列表重匹配角色
        :return:
        """
        prefix = 'avatar_quick_'
        for agent, specific_template_id in possible_agents:
            # 上次识别过的模板 ID，接着用
            if specific_template_id:
                template_to_check = prefix + specific_template_id
                mrl = self.ctx.tm.match_template(img, 'battle', template_to_check, threshold=0.8)
                if mrl.max is not None:
                    return agent
            # 没有上次识别过的模板 ID，匹配所有可能的模板 ID
            else:
                for template_id in agent.template_id_list:
                    template_to_check = prefix + template_id
                    mrl = self.ctx.tm.match_template(img, 'battle', template_to_check, threshold=0.8)
                    if mrl.max is not None:
                        return agent

        return None

    def _check_battle_end(self, screen: MatLike, screenshot_time: float,
                          check_battle_end_normal_result: bool,
                          check_battle_end_hollow_result: bool,
                          check_battle_end_defense_result: bool = False,) -> None:
        if not self._check_end_lock.acquire(blocking=False):
            return

        try:
            if screenshot_time - self._last_check_end_time < cal_utils.random_in_range(self._check_end_interval):
                # 还没有达到识别间隔
                return
            self._last_check_end_time = screenshot_time

            if check_battle_end_hollow_result:
                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='零号空洞-战斗', area_name='挑战结果')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '零号空洞-挑战结果'
                    return

                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='零号空洞-事件', area_name='背包')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '零号空洞-背包'
                    return

                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='零号空洞-战斗', area_name='鸣徽-确定')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '鸣徽-确定'
                    return

                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='零号空洞-战斗', area_name='结算周期上限-确认')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '零号空洞-结算周期上限'
                    return

            if check_battle_end_defense_result:
                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='式舆防卫战', area_name='战斗结束-退出')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '战斗结束-退出'
                    return

                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='式舆防卫战', area_name='战斗结束-撤退')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '战斗结束-撤退'
                    return

            if check_battle_end_normal_result:
                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='战斗画面', area_name='战斗结果-完成')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '普通战斗-完成'
                    return
                result = screen_utils.find_area(ctx=self.ctx, screen=screen,
                                                screen_name='战斗画面', area_name='战斗结果-撤退')
                if result == FindAreaResultEnum.TRUE:
                    self.last_check_end_result = '普通战斗-撤退'
                    return

            self.last_check_end_result = None
        except Exception:
            log.error('识别战斗结束失败', exc_info=True)
        finally:
            self._check_end_lock.release()

    def _check_distance_with_lock(self, screen: MatLike, screenshot_time: float) -> None:
        if not self._check_distance_lock.acquire(blocking=False):
            return

        try:
            if screenshot_time - self._last_check_distance_time < cal_utils.random_in_range(self._check_distance_interval):
                # 还没有达到识别间隔
                return

            self._last_check_distance_time = screenshot_time

            self.check_battle_distance(screen)
        except Exception:
            log.error('识别距离失败', exc_info=True)
        finally:
            self._check_distance_lock.release()

    def check_battle_distance(self, screen: MatLike, last_distance: Optional[float] = None) -> MatchResult:
        """
        识别画面上显示的距离
        :param screen:
        :param last_distance: 上一次使用的距离 极少数情况会出现多个距离 这个时候转动画面保持向特定的距离转动
        :return:
        """
        area = self._check_distance_area
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)

        distance: Optional[float] = None
        mr: Optional[MatchResult] = None
        for ocr_result, mrl in ocr_result_map.items():
            last_idx = ocr_result.rfind('m')
            if last_idx == -1:
                continue
            pre_str = ocr_result[:last_idx]
            distance = str_utils.get_positive_float(pre_str, None)
            if distance is None:
                continue

            tmp_mr = mrl.max
            tmp_mr.data = distance
            tmp_mr.add_offset(area.left_top)
            # 极少数情况下会出现多个距离
            mid_x = self.ctx.project_config.screen_standard_width // 2
            if mr is None:
                mr = tmp_mr
            elif last_distance is not None:
                # 有上一次记录时 需要继续使用上一次的
                if abs(tmp_mr.data - last_distance) < abs(mr.data - last_distance):
                    mr = tmp_mr
            elif abs(tmp_mr.center.x - mid_x) < abs(mr.center.x - mid_x):
                # 选离中间最近的
                mr = tmp_mr

        if mr is not None:
            self.without_distance_times = 0
            self.with_distance_times += 1
            self.last_check_distance = distance
            self._check_distance_interval = 1  # 识别到距离的话 减少识别间隔
        else:
            self.without_distance_times += 1
            self.with_distance_times = 0
            self.last_check_distance = -1
            self._check_distance_interval = 5

        return mr

    def is_normal_attack_btn_available(self, screen: MatLike) -> bool:
        """
        识别普通攻击按钮是否存在 用了粗略判断是否在战斗画面 2~3ms
        :param screen:
        :return:
        """
        part = cv2_utils.crop_image_only(screen, self.area_btn_normal.rect)
        mrl = self.ctx.tm.match_template(part, 'battle', 'btn_normal_attack',
                                         threshold=0.9)
        return mrl.max is not None

    def start_context(self) -> None:
        """
        启动上下文
        :return:
        """
        self.dodge_context.start_context()

    def stop_context(self) -> None:
        """
        暂停上下文
        :return:
        """
        self.dodge_context.stop_context()

        log.info('松开所有按键')
        self.dodge(release=True)
        self.switch_next(release=True)
        self.switch_prev(release=True)
        self.normal_attack(release=True)
        self.special_attack(release=True)
        self.ultimate(release=True)
        self.chain_left(release=True)
        self.chain_right(release=True)
        self.move_w(release=True)
        self.move_s(release=True)
        self.move_a(release=True)
        self.move_d(release=True)
        self.lock(release=True)
        self.chain_cancel(release=True)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
    auto_op = AutoBattleOperator(ctx, 'auto_battle', '专属配队-简')
    auto_op.init_before_running()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1735134333210')
    now = time.time()
    auto_op.auto_battle_context.check_battle_state(screen, now, check_battle_end_normal_result=True)
    time.sleep(5)
    for r in auto_op.state_recorders.values():
        if r.last_record_time != -1:
            print(f'{r.state_name} {r.last_record_time} {r.last_value}')


if __name__ == '__main__':
    __debug()