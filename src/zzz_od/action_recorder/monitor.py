import pickle
import os
import time
from concurrent.futures import ThreadPoolExecutor, Future


from cv2.typing import MatLike
from typing import Optional, List, Any, Union, Tuple

from pynput import keyboard, mouse

from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.conditional_operation.state_recorder import StateRecord
from one_dragon.utils import cv2_utils, thread_utils, cal_utils, os_utils, yolo_config_utils
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.auto_battle.auto_battle_context import AutoBattleContext
from zzz_od.auto_battle.auto_battle_agent_context import AutoBattleAgentContext
from zzz_od.auto_battle.auto_battle_dodge_context import AutoBattleDodgeContext, YoloStateEventEnum
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum
from zzz_od.auto_battle.auto_battle_agent_context import TeamInfo
from zzz_od.game_data.agent import Agent, AgentEnum, CommonAgentStateEnum
from zzz_od.yolo.flash_classifier import FlashClassifier

_record_executor = ThreadPoolExecutor(thread_name_prefix='od_record', max_workers=8)


class BattleAgentContext4Recording(AutoBattleAgentContext):
    def init_battle_agent_context(
            self,
            agent_names: Optional[List[str]] = None,
            to_check_state_list: Optional[List[str]] = None,
            check_agent_interval: Union[float, List[float]] = 0,
            **kwargs) -> None:
        """
        自动战斗前的初始化
        :return:
        """
        # self.auto_op: ConditionalOperator = auto_op  # 重写部分,取消auto_op
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

    def check_agent_related(self, screen: MatLike, screenshot_time: float) -> tuple[Any, Any]:
        """
        判断角色相关内容 并发送事件
        :return:
        """
        if not self._check_agent_lock.acquire(blocking=False):
            return None, None

        try:
            if screenshot_time - self._last_check_agent_time < cal_utils.random_in_range(self._check_agent_interval):
                # 还没有达到识别间隔
                return None, None
            self._last_check_agent_time = screenshot_time

            screen_agent_list = self._check_agent_in_parallel(screen)
            all_agent_state_list = self._check_all_agent_state(screen, screenshot_time, screen_agent_list)

            if screen_agent_list is None or len(screen_agent_list) == 0:
                energy_state_list = []
                other_state_list = []
            else:
                energy_state_list = all_agent_state_list[:len(screen_agent_list)]
                other_state_list = all_agent_state_list[len(screen_agent_list):]

            update_state_record_list = []
            # 尝试更新代理人列表 成功的话 更新状态记录
            if self.team_info.update_agent_list(
                    screen_agent_list,
                    [(i.value if i is not None else 0) for i in energy_state_list],
                    screenshot_time):

                for i in self._get_agent_state_records(screenshot_time):
                    update_state_record_list.append(i)

                # 只有代理人列表更新成功 本次识别的状态才可用
                for i in other_state_list:
                    update_state_record_list.append(i)

            self.auto_op.batch_update_states(update_state_record_list)

            # # # # 重写部分 # # # #
            output_agent_names = []  # 导出用
            output_agent_types = []
            output_energy = []
            output_other_state = []

            for i in range(len(self.team_info.agent_list)):
                prefix = '前台-' if i == 0 else ('后台-%d-' % i)
                agent_info = self.team_info.agent_list[i]
                if agent_info.agent is not None:
                    # 除了display, 还要内部导出
                    output_agent_names.append(prefix + agent_info.agent.agent_name)
                    output_agent_types.append(prefix + agent_info.agent.agent_type.value)
                    output_energy.append(agent_info.energy)
                    output_other_state.append(agent_info.agent.state_list)

            return output_agent_names, output_agent_types
            # # # # 重写部分 # # # #
        except Exception:
            log.error('识别画面角色失败', exc_info=True)
        finally:
            self._check_agent_lock.release()


class BattleDodgeContext4Recording(AutoBattleDodgeContext):
    def init_battle_dodge_context(self,
            use_gpu: bool = True,
            check_dodge_interval: Union[float, List[float]] = 0,
            check_audio_interval: float = 0.02,
            **kwargs
    ) -> None:
        """
        初始化上下文，在运行前调用。
        :param use_gpu: 是否使用GPU
        :param check_dodge_interval: 闪避识别间隔
        :param check_audio_interval: 音频识别间隔
        """
        # self.auto_op: ConditionalOperator = auto_op  # 重写部分,取消auto_op

        if self._flash_model is None or self._flash_model.gpu != use_gpu:
            self._flash_model = FlashClassifier(
                model_name=self.ctx.model_config.flash_classifier,
                backup_model_name=self.ctx.model_config.flash_classifier_backup,
                model_parent_dir_path=yolo_config_utils.get_model_category_dir('flash_classifier'),
                gh_proxy=self.ctx.env_config.is_gh_proxy,
                gh_proxy_url=self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None,
                personal_proxy=self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None,
                gpu=use_gpu
            )

        # 识别间隔
        self._check_dodge_interval = check_dodge_interval
        self._check_audio_interval = check_audio_interval

        # 上一次识别的时间
        self._last_check_dodge_time = 0
        self._last_check_audio_time = 0

        # # # # 重写部分 # # # #
        # 异步加载音频模板
        _record_executor.submit(self.init_audio_template)
        # # # # 重写部分 # # # #

    def check_dodge_flash(self, screen: MatLike, screenshot_time: float, audio_future: Optional[Future[bool]] = None) -> tuple[bool, str]:
        """
        识别画面是否有闪光。
        :param screen: 屏幕截图
        :param screenshot_time: 截图时间
        :param audio_future: 音频识别结果的Future对象
        :return: 是否应该闪避 （识别到闪光或者声音）
        """
        # # # # 重写部分 # # # #
        state_name = '无闪避'

        if not self._check_dodge_flash_lock.acquire(blocking=False):
            return False, state_name

        try:
            if screenshot_time - self._last_check_dodge_time < cal_utils.random_in_range(self._check_dodge_interval):
                # 还没有达到识别间隔
                return False, state_name

            self._last_check_dodge_time = screenshot_time

            result = self._flash_model.run(screen)
            if result.class_idx == 1:
                state_name = YoloStateEventEnum.DODGE_RED.value
            elif result.class_idx == 2:
                state_name = YoloStateEventEnum.DODGE_YELLOW.value
            elif audio_future is not None:
                audio_result = audio_future.result()
                if audio_result:
                    state_name = YoloStateEventEnum.DODGE_AUDIO.value

            with_flash = state_name != '无闪避'
            if with_flash:
                self.auto_op.update_state(StateRecord(state_name, screenshot_time))

            return with_flash, state_name
        # # # # 重写部分 # # # #
        except Exception:
            log.error('识别画面闪光失败', exc_info=True)
        finally:
            self._check_dodge_flash_lock.release()


class BattleContext4Recording(AutoBattleContext):
    def __init__(self, ctx: ZContext):
        super().__init__(ctx)

        self.agent_context: BattleAgentContext4Recording = BattleAgentContext4Recording(self.ctx)  # 替换
        self.dodge_context: BattleDodgeContext4Recording = BattleDodgeContext4Recording(self.ctx)  # 替换

    def init_battle_context(
            self,
            use_gpu: bool = True,
            check_dodge_interval: Union[float, List[float]] = 0,
            agent_names: Optional[List[str]] = None,
            to_check_state_list: Optional[List[str]] = None,
            check_agent_interval: Union[float, List[float]] = 0,
            check_chain_interval: Union[float, List[float]] = 0,
            check_quick_interval: Union[float, List[float]] = 0,
            check_end_interval: Union[float, List[float]] = 5,
            check_target_interval: Union[float, List[float]] = 0.1,
            **kwargs,
    ) -> None:
        """
        自动战斗前的初始化
        :return:
        """
        # # # # 重写部分 # # # #
        self.agent_context.init_battle_agent_context(
            agent_names,
            to_check_state_list,
            check_agent_interval,
        )
        self.dodge_context.init_battle_dodge_context(
            use_gpu=use_gpu,
            check_dodge_interval=check_dodge_interval
        )
        self.target_context.init_battle_target_context(auto_op=self.auto_op,
                                                       check_target_interval=check_target_interval)

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

    def check_battle_state(self, screen: MatLike, screenshot_time: float,
                           check_battle_end_normal_result: bool = False,
                           check_battle_end_hollow_result: bool = False,
                           check_distance: bool = False,
                           in_battle: bool = False,
                           **kwargs
                           ) -> dict:
        """
        识别战斗状态的总入口
        :return:
        """
        # 重写
        # in_battle = self.is_normal_attack_btn_available(screen)

        future_list: List[Future] = []

        # # # # 重写部分 # # # #
        if in_battle:
            # 状态部分
            future_list.append(_record_executor.submit(self.agent_context.check_agent_related, screen, screenshot_time))
            future_list.append(_record_executor.submit(self.target_context.run_all_checks, screen, screenshot_time))
            future_list.append(_record_executor.submit(self.check_quick_assist, screen, screenshot_time))

            audio_future = _record_executor.submit(self.dodge_context.check_dodge_audio, screenshot_time)
            future_list.append(
                _record_executor.submit(self.dodge_context.check_dodge_flash, screen, screenshot_time, audio_future))

            if check_distance:
                future_list.append(_record_executor.submit(self._check_distance_with_lock, screen, screenshot_time))
        else:
            future_list.append(_record_executor.submit(self.check_chain_attack, screen, screenshot_time))
            check_battle_end = check_battle_end_normal_result or check_battle_end_hollow_result
            if check_battle_end:
                future_list.append(_record_executor.submit(
                    self._check_battle_end, screen, screenshot_time,
                    check_battle_end_normal_result, check_battle_end_hollow_result
                ))
        for future in future_list:
            future.add_done_callback(thread_utils.handle_future_result)

        # 返回结果
        future_result = []
        for future in future_list:
            future_result.append(future.result())

        # 特殊状态部分
        try:
            if in_battle:
                output_status_record = {'代理人顺序': future_result[0][:2],
                                        '代理人信息': future_result[0][2:],
                                 BattleStateEnum.STATUS_SPECIAL_READY.value: future_result[1],
                                 BattleStateEnum.STATUS_ULTIMATE_READY.value: future_result[2],
                                 BattleStateEnum.STATUS_QUICK_ASSIST_READY.value: future_result[3],
                                 BattleStateEnum.STATUS_CHAIN_READY.value: None,}
            else:
                output_status_record = {'代理人顺序': None,
                                 BattleStateEnum.STATUS_SPECIAL_READY.value: None,
                                 BattleStateEnum.STATUS_ULTIMATE_READY.value: None,
                                 BattleStateEnum.STATUS_QUICK_ASSIST_READY.value: None,
                                 BattleStateEnum.STATUS_CHAIN_READY.value: future_result[0], }  # 连携技状态需要后续处理合并

        except (Exception, IndexError):
            output_status_record = {'代理人顺序': None,
                             BattleStateEnum.STATUS_SPECIAL_READY.value: None,
                             BattleStateEnum.STATUS_ULTIMATE_READY.value: None,
                             BattleStateEnum.STATUS_QUICK_ASSIST_READY.value: None,
                             BattleStateEnum.STATUS_CHAIN_READY.value: None}

        # 闪避状态部分
        try:
            output_dodge_record = {'闪避状态': future_result[4]}
        except (Exception, IndexError):
            output_dodge_record = {'闪避状态': (False, '无闪避')}

        output_status_record.update(output_dodge_record)

        return output_status_record

        # # # # 重写部分 # # # #
    def check_quick_assist(self, screen: MatLike, screenshot_time: float) -> tuple[str, str, str] | None:
        """
        识别快速支援
        """
        if not self._check_quick_lock.acquire(blocking=False):
            return None

        try:
            if screenshot_time - self._last_check_quick_time < cal_utils.random_in_range(self._check_quick_interval):
                # 还没有达到识别间隔
                return None
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

                # # # # 重写部分 # # # #
                # 返回快速支援状态
                return (f'快速支援-{agent.agent_name}', f'快速支援-{agent.agent_type.value}',
                        BattleStateEnum.STATUS_QUICK_ASSIST_READY.value)
                # # # # 重写部分 # # # #

        except Exception:
            log.error('识别快速支援失败', exc_info=True)
        finally:
            self._check_quick_lock.release()

    def check_chain_attack(self, screen: MatLike, screenshot_time: float) -> None:
        """
        识别连携技
        """
        if not self._check_chain_lock.acquire(blocking=False):
            return None

        try:
            if screenshot_time - self._last_check_chain_time < cal_utils.random_in_range(self._check_chain_interval):
                # 还没有达到识别间隔
                return None
            self._last_check_chain_time = screenshot_time

            # # # # 重写部分 # # # #
            agent_chains = self._check_chain_attack_in_parallel(screen, screenshot_time)
            return agent_chains
            # # # # 重写部分 # # # #

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
        future_list.append(_record_executor.submit(self._match_chain_agent_in, c1, possible_agents))
        future_list.append(_record_executor.submit(self._match_chain_agent_in, c2, possible_agents))

        for future in future_list:
            try:
                result = future.result()
                result_agent_list.append(result)
            except Exception:
                log.error('识别连携技角色头像失败', exc_info=True)
                result_agent_list.append(None)

        # # # # 重写部分 # # # #
        agent_chains = []
        state_records: List[StateRecord] = []
        for i in range(len(result_agent_list)):
            if result_agent_list[i] is None:
                continue
            state_records.append(StateRecord(f'连携技-{i + 1}-{result_agent_list[i].agent_name}', screenshot_time))
            state_records.append(StateRecord(f'连携技-{i + 1}-{result_agent_list[i].agent_type.value}', screenshot_time))

            agent_chains.append((f'连携技-{i + 1}-{result_agent_list[i].agent_name}',
                                 f'连携技-{i + 1}-{result_agent_list[i].agent_type.value}'))

        if len(state_records) > 0:
            state_records.append(StateRecord(BattleStateEnum.STATUS_CHAIN_READY.value, screenshot_time))
            self.auto_op.batch_update_states(state_records)

            return agent_chains
        else:
            return None
        # # # # 重写部分 # # # #


class PcButtonListener:
    # 重写 from one_dragon.base.controller.pc_button.pc_button_listener import PcButtonListener
    def __init__(self,
                 listen_keyboard: bool = False,
                 listen_mouse: bool = False,
                 ):
        self.keyboard_listener = keyboard.Listener(on_press=self._on_keyboard_press, on_release=self._on_keyboard_release)
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)

        # GIL锁,应该没必要额外加锁
        self.keyboard_records = []
        self.mouse_records = []

        self.listen_keyboard: bool = listen_keyboard
        self.listen_mouse: bool = listen_mouse

    def _on_keyboard_press(self, event):
        if isinstance(event, keyboard.Key):
            now = time.time()
            k = event.name
            self.keyboard_records.append([now, 'keyboard_' + k])
            log.info('keyboard_' + k)

        elif isinstance(event, keyboard.KeyCode):
            now = time.time()
            k = event.char
            self.keyboard_records.append([now, 'keyboard_' + k])
            log.info('keyboard_' + k)


    def _on_keyboard_release(self, event):
        if isinstance(event, keyboard.Key):
            now = time.time()
            k = event.name
            self.keyboard_records.append([now, 'release|keyboard_' + k])
            log.info('release|keyboard_' + k)

        elif isinstance(event, keyboard.KeyCode):
            now = time.time()
            k = event.char
            self.keyboard_records.append([now, 'release|keyboard_' + k])
            log.info('release|keyboard_' + k)


    def _on_mouse_click(self, x, y, button: mouse.Button, pressed):
        if pressed == 1:
            now = time.time()
            self.mouse_records.append([now, 'mouse_' + button.name])
            log.info('mouse_' + button.name)
        else:
            now = time.time()
            self.mouse_records.append([now, 'release|mouse_' + button.name])
            log.info('release|mouse_' + button.name)

    def start(self):
        if self.listen_keyboard:
            self.keyboard_listener.start()
        if self.listen_mouse:
            self.mouse_listener.start()

    def stop(self):
        if self.listen_keyboard:
            self.keyboard_listener.stop()
        if self.listen_mouse:
            self.mouse_listener.stop()

    def get_records(self):
        return self.keyboard_records, self.mouse_records


class RecordContext:

    sh_independent = False  # independent=True: use mss, False: use openCV

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.battle = BattleContext4Recording(ctx)
        self.battle.start_context()
        self._init_before_running()

        self.button_listener = PcButtonListener(listen_keyboard=True, listen_mouse=True)

        # 截图函数
        self.screenshot = self.ctx.controller.screenshot

        self.status_flows = []  # 状态流
        self.keyboard_flows = None  # 动作流
        self.mouse_flows = None

        self.in_battle = False

    def _init_before_running(self) -> Tuple[bool, str]:
        """
        运行前进行初始化
        :return:
        """
        try:
            # 尽量小间隔,避免漏检
            self.battle.init_battle_context(
                use_gpu=self.ctx.model_config.flash_classifier_gpu,
                check_dodge_interval=0.02,
                check_agent_interval=0.02,
                check_chain_interval=0.05,
                check_quick_interval=0.05,
                check_end_interval=5,
                check_target_interval=0.02,
            )

            return True, ''
        except Exception as e:
            log.error('自动战斗初始化失败', exc_info=True)
            return False, '初始化失败'

    def records_status_and_action(self):
        # 不在战斗中就等待
        self.in_battle = False
        while not self.in_battle:
            log.info("等待战斗开始...")
            screen = self.screenshot(self.sh_independent)
            self.in_battle = self.battle.is_normal_attack_btn_available(screen)
            time.sleep(0.5)  # 防止循环过快导致卡顿

        log.info("开始记录...")

        self.button_listener.start()  # 动作流记录器
        while self.battle.last_check_end_result is None:  # check_screen内会检查
            now = time.time()

            screen = self.screenshot(self.sh_independent)

            self.in_battle = self.battle.is_normal_attack_btn_available(screen)

            current_status = self.battle.check_battle_state(screen, now,
                                                      check_battle_end_normal_result=True,
                                                      check_battle_end_hollow_result=False,
                                                      check_distance=False,
                                                      in_battle=self.in_battle)

            self.status_flows.append([now, current_status])  # 就这量,能内存溢出估计要打上W小时吧,没必要写disk了

        self.keyboard_flows, self.mouse_flows = self.button_listener.get_records()

        self.button_listener.stop()
        self.battle.stop_context()

        log.error("记录完毕...")

    def output_records(self):
        # 临时保存至LOG日志文件夹,再进行后续处理,避免动作和状态数据丢失
        keyboard_action_file_path = os.path.join(os_utils.get_path_under_work_dir('.log'), 'keyboard_actions.pkl')
        with open(keyboard_action_file_path, 'wb') as file:  # 使用 'wb' 模式写入二进制文件
            pickle.dump(self.keyboard_flows, file)

        mouse_action_file_path = os.path.join(os_utils.get_path_under_work_dir('.log'), 'mouse_actions.pkl')
        with open(mouse_action_file_path, 'wb') as file:  # 使用 'wb' 模式写入二进制文件
            pickle.dump(self.mouse_flows, file)

        status_file_path = os.path.join(os_utils.get_path_under_work_dir('.log'), 'status.pkl')
        with open(status_file_path, 'wb') as file:  # 使用 'wb' 模式写入二进制文件
            pickle.dump(self.status_flows, file)



def _debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()

    rc_ctx = RecordContext(ctx)
    rc_ctx.records_status_and_action()
    rc_ctx.output_records()



if __name__ == '__main__':
    _debug()

