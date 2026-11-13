import time
from dataclasses import dataclass
from typing import ClassVar

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
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
    stuck_times: int = 0
    prefer_left_escape: bool = True  # 当前绕行方向
    same_side_times: int = 0  # 当前方向已经绕行的次数 只在 smart_escape 时使用


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

    # 以下常量只在挑战配置开启 smart_escape 时使用
    # 画面静止判卡住 按住前进时画面长时间几乎不变 说明被挡住在原地跑
    SCENE_DIFF_SCALE: ClassVar[int] = 8  # 画面缩小倍数
    SCENE_STATIC_DIFF: ClassVar[float] = 3.0  # 缩小灰度图逐像素平均差低于这个值算静止
    SCENE_STATIC_SECONDS: ClassVar[float] = 1.5  # 连续静止多久算卡住
    SCENE_IGNORE_RECT: ClassVar[tuple[int, int, int, int]] = (820, 420, 1100, 1080)  # 1080p 角色所在区域 跑动动画不算画面变化
    SCENE_Y1: ClassVar[int] = 150  # 只比较中间部分 排除顶部队伍头像和小地图
    SCENE_Y2: ClassVar[int] = 850  # 排除底部技能按钮

    MOVING_MAX_TURN: ClassVar[int] = 15  # 移动中每次最多转多少 保守跟随目标
    ESCAPE_MAX_TURN: ClassVar[int] = 100  # 脱困横移时每次最多转多少 横移时目标横向漂得快 要跟得上
    ESCAPE_TARGET_MIN_DX: ClassVar[int] = 10  # 脱困时目标图标偏离画面中心超过这个像素 才按图标所在一侧绕
    ESCAPE_BACK_STEP: ClassVar[float] = 0.5  # 脱困时每多卡一次 多后退多少秒
    ESCAPE_BACK_MAX: ClassVar[float] = 2.0  # 脱困后退最长秒数
    ESCAPE_FORWARD_STEP: ClassVar[float] = 0.2  # 脱困时每多卡一次 横移后多前进多少秒
    ESCAPE_FORWARD_MAX: ClassVar[float] = 2.0  # 脱困横移后前进最长秒数

    # 转向 比例 = 鼠标移动量 ÷ 目标在画面上横移的像素 初始值在 LostVoidContext.move_turn_ratio
    STATIC_MAX_TURN: ClassVar[int] = 600  # 原地转向每次最多转多少 按比例 0.6 约 1000 像素 覆盖半个画面
    TURN_RATIO_MIN_PIXEL: ClassVar[int] = 30  # 目标横移少于这么多像素不用来校准
    TURN_RATIO_MIN: ClassVar[float] = 0.3  # 单次测出的比例在这个范围外不采用
    TURN_RATIO_MAX: ClassVar[float] = 1.2
    TURN_RATIO_SMOOTH: ClassVar[float] = 0.2  # 每次测出的比例占多少权重

    # 锁定规划的入口 过不去时解除 按画面里的入口选
    LOCKED_ENTRY_MAX_LOST_TIMES: ClassVar[int] = 10  # 连续多少次无目标处理还没看到就解除 每次转 200 按默认灵敏度约 36° 10 次约一圈
    LOCKED_ENTRY_MAX_STUCK_TIMES: ClassVar[int] = 6  # 锁定后卡住多少次就解除 本层上限 12 次的一半 留一半给按画面选门

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
        locked_entry_name: str | None = None,
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
        @param locked_entry_name: 规划的下一个区域 寻路全程只去这种入口 过不去时解除
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
        self.locked_entry_name: str | None = locked_entry_name
        self._locked_lost_times: int = 0  # 锁定期间连续进入无目标处理的次数 看到锁定的入口时清零
        self._locked_start_stuck_times: int = self.stuck_state.stuck_times  # 锁定开始时本层已卡住的次数

        # 挑战配置开启后 用画面静止判卡住、后退/横移/前进脱困、跨移动保留的转向比例
        challenge_config = self.ctx.lost_void.challenge_config
        self.smart_escape: bool = challenge_config is not None and challenge_config.smart_escape

        # 需要按方向选的时候 按最大x值选
        # 入口时 从右往左选可以上楼梯
        self.choose_by_max_x: bool = self.current_region in [
            LostVoidRegionType.ENTRY,
        ]

        self.last_target_result: MoveTargetWrapper | None = None  # 最后一次识别到的目标
        self.last_visible_target_list: list[MoveTargetWrapper] = []  # 上一次识别到的全部可见目标
        self.last_target_name: str | None = None  # 最后识别到的交互目标名称
        self.same_target_times: float = 0  # 识别到相同目标的次数
        self.total_turn_times: int = 0  # 总共转向次数

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

        self._last_scene: np.ndarray | None = None  # 上一帧缩小后的灰度画面
        self._scene_mask: np.ndarray | None = None  # 参与画面比较的区域
        self._scene_static_start_time: float = 0  # 画面开始静止的截图时间
        self._escape_side_decided: bool = False  # 本次寻路是否已决定过脱困方向
        self._search_turn_right: bool = False  # 丢失目标时往右转找 脱困向左横移后镜头跟着左转 目标落到了右边
        self._escape_times: int = 0  # 本段移动触发脱困的次数 决定脱困横移多久

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

    def _update_turn_ratio(self, diff_x: float) -> None:
        """
        smart_escape 时 用上一次原地转向后目标实际横移的像素 平滑更新转向比例
        :param diff_x: 当前目标相对画面中心的横向偏移
        """
        if self.last_target_x is None or self.last_actual_turn_distance == 0:
            return
        last_diff_x = self.last_target_x - self.ctx.controller.standard_width / 2
        actual_pixel_moved = last_diff_x - diff_x
        turn_distance = self.last_actual_turn_distance
        self.last_target_x = None  # 每次转向只校准一次
        self.last_actual_turn_distance = 0
        if abs(actual_pixel_moved) < LostVoidMoveByDet.TURN_RATIO_MIN_PIXEL:  # 移动太少 识别框抖动占比大
            return
        sample = turn_distance / actual_pixel_moved
        if not LostVoidMoveByDet.TURN_RATIO_MIN <= sample <= LostVoidMoveByDet.TURN_RATIO_MAX:
            return  # 多半是换了目标或识别框跳了
        ratio = self.ctx.lost_void.move_turn_ratio
        self.ctx.lost_void.move_turn_ratio = ratio * (1 - LostVoidMoveByDet.TURN_RATIO_SMOOTH) + sample * LostVoidMoveByDet.TURN_RATIO_SMOOTH
        if self.ctx.env_config.is_debug:
            log.debug(f'转向比例 本次={sample:.3f} 更新为={self.ctx.lost_void.move_turn_ratio:.3f}')

    def _reset_stuck_status(self) -> None:
        """
        重置卡住判断相关的状态
        """
        self.same_target_times = 0
        self.last_visible_target_list = []
        self._last_scene = None
        self._scene_static_start_time = 0

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
                self._reset_stuck_status()
                # 如果出现多次转向 说明可能是识别不准 然后又恰巧被卡住无法前进
                self.lost_target_during_move_times += 1
                # https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/issues/867
                if self.lost_target_during_move_times % 5 == 0:  # 尝试脱困
                    self.stuck_state.stuck_times += 1
                    self.get_out_of_stuck()
            self.last_target_result = None
            return self.round_success(LostVoidMoveByDet.STATUS_NO_FOUND)
        self.no_target_handle_times = 0
        self.last_target_result = target_result
        pos = target_result.entire_rect.center
        turn = self.turn_to_target(pos)
        if turn:
            return self.round_wait('转动朝向目标', wait=0.5)

        if self.smart_escape:
            # 走起来之后目标位置变化不是转向造成的 不能用来校准比例
            self.last_target_x = None
            self.last_actual_turn_distance = 0
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
                return self.round_wait('短暂丢失目标', wait_round_time=0.1)

            self._reset_stuck_status()
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
                self.get_out_of_stuck()

            return self.round_success(LostVoidMoveByDet.STATUS_NO_FOUND)

        self.target_lost_start_time = 0
        self.no_target_handle_times = 0
        is_stuck = self.check_stuck(frame_result, target_result)
        if is_stuck is not None:
            return is_stuck

        if self.smart_escape and self.check_scene_static(self.last_screenshot, self.last_screenshot_time):
            log.info('寻路节点[%s] 当前目标=%s 前进中画面持续静止 判定卡住', '移动', self.target_type)
            return self._on_stuck()

        self.last_target_result = target_result
        self.last_target_name = target_result.leftest_target_name
        self.turn_to_target(target_result.entire_rect.center, is_moving=True)
        self.ctx.controller.start_moving_forward()

        return self.round_wait('移动中', wait_round_time=0.1)

    def turn_to_target(self, target: Point, is_moving: bool = False, calibration_axis: str = 'x',
                       moving_max_turn: int = MOVING_MAX_TURN) -> bool:
        """
        根据目标的位置转动 smart_escape 时按跨移动保留的转向比例转 否则用自适应算法
        :param target: 目标位置
        :param is_moving: 是否在移动中
        :param calibration_axis: 校准轴。可以是 'xy', 'x', 'y'
        :param moving_max_turn: smart_escape 时移动中每次最多转多少
        :return: 是否进行了转动
        """
        if self.smart_escape:
            return self._turn_to_target_by_ratio(target, is_moving, calibration_axis, moving_max_turn)
        return self._turn_to_target_adaptive(target, is_moving, calibration_axis)

    def _turn_to_target_by_ratio(self, target: Point, is_moving: bool, calibration_axis: str,
                                 moving_max_turn: int) -> bool:
        """
        按转向比例把目标转到画面中心 原地转向后用实际转动校准比例
        :param target: 目标位置
        :param is_moving: 是否在移动中。移动中每次少转一点 保守跟随
        :param calibration_axis: 转向轴。可以是 'xy', 'x', 'y'
        :param moving_max_turn: 移动中每次最多转多少
        :return: 是否进行了转动
        """
        screen_center_x = self.ctx.controller.standard_width / 2
        screen_center_y = self.ctx.controller.standard_height / 2
        diff_x = target.x - screen_center_x
        diff_y = target.y - screen_center_y
        x_dead_zone = 50

        turn_distance_x = 0
        if 'x' in calibration_axis:
            if not is_moving:
                self._update_turn_ratio(diff_x)
            if abs(diff_x) > x_dead_zone:
                min_turn = 5
                max_turn = moving_max_turn if is_moving else LostVoidMoveByDet.STATIC_MAX_TURN
                turn_distance_x = int(diff_x * self.ctx.lost_void.move_turn_ratio)
                if 0 < abs(turn_distance_x) < min_turn:
                    turn_distance_x = min_turn if turn_distance_x > 0 else -min_turn
                elif abs(turn_distance_x) > max_turn:
                    turn_distance_x = max_turn if turn_distance_x > 0 else -max_turn

                if not is_moving:
                    self.last_target_x = target.x
                    self.last_actual_turn_distance = turn_distance_x

        turn_distance_y = 0
        if 'y' in calibration_axis:
            # 让目标稳定在屏幕上半区 diff_y 约 -300 有死区避免频繁微调
            target_y = -300
            dead_zone = 100
            if diff_y > target_y + dead_zone:
                turn_distance_y = 20
            elif diff_y < target_y - dead_zone:
                turn_distance_y = -20

        if turn_distance_x == 0 and turn_distance_y == 0:
            return False

        if self.ctx.env_config.is_debug:
            log.debug(f'转向指令: X={turn_distance_x}, Y={turn_distance_y}, 当前X比例: {self.ctx.lost_void.move_turn_ratio:.4f}, 移动中: {is_moving}, 校准轴: {calibration_axis}')

        self.ctx.controller.move_mouse_relative(turn_distance_x, turn_distance_y)
        self.total_turn_times += 1
        return True

    def _turn_to_target_adaptive(self, target: Point, is_moving: bool = False, calibration_axis: str = 'x') -> bool:
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
        if self.locked_entry_name is not None:
            return self._get_locked_entry_target(frame_result)

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

    def _get_locked_entry_target(self, frame_result: DetectFrameResult) -> MoveTargetWrapper | None:
        """
        只找锁定的入口 不与相邻入口合并 混合入口的中心在两扇门之间 朝中心跑可能进了旁边的门
        多个时取最右 与 get_entry_by_priority 一致
        @param frame_result: 当前帧识别结果
        @return: 画面里没有锁定的入口时返回 None
        """
        target: DetectObjectResult | None = None
        for result in frame_result.results:
            if result.detect_class.class_name[5:] != self.locked_entry_name:
                continue
            if target is None or result.x1 > target.x1:
                target = result

        if target is None:
            return None
        self._locked_lost_times = 0
        return MoveTargetWrapper(target)

    def _check_unlock_entry(self) -> None:
        """
        锁定的入口过不去时解除锁定 之后按画面里的入口选
        """
        if self.locked_entry_name is None:
            return

        reason: str | None = None
        if self._locked_lost_times >= LostVoidMoveByDet.LOCKED_ENTRY_MAX_LOST_TIMES:
            reason = f'转了 {self._locked_lost_times} 次没看到'
        elif self.stuck_state.stuck_times - self._locked_start_stuck_times >= LostVoidMoveByDet.LOCKED_ENTRY_MAX_STUCK_TIMES:
            reason = f'锁定后卡住 {LostVoidMoveByDet.LOCKED_ENTRY_MAX_STUCK_TIMES} 次'
        if reason is None:
            return

        log.info(f'路线规划 | 寻路去 {self.locked_entry_name} {reason} 解除锁定 按画面里的入口选')
        self.locked_entry_name = None
        self.last_target_result = None

    def get_visible_targets(self, frame_result: DetectFrameResult) -> list[MoveTargetWrapper]:
        """
        获取当前画面里可用于卡住判断的全部目标
        """
        visible_target_list: list[MoveTargetWrapper] = []
        for result in frame_result.results:
            visible_target_list.append(MoveTargetWrapper(result))

        return visible_target_list

    def is_same_visible_target_list(
        self,
        last_target_list: list[MoveTargetWrapper],
        new_target_list: list[MoveTargetWrapper],
    ) -> tuple[bool, str]:
        """
        判断两次识别到的可见目标是否整体保持不动
        """
        if len(last_target_list) == 0:
            return False, f'上一轮无可见目标 current={len(new_target_list)}'

        if len(last_target_list) != len(new_target_list):
            return False, f'目标数量变化 last={len(last_target_list)} current={len(new_target_list)}'

        used_idx_set: set[int] = set()
        class_changed: bool = False
        for new_target in new_target_list:
            matched_idx: int | None = None
            matched_distance: float | None = None
            matched_last_target: MoveTargetWrapper | None = None

            for idx, last_target in enumerate(last_target_list):
                if idx in used_idx_set:
                    continue

                dis = cal_utils.distance_between(last_target.entire_rect.center, new_target.entire_rect.center)
                if dis >= 10:
                    continue

                if matched_distance is None or dis < matched_distance:
                    matched_idx = idx
                    matched_distance = dis
                    matched_last_target = last_target

            if matched_idx is None:
                return False, (
                    f'目标未匹配 name={new_target.leftest_target_name} '
                    f'center={new_target.entire_rect.center}'
                )

            if matched_last_target is not None and matched_last_target.leftest_target_name != new_target.leftest_target_name:
                class_changed = True

            used_idx_set.add(matched_idx)

        if class_changed:
            return True, '全部可见目标位移都在阈值内，且存在类别抖动'
        else:
            return True, '全部可见目标位移都在阈值内'

    def check_stuck(self, frame_result: DetectFrameResult, new_target: MoveTargetWrapper) -> OperationRoundResult | None:
        """
        判断是否被困
        @return:
        """
        visible_target_list = self.get_visible_targets(frame_result)
        if self.last_target_result is None or new_target is None:
            self._reset_stuck_status()
            self.last_visible_target_list = visible_target_list
            return None

        all_visible_targets_static, _ = self.is_same_visible_target_list(
            self.last_visible_target_list,
            visible_target_list,
        )

        if all_visible_targets_static:
            increase_count = 0.2 if len(visible_target_list) == 1 else 1
            self.same_target_times += increase_count
        else:
            self.same_target_times = 0

        self.last_visible_target_list = visible_target_list
        stuck_threshold = 5 if len(visible_target_list) == 1 else 20

        if self.same_target_times >= stuck_threshold:
            return self._on_stuck()
        else:
            return None

    def _on_stuck(self) -> OperationRoundResult:
        """
        判定卡住后 停止前进并进入脱困
        """
        self.ctx.controller.stop_moving_forward()
        self.stuck_state.stuck_times += 1
        self._reset_stuck_status()
        self._check_unlock_entry()
        if self.stuck_state.stuck_times > 12:
            return self.round_fail('无法脱困')
        else:
            return self.round_success('尝试脱困')

    def check_scene_static(self, screen: MatLike, screenshot_time: float) -> bool:
        """
        按住前进时 画面(排除角色和HUD)持续几乎不变 说明被障碍物挡住在原地跑
        正常跑动或转动镜头时画面都会明显变化
        @return: 是否判定卡住
        """
        scale = LostVoidMoveByDet.SCENE_DIFF_SCALE
        small = cv2.resize(screen, (screen.shape[1] // scale, screen.shape[0] // scale), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        if self._scene_mask is None:
            self._scene_mask = np.zeros(gray.shape, dtype=bool)
            self._scene_mask[LostVoidMoveByDet.SCENE_Y1 // scale:LostVoidMoveByDet.SCENE_Y2 // scale, :] = True
            x1, y1, x2, y2 = LostVoidMoveByDet.SCENE_IGNORE_RECT
            self._scene_mask[y1 // scale:y2 // scale, x1 // scale:x2 // scale] = False

        last_scene = self._last_scene
        self._last_scene = gray
        if last_scene is None or not self.ctx.controller.is_moving:
            self._scene_static_start_time = 0
            return False

        diff = float(cv2.absdiff(gray, last_scene)[self._scene_mask].mean())
        if self.ctx.env_config.is_debug:
            log.debug(f'寻路画面差值: {diff:.2f}')

        if diff >= LostVoidMoveByDet.SCENE_STATIC_DIFF:
            self._scene_static_start_time = 0
            return False

        if self._scene_static_start_time == 0:
            self._scene_static_start_time = screenshot_time
            return False

        return screenshot_time - self._scene_static_start_time >= LostVoidMoveByDet.SCENE_STATIC_SECONDS

    def _get_escape_side(self) -> bool | None:
        """
        本次寻路第一次脱困往哪边横移 目标图标偏在画面中心哪一侧 就往哪一侧绕
        入口在障碍物后面偏哪边 从那边绕路最短
        @return: True 往左 False 往右 判断不了时返回 None 沿用原来的方向
        """
        target = self.last_target_result
        if target is not None:
            diff_x = target.entire_rect.center.x - self.ctx.controller.standard_width / 2
            if abs(diff_x) >= LostVoidMoveByDet.ESCAPE_TARGET_MIN_DX:
                log.info('寻路脱困 目标偏%s %d像素 往目标一侧绕', '左' if diff_x < 0 else '右', abs(diff_x))
                return diff_x < 0
        return None

    @staticmethod
    def get_escape_durations(escape_idx: int) -> tuple[float, float]:
        """
        smart_escape 时脱困后退和横移后前进的时长 随本层卡住次数增长
        @param escape_idx: 第几次脱困 从 0 开始 第 0 次不后退不前进
        @return: (后退秒数, 前进秒数)
        """
        back_time = min(escape_idx * LostVoidMoveByDet.ESCAPE_BACK_STEP, LostVoidMoveByDet.ESCAPE_BACK_MAX)
        forward_time = min(escape_idx * LostVoidMoveByDet.ESCAPE_FORWARD_STEP, LostVoidMoveByDet.ESCAPE_FORWARD_MAX)
        return back_time, forward_time

    @node_from(from_name='移动', status='尝试脱困')
    @node_from(from_name='无目标处理', status='尝试脱困')
    @operation_node(name='脱困')
    def get_out_of_stuck(self) -> OperationRoundResult:
        """
        脱困
        @return:
        """
        self._escape_times += 1
        if self.smart_escape:
            self._escape_facing_target()
        else:
            self._escape_by_attack_and_move()

        self.screenshot()
        frame_result = self.ctx.lost_void.detect_to_go(
            self.last_screenshot, screenshot_time=self.last_screenshot_time,
            ignore_list=self.ignore_entry_list,
        )
        if self.target_type == LostVoidDetector.CLASS_INTERACT:
            return self.round_success(LostVoidMoveByDet.STATUS_NEED_DETECT)

        distance_result = self.ctx.lost_void.detector.get_result_by_x(frame_result, LostVoidDetector.CLASS_DISTANCE)
        if distance_result is not None:
            return self.round_success(LostVoidMoveByDet.STATUS_NEED_DETECT)

        return self.round_success('继续识别目标')

    def _escape_by_attack_and_move(self) -> None:
        """
        原来的脱困方式 切换移动最优角色 尝试普攻打破障碍 后退 → 横移(左右交替) → 前进
        """
        # 在大世界 先切换到移动最优角色
        auto_battle_utils.switch_to_best_agent_for_moving(self.ctx)
        # 部分障碍物可以破坏，仅在识别到普攻按钮时尝试攻击
        if self.ctx.auto_battle_context.is_normal_attack_btn_available(self.last_screenshot):
            self.ctx.controller.normal_attack(press=True, press_time=0.2, release=True)
            time.sleep(1)

        escape_phase = (self.stuck_state.stuck_times - 1) % 8
        backward_press_time = min(escape_phase * 0.5, 2)
        side_press_time = min((escape_phase + 1) * 0.2, 2)
        forward_press_time = min(escape_phase * 0.2, 2)

        self.ctx.controller.move_s(press=True, press_time=backward_press_time, release=True)
        if self.stuck_state.prefer_left_escape:
            self.ctx.controller.move_a(press=True, press_time=side_press_time, release=True)
        else:
            self.ctx.controller.move_d(press=True, press_time=side_press_time, release=True)
        self.stuck_state.prefer_left_escape = not self.stuck_state.prefer_left_escape

        if forward_press_time > 0:
            self.ctx.controller.move_w(press=True, press_time=forward_press_time, release=True)

    def _escape_facing_target(self) -> None:
        """
        smart_escape 的脱困方式 后退 → 横移 → 前进 只横移会贴着宽障碍或墙角滑 先退开再绕 绕过边缘后往前走
        不普攻 不切人 横移过程中镜头一直对准目标
        朝同一方向连续绕行2次 仍卡住才换另一侧 避免左右交替互相抵消
        """
        state = self.stuck_state
        prefer_left = self._get_escape_side() if not self._escape_side_decided else None
        self._escape_side_decided = True
        if prefer_left is not None:
            state.prefer_left_escape = prefer_left
            state.same_side_times = 0
        elif state.same_side_times >= 2:
            state.prefer_left_escape = not state.prefer_left_escape
            state.same_side_times = 0
        state.same_side_times += 1
        # 横移时间随本段移动卡住次数增长 换边后能覆盖到更远的位置
        # 不按本层累计次数算 否则前一段移动卡过 这一段第一次横移就过长 镜头转走丢了目标
        escape_idx = max(self._escape_times - 1, 0)
        side_press_time = min(0.8 + 0.4 * escape_idx, 2.5)
        # 后退和前进按本层累计卡住次数算 每次脱困后会重新开一段寻路 本段计数永远是第1次
        level_idx = (max(state.stuck_times, 1) - 1) % 8
        back_time, forward_time = LostVoidMoveByDet.get_escape_durations(level_idx)
        log.info('寻路脱困 本段第%d次 本层第%d次 后退%.1f秒 向%s横移%.1f秒 前进%.1f秒',
                 self._escape_times, state.stuck_times,
                 back_time, '左' if state.prefer_left_escape else '右', side_press_time, forward_time)

        if back_time > 0:
            self.ctx.controller.move_s(press=True, press_time=back_time, release=True)
        self._strafe_facing_target(state.prefer_left_escape, side_press_time)
        if forward_time > 0:
            self.ctx.controller.move_w(press=True, press_time=forward_time, release=True)
        # 横移后仍丢失目标时 往横移的反方向转着找
        self._search_turn_right = state.prefer_left_escape

    def _strafe_facing_target(self, to_left: bool, press_time: float) -> None:
        """
        按住 A/D 横移 期间不断识别目标 转镜头让目标保持在画面中心
        镜头对准目标时 A/D 始终垂直于目标方向 相当于绕着目标沿障碍物边缘移动
        @param to_left: 是否往左
        @param press_time: 横移多久 秒
        """
        move = self.ctx.controller.move_a if to_left else self.ctx.controller.move_d
        move(press=True)
        try:
            start_time = time.time()
            while time.time() - start_time < press_time:
                self.screenshot()
                frame_result = self.ctx.lost_void.detect_to_go(
                    self.last_screenshot, screenshot_time=self.last_screenshot_time,
                    ignore_list=self.ignore_entry_list,
                )
                target_result = self.get_move_target(frame_result)
                if target_result is not None:  # 看不到目标时只横移 不转
                    self.last_target_result = target_result
                    self.turn_to_target(target_result.entire_rect.center, is_moving=True,
                                        moving_max_turn=LostVoidMoveByDet.ESCAPE_MAX_TURN)
                time.sleep(0.05)
        finally:
            move(release=True)

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

            if self.locked_entry_name is not None and result.detect_class.class_name[5:] != self.locked_entry_name:
                # 锁定了规划的入口时 站在别的门旁边不算到达 否则会直接进了旁边的门
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
        if self.locked_entry_name is not None:
            self._locked_lost_times += 1
            self._check_unlock_entry()

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

        self.ctx.controller.turn_by_distance(200 if self._search_turn_right else -200)
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
