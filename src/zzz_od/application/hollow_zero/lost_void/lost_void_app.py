import math
import time
from typing import TYPE_CHECKING, ClassVar

import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.utils import cv2_utils, gpu_executor, log_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig
from zzz_od.application.hollow_zero.lost_void.lost_void_run_record import (
    LostVoidRunRecord,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent
from zzz_od.operation.agent_template_matcher import match_team_agent_template
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.deploy import Deploy

if TYPE_CHECKING:
    from cv2.typing import MatLike


class LostVoidApp(ZApplication):

    """零号空洞-迷失之地:周限肉鸽玩法(与枯萎之都共享每周奖励次数)。周限、进入战斗、耗时较长。"""
    STATUS_ENOUGH_TIMES: ClassVar[str] = '完成通关次数'
    STATUS_AGAIN: ClassVar[str] = '继续挑战'
    STATUS_AGAIN_MATRIX: ClassVar[str] = '继续挑战-矩阵行动'
    STATUS_NO_STRATEGY: ClassVar[str] = '没有可刷的调查战略'

    def __init__(self, ctx: ZContext,
                 lost_void_debug: bool = False,
                 next_region_type: LostVoidRegionType = LostVoidRegionType.ENTRY):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=lost_void_const.APP_ID,
            op_name=lost_void_const.APP_NAME,
        )
        self.config: LostVoidConfig = self.ctx.run_context.get_config(
            app_id=lost_void_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: LostVoidRunRecord = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=lost_void_const.APP_ID,
        )

        self.next_region_type = next_region_type  # 下一个区域的类型
        self.priority_agent_list: list[Agent] = []  # 优先选择的代理人列表

        self.use_priority_agent: bool = False  # 本次挑战是否使用了UP代理人

        self._strategy_scan_phase: str = '回到左端'
        self._strategy_last_page: list[tuple[str, int]] = []
        self._strategy_level_map: dict[str, int] = {}  # 向右检查时看到的 可选战略名称 -> 等级 只记 0～7
        self._strategy_target_name: str | None = None  # 看完整个列表后要选的战略
        self._stop_reason: str | None = None  # 挑战配置要求提前结束运行的原因

        # debug
        self.lost_void_debug = lost_void_debug

    @operation_node(name='初始化加载', is_start_node=True)
    def init_for_lost_void(self) -> OperationRoundResult:
        # 检查分配给今天的任务是否完成
        if self.run_record.is_finished_by_day:
            return self.round_success(LostVoidApp.STATUS_ENOUGH_TIMES)

        try:
            # 这里会加载迷失之洞的数据 识别模型 和自动战斗配置
            self.ctx.lost_void.init_before_run()
        except Exception:
            return self.round_fail('初始化失败')
        return self.round_success(LostVoidApp.STATUS_AGAIN)

    @node_from(from_name='初始化加载', status=STATUS_AGAIN)
    @operation_node(name='识别初始画面')
    def check_initial_screen(self) -> OperationRoundResult:
        if self.lost_void_debug:
            return self.round_success('迷失之地-大世界')
        result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-大世界', '按钮-挑战-确认')
        # 特殊兼容：在挑战区域开始，接力运行
        if result.is_success:
            self.next_region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
            return self.round_wait(result.status, wait=1)

        mission_name = self.config.mission_name
        screen_name, can_go = self.check_screen_with_can_go(self.last_screenshot, f'迷失之地-{mission_name}')
        if screen_name == '迷失之地-大世界':
            return self.round_success('迷失之地-大世界')

        if can_go or screen_name == f'迷失之地-{mission_name}':
            return self.round_success('可前往副本画面')

        # 未识别到画面；走快捷手册传送流程
        can_go = self.check_current_can_go('快捷手册-作战')
        if can_go:
            return self.round_success('可前往快捷手册')

        return self.round_success('未识别初始画面', wait=1)

    @node_from(from_name='识别初始画面', status='可前往快捷手册')
    @node_from(from_name='识别初始画面', status=Operation.STATUS_SCREEN_UNKNOWN)
    @node_from(from_name='识别初始画面', status='未识别初始画面')
    @operation_node(name='前往零号空洞-入口')
    def tp_to_lost_void(self) -> OperationRoundResult:
        op = TransportByCompendium(self.ctx,
                                   '作战',
                                   '周期征讨',
                                   '迷失之地')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='可前往副本画面')
    @node_from(from_name='前往零号空洞-入口')
    @operation_node(name='前往迷失之地-入口', node_max_retry_times=20)
    def choose_lost_void_entry(self) -> OperationRoundResult:
        """前往迷失之地入口"""
        result = self.round_by_ocr_and_click(self.last_screenshot, '迷失之地')
        if result.is_success:
            return self.round_retry('尝试进入迷失之地-入口', wait=1)

        if result.status == '找不到 迷失之地':
            return self._wait_for_lost_void_entry()

        return self.round_retry(result.status, wait=1)

    def _wait_for_lost_void_entry(self) -> OperationRoundResult:
        """等待迷失之地入口加载完成。"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-入口', '按钮-更新弹窗-关闭')
        if result.is_success:
            return self.round_retry(result.status, wait=0.5)

        screen_name_list = ['迷失之地-入口-周期', '迷失之地-入口-常规']
        screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=screen_name_list)
        if screen_name not in screen_name_list:
            return self.round_wait(status='等待画面加载', wait=1)
        return self.round_success(status=screen_name)

    @node_from(from_name='前往迷失之地-入口')
    @node_from(from_name='通关后处理')
    @node_notify(when=NotifyTiming.CURRENT_DONE, send_image=False, detail=True)
    @operation_node(name='识别悬赏委托完成进度')
    def check_bounty_commission_before(self) -> OperationRoundResult:
        """
        识别悬赏委托完成进度
        通过OCR识别屏幕中 '8000' 出现的次数来判断:
        - 1次: xxxx/8000 (未完成)
        - 2次: 8000/8000 (已完成)

        :return: 操作结果
        """
        if not self.config.is_bounty_commission_mode:
            if self.run_record.is_finished_by_day:
                return self.round_success(LostVoidApp.STATUS_ENOUGH_TIMES)
            if self.config.mission_name == '矩阵行动':
                return self.round_success(LostVoidApp.STATUS_AGAIN_MATRIX)
            return self.round_success(LostVoidApp.STATUS_AGAIN)

        result = self.round_by_find_area(self.last_screenshot, '迷失之地-入口', '按钮-悬赏委托')
        if not result.is_success:
            return self.round_retry('未识别到悬赏委托', wait=0.5)

        TARGET_SCORE = '8000'  # 目标分数文本

        # 裁剪悬赏委托进度区域
        area = self.ctx.screen_loader.get_area('迷失之地-入口', '区域-悬赏委托-进度')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

        # OCR识别
        ocr_result_list = self.ctx.ocr.ocr(part)

        # 统计 '8000' 出现次数
        target_count = sum(ocr_text.data.count(TARGET_SCORE) for ocr_text in ocr_result_list)

        # 根据次数判断完成状态
        if target_count == 1:
            # 只有一个 8000,表示 xxxx/8000 (未完成)
            if self.config.mission_name == '矩阵行动':
                return self.round_success(LostVoidApp.STATUS_AGAIN_MATRIX)
            return self.round_success(LostVoidApp.STATUS_AGAIN)
        elif target_count == 2:
            # 两个 8000,表示 8000/8000 (已完成)
            if not self.run_record.bounty_commission_complete:
                self.run_record.bounty_commission_complete = True
            return self.round_success(LostVoidApp.STATUS_ENOUGH_TIMES)
        else:
            # 未识别到预期的结果(0次或3次以上),返回重试
            return self.round_retry(wait=0.5)

    # ========== 矩阵行动入口流程节点 ==========

    @node_from(from_name='识别悬赏委托完成进度', status=STATUS_AGAIN_MATRIX)
    @operation_node(name='矩阵行动-前往入口')
    def matrix_goto_entry(self) -> OperationRoundResult:
        # 排除因为ocr太慢导致的错误信息
        error = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-矩阵行动-编队选择', '确认', success_wait=1)
        if error.is_success:
            log_utils.log('已点击意外出现的确认按钮')

        return self.round_by_goto_screen(
            screen_name='迷失之地-矩阵行动-编队选择',
            screen_switch_debounce=3,
        )

    @node_from(from_name='矩阵行动-前往入口')
    @operation_node(name='矩阵行动-点击预备编队')
    def matrix_click_preset_team(self) -> OperationRoundResult:
        if self.ctx.lost_void.challenge_config.manually_choose_agent:
            return self.round_success('手动选取角色')
        area = self.ctx.screen_loader.get_area('迷失之地-矩阵行动-编队选择', '预备编队')
        if area is not None:
            part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
            if cv2_utils.is_colorful(part):
                # 按钮已变成彩色，说明加载完成
                return self.round_success(status='预备编队已加载', wait=1)

        # 按钮还是灰度，需要点击
        result = self.round_by_find_and_click_area(
            self.last_screenshot,
            '迷失之地-矩阵行动-编队选择',
            '预备编队',
            success_wait=1,
        )
        if result.is_success:
            return self.round_wait(status='预备编队加载中', wait=0.5)

        return self.round_retry(status='点击预备编队失败', wait=0.5)

    @node_from(from_name='矩阵行动-点击预备编队')
    @operation_node(name='矩阵行动-选择预备编队', node_max_retry_times=7)
    def matrix_select_team(self) -> OperationRoundResult:
        # 初始为较高的匹配阈值，如果超过5次匹配失败则改用0.5的阈值兜底
        lcs_percent = 0.7 if self.node_retry_times < 5 else 0.5

        main_team_area = self.ctx.screen_loader.get_area('迷失之地-矩阵行动-编队选择', '主战编队槽')

        # 获取目标编队名称
        predefined_idx = self.ctx.lost_void.challenge_config.predefined_team_idx
        if predefined_idx == -1:
            predefined_idx = 0
        self.ctx.lost_void.predefined_team_idx = predefined_idx
        team_name = self.ctx.team_config.team_list[predefined_idx].name

        # 查找并点击目标配队
        team_match_result = self.round_by_ocr_and_click(
            screen=self.last_screenshot,
            target_cn=team_name,
            lcs_percent=lcs_percent,
            remove_whitespace=True, # 去除空白字符提高匹配兼容性
        )

        if team_match_result.is_success:
            # 等待画面更新
            time.sleep(0.5)
            self.screenshot()
            # 在主战编队槽区域检测是否出现"主战"
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                image=self.last_screenshot,
                rect=main_team_area.rect,
            )
            success_msg = '已选择配队'
            if self.node_retry_times >= 5:
                success_msg += '(随机)'
            for ocr_text in ocr_result_list:
                if '主战' in ocr_text.data:
                    return self.round_success(success_msg, wait=1)
            return self.round_retry('未找到主战', wait=0.5)

        self.scroll_area(screen_name='迷失之地-矩阵行动-编队选择', area_name='编队列表', direction='down')
        return self.round_retry(f'未找到{team_name}, 尝试向下滚动', wait=0.3)

    @node_from(from_name='矩阵行动-点击预备编队', status='手动选取角色')
    @operation_node(name='矩阵行动-选择代理人')
    def matrix_select_agent(self) -> OperationRoundResult:
        # 代理人列表
        agent_list_str = self.ctx.lost_void.challenge_config.team_info
        # agent_list_str = ['anby', 'yeshunguang', 'ellen']
        # 记录角色在第几页的哪个位置
        agent_page_match_list: list[[int, Point] | None] = [None] * len(agent_list_str)

        agent_area = self.ctx.screen_loader.get_area('迷失之地-矩阵行动-编队选择', '代理人列表')
        main_team_area = self.ctx.screen_loader.get_area('迷失之地-矩阵行动-编队选择', '主战编队槽')

        # 1. 取消主战代理人
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot,
            rect=main_team_area.rect)
        if len(ocr_result_list) > 0:
            # 需要先点一下主战编队框才能取消
            self.ctx.controller.click(ocr_result_list[0].center)
            time.sleep(0.5)
        for ocr_text in ocr_result_list:
            if '主战' in ocr_text.data:
                self.ctx.controller.click(ocr_text.center)
                time.sleep(0.5)

        # 2. 找人
        found = 0
        max_swipe_times = 5
        for page in range(max_swipe_times):
            # 从取屏幕左半边选人
            agent_mr_list = match_team_agent_template(self.ctx, self.last_screenshot, agent_area.rect, agent_list_str)
            # 匹配人
            for agent_idx in range(len(agent_list_str)):
                if agent_page_match_list[agent_idx] is not None:
                    continue
                for match_idx in range(len(agent_mr_list)):
                    if agent_list_str[agent_idx] == agent_mr_list[match_idx].data.agent_id:
                        agent_page_match_list[agent_idx] = [page, agent_mr_list[match_idx].center]
                        found += 1
                        break
            if found == len(agent_list_str):
                # 角色定位齐了, 可以选角色了
                break
            # 后面一页继续找
            self.swipe_multiple_times(agent_area, 1, 0.5, 'down')
            self.screenshot()

        # 未找齐代理人
        if found < len(agent_list_str):
            self.swipe_multiple_times(agent_area, max_swipe_times, 0.2, 'up')
            return self.round_retry('未找齐代理人')

        # 3. 选人
        # noinspection PyUnboundLocalVariable
        self.swipe_multiple_times(agent_area, page, 0.1, 'up')
        for agent_loc in range(len(agent_page_match_list)):
            self.swipe_multiple_times(agent_area, agent_page_match_list[agent_loc][0], 0.1, 'down')
            self.ctx.controller.click(agent_page_match_list[agent_loc][1])
            time.sleep(0.5)
            self.swipe_multiple_times(agent_area, agent_page_match_list[agent_loc][0], 0.1, 'up')

        return self.round_success()

    # 滑动x次 (滑慢点以免帧率低时可能出现的滑不到位)
    def swipe_multiple_times(self, area, swipe_num, wait, direction) -> None:
        for _ in range(swipe_num):
            screen_utils.scroll_area(self.ctx, area, direction, 0.75, 0.25, duration=1)
            time.sleep(wait)

    @node_from(from_name='矩阵行动-选择预备编队')
    @node_from(from_name='矩阵行动-选择代理人')
    @operation_node(name='矩阵行动-点击协战代理人')
    def matrix_click_support_agent(self) -> OperationRoundResult:
        """在矩阵行动页面点击协战代理人。"""
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '迷失之地-矩阵行动-编队选择',
            '协战代理人',
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='矩阵行动-点击协战代理人')
    @operation_node(name='矩阵行动-等待代理人列表', node_max_retry_times=300)
    def matrix_wait_support_panel(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        if self._find_ocr_text_mr(ocr_result_map, '代理人') is not None:
            return self.round_success('已出现代理人列表')
        return self.round_retry('等待代理人列表', wait=0.1)

    @node_from(from_name='矩阵行动-等待代理人列表')
    @operation_node(name='矩阵行动-选择协战代理人')
    def matrix_select_support_agent(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('迷失之地-矩阵行动-编队选择', '代理人列表')
        support_team_area = self.ctx.screen_loader.get_area('迷失之地-矩阵行动-编队选择', '协战编队槽')
        support_team_property = self.ctx.screen_loader.get_area('迷失之地-矩阵行动-编队选择', '协战代理人属性')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot,
            rect=area.rect,
        )

        # 找UP代理人, 或者第一个60 (有时候up识别会不成功, up代理人会在第一个位置所以也可以点击第一个60)
        center: Point | None = None
        for ocr_text in ocr_result_list:
            if ocr_text.data.lower() == 'up':
                # up
                center = ocr_text.center
                break
            elif center is None and ocr_text.data.lower() == '60':
                # 第一个60
                center = ocr_text.center

        if center is None:
            return self.round_retry('未找到协战代理人', wait=0.5)
        self.ctx.controller.click(center)

        # 等待画面更新，重新截图OCR
        time.sleep(0.5)
        self.screenshot()
        # 在协战编队槽区域检测是否出现"协战"
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot,
            rect=support_team_area.rect,
        )

        for ocr_text in ocr_result_list:
            if '协战' in ocr_text.data:
                self.ctx.lost_void.challenge_config.clear_artifact_priority_in_battle()
                # 检查协战代理人属性, 并添加到鸣徽选择的第一优先级中
                ocr_result_list_1 = self.ctx.ocr_service.get_ocr_result_list(
                    image=self.last_screenshot,
                    rect=support_team_property.rect,
                )
                for ocr_text_1 in ocr_result_list_1:
                    text = ocr_text_1.data.replace('【', '[')
                    if text[0] == '[':
                        text = text[1:3]
                    self.ctx.lost_void.challenge_config.artifact_priority_in_battle.append(text)
                    log.info('添加协战代理人属性武备至第一优先级: [' + text + ']')
                return self.round_success('已选择协战代理人')

        return self.round_retry('未找到协战', wait=0.5)

    @node_from(from_name='矩阵行动-选择协战代理人')
    @operation_node(name='矩阵行动-开始挑战')
    def matrix_start_challenge(self) -> OperationRoundResult:
        """在矩阵行动页面点击开始挑战。"""
        self.ctx.lost_void.reset_for_new_challenge()
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '迷失之地-矩阵行动-编队选择',
            '按钮-开始挑战',
            success_wait=1,
            retry_wait=1,
        )

    # ========== 常规副本入口流程节点 ==========

    @node_from(from_name='识别悬赏委托完成进度', status=STATUS_AGAIN)
    @operation_node(name='前往副本画面')
    def goto_mission_screen(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name=f'迷失之地-{self.config.mission_name}')

    @node_from(from_name='前往副本画面')
    @operation_node(name='副本画面识别')
    def check_for_mission(self) -> OperationRoundResult:
        """
        针对不同的副本类型 进行对应的所需识别
        :return:
        """
        mission_name = self.config.mission_name

        # 如果是特遣调查 则额外识别当期UP角色
        if mission_name == '特遣调查':
            area = self.ctx.screen_loader.get_area('迷失之地-特遣调查', '区域-代理人头像')
            match_agent_list: list[MatchResult] = match_team_agent_template(self.ctx, self.last_screenshot, area.rect, None)

            # 从左往右排序
            match_agent_list.sort(key=lambda x: x.left_top.x)
            self.priority_agent_list = [x.data for x in match_agent_list]

            display_name: str = ', '.join([i.agent_name for i in self.priority_agent_list])
            log.info(f'当前识别UP代理人列表: [{display_name}]')

            if len(self.priority_agent_list) > 0:
                return self.round_success()
            else:
                return self.round_retry(status='未识别UP代理人', wait=1)
        else:
            return self.round_success()

    @node_from(from_name='副本画面识别')
    @operation_node(name='选择难度', node_max_retry_times=5)
    def choose_difficulty(self) -> OperationRoundResult:
        """
        挑战配置指定了难度时 在战线肃清切换到该难度 没指定时沿用游戏当前难度
        难度一~六只差一个字 lcs匹配会互相命中 这里用包含判断
        """
        difficulty = self.ctx.lost_void.challenge_config.difficulty
        if not difficulty or self.config.mission_name != '战线肃清':
            return self.round_success('无需选择')

        target = gt(difficulty, 'game')
        title_area = self.ctx.screen_loader.get_area('迷失之地-战线肃清', '标题-战线肃清')
        title_map = self.ctx.ocr_service.get_ocr_result_map(
            image=self.last_screenshot, rect=title_area.rect, crop_first=True,
        )
        if any(target in text.replace(' ', '') for text in title_map):
            return self.round_success(f'已选择{difficulty}')

        list_area = self.ctx.screen_loader.get_area('迷失之地-战线肃清', '区域-难度列表')
        list_map = self.ctx.ocr_service.get_ocr_result_map(
            image=self.last_screenshot, rect=list_area.rect, crop_first=True,
        )
        for text, mrl in list_map.items():
            if target in text.replace(' ', '') and mrl.max is not None:
                self.ctx.controller.click(mrl.max.center)
                return self.round_retry(f'点击{difficulty}', wait=1)

        self.round_by_click_area('迷失之地-战线肃清', '按钮-难度')
        return self.round_retry('打开难度列表', wait=1)

    @node_from(from_name='选择难度')
    @operation_node(name='打开调查战略列表')
    def open_strategy_list(self) -> OperationRoundResult:
        self._strategy_scan_phase = '回到左端'
        self._strategy_last_page = []
        self._strategy_level_map = {}
        self._strategy_target_name = None
        return self.round_by_click_area(f'迷失之地-{self.config.mission_name}', '按钮-调查战略',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='打开调查战略列表')
    @operation_node(name='选择调查战略')
    def choose_strategy(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(
            self.last_screenshot, screen_name_list=['迷失之地-战线肃清', '迷失之地-特遣调查']
        )
        if current_screen_name is not None:
            return self.round_success(current_screen_name)

        # [DEBUG] 打印关键决策参数
        config = self.ctx.lost_void.challenge_config
        log.debug(f"【决策检查】 追新模式: {config.chase_new_mode}, "
                  f"当前挑战配置: {config.module_name}, "
                  f"预设调查战略: {config.investigation_strategy}")

        # 追新模式逻辑
        if config.chase_new_mode:
            return self._choose_strategy_by_chase_new_mode()
        # 原有逻辑
        else:
            return self._choose_strategy_by_ocr()

    def _choose_strategy_by_chase_new_mode(self) -> OperationRoundResult:
        """先回左端，再一直拖到最右边看完整个列表，选已确认等级最低的战略，同等级按列表顺序。"""
        if self._strategy_scan_phase == '选择目标':
            return self._choose_strategy_by_ocr(self._strategy_target_name)

        page, candidates = self._recognize_strategy_page()
        if not page:
            return self.round_retry('未识别到调查战略名称', wait=1)

        at_edge = (
            len(page) == len(self._strategy_last_page)
            and all(
                name == last_name and abs(x - last_x) <= 5
                for (name, x), (last_name, last_x) in zip(page, self._strategy_last_page, strict=True)
            )
        )
        if self._strategy_scan_phase == '回到左端':
            if not at_edge:
                self._strategy_last_page = page
                self._swipe_strategy_list(towards_right=False)
                return self.round_wait('调查战略列表返回左端')
            self._strategy_scan_phase = '向右检查'
            self._strategy_last_page = []
            at_edge = False

        for name, level, _ in candidates:
            self._strategy_level_map[name] = min(level, self._strategy_level_map.get(name, level))

        if not at_edge:
            self._strategy_last_page = page
            self._swipe_strategy_list()
            return self.round_wait('向右检查调查战略')

        found_text = ', '.join(f'{name}={level}' for name, level in self._strategy_level_map.items())
        log.info('调查战略追新 | 已看完整个列表 可选=%s', found_text if found_text else '无')
        order_list = [i.strategy_name for i in self.ctx.lost_void.investigation_strategy_list]
        found_list = [name for name in order_list if name in self._strategy_level_map]
        if found_list:
            # 选等级最低的 同等级按列表顺序选第一个
            name = min(found_list, key=lambda i: self._strategy_level_map[i])
            self._strategy_target_name = name
            self._strategy_scan_phase = '选择目标'
            log.info('调查战略追新 | 选择等级最低战略=%s 等级=%s', name, self._strategy_level_map[name])
            return self._choose_strategy_by_ocr(name)

        if self.ctx.lost_void.challenge_config.stop_when_no_strategy:
            self._stop_reason = '没有找到可继续刷取的调查战略 结束运行'
            log.warning(self._stop_reason)
            return self.round_success(LostVoidApp.STATUS_NO_STRATEGY)

        # 回退逻辑: 没有确认未满级的战略 选择第一个
        frame_context = self.ctx.cv_service.run_pipeline('调查战略等级圈圈', self.last_screenshot)
        if frame_context.is_success and frame_context.contours:
            target_contour = frame_context.contours[0]
            M = cv2.moments(target_contour)
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
            offset_x, offset_y = frame_context.crop_offset
            click_pos = Point(center_x + offset_x, center_y + offset_y)
            log.debug(f"【追新模式-回退】 点击目标坐标: {click_pos} (相对: ({center_x}, {center_y}), 偏移: {frame_context.crop_offset})")
            self.ctx.controller.click(click_pos)
            time.sleep(1)
            return self._click_confirm_after_strategy_chosen()

        return self.round_fail("追新模式失败：未找到任何可选择的调查战略")

    def _recognize_strategy_page(self) -> tuple[list[tuple[str, int]], list[tuple[str, int, Point]]]:
        """读取当前页名称、位置和等级；不确定的等级不参与选择。"""
        if self.ctx.ocr.is_use_gpu():
            ocr_map = gpu_executor.submit(self.ctx.ocr.run_ocr, self.last_screenshot).result()
        else:
            ocr_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        strategy_names = {
            gt(strategy.strategy_name, 'game').replace(' ', ''): strategy.strategy_name
            for strategy in self.ctx.lost_void.investigation_strategy_list
        }
        page: list[tuple[str, int]] = [
            (strategy_names[text.replace(' ', '')], results.max.center.x)
            for text, results in ocr_map.items()
            if text.replace(' ', '') in strategy_names and results.max is not None
        ]
        page.sort(key=lambda item: item[1])
        candidates: list[tuple[str, int, Point]] = []
        for pipeline_name, allow_empty in (
            ('调查战略无等级圈圈', True),
            ('调查战略等级圈圈', False),
        ):
            result = self.ctx.cv_service.run_pipeline(pipeline_name, self.last_screenshot)
            if not result.is_success:
                continue
            for contour, (x1, y1, x2, y2) in result.get_absolute_rect_pairs():
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0 or 4 * math.pi * cv2.contourArea(contour) / perimeter ** 2 < 0.7:
                    continue
                center = Point((x1 + x2) // 2, (y1 + y2) // 2)
                names_on_left = [(name, x) for name, x in page if center.x - 4 * (x2 - x1) < x < center.x]
                if not names_on_left:
                    continue
                name = names_on_left[-1][0]
                level = self._recognize_strategy_level(
                    self.last_screenshot[y1:y2, x1:x2], allow_empty=allow_empty,
                )
                log.debug('调查战略追新 | 战略=%s 等级=%s', name, level)
                if level is None or level >= 8 or (allow_empty and level != 0):
                    continue
                candidates.append((name, level, center))
        candidates.sort(key=lambda item: (item[1] != 0, item[2].x))
        return page, candidates

    def _recognize_strategy_level(self, badge: 'MatLike', allow_empty: bool = False) -> int | None:
        """提取圆圈内的白色数字，用双孔字形排除 8，其他数字使用单字 OCR。"""
        height, width = badge.shape[:2]
        inner = badge[height // 4:3 * height // 4, width // 4:3 * width // 4]
        mask = cv2.inRange(inner, (160, 160, 160), (255, 255, 255))
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0 if allow_empty else None
        digit_idx = max(range(len(contours)), key=lambda idx: cv2.contourArea(contours[idx]))
        holes = sum(
            1 for idx, contour in enumerate(contours)
            if hierarchy[0][idx][3] == digit_idx and cv2.contourArea(contour) >= 4
        )
        if holes == 2:
            return 8

        x, y, width, height = cv2.boundingRect(contours[digit_idx])
        digit = mask[y:y + height, x:x + width]
        digit = cv2.copyMakeBorder(digit, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=0)
        digit = cv2.resize(digit, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        digit = cv2.cvtColor(digit, cv2.COLOR_GRAY2RGB)
        if self.ctx.ocr.is_use_gpu():
            text = gpu_executor.submit(self.ctx.ocr.run_ocr_single_line, digit, threshold=0.8).result()
        else:
            text = self.ctx.ocr.run_ocr_single_line(digit, threshold=0.8)
        text = text.strip()
        return int(text) if len(text) == 1 and text in '012345678' else None

    def _swipe_strategy_list(self, towards_right: bool = True) -> None:
        """
        滑动调查战略列表 一次拖约 1500 像素 原来拖 800 像素只移动 3 个战略
        :param towards_right: True 看右边的战略(往左拖) False 看左边的战略(往右拖)
        """
        # 调查战略的详情打开之后鼠标不能在详情处滑, 会滑不动
        y = self.ctx.controller.standard_height // 2.5
        left = Point(200, y)
        right = Point(1700, y)
        if towards_right:
            self.ctx.controller.drag_to(start=right, end=left)
        else:
            self.ctx.controller.drag_to(start=left, end=right)
        time.sleep(1)

    def _click_confirm_after_strategy_chosen(self) -> OperationRoundResult:
        """
        选择战略后，点击确定按钮
        """
        self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        ocr_word_list = list(ocr_result_map.keys())
        idx = str_utils.find_best_match_by_difflib(gt('确定', 'game'), ocr_word_list)
        if idx is None or idx < 0:
            return self.round_retry(status='未识别到确定按钮', wait=1)

        target_pos = ocr_result_map[ocr_word_list[idx]].max.center
        self.ctx.controller.click(target_pos)
        time.sleep(1)

        return self.round_wait(status='确定')

    def _choose_strategy_by_ocr(self, strategy_name: str | None = None) -> OperationRoundResult:
        """
        通过OCR识别选择调查战略
        """
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        ocr_word_list = list(ocr_result_map.keys())
        strategy_name = strategy_name or self.ctx.lost_void.challenge_config.investigation_strategy
        target = gt(strategy_name, 'game')
        idx = str_utils.find_best_match_by_difflib(target, ocr_word_list)

        if idx is None or idx < 0:
            is_after = str_utils.is_target_after_ocr_list(
                target_cn=strategy_name,
                order_cn_list=[i.strategy_name for i in self.ctx.lost_void.investigation_strategy_list],
                ocr_result_list=ocr_word_list
            )

            self._swipe_strategy_list(towards_right=is_after)
            return self.round_retry(status='未识别到目标调查战略', wait=1)

        target_pos = ocr_result_map[ocr_word_list[idx]].max.center
        self.ctx.controller.click(target_pos)
        time.sleep(1)

        return self._click_confirm_after_strategy_chosen()

    @node_from(from_name='选择调查战略')
    @operation_node(name='选择周期增益')
    def choose_buff(self) -> OperationRoundResult:
        mission_name = self.config.mission_name
        if mission_name == '特遣调查':
            return self.round_success(status='无需选择')
        else:
            return self.round_by_click_area(
                '迷失之地-战线肃清',
                f'周期增益-{self.ctx.lost_void.challenge_config.period_buff_no}',
                success_wait=1, retry_wait=1)

    @node_from(from_name='选择周期增益')
    @operation_node(name='下一步')
    def click_next(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='通用-出战', area_name='按钮-下一步',
                                                 until_find_all=[('通用-出战', '按钮-出战')],
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='下一步')
    @operation_node(name='检查预备编队')
    def check_predefined_team(self) -> OperationRoundResult:
        """
        根据配置判断是否需要切换编队
        :return:
        """
        self.use_priority_agent = False
        mission_name = self.config.mission_name
        if mission_name == '特遣调查':
            # 本周第一次挑战 且开启了优先级配队
            if (self.ctx.lost_void.challenge_config.choose_team_by_priority
                    and not self.run_record.complete_task_force_with_up):
                self.ctx.lost_void.predefined_team_idx = self.get_target_team_idx_by_priority()
                if self.ctx.lost_void.predefined_team_idx != -1:
                    self.use_priority_agent = True
                    return self.round_success(status='需选择预备编队')

        # 配置中选择特定编队
        if self.ctx.lost_void.challenge_config.predefined_team_idx != -1:
            self.ctx.lost_void.predefined_team_idx = self.ctx.lost_void.challenge_config.predefined_team_idx
            return self.round_success(status='需选择预备编队')

        return self.round_success(status='无需选择预备编队')

    def get_target_team_idx_by_priority(self) -> int:
        """
        根据当前识别的优先代理人 选择最合适的预备编队
        :return:
        """
        best_match_team_idx: int = self.ctx.lost_void.challenge_config.predefined_team_idx  # 如果都没匹配 使用默认的预备编队
        best_match_agent_cnt: int = 0
        for idx, team in enumerate(self.ctx.team_config.team_list):
            match_agent_cnt: int = 0
            for agent in self.priority_agent_list:
                if agent.agent_id in team.agent_id_list:
                    match_agent_cnt += 1

            if match_agent_cnt > best_match_agent_cnt:
                best_match_team_idx = idx
                best_match_agent_cnt = match_agent_cnt

        return best_match_team_idx

    @node_from(from_name='检查预备编队', status='需选择预备编队')
    @operation_node(name='选择预备编队')
    def choose_predefined_team(self) -> OperationRoundResult:
        op = ChoosePredefinedTeam(self.ctx, target_team_idx_list=[self.ctx.lost_void.predefined_team_idx])
        return self.round_by_op_result(op.execute())

    @node_from(from_name='检查预备编队', status='无需选择预备编队')
    @node_from(from_name='选择预备编队')
    @operation_node(name='出战')
    def deploy(self) -> OperationRoundResult:
        self.next_region_type = LostVoidRegionType.ENTRY
        self.ctx.lost_void.reset_for_new_challenge()
        op = Deploy(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='迷失之地-大世界')
    @node_from(from_name='出战')
    @node_from(from_name='矩阵行动-开始挑战')
    @operation_node(name='加载自动战斗配置')
    def load_auto_op(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.init_auto_op(
            sub_dir='auto_battle',
            op_name=self.ctx.lost_void.get_auto_op_name(),
        )
        return self.round_success()

    @node_from(from_name='加载自动战斗配置')
    @node_from(from_name='层间移动')
    @operation_node(name='层间移动')
    def run_level(self) -> OperationRoundResult:
        log.info(f'推测楼层类型 {self.next_region_type.value.value}')
        op = LostVoidRunLevel(self.ctx, self.next_region_type)
        op_result = op.execute()
        if op_result.success:
            if op_result.status == LostVoidRunLevel.STATUS_NEXT_LEVEL:
                self.ctx.lost_void.had_interacted_ophelia_on_current_level = False
                if op_result.data is not None:
                    self.next_region_type = LostVoidRegionType.from_value(op_result.data)
                else:
                    self.next_region_type = LostVoidRegionType.ENTRY
                self.ctx.lost_void.on_enter_region(op_result.data)
            elif op_result.status == LostVoidRunLevel.STATUS_COMPLETE:
                self.ctx.lost_void.had_interacted_ophelia_on_current_level = False
                self.next_region_type = LostVoidRegionType.ENTRY
                # 通关和失败退出空洞都会返回这个状态 本局已经结束
                # 其他失败(如超时)可能还在局内 下次启动从大世界接着跑 不清除
                self.ctx.lost_void.on_challenge_end()

        return self.round_by_op_result(op_result)

    @node_from(from_name='层间移动', status=LostVoidRunLevel.STATUS_COMPLETE)
    @operation_node(name='通关后处理')
    def after_complete(self) -> OperationRoundResult:
        result = self._wait_for_lost_void_entry()
        if not result.is_success:
            return result

        self.run_record.add_complete_times()
        if self.use_priority_agent:
            self.run_record.complete_task_force_with_up = True

        return self.round_success()

    def _find_ocr_text_mr(self, ocr_result_map: dict[str, MatchResultList], target_text: str) -> MatchResult | None:
        target = gt(target_text, 'game')
        ocr_word_list = list(ocr_result_map.keys())

        idx = str_utils.find_best_match_by_difflib(target, ocr_word_list, cutoff=0.5)
        if idx is not None and idx >= 0:
            mrl = ocr_result_map[ocr_word_list[idx]]
            if mrl.max is not None:
                return mrl.max

        for ocr_word, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(target, ocr_word, percent=0.6) and mrl.max is not None:
                return mrl.max

        return None

    @node_from(from_name='识别悬赏委托完成进度', status=STATUS_ENOUGH_TIMES)
    @operation_node(name='打开悬赏委托')
    def open_reward_list(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-入口', area_name='按钮-悬赏委托',
                                                 until_not_find_all=[('迷失之地-入口', '按钮-悬赏委托')],
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='打开悬赏委托')
    @node_notify(when=NotifyTiming.CURRENT_DONE)
    @operation_node(name='全部领取', node_max_retry_times=2)
    def claim_all(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-入口', area_name='按钮-悬赏委托-全部领取',
                                                 success_wait=1, retry_wait=0.5)

    @node_from(from_name='全部领取')
    @node_from(from_name='全部领取', success=False)
    @node_from(from_name='选择调查战略', status=STATUS_NO_STRATEGY)
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        result = self.round_by_op_result(op.execute())
        if result.is_success and self._stop_reason is not None:
            # 提前结束不算正常完成 不触发完成后的关机等动作
            return self.round_fail(self._stop_reason)
        return result


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.current_app_id = lost_void_const.APP_ID
    ctx.run_context.start_running()
    op = LostVoidApp(ctx, lost_void_debug=True, next_region_type = LostVoidRegionType.FRIENDLY_TALK)
    op.execute()


if __name__ == '__main__':
    __debug()
