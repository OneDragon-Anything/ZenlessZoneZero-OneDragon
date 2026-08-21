import math
import time
from dataclasses import dataclass
from typing import ClassVar

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils
from one_dragon.utils.log_utils import log
from one_dragon.yolo.detect_utils import DetectFrameResult, DetectObjectResult
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import (
    LostVoidDetector,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


@dataclass
class LostVoidStuckState:
    """本层共享的脱困状态 由 LostVoidRunLevel 创建并传给本层各个移动指令"""
    stuck_times: int = 0  # 本层累计判定卡住的次数
    prefer_left_escape: bool = True  # 本轮脱困先往左侧尝试 一轮策略走完后翻转


@dataclass
class VisibleTargetSnapshot:
    """某一时刻画面可见目标的快照 用于对比画面是否长时间无变化"""
    time: float  # 截图时间
    move_seconds: float  # 捕获时的累计前进时长(秒)
    box_list: list[tuple[float, float, float]]  # 各可见目标的 (中心x, 中心y, 宽度)


def is_same_box_constellation(
    old_box_list: list[tuple[float, float, float]],
    new_box_list: list[tuple[float, float, float]],
    max_dis: float = 15,
    min_width_ratio: float = 0.8,
    max_width_ratio: float = 1.25,
) -> bool:
    """
    判断两个时刻的可见目标是否整体保持不动

    数量一致 且每个新目标都能和一个旧目标一一配对(中心距离<max_dis 且宽度比在区间内)时
    认为两个时刻的画面无变化

    @param old_box_list: 旧快照的目标列表 每项为 (中心x, 中心y, 宽度)
    @param new_box_list: 新快照的目标列表 每项为 (中心x, 中心y, 宽度)
    @param max_dis: 配对允许的最大中心距离
    @param min_width_ratio: 配对允许的最小宽度比(新/旧)
    @param max_width_ratio: 配对允许的最大宽度比(新/旧)
    @return: 是否整体保持不动
    """
    if len(old_box_list) == 0 or len(old_box_list) != len(new_box_list):
        return False

    # 每个新目标可配对的旧目标下标
    candidate_list: list[list[int]] = []
    for new_x, new_y, new_w in new_box_list:
        candidates: list[int] = []
        for idx, (old_x, old_y, old_w) in enumerate(old_box_list):
            if math.dist((old_x, old_y), (new_x, new_y)) >= max_dis:
                continue
            if old_w <= 0 or not (min_width_ratio <= new_w / old_w <= max_width_ratio):
                continue
            candidates.append(idx)
        if len(candidates) == 0:
            return False
        candidate_list.append(candidates)

    # 增广路径求完全二分匹配 避免贪心按遍历顺序漏配
    old_matched_new: dict[int, int] = {}  # 旧目标下标 -> 已配对的新目标下标

    def try_assign(new_idx: int, visited_old: set[int]) -> bool:
        for old_idx in candidate_list[new_idx]:
            if old_idx in visited_old:
                continue
            visited_old.add(old_idx)
            if old_idx not in old_matched_new or try_assign(old_matched_new[old_idx], visited_old):
                old_matched_new[old_idx] = new_idx
                return True
        return False

    return all(try_assign(new_idx, set()) for new_idx in range(len(new_box_list)))


class MoveTargetWrapper:

    def __init__(
        self,
        detect_result: DetectObjectResult,
    ):
        self.is_mixed: bool = False  # 是否混合楼层
        self.target_name_list: list[str] = [detect_result.detect_class.class_name[5:]]
        self.target_rect_list: list[Rect] = [Rect(detect_result.x1, detect_result.y1, detect_result.x2, detect_result.y2)]

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

    STUCK_SNAPSHOT_KEEP_SECONDS: ClassVar[float] = 10  # 可见目标快照的保留时长
    STUCK_MIN_AGE_SECONDS: ClassVar[float] = 3.5  # 判定卡住时 至少和多少秒前的快照对比
    STUCK_MIN_MOVE_SECONDS: ClassVar[float] = 2.5  # 判定卡住时 对比期间至少累计前进的时长
    STUCK_HIT_WINDOW_SECONDS: ClassVar[float] = 2.5  # 卡住命中的统计时间窗口
    STUCK_HIT_TIMES: ClassVar[int] = 2  # 时间窗口内命中多少次判定为卡住
    MAX_STUCK_TIMES: ClassVar[int] = 12  # 本层累计脱困次数上限 超过则放弃本次寻路

    def __init__(
        self,
        ctx: ZContext,
        current_region: LostVoidRegionType,
        target_type: str,
        stop_when_interact: bool = True,
        stop_when_disappear: bool = True,
        ignore_entry_list: list[str] | None = None,
        allow_arrival_by_interact_btn: bool = False,
        stuck_state: LostVoidStuckState | None = None,
    ):
        """
        朝识别目标移动 最终返回目标图标 data=LostVoidRegionType.label
        @param ctx:
        @param current_region:
        @param target_type:
        @param stop_when_interact:
        @param stop_when_disappear:
        @param ignore_entry_list:
        @param allow_arrival_by_interact_btn: 是否允许仅凭交互按钮出现就判定到位
        @param stuck_state: 当前楼层共享的脱困状态
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
        self.ignore_entry_list: list[str] | None = ignore_entry_list
        self.allow_arrival_by_interact_btn: bool = allow_arrival_by_interact_btn
        self.stuck_state: LostVoidStuckState = (
            stuck_state if stuck_state is not None else LostVoidStuckState()
        )

        # 需要按方向选的时候 按最大x值选
        # 入口时 从右往左选可以上楼梯
        self.choose_by_max_x: bool = self.current_region in [
            LostVoidRegionType.ENTRY,
        ]

        self.last_target_result: MoveTargetWrapper | None = None  # 最后一次识别到的目标
        self.last_target_name: str | None = None  # 最后识别到的交互目标名称
        self.total_turn_times: int = 0  # 总共转向次数

        # 卡住判断相关
        self.visible_snapshot_list: list[VisibleTargetSnapshot] = []  # 近期可见目标快照
        self.stuck_hit_time_list: list[float] = []  # 近期判定画面无变化的时间点
        self.total_move_seconds: float = 0  # 累计前进时长
        self.last_move_frame_time: float = 0  # 上一次前进帧的截图时间

        self.last_save_debug_image_time: float = 0  # 上一次保存debug图片的时间

        self.lost_target_during_move_times: int = 0  # 移动过程中丢失目标次数
        self.target_lost_start_time: float = 0  # 本轮移动中开始丢失目标的时间
        self.no_target_handle_times: int = 0  # 连续进入无目标处理的次数

        # 转向校准
        self.last_target_x: float | None = None  # 上一次识别到的目标x轴坐标
        self.last_actual_turn_distance: int = 0  # 上一次实际的转向距离
        self.estimated_turn_ratio: float = 0.2  # 估算的转向比例
        self.turn_calibration_count: int = 1  # 转向校准次数
        self.turn_settle_frames: int = 0  # 过冲后的稳定帧数

        self._last_attack_btn_check_time: float = 0  # 上一次检查普攻按钮的时间

        self._reset_turn_calibration_status()

    def _reset_turn_calibration_status(self):
        """
        重置转向校准相关的状态
        """
        self.last_target_x = None
        self.last_actual_turn_distance = 0
        self.estimated_turn_ratio = 0.2
        self.turn_calibration_count = 1
        self.turn_settle_frames = 0

    def _reset_stuck_status(self) -> None:
        """
        重置卡住判断相关的状态

        只应在角色位置发生主动变化(如脱困移动)后调用 让旧快照作废
        目标短暂丢失时不要调用 否则周期性丢失目标会让卡住永远无法判定
        """
        self.visible_snapshot_list = []
        self.stuck_hit_time_list = []

    def _get_detected_class_names(self, frame_result: DetectFrameResult) -> list[str]:
        return [result.detect_class.class_name for result in frame_result.results]

    def _get_detected_class_summary(self, frame_result: DetectFrameResult) -> str:
        class_name_list = self._get_detected_class_names(frame_result)
        return '无' if len(class_name_list) == 0 else ', '.join(class_name_list)

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

    @node_from(from_name='脱困', status=STATUS_CONTINUE)
    @node_from(from_name='无目标处理', status=STATUS_CONTINUE)
    @operation_node(name='移动前转向', node_max_retry_times=20, is_start_node=True)
    def turn_at_first(self) -> OperationRoundResult:
        in_world = self.ctx.lost_void.in_normal_world(self.last_screenshot)
        if not in_world:
            return self.handle_not_in_world(self.last_screenshot)

        frame_result = self.ctx.lost_void.detect_to_go(self.last_screenshot, screenshot_time=self.last_screenshot_time,
                                                       ignore_list=self.ignore_entry_list)
        log.info('寻路节点[%s] 当前目标=%s 检测结果=%s',
                 '移动前转向', self.target_type, self._get_detected_class_summary(frame_result))
        self._record_visible_snapshot(self.last_screenshot_time, frame_result)

        if self.check_interact_stop(self.last_screenshot, frame_result):
            return self.round_success(LostVoidMoveByDet.STATUS_ARRIVAL, data=self.last_target_name)

        target_result = self.get_move_target(frame_result)

        if target_result is None:
            if self.target_type == LostVoidDetector.CLASS_ENTRY:
                detected_class_name_list = self._get_detected_class_names(frame_result)
                if LostVoidDetector.CLASS_INTERACT in detected_class_name_list:
                    log.info('寻路节点[%s] 当前目标=%s 未检测到入口，但检测到更高优先级目标=%s，返回上层重识别',
                             '移动前转向', self.target_type, LostVoidDetector.CLASS_INTERACT)
                    return self.round_success(LostVoidMoveByDet.STATUS_NEED_DETECT)
                if LostVoidDetector.CLASS_DISTANCE in detected_class_name_list:
                    log.info('寻路节点[%s] 当前目标=%s 未检测到入口，但检测到更高优先级目标=%s，返回上层重识别',
                             '移动前转向', self.target_type, LostVoidDetector.CLASS_DISTANCE)
                    return self.round_success(LostVoidMoveByDet.STATUS_NEED_DETECT)

            log.info('寻路节点[%s] 当前目标=%s 未识别到可追踪目标，检测结果=%s',
                     '移动前转向', self.target_type, self._get_detected_class_summary(frame_result))
            if self.last_target_result is not None:
                self._reset_turn_calibration_status()  # 丢失目标，重置校准
                # 如果出现多次转向 说明可能是识别不准 然后又恰巧被卡住无法前进
                self.lost_target_during_move_times += 1
                # https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/issues/867
                if self.lost_target_during_move_times % 5 == 0:  # 尝试脱困
                    self.stuck_state.stuck_times += 1
                    escape_result = self.get_out_of_stuck()
                    if escape_result.is_fail:  # 脱困次数超上限 结束本次寻路
                        return escape_result
            self.last_target_result = None
            return self.round_success(LostVoidMoveByDet.STATUS_NO_FOUND)
        self.no_target_handle_times = 0
        self.last_target_result = target_result
        pos = target_result.entire_rect.center
        turn = self.turn_to_target(pos)
        if turn:
            return self.round_wait('转动朝向目标', wait=0.5)

        # 移动前切换到最佳角色
        auto_battle_utils.switch_to_best_agent_for_moving(self.ctx)
        return self.round_success('开始移动')

    @node_from(from_name='移动前转向', status='开始移动')
    @operation_node(name='移动')
    def move_towards(self) -> OperationRoundResult:
        frame_result: DetectFrameResult = self.ctx.lost_void.detect_to_go(
            self.last_screenshot, screenshot_time=self.last_screenshot_time,
            ignore_list=self.ignore_entry_list)
        log.info('寻路节点[%s] 当前目标=%s 检测结果=%s',
                 '移动', self.target_type, self._get_detected_class_summary(frame_result))

        if self.check_interact_stop(self.last_screenshot, frame_result):
            self.ctx.controller.stop_moving_forward()
            return self.round_success(data=self.last_target_name, wait=0.5)

        target_result = self.get_move_target(frame_result)

        if target_result is None:
            current_time = time.time()
            if self.target_lost_start_time == 0:
                self.target_lost_start_time = current_time
            if current_time - self.target_lost_start_time < 1:
                self.ctx.controller.stop_moving_forward()
                # 已停止前进 清除前进帧时间 避免停顿期被计入累计前进时长
                self.last_move_frame_time = 0
                return self.round_wait('短暂丢失目标', wait_round_time=0.1)

            if self.target_type == LostVoidDetector.CLASS_ENTRY:
                # 调用的时候识别的是入口 但进入之后发现有其他优先级更高的 退出执行
                another_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, LostVoidDetector.CLASS_DISTANCE)
                if another_result is not None:
                    log.info('寻路节点[%s] 当前目标=%s 未检测到入口，但检测到更高优先级目标=%s，返回上层重识别',
                             '移动', self.target_type, LostVoidDetector.CLASS_DISTANCE)
                    return self.round_success(status=LostVoidMoveByDet.STATUS_NEED_DETECT)

                another_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, LostVoidDetector.CLASS_INTERACT)
                if another_result is not None:
                    log.info('寻路节点[%s] 当前目标=%s 未检测到入口，但检测到更高优先级目标=%s，返回上层重识别',
                             '移动', self.target_type, LostVoidDetector.CLASS_INTERACT)
                    return self.round_success(status=LostVoidMoveByDet.STATUS_NEED_DETECT)

            log.info('寻路节点[%s] 当前目标=%s 未识别到可追踪目标，检测结果=%s',
                     '移动', self.target_type, self._get_detected_class_summary(frame_result))
            self.lost_target_during_move_times += 1
            # 移动过程中多次丢失目标 通常是因为识别不准
            # 游戏1.6版本出现了可以因为丢失目标转动镜头而一直无法进入脱困 issues #867
            if self.lost_target_during_move_times % 10 == 0:  # 尝试脱困
                self.stuck_state.stuck_times += 1
                escape_result = self.get_out_of_stuck()
                if escape_result.is_fail:  # 脱困次数超上限 结束本次寻路
                    return escape_result

            return self.round_success(LostVoidMoveByDet.STATUS_NO_FOUND)

        self.target_lost_start_time = 0
        self.no_target_handle_times = 0
        is_stuck = self.check_stuck(frame_result, target_result)
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
            # 移动中不做在线校准，只做保守跟随
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
        x_dead_zone = 50
        x_settle_zone = 120

        turn_distance_x = 0
        if 'x' in calibration_axis:
            if abs(diff_x) > x_dead_zone:
                should_update_x_status = True

                if not is_moving and self.last_target_x is not None and self.last_actual_turn_distance != 0:
                    last_diff_x = self.last_target_x - screen_center_x
                    actual_pixel_moved = last_diff_x - diff_x

                    # 当目标穿越中心点(过冲)时，强力抑制，并给一帧稳定时间避免来回横跳
                    if last_diff_x * diff_x < 0:
                        self.estimated_turn_ratio = max(0.02, self.estimated_turn_ratio * 0.5)
                        self.turn_settle_frames = 1
                    # 正常校准：使用移动平均法平滑更新比例
                    elif abs(actual_pixel_moved) > 5:
                        current_ratio = abs(self.last_actual_turn_distance / actual_pixel_moved)
                        current_ratio = min(max(current_ratio, 0.02), 1.0)
                        if self.turn_calibration_count == 1:  # 首次校准，直接采用侦察值
                            self.estimated_turn_ratio = current_ratio
                        else:  # 后续校准，使用移动平均法平滑更新
                            n = self.turn_calibration_count
                            self.estimated_turn_ratio = (self.estimated_turn_ratio * (n - 1) + current_ratio) / n
                        self.turn_calibration_count += 1

                if not is_moving and self.turn_settle_frames > 0 and abs(diff_x) < x_settle_zone:
                    self.turn_settle_frames -= 1
                    should_update_x_status = False
                elif self.turn_calibration_count == 1:
                    turn_distance_x = 5 if diff_x > 0 else -5
                    if not is_moving:
                        self.turn_calibration_count += 1
                else:
                    turn_distance_x = int(diff_x * self.estimated_turn_ratio)

                # 靠近中心时降低最小转向，避免静止状态下的反复横跳
                if 0 < abs(turn_distance_x) < min_turn:
                    if not is_moving and abs(diff_x) < x_settle_zone:
                        turn_distance_x = 0
                    else:
                        turn_distance_x = min_turn if turn_distance_x > 0 else -min_turn
                elif abs(turn_distance_x) > max_turn:
                    turn_distance_x = max_turn if turn_distance_x > 0 else -max_turn

                if not is_moving and should_update_x_status and turn_distance_x != 0:
                    self.last_target_x = target.x
                    self.last_actual_turn_distance = turn_distance_x

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

        return True

    def get_move_target(self, frame_result: DetectFrameResult) -> MoveTargetWrapper | None:
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

    def get_entry_target(self, frame_result: DetectFrameResult) -> MoveTargetWrapper | None:
        """
        获取入口目标 按优先级 尽量避免混合楼层

        @param frame_result: 当前帧识别结果
        @return:
        """
        entry_list: list[MoveTargetWrapper] = []
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

        if self.ctx.lost_void.had_interacted_ophelia_on_current_level:
            entry_list = [
                item
                for item in entry_list
                if LostVoidRegionType.ELITE.value.value not in item.target_name_list
            ]

        if self.last_target_result is not None:  # 优先保持与上次一致的目标
            result = self.get_same_as_last_target(entry_list)
            if result is not None:
                return result

        not_mixed_entry_list = [item for item in entry_list if not item.is_mixed]
        mixed_entry_list = [item for item in entry_list if item.is_mixed]
        if len(not_mixed_entry_list) > 0:
            return self.ctx.lost_void.get_entry_by_priority(not_mixed_entry_list, self.ignore_entry_list)
        elif len(mixed_entry_list) > 0:
            return self.ctx.lost_void.get_entry_by_priority(mixed_entry_list, self.ignore_entry_list)
        else:
            return None

    def _extract_visible_box_list(self, frame_result: DetectFrameResult) -> list[tuple[float, float, float]]:
        """
        提取当前帧全部识别结果的位置信息

        @param frame_result: 当前帧识别结果
        @return: 各目标的 (中心x, 中心y, 宽度)
        """
        return [
            (float(result.center[0]), float(result.center[1]), float(result.width))
            for result in frame_result.results
        ]

    def _record_visible_snapshot(self, screenshot_time: float, frame_result: DetectFrameResult) -> None:
        """
        记录当前帧的可见目标快照 供后续判断画面是否长时间无变化

        @param screenshot_time: 截图时间
        @param frame_result: 当前帧识别结果
        """
        box_list = self._extract_visible_box_list(frame_result)
        if len(box_list) == 0:
            return

        self.visible_snapshot_list.append(VisibleTargetSnapshot(
            time=screenshot_time,
            move_seconds=self.total_move_seconds,
            box_list=box_list,
        ))
        self.visible_snapshot_list = [
            snapshot
            for snapshot in self.visible_snapshot_list
            if screenshot_time - snapshot.time <= LostVoidMoveByDet.STUCK_SNAPSHOT_KEEP_SECONDS
        ]

    def check_stuck(self, frame_result: DetectFrameResult, new_target: MoveTargetWrapper) -> OperationRoundResult | None:
        """
        判断移动过程中是否被卡住

        持续前进时 画面上可见目标的位置和大小应该不断变化
        如果当前帧的可见目标 和足够久之前(且期间确实在前进)的某个快照整体保持不动
        说明角色实际没有位移 短时间内多次命中即判定为卡住

        和逐帧对比不同 这里是和一段时间前的多个快照对比 中间出现单帧抖动、类别抖动、
        目标短暂丢失都不会打断判定 避免以往卡住数分钟都无法触发脱困的问题

        @param frame_result: 当前帧识别结果
        @param new_target: 当前追踪的目标
        @return: 判定卡住时返回对应指令结果 否则返回None
        """
        now = self.last_screenshot_time

        # 累计前进时长 帧间隔过长说明中间没有持续移动 不计入
        if self.last_move_frame_time > 0:
            frame_dt = now - self.last_move_frame_time
            if 0 < frame_dt < 1:
                self.total_move_seconds += frame_dt
        self.last_move_frame_time = now

        if new_target is None:
            return None

        current_box_list = self._extract_visible_box_list(frame_result)
        is_static: bool = False
        for snapshot in self.visible_snapshot_list:
            if now - snapshot.time < LostVoidMoveByDet.STUCK_MIN_AGE_SECONDS:
                continue
            if self.total_move_seconds - snapshot.move_seconds < LostVoidMoveByDet.STUCK_MIN_MOVE_SECONDS:
                continue
            if is_same_box_constellation(snapshot.box_list, current_box_list):
                is_static = True
                break

        self._record_visible_snapshot(now, frame_result)

        if is_static:
            self.stuck_hit_time_list.append(now)
        self.stuck_hit_time_list = [
            hit_time
            for hit_time in self.stuck_hit_time_list
            if now - hit_time <= LostVoidMoveByDet.STUCK_HIT_WINDOW_SECONDS
        ]

        if len(self.stuck_hit_time_list) < LostVoidMoveByDet.STUCK_HIT_TIMES:
            return None

        self.ctx.controller.stop_moving_forward()
        self.stuck_state.stuck_times += 1
        self._reset_stuck_status()
        log.info('寻路节点[移动] 持续前进但画面无变化 判定卡住 本层第%d次', self.stuck_state.stuck_times)
        return self.round_success('尝试脱困')

    def _slide_along_obstacle(self, to_left: bool, side_seconds: float) -> None:
        """
        贴着障碍物横向滑动

        按住前进的同时横向移动 斜向顶着障碍物时会沿其表面滑动
        比先后撤再横移更容易绕过栅栏这类横向较长的障碍

        @param to_left: 是否向左滑动
        @param side_seconds: 横向按键时长
        """
        self.ctx.controller.start_moving_forward()
        if to_left:
            self.ctx.controller.move_a(press=True, press_time=side_seconds, release=True)
        else:
            self.ctx.controller.move_d(press=True, press_time=side_seconds, release=True)
        self.ctx.controller.stop_moving_forward()

    @node_from(from_name='移动', status='尝试脱困')
    @node_from(from_name='无目标处理', status='尝试脱困')
    @operation_node(name='脱困')
    def get_out_of_stuck(self) -> OperationRoundResult:
        """
        脱困 按本层累计卡住次数逐步升级策略

        - 阶段0/1: 向优先侧贴墙横滑 (1.5秒/2.5秒)
        - 阶段2/3: 向另一侧贴墙横滑 (1.5秒/2.5秒)
        - 阶段4: 大幅后撤拉开距离 再向优先侧平移
        - 阶段5: 后撤后大幅转向(约90度)绕行 然后交回上层重新识别
        一轮走完后翻转优先侧 重新循环
        同一侧连续尝试两次(而不是每次换边) 避免左右横跳原地抵消

        超过次数上限时结束本次寻路 返回超时让上层走重开流程
        @return:
        """
        if self.stuck_state.stuck_times > LostVoidMoveByDet.MAX_STUCK_TIMES:
            log.error('迷失之地 本层累计脱困%d次仍未脱出 放弃本次寻路', self.stuck_state.stuck_times)
            return self.round_fail(Operation.STATUS_TIMEOUT)

        self.ctx.controller.stop_moving_forward()
        # 在大世界 先切换到移动最优角色
        auto_battle_utils.switch_to_best_agent_for_moving(self.ctx)
        # 部分障碍物可以破坏，仅在识别到普攻按钮时尝试攻击
        if self.ctx.auto_battle_context.is_normal_attack_btn_available(self.last_screenshot):
            self.ctx.controller.normal_attack(press=True, press_time=0.2, release=True)
            time.sleep(1)

        escape_phase = (self.stuck_state.stuck_times - 1) % 6
        prefer_left = self.stuck_state.prefer_left_escape
        log.info('迷失之地 本层第%d次尝试脱困 阶段=%d 优先侧=%s',
                 self.stuck_state.stuck_times, escape_phase, '左' if prefer_left else '右')

        if escape_phase == 0:
            self._slide_along_obstacle(to_left=prefer_left, side_seconds=1.5)
        elif escape_phase == 1:
            self._slide_along_obstacle(to_left=prefer_left, side_seconds=2.5)
        elif escape_phase == 2:
            self._slide_along_obstacle(to_left=not prefer_left, side_seconds=1.5)
        elif escape_phase == 3:
            self._slide_along_obstacle(to_left=not prefer_left, side_seconds=2.5)
        elif escape_phase == 4:
            self.ctx.controller.move_s(press=True, press_time=2.5, release=True)
            if prefer_left:
                self.ctx.controller.move_a(press=True, press_time=2, release=True)
            else:
                self.ctx.controller.move_d(press=True, press_time=2, release=True)
        else:
            self.ctx.controller.move_s(press=True, press_time=1, release=True)
            self.ctx.controller.turn_by_distance(-300 if prefer_left else 300)
            time.sleep(0.5)
            self.ctx.controller.move_w(press=True, press_time=2, release=True)
            # 一轮策略走完 下一轮从另一侧开始
            self.stuck_state.prefer_left_escape = not prefer_left

        # 位置已主动变化 清除跟踪状态 重新选择目标并重新校准转向
        self.last_target_result = None
        self._reset_turn_calibration_status()
        self._reset_stuck_status()

        if escape_phase == 5:
            # 绕行后朝向已大幅变化 交回上层重新识别
            return self.round_success(LostVoidMoveByDet.STATUS_NEED_DETECT)

        if self.target_type == LostVoidDetector.CLASS_INTERACT:
            return self.round_success(LostVoidMoveByDet.STATUS_NEED_DETECT)

        self.screenshot()
        frame_result = self.ctx.lost_void.detect_to_go(
            self.last_screenshot, screenshot_time=self.last_screenshot_time,
            ignore_list=self.ignore_entry_list,
        )
        distance_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, LostVoidDetector.CLASS_DISTANCE)
        if distance_result is not None:
            return self.round_success(LostVoidMoveByDet.STATUS_NEED_DETECT)

        return self.round_success('继续识别目标')

    def check_interact_stop(self, screen: MatLike, frame_result: DetectFrameResult) -> bool:
        """
        判断是否应该为交互停下来
        1. 先检查交互按钮，如果有则返回True
        2. 检测图标是否变大，如果变大则返回True
        3. 检查普攻按钮是否丢失，如果丢失则停下（停下动作每5秒最多触发一次）
        @param screen: 游戏画面
        @param frame_result: 识别结果
        @return:
        """
        if not self.stop_when_interact:
            return False

        # 1. 先检查交互按钮
        result = self.round_by_find_area(screen, '战斗画面', '按键-交互')
        if not result.is_success:
            # 没有交互按钮，检查普攻按钮是否丢失
            result = self.round_by_find_area(screen, '战斗画面', '按键-普通攻击')
            if not result.is_success:
                # 普攻按钮丢失，检查距离上次停下是否超过5秒
                current_time = time.time()
                if current_time - self._last_attack_btn_check_time >= 5:
                    # 执行停下动作，并记录时间
                    self._last_attack_btn_check_time = current_time
                    self.ctx.controller.stop_moving_forward()
                    time.sleep(0.5)
            return False

        if self.allow_arrival_by_interact_btn:
            return True

        # 2. 检测图标是否变大
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
        self.no_target_handle_times += 1

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

        if self.no_target_handle_times >= 7:
            self.no_target_handle_times = 0
            self.stuck_state.stuck_times += 1
            return self.round_success('尝试脱困')

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

    def get_same_as_last_target(self, entry_list: list[MoveTargetWrapper]) -> MoveTargetWrapper | None:
        """
        从本次结果中 选择与上一次位置最接近
        @param entry_list:
        @return:
        """
        nearest_result: MoveTargetWrapper | None = None
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
