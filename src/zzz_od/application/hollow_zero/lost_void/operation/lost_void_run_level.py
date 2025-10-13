import time
from typing import ClassVar, Optional, List

import cv2
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import LostVoidDetector
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidRegionType
from zzz_od.application.hollow_zero.lost_void.lost_void_run_record import LostVoidRunRecord
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_bangboo_store import LostVoidBangbooStore
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import LostVoidChooseCommon
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_gear import LostVoidChooseGear
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_interact_target_const import \
    match_interact_target, LostVoidInteractTarget, LostVoidInteractNPC
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_lottery import LostVoidLottery
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_route_change import LostVoidRouteChange
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import LostVoidMoveByDet
from zzz_od.application.hollow_zero.lost_void.operation.update_priority_operation import UpdatePriorityOperation
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle
from zzz_od.operation.challenge_mission.restart_in_battle import RestartInBattle
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidRunLevel(ZOperation):

    STATUS_NEXT_LEVEL: ClassVar[str] = '进入下层'
    STATUS_COMPLETE: ClassVar[str] = '通关'

    IT_BATTLE: ClassVar[str] = 'xxxx-战斗'

    def __init__(self, ctx: ZContext, region_type: LostVoidRegionType):
        """
        迷失之地层间移动操作初始化

        该操作负责在迷失之地的不同区域间进行移动和交互，根据区域类型执行相应的逻辑：

        运行逻辑概述：
        1. 等待加载 -> 区域类型初始化 -> 根据区域类型进入相应处理流程
        2. 非战斗区域：识别目标 -> 移动 -> 交互 -> 处理交互结果 -> 返回非战斗区域处理 / 进入下一层
        3. 战斗区域：进入战斗 -> 自动战斗 -> 战斗结束处理 -> 返回非战斗区域处理 / 进入下一层

        非战斗区域处理优先级：
        1. 朝感叹号移动（最高优先级，交互目标）
        2. 朝距离白点移动（中等优先级，可能进入混合区域的下一个区域）
        3. 朝下层入口移动（低优先级，进入下一层）
        4. 无识别目标时：检查右上角文本提示或角色血量变化判断是否进入战斗

        朝距离白点移动后的处理：
        1. 重新识别目标，如有目标则回到非战斗区域逻辑
        2. 无识别目标时：检查右上角文本提示或角色血量变化判断是否进入战斗

        战斗区域处理：
        1. 启动自动战斗系统
        2. 持续监控战斗状态和目标识别
        3. 战斗结束后进行目标识别，判断是否脱离战斗状态

        交互处理：
        - 支持多种交互类型：武备选择、通用选择、邦布商店、路径迭换、抽奖机等
        - 处理对话系统，支持选项选择
        - 交互后根据结果进行相应的移动调整

        @param ctx: 游戏上下文对象，包含各种配置和状态信息
        @param region_type: 当前区域类型，决定初始处理逻辑
        @return: 成功时返回下一个可能的区域类型作为data
        """
        ZOperation.__init__(
            self,
            ctx,
            op_name='迷失之地-层间移动',
            # timeout_seconds=600,  # 不在这里设置超时 而是统一在 '非战斗画面识别' 中处理
        )
        self.run_record: Optional[LostVoidRunRecord] = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=lost_void_const.APP_ID,
        )

        self.region_type: LostVoidRegionType = region_type
        self.detector: LostVoidDetector = self.ctx.lost_void.detector
        self.auto_op: AutoBattleOperator = self.ctx.lost_void.auto_op
        self.nothing_times: int = 0  # 识别不到内容的次数
        self.find_target_fail_count: int = 0  # 寻路失败次数
        self.interact_target: Optional[LostVoidInteractTarget] = None  # 最终识别的交互目标 后续改动应该都是用这个判断
        self.interact_attempted: bool = False  # 是否尝试过交互

        self.last_frame_in_battle: bool = True  # 上一帧画面在战斗
        self.current_frame_in_battle: bool = True  # 当前帧画面在战斗
        self.last_det_time: float = 0  # 上一次进行识别的时间
        self.no_in_battle_times: int = 0  # 识别到不在战斗的次数
        self.last_check_finish_time: float = 0  # 上一次识别结束的时间
        self.talk_opt_idx = 0  # 交互选择的选项
        self.reward_eval_found: bool = False  # 挑战结果中可以识别到业绩点
        self.reward_dn_found: bool = False  # 挑战结果中可以识别到丁尼
        self.click_challenge_confirm: bool = False  # 点击了挑战确认

        self.had_been_list: List[str] = []  # 已经访问过的类型 1.5更新后 交互后交互类型的图标不会消失 需要自己过滤

    @node_from(from_name='非战斗画面识别', status='未在大世界')  # 有小概率交互入口后 没处理好结束本次RunLevel 重新从等待加载 开始
    @node_from(from_name='非战斗画面识别', status='按钮-挑战-确认')  # 挑战类型的对话框确认后 第一次点击可能无效 跳回来这里点击到最后生效为止
    @operation_node(name='等待加载', node_max_retry_times=60, is_start_node=True)
    def wait_loading(self) -> OperationRoundResult:
        if self.ctx.lost_void.in_normal_world(self.last_screenshot):
            # 有一个战略会在挚交会谈时奖励一个鸣徽 这个画面会在进入大世界一秒内触发
            if self.region_type == LostVoidRegionType.FRIENDLY_TALK:
                wait = 1
            else:
                wait = 0
            return self.round_success('大世界', wait=wait)

        # 1. 在精英怪后 点击完挑战结果后 加载挚交会谈前 可能会弹出奖励
        # 2. 有战略可以导致进入新一层时获取战利品
        # 因此在加载这里判断是否有奖励需要选择
        possible_screen_name_list = [
            '迷失之地-武备选择', '迷失之地-通用选择',
        ]
        screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=possible_screen_name_list)
        if screen_name is not None:
            self.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)
            return self.round_success('识别正在交互')

        # 挑战-限时 挑战-无伤都是这个 都是需要战斗
        result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-大世界', '按钮-挑战-确认')
        if result.is_success:
            self.region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
            self.click_challenge_confirm = True
            return self.round_wait(result.status)

        # 可能某个卡在对话
        result = self.try_talk(self.last_screenshot)
        if result is not None:
            return result

        return self.round_retry('未找到攻击交互按键', wait=1)

    @node_from(from_name='等待加载')
    @operation_node(name='区域类型初始化')
    def init_for_region_type(self) -> OperationRoundResult:
        """
        根据区域类型 跳转到具体的识别逻辑

        @return:
        """
        if self.region_type == LostVoidRegionType.ENTRY:
            return self.round_success('非战斗区域')
        # 红色战斗识别不准 目前都从非战斗区域开始处理
        # 游戏1.6版本更新后 战斗层可能出现代理人 导致直接跳过战斗 交互感叹号即可领取奖励 因此统一从非战斗区域开始处理
        if self.region_type == LostVoidRegionType.COMBAT_RESONIUM:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.COMBAT_GEAR:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.COMBAT_COIN:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.CHANLLENGE_FLAWLESS:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.CHANLLENGE_TIME_TRAIL:
            if self.click_challenge_confirm:
                # 恢复默认值 避免战斗之后 进入了下一层时 小概率还在这个op里 导致卡住
                self.click_challenge_confirm = False
                return self.round_success('战斗区域')
            else:
                return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.ENCOUNTER:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.PRICE_DIFFERENCE:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.REST:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.BANGBOO_STORE:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.FRIENDLY_TALK:
            # 挚交会谈 刚开始时 先往右走一段距离 避开桌子
            # 如果桌子旁有感叹号交互会走过去 交互之后往右后移动
            # 如果桌子旁没有感叹号交互 可以直接走到后方的感叹号
            self.ctx.controller.move_w(press=True, press_time=0.7, release=True)
            self.ctx.controller.move_d(press=True, press_time=2, release=True)
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.ELITE:
            return self.round_success('战斗区域')
        if self.region_type == LostVoidRegionType.BOSS:
            return self.round_success('战斗区域')

        return self.round_success('非战斗区域')

    @node_from(from_name='区域类型初始化', status='非战斗区域')
    @node_from(from_name='非战斗画面识别', status=LostVoidDetector.CLASS_DISTANCE)  # 朝白点移动后重新循环
    @node_from(from_name='非战斗画面识别', status=LostVoidMoveByDet.STATUS_NEED_DETECT)  # 之前判断是入口 进入后发现有更高优先级的目标 重新识别
    @node_from(from_name='交互后处理', status='大世界')  # 目前交互之后都不会有战斗
    @node_from(from_name='战斗中', status='识别需移动交互')  # 战斗后出现距离 或者下层入口
    @node_from(from_name='尝试交互', success=False)  # 没能交互到
    @node_from(from_name='更新优先级')  # 更新优先级后
    @operation_node(name='非战斗画面识别', timeout_seconds=180)
    def non_battle_check(self) -> OperationRoundResult:
        # 不在大世界处理
        if not self.ctx.lost_void.in_normal_world(self.last_screenshot):
            result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-大世界', '按钮-挑战-确认')
            if result.is_success:
                self.region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
                self.click_challenge_confirm = True
                return self.round_success(result.status)

            self.nothing_times += 1
            if self.nothing_times >= 10:
                # 有小概率交互入口后 没处理好结束本次RunLevel 重新从等待加载 开始
                return self.round_success('未在大世界')
            else:
                return self.round_wait("未在大世界", wait=1)

        # 在大世界 判断整体超时
        # 在这里判断是因为需要确保在大世界画面 可以按到菜单退出按钮 防止卡在事件选择之类的地方
        if self.last_screenshot_time - self.operation_start_time >= 600:  # 10分钟超时
            return self.round_fail(Operation.STATUS_TIMEOUT)

        # 在大世界 开始检测
        frame_result: DetectFrameResult = self.ctx.lost_void.detect_to_go(
            self.last_screenshot, screenshot_time=self.last_screenshot_time,
            ignore_list=self.had_been_list)
        with_interact, with_distance, with_entry = self.ctx.lost_void.detector.is_frame_with_all(frame_result)

        # 优先处理感叹号
        if with_interact:
            self.nothing_times = 0
            op = LostVoidMoveByDet(self.ctx, self.region_type, LostVoidDetector.CLASS_INTERACT,
                                   stop_when_disappear=False)
            op_result = op.execute()
            if op_result.success:
                if op_result.status == LostVoidMoveByDet.STATUS_IN_BATTLE:
                    self.interact_target = LostVoidInteractTarget(name='战斗后', icon='战斗后', after_battle=True)
                    return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)
                elif op_result.status == LostVoidMoveByDet.STATUS_INTERACT:
                    self.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)
                    return self.round_success('未在大世界')
                else:
                    self.interact_target = LostVoidInteractTarget(name='感叹号', icon='感叹号', is_exclamation=True)
                    return self.round_success(LostVoidDetector.CLASS_INTERACT, wait=1)
            elif op_result.status == Operation.STATUS_TIMEOUT:  # 移动超时
                return self.round_fail(Operation.STATUS_TIMEOUT)
            else:
                return self.round_retry('移动失败')

        # 处理白点移动
        if with_distance:
            self.nothing_times = 0
            op = LostVoidMoveByDet(self.ctx, self.region_type, LostVoidDetector.CLASS_DISTANCE,
                                   stop_when_interact=False)
            op_result = op.execute()
            if op_result.success:
                if op_result.status == LostVoidMoveByDet.STATUS_IN_BATTLE:
                    self.interact_target = LostVoidInteractTarget(name='战斗后', icon='战斗后', after_battle=True)
                    return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)
                elif op_result.status == LostVoidMoveByDet.STATUS_INTERACT:
                    self.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)
                    return self.round_success('未在大世界')
                else:
                    self.interact_target = LostVoidInteractTarget(name=LostVoidDetector.CLASS_DISTANCE,
                                                                  icon=LostVoidDetector.CLASS_DISTANCE,
                                                                  is_distance=True)
                    return self.round_success(LostVoidDetector.CLASS_DISTANCE)
            else:
                return self.round_retry('移动失败')

        # 在转动视角之前，检查是否需要更新优先级
        if not self.ctx.lost_void.priority_updated:
            return self.round_success('需要更新优先级')

        # 处理下层入口
        if with_entry:
            self.nothing_times = 0
            op = LostVoidMoveByDet(self.ctx, self.region_type, LostVoidDetector.CLASS_ENTRY,
                                   stop_when_disappear=False, ignore_entry_list=self.had_been_list)
            op_result = op.execute()
            if op_result.success:
                if op_result.status == LostVoidMoveByDet.STATUS_IN_BATTLE:
                    self.interact_target = LostVoidInteractTarget(name='战斗后', icon='战斗后', after_battle=True)
                    return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)
                elif op_result.status == LostVoidMoveByDet.STATUS_INTERACT:
                    self.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)
                    return self.round_success('未在大世界')
                elif op_result.status == LostVoidMoveByDet.STATUS_NEED_DETECT:
                    return self.round_success(op_result.status)
                else:
                    interact_type = op_result.data  # 根据显示图标 返回入口类型
                    self.interact_target = LostVoidInteractTarget(name=interact_type, icon=interact_type, is_entry=True)
                    return self.round_success(LostVoidDetector.CLASS_ENTRY, wait=1)
            else:
                return self.round_retry('移动失败')

        # 没找到目标 转动
        self.ctx.controller.turn_by_distance(-200)
        self.nothing_times += 1

        if self.nothing_times >= 50:
            self.nothing_times = 0
            return self.round_success('处理寻路失败')

        # 识别不到目标的时候 判断是否在战斗 转动等待的时候持续识别 否则0.5秒才识别一次间隔太久 很难识别到黄光
        in_battle = self.ctx.lost_void.check_battle_encounter_in_period(0.5)
        if in_battle:
            self.last_det_time = time.time()
            self.last_check_finish_time = time.time()
            return self.round_success(status='进入战斗')

        return self.round_wait(status='转动识别目标')

    @node_from(from_name='非战斗画面识别', status='需要更新优先级')
    @operation_node(name='更新优先级')
    def update_priority(self) -> OperationRoundResult:
        op = UpdatePriorityOperation(self.ctx)
        op_result = op.execute()
        if op_result.success:
            self.ctx.lost_void.priority_updated = True
            # 更新成功后，返回非战斗画面识别节点，重新进行判断
            return self.round_success(status='非战斗区域')
        else:
            return self.round_fail(op_result.status)

    @node_from(from_name='非战斗画面识别', status=LostVoidDetector.CLASS_INTERACT)
    @node_from(from_name='非战斗画面识别', status=LostVoidDetector.CLASS_ENTRY)
    @operation_node(name='尝试交互')
    def try_interact(self) -> OperationRoundResult:
        """
        走到了交互点后 尝试交互
        @return:
        """
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')

        if result.is_success:
            # 尝试文本识别准备交互的目标 这样会比使用图标更为准确
            time.sleep(0.5)
            self.screenshot()  # 重新截图
            area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-交互文本')
            part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
            ocr_result_map = self.ctx.ocr.run_ocr(part)
            current_interact_target = None
            for ocr_result in ocr_result_map.keys():
                target = match_interact_target(self.ctx, ocr_result)
                if target is not None:
                    current_interact_target = target
                    break

            if current_interact_target is not None:
                self.interact_target = current_interact_target

            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            self.interact_attempted = True # 标记已经尝试过交互
            return self.round_wait('交互', wait=0.5)

        # 只有交互后才可能交互成功
        if not self.ctx.lost_void.in_normal_world(self.last_screenshot) and self.interact_attempted:
            self.interact_attempted = False # 重置状态
            return self.round_success('交互成功')

        self.interact_attempted = False # 重置状态

        # 没有交互按钮 可能走过头了 尝试往后走
        self.ctx.controller.move_s(press=True, press_time=0.2, release=True)
        time.sleep(0.2)
        self.ctx.controller.move_s(press=True, press_time=0.2, release=True)
        time.sleep(0.2)
        self.ctx.controller.move_w(press=True, press_time=0.2, release=True)
        time.sleep(1)

        return self.round_retry('未发现交互按键')

    @node_from(from_name='等待加载', status='识别正在交互')
    @node_from(from_name='尝试交互', status='交互成功')
    @node_from(from_name='战斗中', status='识别正在交互')
    @operation_node(name='交互处理')
    def handle_interact(self) -> OperationRoundResult:
        """
        只有以下情况确认交互完成

        1. 返回大世界
        2. 出现挑战结果
        @return:
        """
        screen_name = self.check_and_update_current_screen(
            self.last_screenshot,
            screen_name_list=[
                '迷失之地-武备选择',
                '迷失之地-通用选择',
                '迷失之地-邦布商店',
                '迷失之地-路径迭换',
                '迷失之地-抽奖机',
                '迷失之地-大世界'
            ]
        )
        interact_op: Optional[ZOperation] = None
        interact_type: Optional[str] = None
        if screen_name == '迷失之地-武备选择':
            interact_op = LostVoidChooseGear(self.ctx)
        elif screen_name == '迷失之地-通用选择':
            interact_op = LostVoidChooseCommon(self.ctx)
        elif screen_name == '迷失之地-邦布商店':
            interact_type = '邦布商店'
            interact_op = LostVoidBangbooStore(self.ctx)
        elif screen_name == '迷失之地-路径迭换':
            interact_type = '路径迭换'
            interact_op = LostVoidRouteChange(self.ctx)
        elif screen_name == '迷失之地-抽奖机':
            interact_type = '邦布商店'  # TODO 1.6新增的抽奖机图标 会被误判成商店 等待后续模型更新
            interact_op = LostVoidLottery(self.ctx)
        elif screen_name == '迷失之地-大世界':
            return self.round_success('迷失之地-大世界')

        if interact_op is not None:
            # 出现选择的情况 交互到的不是下层入口 而是中途交互到其他内容了
            if self.interact_target is not None and self.interact_target.is_entry:
                self.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)
            op_result = interact_op.execute()
            if op_result.success:
                if interact_type is not None:
                    self.had_been_list.append(interact_type)

                return self.round_wait(op_result.status, wait=1)
            else:
                return self.round_fail(op_result.status)

        talk_result = self.try_talk(self.last_screenshot)
        if talk_result is not None:
            # 对话的情况 说明交互到的不是下层入口 中途交互到其他内容了
            if self.interact_target is not None and self.interact_target.is_entry:
                self.interact_target = LostVoidInteractTarget(name='未知', icon='感叹号', is_exclamation=True)

            return talk_result

        if self.ctx.lost_void.in_normal_world(self.last_screenshot):
            return self.round_success('迷失之地-大世界')

        result = self.round_by_find_area(self.last_screenshot, '迷失之地-挑战结果', '标题-挑战结果')
        if result.is_success:
            return self.round_success('迷失之地-挑战结果')

        # 有可能出现对话框需要确认 issue #1104
        # 这里偷懒了 复用了挑战对话框的按钮
        result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-大世界', '按钮-挑战-确认')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        # 不在大世界的话 说明交互入口成功了
        if self.interact_target is not None and self.interact_target.is_entry:
            return self.round_success(LostVoidRunLevel.STATUS_NEXT_LEVEL)

        # 交互后 可能出现了后续的交互
        return self.round_retry(status=f'未知画面', wait_round_time=1)

    def try_talk(self, screen: MatLike) -> OperationRoundResult | None:
        """
        判断是否在对话 并进行点击
        @return:
        """
        # 有对话名称的
        area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-对话角色名称')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)

        if len(ocr_result_map) > 0:  # 有可能在交互
            # 判断是否有选项
            opt_result = self.try_talk_options(screen)
            if opt_result is not None:
                return opt_result

            self.ctx.controller.click(area.center + Point(0, 50))  # 往下一点点击 防止遮住了名称

            return self.round_wait(f'尝试交互 {str(list(ocr_result_map.keys()))}', wait=0.5)

        # 对话内容 特殊的 没有对话名称的
        area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-对话内容')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)

        special_talk_list = [
            '似乎购买了充值卡就会得到齿轮硬币奖励，但是在离开之后身上的齿轮硬币都',  # 奸商布
            '（声音消失了，伸手从裂隙那头好像摸到了什么）',  # 零号业绩
            '这位似曾相识的研究员为我们准备了一些「礼物」。', '但当正要选择的时候，她却拦住了我们。',  # 助理研究员
        ]

        for ocr_result in ocr_result_map.keys():
            for special_talk in special_talk_list:
                # 穷举比较麻烦 有超过10个字符的 就认为这里有对话吧
                if len(ocr_result) <= 10 and not str_utils.find_by_lcs(gt(special_talk, 'game'), ocr_result):
                    continue

                # 判断是否有选项
                opt_result = self.try_talk_options(screen)
                if opt_result is not None:
                    return opt_result

                self.ctx.controller.click(area.center)
                return self.round_wait(f'尝试交互 {str(list(ocr_result_map.keys()))}', wait=0.5)

    def try_talk_options(self, screen: MatLike) -> Optional[OperationRoundResult]:
        """
        判断是否有对话选项
        @return:
        """
        area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-右侧对话选项')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        # cv2_utils.show_image(to_ocr, wait=0)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)

        ocr_result_list = []
        mr_list = []
        for ocr_result, mrl in ocr_result_map.items():
            if mrl.max is None:
                continue

            for mr in mrl:
                mr_list.append(mr)
                ocr_result_list.append(ocr_result)

        if len(mr_list) > 0:
            to_click_mr = mr_list[self.talk_opt_idx] if self.talk_opt_idx < len(mr_list) else mr_list[0]
            to_click_ocr_result = ocr_result_list[self.talk_opt_idx] if self.talk_opt_idx < len(ocr_result_list) else ocr_result_list[0]
            to_click_mr.add_offset(area.left_top)

            self.ctx.controller.click(to_click_mr.center)
            self.talk_opt_idx += 1
            return self.round_wait(f'尝试交互选项 {to_click_ocr_result}', wait=0.5)
        else:
            self.talk_opt_idx = 0

        # 有可能选项里只有符号 识别不到 这时候用图标识别兜底

        result = self.round_by_find_and_click_area(screen, '迷失之地-大世界', '区域-右侧对话图标')
        if result.is_success:
            return self.round_wait(f'尝试交互选项图标', wait=0.5)

    @node_from(from_name='交互处理', status='迷失之地-大世界')
    @node_from(from_name='交互处理', status='迷失之地-挑战结果')
    @node_from(from_name='交互处理', status=STATUS_NEXT_LEVEL)
    @node_from(from_name='交互处理', success=False, status='未知画面')
    @operation_node(name='交互后处理', node_max_retry_times=10)
    def after_interact(self) -> OperationRoundResult:
        """
        交互后
        1. 在大世界的 先退后 让交互按键消失 再继续后续寻路
        2. 不在大世界的 可能是战斗后结果画面 也可能是交互进入下层
        @return:
        """
        if self.interact_target is not None:
            log.info('交互后处理 上次交互对象为 %s %s', self.interact_target.icon, self.interact_target.name)

        if self.ctx.lost_void.in_normal_world(self.last_screenshot):
            self.move_after_interact()
            return self.round_success(status='大世界', wait=1)

        result = self.round_by_find_area(self.last_screenshot, '迷失之地-挑战结果', '标题-挑战结果')
        if result.is_success:
            # 这个标题出来之后 按钮还需要一段时间才能出来
            r2 = self.round_by_find_area(self.last_screenshot, '迷失之地-挑战结果', '按钮-确定')
            if r2.is_success:
                return self.round_success('挑战结果-确定', wait=2)

            r2 = self.round_by_find_area(self.last_screenshot, '迷失之地-挑战结果', '按钮-完成')
            if r2.is_success:
                return self.round_success('挑战结果-完成', wait=2)

        if self.interact_target is not None and self.interact_target.is_entry:
            return self.round_success(
                LostVoidRunLevel.STATUS_NEXT_LEVEL, data=self.interact_target.icon
            )

        return self.round_retry('等待画面返回', wait=1)

    def move_after_interact(self) -> None:
        """
        交互后 进行的特殊移动
        :return:
        """
        if self.interact_target is None:
            return

        if self.interact_target.after_battle:  # 战斗后的交互 不需要移动
            return

        if self.region_type == LostVoidRegionType.ENTRY:
            # 第一层 两个武备选择后 往后走 可以方便走上楼梯
            # 2.0版本 入口左侧增加了一个研究员 因此交互后往后多走一点 方便看到这个研究员
            self.ctx.controller.move_s(press=True, press_time=2, release=True)
            if self.interact_target.is_npc:
                if self.interact_target.name == LostVoidInteractNPC.SCGMDYJY.value:
                    # 研究员交互后 往右一点方便走到白点位置
                    self.ctx.controller.move_d(press=True, press_time=0.5, release=True)
        elif self.region_type == LostVoidRegionType.FRIENDLY_TALK:
            # 挚交会谈
            if self.interact_target.is_agent:  # 如果是代理人 向后右移动 可以避开中间桌子的障碍
                self.ctx.controller.move_s(press=True, press_time=1, release=True)
                self.ctx.controller.move_d(press=True, press_time=1.5, release=True)
            elif self.interact_target.is_npc:  # 如果是NPC
                if self.interact_target.name in [LostVoidInteractNPC.A_YUAN.value, LostVoidInteractNPC.MA_LIN.value]:
                    # 阿援和玛琳 在左边
                    self.ctx.controller.move_s(press=True, press_time=1, release=True)
                    self.ctx.controller.move_d(press=True, press_time=1.5, release=True)
                elif self.interact_target.name == LostVoidInteractNPC.AO_FEI_LI_YA.value:
                    # 奥菲莉亚 在有右边
                    self.ctx.controller.move_s(press=True, press_time=1, release=True)
                    self.ctx.controller.move_a(press=True, press_time=1, release=True)
                else:
                    self.ctx.controller.move_s(press=True, press_time=1, release=True)
            else:
                self.ctx.controller.move_s(press=True, press_time=1, release=True)
        else:
            # 兜底的情况 统一往后走
            # 1. 由于奸商布的位置和商店很靠近 交互后往后移动可以避开奸商布
            self.ctx.controller.move_s(press=True, press_time=1, release=True)

    @node_from(from_name='非战斗画面识别', status='进入战斗')  # 非挑战类型的 识别开始战斗后
    @node_from(from_name='非战斗画面识别', status=LostVoidMoveByDet.STATUS_IN_BATTLE)  # 移动过程中 识别到战斗
    @node_from(from_name='区域类型初始化', status='战斗区域')  # 区域类型就是战斗的
    @operation_node(name='战斗中', mute=True, timeout_seconds=600)
    def in_battle(self) -> OperationRoundResult:
        if not self.auto_op.is_running:
            self.auto_op.start_running_async()

        self.last_frame_in_battle = self.current_frame_in_battle
        self.current_frame_in_battle = self.auto_op.auto_battle_context.check_battle_state(self.last_screenshot, self.last_screenshot_time)

        if self.current_frame_in_battle:  # 当前回到可战斗画面
            if (not self.last_frame_in_battle  # 之前在非战斗画面
                or self.last_screenshot_time - self.last_det_time >= 1  # 1秒识别一次
                or (self.no_in_battle_times > 0 and self.last_screenshot_time - self.last_check_finish_time >= 0.1)  # 之前也识别到脱离战斗 0.1秒识别一次
            ):
                no_in_battle = False
                screen2 = self.screenshot()  # 因为跟自动战斗是异步同时识别 这里重新截图避免两边冲突

                # 尝试识别下层入口 (道中危机 和 终结之役 不需要识别)
                if self.region_type not in [LostVoidRegionType.ELITE, LostVoidRegionType.BOSS]:
                    self.last_det_time = self.last_screenshot_time
                    try:
                        # 为了不随意打断战斗 这里的识别阈值要高一点
                        frame_result: DetectFrameResult = self.detector.run(screen2, run_time=self.last_screenshot_time, conf=0.9)
                        with_interact, with_distance, with_entry = self.detector.is_frame_with_all(frame_result)
                        if with_interact or with_distance or with_entry:
                            no_in_battle = True
                    except Exception as e:
                        # 刚开始可能有一段时间识别报错 有可能是一张图同时在两个onnx里面跑 加入第二次截图观察
                        log.error('战斗中识别交互出现异常', exc_info=e)
                        return self.round_wait()

                if not no_in_battle:
                    area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-文本提示')
                    if screen_utils.find_by_ocr(self.ctx, screen2, target_cn='前往下一个区域', area=area):
                        no_in_battle = True

                if no_in_battle:
                    self.no_in_battle_times += 1
                else:
                    self.no_in_battle_times = 0

                if self.no_in_battle_times >= 10:
                    auto_battle_utils.stop_running(self.auto_op)
                    return self.round_success('识别需移动交互')

                return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)
        else:  # 当前不在战斗画面
            if (self.last_screenshot_time - self.last_check_finish_time >= 1  # 1秒识别一次
                or (self.no_in_battle_times > 0 and self.last_screenshot_time - self.last_check_finish_time >= 0.1)  # 之前也识别到脱离战斗 0.1秒识别一次
            ):
                self.last_check_finish_time = self.last_screenshot_time

                # 部分情况刚好战斗结束站在交互点上
                interact_result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')

                no_in_battle_screen_name_list = [
                    '迷失之地-武备选择', '迷失之地-通用选择',
                    '迷失之地-挑战结果',
                    '迷失之地-战斗失败'
                ]
                screen_name = self.check_and_update_current_screen(self.last_screenshot, no_in_battle_screen_name_list)
                if screen_name in no_in_battle_screen_name_list or interact_result.is_success:
                    self.no_in_battle_times += 1
                else:
                    self.no_in_battle_times = 0

                if self.no_in_battle_times >= 10:
                    auto_battle_utils.stop_running(self.auto_op)
                    self.no_in_battle_times = 0

                    if screen_name == '迷失之地-战斗失败':
                        return self.round_success(screen_name)
                    else:
                        self.interact_target = LostVoidInteractTarget(name='战斗后', icon='战斗后', after_battle=True)
                        log.info('识别正在交互')
                        return self.round_success('识别正在交互')

                return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)

        return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='交互后处理', status='挑战结果-确定')
    @operation_node(name='挑战结果处理确定')
    def handle_challenge_result_confirm(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='迷失之地-挑战结果', area_name='按钮-确定',
                                                   until_not_find_all=[('迷失之地-挑战结果', '按钮-确定')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_success(LostVoidRunLevel.STATUS_NEXT_LEVEL, data=LostVoidRegionType.FRIENDLY_TALK.value.value)
        else:
            return result

    @node_from(from_name='交互后处理', status='挑战结果-完成')
    @operation_node(name='挑战结果处理完成')
    def handle_challenge_result_finish(self) -> OperationRoundResult:
        # 由于有动画效果 这里需要识别很多轮 只要有一轮识别到就算有
        result = self.round_by_find_area(self.last_screenshot, '迷失之地-挑战结果', '奖励-零号业绩')
        if result.is_success:
            self.reward_eval_found = True
        result = self.round_by_find_area(self.last_screenshot, '迷失之地-挑战结果', '奖励-丁尼')
        if result.is_success:
            self.reward_dn_found = True

        result = self.round_by_find_and_click_area(screen=self.last_screenshot, screen_name='迷失之地-挑战结果', area_name='按钮-完成',
                                                   until_not_find_all=[('迷失之地-挑战结果', '按钮-完成')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            if self.reward_eval_found:
                # 有业绩点 说明两个都没达成
                self.run_record.eval_point_complete = False
                self.run_record.period_reward_complete = False
            else:
                self.run_record.eval_point_complete = True
                self.run_record.period_reward_complete = not self.reward_dn_found

            if self.run_record.period_reward_complete:
                if self.ctx.env_config.is_debug:
                    self.save_screenshot(prefix='period_reward_complete')

            return self.round_success(LostVoidRunLevel.STATUS_COMPLETE, data=LostVoidRegionType.FRIENDLY_TALK.value.value)
        else:
            return result

    @node_from(from_name='非战斗画面识别', success=False, status='处理寻路失败')
    @operation_node(name='处理寻路失败')
    def handle_find_target_fail(self) -> OperationRoundResult:
        if self.find_target_fail_count < 3:
            self.find_target_fail_count += 1
            log.info(f'寻路失败，开始第 {self.find_target_fail_count} 次重试')
            op = RestartInBattle(self.ctx)
            op_result = op.execute()
            if op_result.success:
                return self.round_success(self.STATUS_COMPLETE)
            else:
                return self.round_fail(op_result.status)
        else:
            log.info('重试次数已达上限，准备退出挑战')
            return self.round_success('准备最终退出')

    @node_from(from_name='非战斗画面识别', success=False, status=Operation.STATUS_TIMEOUT)
    @node_from(from_name='战斗中', success=False, status=Operation.STATUS_TIMEOUT)
    @node_from(from_name='处理寻路失败', status='准备最终退出')
    @operation_node(name='失败退出空洞')
    def fail_exit_lost_void(self) -> OperationRoundResult:
        auto_battle_utils.stop_running(self.auto_op)
        op = ExitInBattle(self.ctx, '迷失之地-挑战结果', '按钮-完成')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='战斗中', status='迷失之地-战斗失败')
    @operation_node(name='处理战斗失败')
    def handle_battle_fail(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-战斗失败', area_name='按钮-撤退',
                                                 until_not_find_all=[('迷失之地-战斗失败', '按钮-撤退')],
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='失败退出空洞')
    @node_from(from_name='处理战斗失败')
    @operation_node(name='点击失败退出完成')
    def handle_fail_exit(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='迷失之地-挑战结果', area_name='按钮-完成',
                                                 until_not_find_all=[('迷失之地-挑战结果', '按钮-完成')],
                                                 success_wait=1, retry_wait=1)

        if result.is_success:
            return self.round_success(LostVoidRunLevel.STATUS_COMPLETE, data=LostVoidRegionType.ENTRY.value.value)
        else:
            return result

    def handle_pause(self) -> None:
        ZOperation.handle_pause(self)
        auto_battle_utils.stop_running(self.auto_op)

    def after_operation_done(self, result: OperationResult):
        ZOperation.after_operation_done(self, result)
        auto_battle_utils.stop_running(self.auto_op)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.lost_void.init_before_run()
    ctx.init_ocr()
    ctx.run_context.start_running()

    ctx.lost_void.init_auto_op()
    op = LostVoidRunLevel(ctx, LostVoidRegionType.ENTRY)
    op.execute()


if __name__ == '__main__':
    __debug()
