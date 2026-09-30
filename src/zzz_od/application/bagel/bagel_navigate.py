from __future__ import annotations

from math import atan2, degrees, hypot
from typing import TYPE_CHECKING, Literal

import cv2

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import cal_utils, cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_const import (
    NAV_ALIGN_PRESS,
    NAV_CRUISE_DISTANCE,
    NAV_CRUISE_TURN_CAP,
    NAV_CRUISE_TURN_GAP,
    NAV_CRUISE_TURN_LIMIT,
    NAV_FORWARD_PRESS,
    NAV_LOCATE_MISS_LIMIT,
    NAV_SAFE_APPROACH_DISTANCE,
    NAV_SAFE_APPROACH_PRESS,
    NAV_SAFE_BRAKE_WAIT,
    NAV_STOP_TURN_CAP,
    NAV_TURN_DEADBAND,
)
from zzz_od.application.bagel.bagel_flow import NavigationOptions, load_published_flow
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_route import BagelRoute
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision
from zzz_od.operation.turning.turn_compensation import AngleTurnCompensator

if TYPE_CHECKING:
    from collections.abc import Callable

    from cv2.typing import MatLike

    from one_dragon.base.operation.operation_base import OperationResult
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext

Destination = Literal['box', 'safe']


class BagelNavigate(BagelOperation):
    """支持出生点短线导航：远段按住走到节点附近，近处和电子保险箱最后一段改为短步。

    两个出生地共用地图路点导航，按实际定位计算下一点方向。
    """

    STATUS_UNSUPPORTED: str = '非支持出生点'
    STATUS_WAYPOINT: str = '已到路点'
    STATUS_ARRIVED_BOX: str = '已到武备箱'
    STATUS_ARRIVED_SAFE: str = '已到电子保险箱'

    def __init__(
        self,
        ctx: ZContext,
        destination: str = 'box',
        map_id: str = 'janus_high_a',
        route_data: BagelRoute | None = None,
        on_observation: Callable[[dict[str, object]], None] | None = None,
        navigation: NavigationOptions | None = None,
        require_spawn: bool = True,
        check_target_position: bool = False,
        coordinate_only: bool = False,
        final_approach: bool = False,
    ) -> None:
        """指定容器类型；流程传入独立路点，并允许从当前可定位位置开始。"""
        if destination not in ('box', 'safe'):
            raise ValueError('导航目标只能是 box 或 safe')
        route_label = '录像店复活点' if map_id == 'janus_high_a' else '白鸽工地地铁站复活点'
        name = (
            f'贝果-{route_label}前往武备箱'
            if destination == 'box'
            else '贝果-前往电子保险箱'
        )
        default_step = None
        if route_data is None:
            points = []
            for step in load_published_flow(map_id).steps:
                if step.action not in ('move', 'approach') or step.target != destination:
                    continue
                for point in step.waypoints:
                    if not points or point != points[-1]:
                        points.append(point)
                if step.action == 'approach':
                    default_step = step
                    break
            if default_step is None:
                raise ValueError('发布流程没有对应的移动步骤')
            route_data = BagelRoute(map_id, tuple(points))
        self.navigation: NavigationOptions = navigation or (default_step.navigation if default_step else NavigationOptions())
        self.require_spawn: bool = require_spawn
        self.check_target_position: bool = check_target_position
        self.coordinate_only: bool = coordinate_only
        self.final_approach: bool = final_approach
        super().__init__(ctx, op_name=name, timeout_seconds=self.navigation.effective_timeout(destination))
        self.destination: Destination = destination
        self.map_id: str = map_id
        self.on_observation: Callable[[dict[str, object]], None] | None = on_observation
        self.vision: BagelRouteVision = BagelRouteVision(map_id, route_data)
        if not self.vision.route.points_for(destination):
            raise ValueError(f'{map_id} 暂不支持该导航路段：{destination}')
        self.active_waypoints: list[tuple[str, tuple[float, float]]] = self._select_waypoints()
        self.interact_area: str = '武备箱交互' if destination == 'box' else '电子保险箱交互'
        self.forward_press: float = NAV_FORWARD_PRESS
        self.arrive_status: str = (
            self.STATUS_ARRIVED_BOX if destination == 'box' else self.STATUS_ARRIVED_SAFE
        )
        self.waypoint_index: int = 0
        self.steps: int = 0
        self.heading_aligned: bool = False
        self.last_input_frame: float | None = None
        self.pending_turn: tuple[float, float] | None = None
        self.turn_compensator: AngleTurnCompensator = AngleTurnCompensator(ctx.controller)
        self.target_wait_started: float | None = None
        self.pickup_misses: int = 0
        self.locate_misses: int = 0
        self.last_position: tuple[float, float] | None = None
        self._cruise_progress: tuple[tuple[float, float], float] | None = None
        self.last_cruise_turn_at: float | None = None
        self._spawn_far: int = 0
        self._spawn_miss: int = 0
        self._safe_brake_until: float | None = None

    def _select_waypoints(self) -> list[tuple[str, tuple[float, float]]]:
        """按显式路段选点，名称仅用于显示。"""
        return [(point.name, point.xy) for point in self.vision.route.points_for(self.destination)]

    def handle_init(self) -> None:
        """每次执行从起点检查开始。"""
        super().handle_init()
        self.waypoint_index = len(self.active_waypoints) - 1 if self.final_approach else 0
        self.steps = 0
        self.target_wait_started = None
        self.pickup_misses = 0
        self.locate_misses = 0
        self.last_position = None
        self._cruise_progress = None
        self.last_cruise_turn_at = None
        self._spawn_far = 0
        self._spawn_miss = 0
        self._safe_brake_until = None
        self._invalidate_heading()
        self.turn_compensator.reset()
        log.info('贝果导航路线快照：%s', self.vision.route.to_dict())

    def minimap(self) -> MatLike:
        """按原生区域裁图，并将框架 RGB 截图转为定位模块的 BGR。"""
        area = self.ctx.screen_loader.get_area('贝果-局内', '定位小地图')
        if area is None:
            raise ValueError('缺少贝果定位小地图区域')
        crop = cv2_utils.crop_image_only(self.last_screenshot, area.pc_rect)
        return cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)

    @operation_node(name='检查起点', is_start_node=True, node_max_retry_times=6)
    def check_start(self) -> OperationRoundResult:
        """到箱前须确认本路线出生点；到大保险前只需确认局内 HUD。

        配准没有结果时再看。连续三帧没有位置，或连续三帧离开出生点超过 5 像素，才当作不是这条路线。
        """
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        if not self.round_by_find_area(self.last_screenshot, '贝果-局内', '喧响值').is_success:
            return self.round_fail('未识别贝果局内画面')
        if self.destination != 'box' or not self.require_spawn:
            if self.vision.locate(self.minimap()) is None:
                return self.round_retry('起点小地图暂时无法定位', wait=0.15)
            return self.round_success('开始移动')
        position = self.vision.locate(self.minimap())
        if position is None:
            self._spawn_far = 0
            self._spawn_miss += 1
            if self._spawn_miss >= 3:
                return self.round_success(self.STATUS_UNSUPPORTED)
            return self.round_retry('小地图暂时对不上出生点', wait=0.15)
        self._spawn_miss = 0
        distance = hypot(position[0] - self.vision.spawn[0], position[1] - self.vision.spawn[1])
        if distance <= 5:
            self._spawn_far = 0
            return self.round_success('开始移动')
        self._spawn_far += 1
        if self._spawn_far >= 3:
            return self.round_success(self.STATUS_UNSUPPORTED)
        return self.round_retry('出生点位置未稳定', wait=0.15)

    @node_from(from_name='检查起点', status='开始移动')
    @operation_node(name='沿小地图节点移动')
    def move_to_target(self) -> OperationRoundResult:
        """远段按住前进，近处改短步；到达只认目标交互提示。"""
        if self.is_bagel_result():
            self._release_forward()
            return self.round_fail(self.STATUS_DEFEATED)
        if self.last_input_frame is not None and self.last_screenshot_time <= self.last_input_frame:
            return self.round_retry('等待动作后的新截图', wait=0.15)
        if self._safe_brake_until is not None:
            self._release_forward()
            if self.last_screenshot_time < self._safe_brake_until:
                return self.round_wait('等待保险箱前停稳', wait=0.15)
            self._safe_brake_until = None
        has_interaction = (
            self.round_by_find_area(self.last_screenshot, '贝果-局内', self.interact_area).is_success
            and (self.destination != 'safe' or self.round_by_find_area(
                self.last_screenshot, '贝果-局内', '交互F键',
            ).is_success)
        )
        if has_interaction and not self.check_target_position and not self.coordinate_only:
            self._release_forward()
            return self.round_success(self.arrive_status)
        if not self.round_by_find_area(self.last_screenshot, '贝果-局内', '喧响值').is_success:
            self._release_forward()
            if self.round_by_find_area(self.last_screenshot, '战斗-菜单', '按钮-退出战斗').is_success:
                return self.round_fail('移动中打开了暂停菜单')
            return self.round_retry('移动后暂未识别局内 HUD', wait=0.25)
        crop = self.minimap()
        position = self.vision.locate(crop)
        log.debug('贝果导航定位 map=%s stage=%s point=%s xy=%s', self.map_id, self.destination, self.waypoint_index, position)
        if self.on_observation is not None:
            self.on_observation({
                'time': self.last_screenshot_time, 'position': position,
                'angle': self.vision.player_angle(crop), 'target': self.waypoint_index,
            })
        near_safe = (
            not self.coordinate_only
            and self.navigation.effective_final_mode(self.destination) == 'short_steps'
            and self.waypoint_index == len(self.active_waypoints) - 1
        )
        if position is None:
            if not near_safe and self._ignoring_pickup() and self.heading_aligned and self.pickup_misses < 8:
                self.pickup_misses += 1
                self.ctx.controller.start_moving_forward()
                return self.round_wait('忽略路上可拾取物')
            if self.last_position is not None and self.locate_misses < NAV_LOCATE_MISS_LIMIT:
                self.locate_misses += 1
                self._release_forward()
                return self.round_wait('小地图暂时对不上，再看一帧', wait=0.15)
            self._release_forward()
            return self.round_fail('小地图定位失败，停止移动')
        self.pickup_misses = 0
        self.locate_misses = 0
        self.last_position = position
        final_xy = self.active_waypoints[-1][1]
        if (not self.coordinate_only and has_interaction and self.check_target_position
                and self.waypoint_index == len(self.active_waypoints) - 1
                and hypot(position[0] - final_xy[0], position[1] - final_xy[1]) <= self.navigation.effective_interaction_distance):
            self._release_forward()
            return self.round_success(self.arrive_status)
        if self.destination == 'safe' and self._cruise_progress is not None:
            previous, started = self._cruise_progress
            if hypot(position[0] - previous[0], position[1] - previous[1]) >= 2:
                self._cruise_progress = (position, self.last_screenshot_time)
            elif self.last_screenshot_time - started >= 3:
                self._release_forward()
                return self.round_fail('持续前进但位置未变化，停止移动')
        name, target = self.active_waypoints[self.waypoint_index]
        distance = hypot(target[0] - position[0], target[1] - position[1])
        point = self.vision.route.points_for(self.destination)[self.waypoint_index]
        brake_before_safe = (
            self.destination == 'safe'
            and (self.waypoint_index == len(self.active_waypoints) - 2
                 or (self.coordinate_only and point.role == 'approach'))
        )
        if (
            brake_before_safe
            and self.navigation.effective_final_mode(self.destination) == 'short_steps'
            and distance <= self.navigation.effective_brake_distance
            and abs(position[1] - target[1]) <= NAV_SAFE_APPROACH_DISTANCE
        ):
            # 已沿墙接近时提前松键；必须等停稳后的新截图，不能用旧帧直接补一步。
            self._release_forward()
            if self.coordinate_only:
                return self.round_success(self.STATUS_WAYPOINT, wait=NAV_SAFE_BRAKE_WAIT)
            self.waypoint_index += 1
            self.last_input_frame = self.last_screenshot_time
            self._safe_brake_until = self.last_screenshot_time + NAV_SAFE_BRAKE_WAIT
            return self.round_wait('保险箱前松键，等待停稳后碎步', wait=NAV_SAFE_BRAKE_WAIT)
        # 巷口提前切段；楼角和贴墙中间点收紧距离，避免抄近路穿过停车位。
        intermediate = self.waypoint_index + 1 < len(self.active_waypoints)
        safe_corner = self.destination == 'safe' and intermediate
        point = self.vision.route.points_for(self.destination)[self.waypoint_index]
        if (intermediate or self.coordinate_only) and not near_safe and self._corner_is_behind(
            position, target, distance, point.passed_radius,
        ):
            if point.stop:
                self._release_forward()
                self.heading_aligned = False
                self.pending_turn = None
            if self.coordinate_only:
                self._release_forward()
                return self.round_success(self.STATUS_WAYPOINT)
            self.waypoint_index += 1
            return self.round_wait('已越过中间节点，准备下一段', wait=0.1)
        arrival_radius = point.arrival_radius
        if distance <= arrival_radius and not near_safe:
            if point.stop or not intermediate:
                self._release_forward()
            if self.coordinate_only:
                return self.round_success(self.STATUS_WAYPOINT)
            if self.waypoint_index + 1 == len(self.active_waypoints):
                if self.target_wait_started is None:
                    self.target_wait_started = self.last_screenshot_time
                if self.last_screenshot_time - self.target_wait_started < 2:
                    return self.round_wait('目标前停步等待交互提示', wait=0.25)
                return self.round_fail(f'已到{name}但未发现{self.interact_area}')
            self.waypoint_index += 1
            return self.round_wait('已到中间节点，准备下一段', wait=0.1)
        self.target_wait_started = None
        angle = self.vision.player_angle(crop)
        if angle is None:
            self._release_forward()
            return self.round_fail('无法识别角色箭头，停止移动')
        target_angle = degrees(atan2(position[1] - target[1], target[0] - position[0])) % 360
        if near_safe:
            # 最后一段沿接近方向碎步到交互提示，不因越过参考坐标而停步或回头。
            _, approach = self.active_waypoints[self.waypoint_index - 1]
            target_angle = degrees(atan2(approach[1] - target[1], target[0] - approach[0])) % 360
        if not near_safe and (safe_corner or distance > NAV_CRUISE_DISTANCE):
            return self._cruise_toward(angle, target_angle, name)
        limited = self._fail_if_action_limit()
        if limited is not None:
            return limited
        adjustment = self._align_to_heading(angle, target_angle)
        if adjustment is not None:
            return adjustment
        press_time = NAV_SAFE_APPROACH_PRESS if near_safe else self.forward_press
        self._release_forward()
        self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
        self._record_input()
        return self.round_wait(f'前往{name}', wait=0.15)

    def _cruise_toward(
        self, image_angle: float, target_angle: float, name: str,
    ) -> OperationRoundResult:
        """距节点较远时按住前进；小偏差边走边转，大偏差停车转。"""
        if not self.heading_aligned:
            limited = self._fail_if_action_limit()
            if limited is not None:
                return limited
            # 停车转动的是镜头，静止角色箭头仍是旧朝向；短步后才能核验转幅。
            if self.pending_turn is not None:
                return self._tap_align()
            controller_angle, angle_diff = self._observe_heading(image_angle, target_angle)
            # 首次观测偏差大时先停车转向。
            if abs(angle_diff) > NAV_CRUISE_TURN_LIMIT:
                return self._stop_and_turn(controller_angle, angle_diff)
            return self._tap_align()
        controller_angle, angle_diff = self._observe_heading(image_angle, target_angle)
        if abs(angle_diff) > NAV_CRUISE_TURN_LIMIT:
            self._cruise_progress = None
            limited = self._fail_if_action_limit()
            if limited is not None:
                return limited
            return self._stop_and_turn(controller_angle, angle_diff)
        if self._ignoring_pickup():
            # 路边药粉等可拾取物会把镜头拉偏；不按 F，也不跟着小角度来回转。
            if self._cruise_progress is None and self.last_position is not None:
                self._cruise_progress = (self.last_position, self.last_screenshot_time)
            self.ctx.controller.start_moving_forward()
            return self.round_wait('忽略路上可拾取物')
        if abs(angle_diff) > NAV_TURN_DEADBAND:
            if (
                self.last_cruise_turn_at is not None
                and self.last_screenshot_time - self.last_cruise_turn_at < NAV_CRUISE_TURN_GAP
            ):
                if self._cruise_progress is None and self.last_position is not None:
                    self._cruise_progress = (self.last_position, self.last_screenshot_time)
                self.ctx.controller.start_moving_forward()
                return self.round_wait(f'前往{name}')
            limited = self._fail_if_action_limit()
            if limited is not None:
                return limited
            self.last_cruise_turn_at = self.last_screenshot_time
            if self._cruise_progress is None and self.last_position is not None:
                self._cruise_progress = (self.last_position, self.last_screenshot_time)
            self.ctx.controller.start_moving_forward()
            effective = self.turn_compensator.turn(angle_diff, max_abs_angle_diff=NAV_CRUISE_TURN_CAP)
            self.pending_turn = (controller_angle, effective)
            self._record_input()
            return self.round_wait(f'行进转向 {angle_diff:.1f}度')
        if self._cruise_progress is None and self.last_position is not None:
            self._cruise_progress = (self.last_position, self.last_screenshot_time)
        self.ctx.controller.start_moving_forward()
        return self.round_wait(f'前往{name}')

    def _align_to_heading(
        self, image_angle: float, target_angle: float,
    ) -> OperationRoundResult | None:
        """短步前停车对齐。偏差超过死区就停车转，转完再短按 W。"""
        if not self.heading_aligned:
            return self._tap_align()
        controller_angle, angle_diff = self._observe_heading(image_angle, target_angle)
        if abs(angle_diff) > NAV_TURN_DEADBAND:
            return self._stop_and_turn(controller_angle, angle_diff)
        return None

    def _corner_is_behind(
        self,
        position: tuple[float, float],
        target: tuple[float, float],
        distance: float,
        limit: float = 3,
    ) -> bool:
        """人已经贴在拐点附近，且朝向把拐点留在身后。"""
        if distance > limit:
            return False
        angle = self.vision.player_angle(self.minimap())
        if angle is None:
            return False
        controller_angle = (-angle) % 360
        target_angle = degrees(atan2(position[1] - target[1], target[0] - position[0])) % 360
        return abs(cal_utils.angle_delta(controller_angle, target_angle)) > 90

    def _tap_align(self) -> OperationRoundResult:
        """短按 W，让角色朝向对齐镜头。下一轮必须用新截图。"""
        self._release_forward()
        self.ctx.controller.move_w(press=True, press_time=NAV_ALIGN_PRESS, release=True)
        self.heading_aligned = True
        self._record_input()
        return self.round_wait('短按W后等待箭头对齐', wait=0.15)

    def _stop_and_turn(self, controller_angle: float, angle_diff: float) -> OperationRoundResult:
        """松键后转向，单次不超过停车上限。转完需重新对齐镜头。"""
        self._release_forward()
        effective = self.turn_compensator.turn(angle_diff, max_abs_angle_diff=NAV_STOP_TURN_CAP)
        self.pending_turn = (controller_angle, effective)
        self.heading_aligned = False
        self._record_input()
        return self.round_wait(f'停车转向 {angle_diff:.1f}度', wait=0.15)

    def _observe_heading(self, image_angle: float, target_angle: float) -> tuple[float, float]:
        """用新朝向学习上一拍转向，返回控制器朝向和到目标的有向偏差。"""
        controller_angle = (-image_angle) % 360
        if self.pending_turn is not None:
            source, effective = self.pending_turn
            self.turn_compensator.learn(source, effective, controller_angle)
            self.pending_turn = None
        return controller_angle, cal_utils.angle_delta(controller_angle, target_angle)

    def _ignoring_pickup(self) -> bool:
        """右侧出现 F 提示，且不是武备箱或电子保险箱。药粉等可拾取物直接忽略。"""
        if not self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '交互F键',
        ).is_success:
            return False
        for area_name in ('武备箱交互', '电子保险箱交互'):
            if self.round_by_find_area(
                self.last_screenshot, '贝果-局内', area_name,
            ).is_success:
                return False
        return True

    def _action_limit(self) -> int:
        """两地到武备箱均限制 60 次，到电子保险箱限制 100 次。"""
        return 100 if self.destination == 'safe' else 60

    def _fail_if_action_limit(self) -> OperationRoundResult | None:
        """计次输入达到上限时松键停止。按住观察不走这里。"""
        if self.steps < self._action_limit():
            return None
        self._release_forward()
        return self.round_fail('导航达到动作上限')

    def _release_forward(self) -> None:
        """松开前进键。重复调用是安全的。"""
        self._cruise_progress = None
        self.ctx.controller.stop_moving_forward()

    def _record_input(self) -> None:
        """校准、转向和短步计数，并拒绝复用动作前截图。按住观察不计。"""
        self.steps += 1
        self.last_input_frame = self.last_screenshot_time

    def _invalidate_heading(self) -> None:
        """启动或暂停后不再信任旧镜头方向和转向样本。"""
        self.heading_aligned = False
        self.last_input_frame = None
        self.pending_turn = None
        self.target_wait_started = None

    def handle_pause(self) -> None:
        """暂停时释放前进键，恢复后重新校准。"""
        self._release_forward()
        self._invalidate_heading()
        self.turn_compensator.clear_pending_sample()
        super().handle_pause()

    def after_operation_done(self, result: OperationResult) -> None:
        """所有退出路径释放前进键并保留失败截图。"""
        self.ctx.controller.stop_moving_forward()
        self._invalidate_heading()
        super().after_operation_done(result)
