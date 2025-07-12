import cv2
import difflib
from cv2.typing import MatLike
from typing import Optional, List, ClassVar

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent, AgentEnum
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.event_ocr_result_handler import EventOcrResultHandler
from zzz_od.operation.zzz_operation import ZOperation


class RejectOption:

    def __init__(self, word: str, lcs_percent: float = 0.5):
        self.word: str = word
        self.lcs_percent: float = lcs_percent


class CallForSupport(ZOperation):

    OPT_LIKE_EVENT_NAME: ClassVar[str] = '支援代理人吧'
    STATUS_ACCEPT: ClassVar[str] = '接应支援代理人'
    STATUS_NO_NEED: ClassVar[str] = '无需支援'
    STATUS_REPLACE: ClassVar[str] = '接替小组成员'

    def __init__(self, ctx: ZContext):
        """
        确定出现事件后调用
        :param ctx:
        """
        event_name = HollowZeroSpecialEvent.CALL_FOR_SUPPORT.value.event_name
        ZOperation.__init__(
            self, ctx,
            op_name=gt(event_name, 'game')
        )

        self._handlers: List[EventOcrResultHandler] = [
            EventOcrResultHandler(CallForSupport.STATUS_ACCEPT, method=self.check_team),
            EventOcrResultHandler(CallForSupport.STATUS_REPLACE, method=self.check_team),
            EventOcrResultHandler(CallForSupport.OPT_LIKE_EVENT_NAME, is_event_mark=True),
            EventOcrResultHandler(event_name, is_event_mark=True)
        ]

    def handle_init(self):
        self.should_call_pos: int = 0  # 呼叫支援的位置
        self.new_agent: Optional[Agent] = None  # 本次加入的代理人

    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()
        return hollow_event_utils.check_event_text_and_run(self, screen, self._handlers)

    def check_team(self, text: str, rect: Rect) -> OperationRoundResult:
        """
        判断当前配队 决定选择的角色
        """
        screen = self.screenshot()
        agent_list = self.ctx.hollow.check_agent_list(screen)

        if agent_list is None:
            return self.round_retry('无法识别当前角色列表', wait=1)

        self.new_agent = self._get_support_agent(screen)
        if self.new_agent is None:
            log.error('无法识别当前增援角色')
        self.should_call_pos = self._should_call_backup(agent_list, self.new_agent)

        if self.should_call_pos is not None:
            return self.round_success(CallForSupport.STATUS_ACCEPT)
        else:
            return self.round_success(CallForSupport.STATUS_NO_NEED)

    def _get_support_agent(self, screen: MatLike) -> Optional[Agent]:
        area = self.ctx.screen_loader.get_area('零号空洞-事件', '呼叫增援-角色行')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)

        return self._best_match_agent(ocr_result)

    def _best_match_agent(self, ocr_result: str) -> Optional[Agent]:
        ocr_result = ocr_result.replace('「', '')
        idx1 = ocr_result.find('响')
        idx2 = ocr_result.find('应')
        idx3 = ocr_result.find('了')
        if idx1 != -1 and idx1 > 0:
            to_match = ocr_result[:idx1]
        elif idx2 != -1 and idx2 - 1 > 0:
            to_match = ocr_result[:idx2-1]
        elif idx3 != -1 and idx3 - 2 > 0:
            to_match = ocr_result[:idx3-2]
        else:  # 默认情况只取前面3个字匹配
            to_match = ocr_result[:3]

        agent_list: List[Agent] = [agent.value for agent in AgentEnum]
        target_list: List[str] = [gt(agent.value.agent_name, 'game') for agent in AgentEnum]

        results = difflib.get_close_matches(to_match, target_list, n=1, cutoff=0.1)

        if results is not None and len(results) > 0:
            idx = target_list.index(results[0])
            return agent_list[idx]
        else:
            return None

    def _should_call_backup(self, agent_list: List[Agent], new_agent: Agent) -> Optional[int]:
        """
        是否应该呼叫增援
        """
        targets = self.ctx.hollow_zero_challenge_config.target_agents
        start_idx = 0
        for i in range(len(targets)):
            ta = targets[i]
            if ta is None:
                continue
            if self._is_agent_for_target(agent_list[0], ta):
                start_idx = i
                break

        order_targets = targets[start_idx:] + targets[:start_idx]

        if agent_list[1] is None:  # 当前有1个代理人
            if self._is_agent_for_target(new_agent, order_targets[1]):  # 新的应该在2号位
                return 2
            elif self._is_agent_for_target(new_agent, order_targets[2]):  # 新的应该在3号位 需要先插入到1号位
                return 1
            else:  # 新角色不在目标列表 随便放置到2号位
                return 2
        elif agent_list[2] is None:  # 当前有2个代理人
            if self._is_agent_for_target(agent_list[1], order_targets[1]):  # 当前第2位位置正确
                return 3
            elif self._is_agent_for_target(agent_list[1], order_targets[2]):  # 当前第2位应该在第3位
                return 2
            elif self._is_agent_for_target(new_agent, order_targets[1]):  # 当前第2位不在目标列表 新的应该在第2位
                return 2
            elif self._is_agent_for_target(new_agent, order_targets[2]):  # 当前第2位不在目标列表 新的应该在第3位
                return 3
            else:  # 兜底第3位
                return 3
        else:  # 当前有3个代理人
            if new_agent is None:
                return None

            # 新代理人匹配的位置
            new_target_idx = -1
            for i in range(len(order_targets)):
                if self._is_agent_for_target(new_agent, order_targets[i]):
                    new_target_idx = i
                    break

            if new_target_idx == -1:  # 不在目标中
                return None
            else:
                # 如果之前已经有2人符合目标 则这2人一定会在指定位置上
                # 因此第3人只需要直接放到指定位置上即可
                return new_target_idx + 1

    def _is_agent_for_target(self, agent: Agent, target: str) -> bool:
        """
        代理人是否符合目标配队
        :param agent: 代理人
        :param target: 目标配队的名称 = 代理人ID or 类型名称
        :return:
        """
        if agent is None:
            return False
        return agent.agent_id == target or agent.agent_type.value == target

    @node_from(from_name='画面识别', status=STATUS_ACCEPT)
    @operation_node(name=STATUS_ACCEPT)
    def accept_backup(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = hollow_event_utils.get_event_text_area(self.ctx)
        result = self.round_by_ocr_and_click(screen, CallForSupport.STATUS_ACCEPT, area=area)
        if result.is_success:
            self.replace = False
            return self.round_success(wait=2)

        result = self.round_by_ocr_and_click(screen, '接替小队成员', area=area, lcs_percent=0.8)
        if result.is_success:
            self.replace = True
            return self.round_success(wait=2)

        return self.round_retry(wait=1)

    @node_from(from_name=STATUS_ACCEPT)
    @operation_node(name='选择位置')
    def choose_pos(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = hollow_event_utils.get_event_text_area(self.ctx)
        if self.replace:
            cn = '接替%d号队员的位置' % self.should_call_pos
        else:
            cn = '%d号位' % self.should_call_pos
        return self.round_by_ocr_and_click(screen, cn, area=area, lcs_percent=1,
                                           success_wait=2, retry_wait=1)

    @node_from(from_name='选择位置')
    @operation_node(name='确认')
    def confirm(self) -> OperationRoundResult:
        self.ctx.hollow.update_agent_list_after_support(self.new_agent, self.should_call_pos)
        return hollow_event_utils.click_empty(self)

    @node_from(from_name='画面识别', status=STATUS_NO_NEED)
    @operation_node(name='拒绝')
    def reject_agent(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = hollow_event_utils.get_event_text_area(self.ctx)
        # 每个角色的不接受选项不一样
        opts = [
            RejectOption('下次再依靠你'),  # 本
            RejectOption('这次没有研究的机会'),  # 格蕾丝
            RejectOption('先不劳烦青衣了'),  # 青衣
            RejectOption('暂不需要援护'),  # 丽娜
            RejectOption('目前不需要支援'),  # 派派, 耀嘉音, 零号·安比, 薇薇安
            RejectOption('下次再雇你'),  # 妮可
            RejectOption('市民更需要你'),  # 朱鸢
            RejectOption('无需增援', lcs_percent=0.6),  # 安比
            RejectOption('无需增援over'),  # 11号
            RejectOption('下次指名你'),  # 莱卡恩
            RejectOption('辛苦了兄弟下次一起'),  # 安东
            RejectOption('谢谢可琳这次不用'),  # 可琳
            RejectOption('星徽骑士再见'),  # 比利
            RejectOption('还不用请出白祇重工'),  # 珂蕾妲
            RejectOption('杀以骸焉用艾莲'),  # 艾莲
            RejectOption('这次不用快回去吃饭吧'),  # 苍角
            RejectOption('谢谢你的好意下次一定'),  # 赛斯
            RejectOption('这点小事不用专家出马'),  # 简
            RejectOption('下一次一起玩'),  # 猫又
            RejectOption('谢谢露西但我能搞定'),  # 露西
            RejectOption('之后有机会再一起玩吧'),  # 柏妮思
            RejectOption('不打扰你工作了'),  # 月城柳
            RejectOption('还不到常胜冠军出马的时候'),  # 莱特
            RejectOption('等遇到大问题再找你帮忙！'),  # 雅
            RejectOption('怎么能让你加班呢'),  # 悠真
            RejectOption('放心去照顾嘉音吧，我没问题的'),  # 伊芙琳
        ]

        part = cv2_utils.crop_image_only(screen, area.rect)
        white = cv2.inRange(part, (240, 240, 240), (255, 255, 255))
        white = cv2_utils.dilate(white, 5)
        to_ocr = cv2.bitwise_and(part, part, mask=white)

        target_list = [gt(i.word, 'game') for i in opts]
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        for ocr_result, mrl in ocr_result_map.items():
            results = difflib.get_close_matches(ocr_result, target_list, n=1)
            if results is None or len(results) == 0:
                continue
            opt = opts[target_list.index(results[0])]
            if str_utils.find_by_lcs(results[0], ocr_result, percent=opt.lcs_percent):
                click = self.ctx.controller.click(mrl.max.center + area.left_top)
                return self.round_success(wait=1)

        return self.round_retry('未配置对应的代理人选项', wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.start_running()
    ctx.init_ocr()
    op = CallForSupport(ctx)
    op.execute()


def __debug_support_agent():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    op = CallForSupport(ctx)
    from one_dragon.utils import os_utils
    import os
    screen = cv2_utils.read_image(os.path.join(
        os_utils.get_path_under_work_dir('.debug', 'devtools', 'screen', 'hollow_zero_support'),
        'laikaen.png'
    ))
    print(op._get_support_agent(screen).agent_name)


def __debug_current_agent():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    op = CallForSupport(ctx)
    from one_dragon.utils import os_utils
    import os
    screen = cv2_utils.read_image(os.path.join(
        os_utils.get_path_under_work_dir('.debug', 'devtools', 'screen', 'hollow_zero_support'),
        'laikaen.png'
    ))
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('1')
    agent_list = ctx.hollow.check_agent_list(screen)
    print([i.agent_name for i in agent_list if i is not None])
    print(op._get_support_agent(screen).agent_name)


def __debug_check_screen():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    op = CallForSupport(ctx)
    from one_dragon.utils import os_utils
    import os
    screen = cv2_utils.read_image(os.path.join(
        os_utils.get_path_under_work_dir('.debug', 'devtools', 'screen', 'hollow_zero_support'),
        'empty.png'
    ))
    hollow_event_utils.check_event_text_and_run(op, screen, op._handlers)


if __name__ == '__main__':
    # __debug()
    # __debug_support_agent()
    __debug_current_agent()
    # __debug_check_screen()
