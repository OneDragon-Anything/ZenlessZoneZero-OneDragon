import time

from cv2.typing import MatLike
from typing import List, Optional, ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils
from one_dragon.yolo.detect_utils import DetectObjectResult, DetectFrameResult
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import LostVoidDetector
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidRegionType
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation
from one_dragon.utils.log_utils import log


class MoveTargetWrapper:

    def __init__(
        self,
        detect_result: DetectObjectResult,
    ):
        self.is_mixed: bool = False  # 是否混合楼层
        self.target_name_list: List[str] = [detect_result.detect_class.class_name[5:]]
        self.target_rect_list: List[Rect] = [Rect(detect_result.x1, detect_result.y1, detect_result.x2, detect_result.y2)]

        self.leftest_target_name: str = self.target_name_list[0]  # 最左边的入口类型 也就是第一个遇到的区域
        self.entire_rect: Rect = self.target_rect_list[0]
        self.merge_parent = None  # 合并后的父节点

    def merge_another_target(self, other) -> bool:
        """
        尝试合并一个入口
        @return: 是否合并成功
        """
        if other.is_mixed and other.merge_parent is not None:
            other: MoveTargetWrapper = other.merge_parent

        this = self
        if this.is_mixed and this.merge_parent is not None:
            this: MoveTargetWrapper = this.merge_parent

        is_merge = False
        for x in this.target_rect_list:
            for y in other.target_rect_list:
                if cal_utils.distance_between(x.center, y.center) < x.width * 2:
                    is_merge = True
                    break

            if is_merge:
                break

        if is_merge:
            this.is_mixed = True
            other.is_mixed = True
            other.merge_parent = this

            this.target_name_list.extend(other.target_name_list)
            this.target_rect_list.extend(other.target_rect_list)

            leftest_entry_idx = 0
            x1 = this.target_rect_list[0].x1
            y1 = this.target_rect_list[0].y1
            x2 = this.target_rect_list[0].x2
            y2 = this.target_rect_list[0].y2
            for i in range(len(this.target_rect_list)):
                rect = this.target_rect_list[i]

                if rect.x1 < x1:
                    x1 = rect.x1
                    leftest_entry_idx = i
                if rect.x2 > x2:
                    x2 = rect.x2
                if rect.y1 < y1:
                    y1 = rect.y1
                if rect.y2 > y2:
                    y2 = rect.y2

            self.leftest_target_name = this.target_name_list[leftest_entry_idx]
            self.entire_rect = Rect(x1, y1, x2, y2)

        return is_merge


class LostVoidMoveByDet(ZOperation):

    STATUS_IN_BATTLE: ClassVar[str] = '遭遇战斗'
    STATUS_ARRIVAL: ClassVar[str] = '到达目标'
    STATUS_NO_FOUND: ClassVar[str] = '未识别到目标'
    STATUS_CONTINUE: ClassVar[str] = '继续识别目标'
    STATUS_INTERACT: ClassVar[str] = '处于交互中'
    STATUS_NEED_DETECT: ClassVar[str] = '需要重新识别'

    def __init__(
        self,
        ctx: ZContext,
        current_region: LostVoidRegionType,
        target_type: str,
        stop_when_interact: bool = True,
        stop_when_disappear: bool = True,
        ignore_entry_list: Optional[List[str]] = None
    ):
        """
        朝识别目标移动 最终返回目标图标 data=LostVoidRegionType.label
        @param ctx:
        @param current_region:
        @param target_type:
        @param stop_when_interact:
        @param stop_when_disappear:
        @param ignore_entry_list:
        """
        ZOperation.__init__(
            self,
            ctx,
            op_name=f'迷失之地-识别寻路-{target_type[5:]}',
            timeout_seconds=180,  # 3分钟走不到 基本就是卡死了
        )

        self.current_region: LostVoidRegionType = current_region
        self.target_type: str = target_type
        self.stop_when_interact: bool = stop_when_interact  # 可交互时停止移动
        self.stop_when_disappear: bool = stop_when_disappear  # 目标消失时停止移动
        self.ignore_entry_list: List[str] = ignore_entry_list

        # 需要按方向选的时候 按最大x值选
        # 入口时 从右往左选可以上楼梯
        self.choose_by_max_x: bool = self.current_region in [
            LostVoidRegionType.ENTRY,
        ]

        self.last_target_result: Optional[MoveTargetWrapper] = None  # 最后一次识别到的目标
        self.last_target_name: Optional[str] = None  # 最后识别到的交互目标名称
        self.same_target_times: int = 0  # 识别到相同目标的次数
        self.stuck_times: int = 0  # 被困次数
        self.total_turn_times: int = 0  # 总共转向次数

        self.last_save_debug_image_time: float = 0  # 上一次保存debug图片的时间

        self.lost_target_during_move_times: int = 0  # 移动过程中丢失目标次数

        # 转向校准
        self.last_target_x: Optional[float] = None  # 上一次识别到的目标x轴坐标
        self.last_actual_turn_distance: int = 0  # 上一次实际的转向距离
        self.estimated_turn_ratio: float = 0.2  # 估算的转向比例
        self.turn_calibration_count: int = 1  # 转向校准次数

        self._reset_turn_calibration_status()

    def _reset_turn_calibration_status(self):
        """
        重置转向校准相关的状态
        """
        self.last_target_x = None
        self.last_actual_turn_distance = 0
        self.estimated_turn_ratio = 0.2
        self.turn_calibration_count = 1

    def handle_not_in_world(self, screen: MatLike) -> OperationRoundResult:
        """
        处理不在大世界的情况

        - 可能是进入新一层的时候 识别到里感叹号之类的 然后触发了获得战利品的效果 进入了选择
        :param screen:
        :return:
        """
        possible_screen_name_list = [
            '迷失之地-武备选择', '迷失之地-通用选择',
        ]
        screen_name = self.check_and_update_current_screen(screen, possible_screen_name_list)
        if screen_name is not None:
            return self.round_success(LostVoidMoveByDet.STATUS_INTERACT)
        else:
            return self.round_retry('未在大世界画面')

    @node_from(from_name='脱困')
    @node_from(from_name='无目标处理', status=STATUS_CONTINUE)
    @operation_node(name='移动前转向', node_max_retry_times=20, is_start_node=True)
    def turn_at_first(self) -> OperationRoundResult:
        in_world = self.ctx.lost_void.in_normal_world(self.last_screenshot)
        if not in_world:
            return self.handle_not_in_world(self.last_screenshot)

        frame_result = self.ctx.lost_void.detect_to_go(self.last_screenshot, screenshot_time=self.last_screenshot_time,
                                                       ignore_list=self.ignore_entry_list)

        if self.check_interact_stop(self.last_screenshot, frame_result):
            return self.round_success(LostVoidMoveByDet.STATUS_ARRIVAL, data=self.last_target_name)

        target_result = self.get_move_target(frame_result)

        if target_result is None:
            if self.last_target_result is not None:
                self._reset_turn_calibration_status()  # 丢失目标，重置校准
                # 如果出现多次转向 说明可能是识别不准 然后又恰巧被卡住无法前进
                self.lost_target_during_move_times += 1
                # https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/issues/867
                if self.lost_target_during_move_times % 5 == 0:  # 尝试脱困
                    self.stuck_times += 1
                    self.get_out_of_stuck()
            self.last_target_result = None
            return self.round_success(LostVoidMoveByDet.STATUS_NO_FOUND)
        self.last_target_result = target_result
        pos = target_result.entire_rect.center
        turn = self.turn_to_target(pos)
        if turn:
            return self.round_wait('转动朝向目标', wait=0.5)

        # 移动前切换到最佳角色
        auto_battle_utils.switch_to_best_agent_for_moving(self.ctx.lost_void.auto_op)
        return self.round_success('开始移动')

    @node_from(from_name='移动前转向', status='开始移动')
    @operation_node(name='移动')
    def move_towards(self) -> OperationRoundResult:
        frame_result: DetectFrameResult = self.ctx.lost_void.detect_to_go(
            self.last_screenshot, screenshot_time=self.last_screenshot_time,
            ignore_list=self.ignore_entry_list)

        if self.check_interact_stop(self.last_screenshot, frame_result):
            self.ctx.controller.stop_moving_forward()
            return self.round_success(data=self.last_target_name, wait=0.5)

        target_result = self.get_move_target(frame_result)

        if target_result is None:
            if self.target_type == LostVoidDetector.CLASS_ENTRY:
                # 调用的时候识别的是入口 但进入之后发现有其他优先级更高的 退出执行
                another_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, LostVoidDetector.CLASS_DISTANCE)
                if another_result is not None:
                    return self.round_success(status=LostVoidMoveByDet.STATUS_NEED_DETECT)

                another_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, LostVoidDetector.CLASS_INTERACT)
                if another_result is not None:
                    return self.round_success(status=LostVoidMoveByDet.STATUS_NEED_DETECT)

            self.lost_target_during_move_times += 1
            # 移动过程中多次丢失目标 通常是因为识别不准
            # 游戏1.6版本出现了可以因为丢失目标转动镜头而一直无法进入脱困 issues #867
            if self.lost_target_during_move_times % 10 == 0:  # 尝试脱困
                self.stuck_times += 1
                self.get_out_of_stuck()

            return self.round_success(LostVoidMoveByDet.STATUS_NO_FOUND)

        is_stuck = self.check_stuck(target_result)
        if is_stuck is not None:
            return is_stuck

        self.last_target_result = target_result
        self.last_target_name = target_result.leftest_target_name
        self.turn_to_target(target_result.entire_rect.center, is_moving=True)
        self.ctx.controller.start_moving_forward()

        return self.round_wait('移动中', wait_round_time=0.1)

    def turn_to_target(self, target: Point, is_moving: bool = False, calibration_axis: str = 'x') -> bool:
        """
        根据目标的位置,使用自适应算法进行转动
        :param target: 目标位置
        :param is_moving: 是否在移动中。移动中会使用更保守的转向策略
        :param calibration_axis: 校准轴。可以是 'xy', 'x', 'y'。默认为 'xy'。
        :return: 是否进行了转动
        """
        if is_moving:
            # 如果在移动中，每次都重置校准，并使用非常小的转向限制
            self.turn_calibration_count = 1
            min_turn = 5
            max_turn = 15
        else:
            # 静止时，使用原有的、更激进的转向限制
            min_turn = 5
            max_turn = 200

        screen_center_x = self.ctx.controller.standard_width / 2
        screen_center_y = self.ctx.controller.standard_height / 2
        diff_x = target.x - screen_center_x
        diff_y = target.y - screen_center_y

        turn_distance_x = 0
        if 'x' in calibration_axis:
            # --- X轴转向计算 (逻辑完全不变) ---
            if abs(diff_x) > 50:
                # 根据上次转向的实际效果，动态校准转向比例
                if self.last_target_x is not None and self.last_actual_turn_distance != 0:
                    last_diff_x = self.last_target_x - screen_center_x
                    actual_pixel_moved = diff_x - last_diff_x

                    # 当目标穿越中心点(过冲)时，强力抑制，比例减半并重置校准过程
                    if last_diff_x * diff_x < 0:
                        self.estimated_turn_ratio *= 0.5
                        self.turn_calibration_count = 1
                    # 正常校准：使用移动平均法平滑更新比例
                    elif abs(actual_pixel_moved) > 1:
                        current_ratio = abs(self.last_actual_turn_distance / actual_pixel_moved)
                        if self.turn_calibration_count == 1:  # 首次校准，直接采用侦察值
                            self.estimated_turn_ratio = current_ratio
                        else:  # 后续校准，使用移动平均法平滑更新
                            n = self.turn_calibration_count
                            self.estimated_turn_ratio = (self.estimated_turn_ratio * (n - 1) + current_ratio) / n
                        self.turn_calibration_count += 1

                # 计算转向指令，首次使用固定值进行侦察，后续使用自适应指令
                if self.turn_calibration_count == 1:
                    turn_distance_x = 5 if diff_x > 0 else -5
                    self.turn_calibration_count += 1
                else:
                    turn_distance_x = int(diff_x * self.estimated_turn_ratio)

                # 限制指令幅度，防止过小或过大
                if 0 < abs(turn_distance_x) < min_turn:
                    turn_distance_x = min_turn if turn_distance_x > 0 else -min_turn
                elif abs(turn_distance_x) > max_turn:
                    turn_distance_x = max_turn if turn_distance_x > 0 else -max_turn

        turn_distance_y = 0
        if 'y' in calibration_axis:
            # --- Y轴转向计算 (将目标保持在屏幕上半区，以获得更佳视野) ---
            # 目标是让 diff_y 稳定在 -300 附近
            target_y = -300
            # 设置一个死区，避免在目标附近频繁微调
            dead_zone = 100
            
            if diff_y > target_y + dead_zone:
                # 目标在预定位置下方，需要向上转
                turn_distance_y = 20  # 您可以根据需要调整这个值
            elif diff_y < target_y - dead_zone:
                # 目标在预定位置上方，需要向下转
                turn_distance_y = -20 # 您可以根据需要调整这个值
            else:
                # 在目标区域内，不进行Y轴转向
                turn_distance_y = 0

        # --- 如果没有任何移动指令，则提前返回 ---
        if turn_distance_x == 0 and turn_distance_y == 0:
            return False

        # --- 执行转向并更新状态 ---
        if self.ctx.env_config.is_debug:
            log.debug(f'转向指令: X={turn_distance_x}, Y={turn_distance_y}, 当前X比例: {self.estimated_turn_ratio:.4f}, 移动中: {is_moving}, 校准轴: {calibration_axis}')

        # 使用新的统一方法执行移动
        self.ctx.controller.move_mouse_relative(turn_distance_x, turn_distance_y)

        self.total_turn_times += 1

        # 只更新X轴的校准状态
        self.last_target_x = target.x
        self.last_actual_turn_distance = turn_distance_x

        return True
    def get_move_target(self, frame_result: DetectFrameResult) -> Optional[MoveTargetWrapper]:
        """
        获取移动目标

        @param frame_result: 当前帧识别结果
        @return:
        """
        if self.target_type != LostVoidDetector.CLASS_ENTRY:
            detect_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, self.target_type,
                                                                        by_max_x=self.choose_by_max_x)
            if detect_result is not None:
                return MoveTargetWrapper(detect_result)
            else:
                return None
        else:
            entry_target = self.get_entry_target(frame_result)
            if entry_target is not None:
                return entry_target

            detect_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, self.target_type,
                                                                        by_max_x=self.choose_by_max_x)

        return None

    def get_entry_target(self, frame_result: DetectFrameResult) -> Optional[MoveTargetWrapper]:
        """
        获取入口目标 按优先级 尽量避免混合楼层

        @param frame_result: 当前帧识别结果
        @return:
        """
        entry_list: List[MoveTargetWrapper] = []
        for result in frame_result.results:
            if result.detect_class.class_name in [LostVoidDetector.CLASS_INTERACT, LostVoidDetector.CLASS_DISTANCE]:
                continue

            new_item = MoveTargetWrapper(result)
            entry_list.append(new_item)

        # 合并结果
        for x in entry_list:
            for y in entry_list:
                if x == y:
                    continue
                x.merge_another_target(y)

        # 筛选合并后的结果
        entry_list = [
            i
            for i in entry_list
            if i.merge_parent is None
        ]

        if self.last_target_result is not None:  # 优先保持与上次一致的目标
            result = self.get_same_as_last_target(entry_list)
            if result is not None:
                return result

        not_mixed_entry_list = [item for item in entry_list if not item.is_mixed]
        mixed_entry_list = [item for item in entry_list if item.is_mixed]
        if len(not_mixed_entry_list) > 0:
            return self.ctx.lost_void.get_entry_by_priority(not_mixed_entry_list)
        elif len(mixed_entry_list) > 0:
            return self.ctx.lost_void.get_entry_by_priority(mixed_entry_list)
        else:
            return None

    def check_stuck(self, new_target: MoveTargetWrapper) -> Optional[OperationRoundResult]:
        """
        判断是否被困
        @return:
        """
        if self.last_target_result is None or new_target is None:
            self.same_target_times = 0
            return None

        if self.last_target_result.leftest_target_name != new_target.leftest_target_name:
            self.same_target_times = 0
            return None

        dis = cal_utils.distance_between(self.last_target_result.entire_rect.center, new_target.entire_rect.center)
        if dis < 20:
            self.same_target_times += 1

        if self.same_target_times >= 50:
            self.ctx.controller.stop_moving_forward()
            self.stuck_times += 1
            self.same_target_times = 0
            if self.stuck_times > 12:
                return self.round_fail('无法脱困')
            else:
                return self.round_success('尝试脱困')
        else:
            return None

    @node_from(from_name='移动', status='尝试脱困')
    @operation_node(name='脱困')
    def get_out_of_stuck(self) -> OperationRoundResult:
        """
        脱困
        @return:
        """
        # 在大世界 先切换到移动最优角色
        auto_battle_utils.switch_to_best_agent_for_moving(self.ctx.lost_void.auto_op)
        # 部分障碍物可以破坏 尝试攻击
        self.ctx.controller.normal_attack(press=True, press_time=0.2, release=True)

        if self.stuck_times % 6 == 1:  # 向左走
            self.ctx.controller.move_a(press=True, press_time=1, release=True)
        elif self.stuck_times % 6 == 2:  # 向右走
            self.ctx.controller.move_d(press=True, press_time=1, release=True)
        elif self.stuck_times % 6 == 3:  # 后左前 1秒
            self.ctx.controller.move_s(press=True, press_time=1, release=True)
            self.ctx.controller.move_a(press=True, press_time=1, release=True)
            self.ctx.controller.move_w(press=True, press_time=1, release=True)
        elif self.stuck_times % 6 == 4:  # 后右前 1秒
            self.ctx.controller.move_s(press=True, press_time=1, release=True)
            self.ctx.controller.move_d(press=True, press_time=1, release=True)
            self.ctx.controller.move_w(press=True, press_time=1, release=True)
        elif self.stuck_times % 6 == 5:  # 后左前 2秒
            self.ctx.controller.move_s(press=True, press_time=2, release=True)
            self.ctx.controller.move_a(press=True, press_time=2, release=True)
            self.ctx.controller.move_w(press=True, press_time=2, release=True)
        elif self.stuck_times % 6 == 0:  # 后右前 2秒
            self.ctx.controller.move_s(press=True, press_time=2, release=True)
            self.ctx.controller.move_d(press=True, press_time=2, release=True)
            self.ctx.controller.move_w(press=True, press_time=2, release=True)

        return self.round_success()

    def check_interact_stop(self, screen: MatLike, frame_result: DetectFrameResult) -> bool:
        """
        判断是否应该为交互停下来
        1. 要求出现交互时停下
        2. 出现交互按钮
        3. 有较大的可以交互的图标
        @param screen: 游戏画面
        @param frame_result: 识别结果
        @return:
        """
        if not self.stop_when_interact:
            return False

        result = self.round_by_find_area(screen, '战斗画面', '按键-交互')
        if not result.is_success:
            return False

        for result in frame_result.results:
            if result.detect_class.class_name == LostVoidDetector.CLASS_DISTANCE:
                # 不考虑 [距离]白点
                continue

            if result.detect_class.class_name == LostVoidDetector.CLASS_INTERACT:
                min_width = 70  # 感叹号的图标会大一点
            else:
                min_width = 50  # 普通入口的图标

            if result.width > min_width and result.height > min_width:
                return True

        return False

    @node_from(from_name='移动前转向', status=STATUS_NO_FOUND)
    @node_from(from_name='移动', status=STATUS_NO_FOUND)
    @operation_node(name='无目标处理')
    def handle_no_target(self) -> OperationRoundResult:
        self.ctx.controller.stop_moving_forward()
        time.sleep(0.5)
        self.screenshot()  # 重新截图
        self._reset_turn_calibration_status()  # 彻底丢失目标，重置转向状态以开始全新搜索

        if self.stop_when_interact:  # 目标是要交互
            # 当前可能准备进入可以交互状态 先等等交互按钮出现
            in_battle = self.ctx.lost_void.check_battle_encounter_in_period(1)
            if in_battle:
                return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)


        if self.stop_when_disappear:
            return self.round_success(LostVoidMoveByDet.STATUS_ARRIVAL, data=self.last_target_name)

        frame_result: DetectFrameResult = self.ctx.lost_void.detect_to_go(
            self.last_screenshot, screenshot_time=self.last_screenshot_time,
            ignore_list=self.ignore_entry_list)
        if self.check_interact_stop(self.last_screenshot, frame_result):
            result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
            if result.is_success:
                return self.round_success(LostVoidMoveByDet.STATUS_ARRIVAL, data=self.last_target_name)

        # 保存截图用于优化
        if self.ctx.env_config.is_debug and self.last_screenshot_time - self.last_save_debug_image_time > 5:
            self.last_save_debug_image_time = self.last_screenshot_time
            self.save_screenshot(prefix='lost_void_move_by_det')

        if self.last_target_result is not None:
            # 曾经识别到过 可能被血条 或者其它东西遮住了 尝试往前走一点
            self.ctx.controller.move_w(press=True, press_time=0.5, release=True)
            self.last_target_result = None

        # 没找到目标 转动
        self.total_turn_times += 1
        if self.total_turn_times >= 100:  # 基本不可能转向这么多次还没有到达
            return self.round_fail(LostVoidMoveByDet.STATUS_NO_FOUND)

        self.ctx.controller.turn_by_distance(-200)
        # 识别不到目标的时候 判断是否在战斗 转动等待的时候持续识别 否则0.5秒才识别一次间隔太久 很难识别到黄光
        in_battle = self.ctx.lost_void.check_battle_encounter_in_period(0.5)
        if in_battle:
            return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)

        return self.round_success(LostVoidMoveByDet.STATUS_CONTINUE)

    def get_same_as_last_target(self, entry_list: List[MoveTargetWrapper]) -> Optional[MoveTargetWrapper]:
        """
        从本次结果中 选择与上一次位置最接近
        @param entry_list:
        @return:
        """
        nearest_result: Optional[MoveTargetWrapper] = None
        for entry in entry_list:
            if len(entry.target_name_list) != len(self.last_target_result.target_name_list):
                continue

            # 偷懒 只判断最左边类型就算了
            if entry.leftest_target_name != self.last_target_result.leftest_target_name:
                continue

            if nearest_result is None:
                nearest_result = entry
                continue

            entry_dis = abs(cal_utils.distance_between(entry.entire_rect.center, self.last_target_result.entire_rect.center))
            nearest_dis = abs(cal_utils.distance_between(nearest_result.entire_rect.center, self.last_target_result.entire_rect.center))
            if entry_dis < nearest_dis:
                nearest_result = entry

        return nearest_result

    def handle_pause(self) -> None:
        ZOperation.handle_pause(self)
        self.ctx.controller.stop_moving_forward()
