import time
from typing import Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.world_patrol import world_patrol_const
from zzz_od.application.world_patrol.mini_map_wrapper import MiniMapWrapper
from zzz_od.application.world_patrol.operation.transport_by_3d_map import (
    TransportBy3dMap,
)
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolLargeMap
from zzz_od.application.world_patrol.world_patrol_config import WorldPatrolConfig
from zzz_od.application.world_patrol.world_patrol_route import (
    WorldPatrolOperation,
    WorldPatrolOpType,
    WorldPatrolRoute,
)
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class WorldPatrolRunRoute(ZOperation):

    def __init__(
        self,
        ctx: ZContext,
        route: WorldPatrolRoute,
        start_idx: int = 0,
    ):
        """
        运行一条指定的路线
        """
        ZOperation.__init__(self, ctx, op_name=gt('运行路线'))

        self.config: WorldPatrolConfig = self.ctx.run_context.get_config(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.route: WorldPatrolRoute = route
        self.current_large_map: WorldPatrolLargeMap | None = self.ctx.world_patrol_service.get_route_large_map(route)
        self.current_idx: int = start_idx
        self.current_pos: Point = Point(0, 0)

        # 智能回溯状态变量
        self.backtrack_active: bool = False  # 是否正在回溯到上一个点位
        self.backtrack_target: Point | None = None  # 回溯目标点
        self.backtrack_deadline: float = 0  # 回溯超时时间
        self.last_backtrack_target: Point | None = None  # 上一个目标点（可作为回溯点）
        self.route_start_pos: Point | None = None  # 起点（可作为初始回溯点）

        # 执行脱困状态变量
        self.stuck_move_direction: int = 0  # 脱困使用的方向
        self.route_op_start_time: float = 0  # 某个指令的开始时间
        self.no_pos_start_time: float = 0  # 计算坐标失败的开始时间
        self.stuck_pos: Point = self.current_pos  # 被困的坐标
        self.stuck_pos_start_time: float = 0  # 被困坐标的开始时间
        self.pos_stuck_attempts: int = 0  # 有坐标但卡住的连续脱困尝试次数

        # 自动战斗状态变量
        self.in_battle: bool = False  # 是否在战斗中
        self.last_check_battle_time: float = 0  # 上一次检测是否还在战斗的时间

        # 自适应转向算法状态变量
        self.sensitivity: float = 1.0  # 转向灵敏度
        self.last_angle: float | None = None  # 上一次获取到的人物朝向
        self.last_angle_diff_command: float | None = None  # 上一次下发的转向指令

    # 距离判定阈值（用于到达/回溯成功/卡住判定的统一半径）
    REACH_DISTANCE: int = 10

    @operation_node(name='初始回到大世界', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        if self.current_idx != 0:
            return self.round_success(status='DEBUG')

        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='初始回到大世界')
    @operation_node(name='传送')
    def transport(self) -> OperationRoundResult:
        op = TransportBy3dMap(self.ctx, self.route.tp_area, self.route.tp_name)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='初始回到大世界', status='DEBUG')
    @node_from(from_name='传送')
    @operation_node(name='设置起始坐标')
    def set_start_idx(self) -> OperationRoundResult:
        # 根据路线与当前指令下标，计算起点坐标（先用局部变量避免给字段赋 None）
        start_pos = self.ctx.world_patrol_service.get_route_pos_before_op_idx(self.route, self.current_idx)
        if start_pos is None:
            # 起点坐标缺失，视为配置错误
            log.error('未找到初始坐标，请检查路线配置')
            return self.round_fail(status='路线或开始下标有误')
        self.current_pos = start_pos
        self.route_start_pos = start_pos  # 记录起点
        self.ctx.controller.turn_vertical_by_distance(300)
        return self.round_success(wait=1)

    @node_from(from_name='设置起始坐标')
    @node_from(from_name='自动战斗结束')
    @operation_node(name='运行指令')
    def run_op(self) -> OperationRoundResult:
        """
        执行一个个的指令
        Returns:
        """
        if self.current_idx >= len(self.route.op_list):
            return self.round_success(status='全部指令已完成')

        op = self.route.op_list[self.current_idx]
        next_op = self.route.op_list[self.current_idx + 1] if self.current_idx + 1 < len(self.route.op_list) else None
        mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)

        if not mini_map.play_mask_found:
            return self.round_success(status='进入战斗')

        if op.op_type == WorldPatrolOpType.MOVE:
            is_next_move = next_op is not None and next_op.op_type == WorldPatrolOpType.MOVE
            return self.handle_move(op, mini_map, is_next_move)
        else:
            return self.round_fail(status=f'未知指令类型 {op.op_type}')

    def handle_move(
        self,
        op: WorldPatrolOperation,
        mini_map: MiniMapWrapper,
        is_next_move: bool,
    ) -> OperationRoundResult:
        """
        处理移动指令的核心逻辑
        """
        # 1. 更新当前位置，并处理无法计算坐标/卡住超限的情况
        res = self._update_current_pos(mini_map)
        if isinstance(res, OperationRoundResult):
            return res
        if res is None or self._process_stuck_with_pos(res):
            return self.round_fail(status='卡住超限，重启当前路线')
        self.current_pos = res

        # 回溯态维护与目标点选择
        backtrack_status = None
        if self.backtrack_active:
            backtrack_status = self._backtrack_step(self.current_pos)
            if backtrack_status == 'reached':
                return self.round_wait(status='回溯成功，已到达回溯点')

        # 2. 执行转向和移动
        target_pos = (
            self.backtrack_target
            if (self.backtrack_active and self.backtrack_target is not None)
            else Point(int(op.data[0]), int(op.data[1]))
        )
        self._turn_and_move(target_pos, mini_map)

        # 3. 判断是否到达目标点
        # 到达目标点距离阈值
        if (not self.backtrack_active) and cal_utils.distance_between(self.current_pos, target_pos) < self.REACH_DISTANCE:
            self.current_idx += 1
            if is_next_move:
                # 到达途径点后，点刹，用于校准
                self.ctx.controller.stop_moving_forward()
                time.sleep(0.006)
                self.ctx.controller.start_moving_forward()
            # 到达目标点后，重置脱困计数
            if self.pos_stuck_attempts > 0:
                log.info('已到达目标点，重置脱困计数')
                self.pos_stuck_attempts = 0
            return self.round_wait(status=f'已到达目标点 {target_pos}')

        return self.round_wait(status=f'当前坐标 {self.current_pos} 角度 {mini_map.view_angle} 目标点 {target_pos}',
                       wait_round_time=0.3,  # 这个时间设置太小的话，会出现转向之后方向判断不准
                       )

    def _update_current_pos(self, mini_map: MiniMapWrapper) -> Point | OperationRoundResult | None:
        """
        更新当前位置，并处理无法计算坐标的情况
        :param mini_map: 小地图信息
        :return: 成功则返回新的坐标点，失败则返回 OperationRoundResult
        """
        if self.current_large_map is None:
            log.error('缺少大地图数据，无法计算坐标')
            raise RuntimeError('缺少大地图数据，路线配置错误')
        # 基于上一次的已知位置，估算本次可能出现的搜索范围矩形，搜索范围再加上小地图尺寸
        if self.no_pos_start_time == 0:
            move_seconds = 0
        else:
            move_seconds = self.last_screenshot_time - self.no_pos_start_time
        move_seconds += 1  # 给出一个保守的前移估计
        move_distance = move_seconds * 50  # 移动速度估值
        mini_map_d = mini_map.rgb.shape[0]
        possible_rect = Rect(
            int(self.current_pos.x - move_distance - mini_map_d),
            int(self.current_pos.y - move_distance - mini_map_d),
            int(self.current_pos.x + move_distance + mini_map_d),
            int(self.current_pos.y + move_distance + mini_map_d),
        )

        # 尝试计算当前位置（在估算范围内匹配）
        next_pos = self.ctx.world_patrol_service.cal_pos(
            self.current_large_map,
            mini_map,
            possible_rect
        )

        if next_pos is None:
            # 处理无法计算坐标的情况
            no_pos_seconds = 0 if self.no_pos_start_time == 0 else self.last_screenshot_time - self.no_pos_start_time
            if self.no_pos_start_time == 0:
                # 首次进入无坐标态，记录起始时间
                self.no_pos_start_time = self.last_screenshot_time
            # 达到重启阈值：请求重启
            elif no_pos_seconds > 20.0:
                log.error('[no-pos]卡住，重启当前路线')
                return None
            # 达到脱困阈值：执行脱困（不计数）
            elif no_pos_seconds > 4.0:
                self._do_unstuck_move('no-pos')
            # 达到停止阈值：停止前进，避免盲走
            elif no_pos_seconds > 2.0:
                self.ctx.controller.stop_moving_forward()

            self.ctx.controller.turn_vertical_by_distance(300)

            return self.round_wait(status=f'坐标计算失败 持续 {no_pos_seconds:.2f} 秒')
        else:
            self.no_pos_start_time = 0  # 成功获取坐标，重置计时器
            return next_pos

    def _process_stuck_with_pos(self, next_pos: Point) -> bool:
        """
        处理有坐标但卡住的情况
        Returns:
            bool: True 表示达到脱困上限，重启当前路线；False 表示已处理或无需处理
        """
        # 疑似卡住的阈值（若当时移动较慢或转向未完成，过小可能误判，过大转悠太久）
        if cal_utils.distance_between(next_pos, self.stuck_pos) < self.REACH_DISTANCE:
            if self.stuck_pos_start_time == 0:
                self.stuck_pos_start_time = self.last_screenshot_time
            elif self.last_screenshot_time - self.stuck_pos_start_time > 2:
                self.ctx.controller.stop_moving_forward()
                # 先尝试智能回溯
                status = self._backtrack_step(next_pos, emit_log=True)
                if status in ('unavailable', 'expired'):
                    # 回溯超时/跳过，则尝试执行脱困（计数）
                    self._do_unstuck_move('with-pos')
                    self.pos_stuck_attempts += 1
                    if self.pos_stuck_attempts >= 6:  # 脱困最大尝试次数
                        log.info('[with-pos]卡住，重启当前路线')
                        self.pos_stuck_attempts = 0
                        return True
                elif status == 'started':
                    pass
                # 成功执行一次脱困后，重置卡点计时，避免连续触发
                self.stuck_pos = Point(0, 0)
                self.stuck_pos_start_time = 0
        else:
            self.stuck_pos = next_pos
            self.stuck_pos_start_time = 0
        return False

    def _turn_and_move(self, target_pos: Point, mini_map: MiniMapWrapper):
        """
        根据目标点执行转向和移动
        """
        current_angle = mini_map.view_angle
        if current_angle is None:
            # 重置自适应状态，避免使用过时数据
            self.last_angle = None
            self.last_angle_diff_command = None
            self.ctx.controller.start_moving_forward()  # 没有角度信息时，先往前走
            return

        target_angle = cal_utils.calculate_direction_angle(self.current_pos, target_pos)
        angle_diff = cal_utils.angle_delta(current_angle, target_angle)

        # --- 自适应转向算法 ---
        # 1. 校准灵敏度: 通过对比上一次的指令和实际的视角变化，动态微调灵敏度
        if self.last_angle is not None and self.last_angle_diff_command is not None:
            # 计算实际上视角变化了多少度
            actual_angle_change = cal_utils.angle_delta(self.last_angle, current_angle)
            # 防止除零错误
            if abs(self.last_angle_diff_command) > 1e-6:
                # 根据“实际变化/指令变化”计算出理论上最匹配的灵敏度
                theoretical_sensitivity = actual_angle_change / self.last_angle_diff_command
                # 计算理论灵敏度与当前灵敏度的差距
                sensitivity_change = theoretical_sensitivity - self.sensitivity
                # 限制单次调整幅度，防止突变，让校准过程更平滑
                clipped_change = max(-0.02, min(sensitivity_change, 0.02))
                self.sensitivity += clipped_change
                # 限制灵敏度在合理范围内，防止累积偏离
                self.sensitivity = max(0.5, min(self.sensitivity, 2.0))
                # 可选：打印调试信息
                # log.debug(f"校准: 理论灵敏度={theoretical_sensitivity:.4f}, 新灵敏度={self.sensitivity:.4f}")

        # 2. 计算并执行转向
        calibrated_angle_diff = angle_diff * self.sensitivity
        # 判断是否需要停下转向的角度阈值
        need_turn = abs(angle_diff) > 2.0

        if need_turn:
            # 角度偏差大，点刹，再转向
            self.ctx.controller.stop_moving_forward()
            # 执行转向
            self.ctx.controller.turn_by_angle_diff(calibrated_angle_diff)
        else:
            # 角度偏差小，直接在移动中微调
            self.ctx.controller.turn_by_angle_diff(calibrated_angle_diff)

        # 3. 记录本次数据
        self.last_angle = current_angle
        self.last_angle_diff_command = calibrated_angle_diff
        # --- 算法结束 ---

        # 4. 开始移动
        self.ctx.controller.start_moving_forward()

    def _backtrack_step(self, next_pos: Point, emit_log: bool = False) -> str:
        """
        智能回溯：推进一次“折返到上一个目标点”的状态机
        :param next_pos: 当前计算出的角色坐标
        :param emit_log: 是否输出通用日志
        :return:状态字符串：'started'（开始回溯）、'ongoing'（正在回溯）、'reached'（回溯成功）、
                           'expired'（回溯超时）、'unavailable'（回溯跳过）
        """
        now = self.last_screenshot_time

        # 尝试启动回溯：决定 unavailable 或 started
        if not self.backtrack_active or self.backtrack_target is None:
            prev_pos = self.ctx.world_patrol_service.get_route_pos_before_op_idx(self.route, self.current_idx)
            if prev_pos is None and self.route_start_pos is not None:
                prev_pos = self.route_start_pos
            last_target = self.last_backtrack_target
            same_as_last = (
                prev_pos is not None
                and last_target is not None
                and cal_utils.distance_between(prev_pos, last_target) < self.REACH_DISTANCE
            )
            if prev_pos is None or same_as_last:
                if emit_log and same_as_last:
                    log.info('回溯跳过，回溯点与上次相同')
                return 'unavailable'

            if emit_log:
                log.info(f'尝试回溯到上一个目标点 {prev_pos}')
            self.backtrack_active = True
            self.backtrack_target = prev_pos
            self.backtrack_deadline = now + 6.0
            self.ctx.controller.start_moving_forward()
            return 'started'

        # 维护进行中的回溯：先返回 ongoing，再处理 reached / expired
        reached = cal_utils.distance_between(next_pos, self.backtrack_target) < self.REACH_DISTANCE
        expired = now >= self.backtrack_deadline
        if not reached and not expired:
            return 'ongoing'
        target = self.backtrack_target
        if reached:
            self.ctx.controller.stop_moving_forward()
            if emit_log:
                log.info(f'回溯成功，已到达 {target}')
        elif emit_log:
            log.info('回溯超时')
        # 清理状态
        self.last_backtrack_target = self.backtrack_target
        self.backtrack_active = False
        self.backtrack_target = None
        self.backtrack_deadline = 0
        return 'reached' if reached else 'expired'

    def _do_unstuck_move(self, tag: str):
        """
        执行一次脱困动作，自动切换角色并按 stuck_move_direction 选择方向
        tag: 日志标记（如 'with-pos' 或 'no-pos'）
        """
        if self.ctx.auto_op is not None:
            # 脱困前，切换到下一位（利用不同角色体型/站位尝试摆脱卡点）
            self.ctx.auto_op.auto_battle_context.switch_next()
        log.info(f'[{tag}] 本次脱困方向 {self.stuck_move_direction}')
        if self.stuck_move_direction == 0:  # 向左走
            self.ctx.controller.move_a(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 1:  # 向右走
            self.ctx.controller.move_d(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 2:  # 后左前 1秒
            self.ctx.controller.move_s(press=True, press_time=1, release=True)
            self.ctx.controller.move_a(press=True, press_time=1, release=True)
            self.ctx.controller.move_w(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 3:  # 后右前 1秒
            self.ctx.controller.move_s(press=True, press_time=1, release=True)
            self.ctx.controller.move_d(press=True, press_time=1, release=True)
            self.ctx.controller.move_w(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 4:  # 后左前 2秒
            self.ctx.controller.move_s(press=True, press_time=2, release=True)
            self.ctx.controller.move_a(press=True, press_time=2, release=True)
            self.ctx.controller.move_w(press=True, press_time=2, release=True)
        elif self.stuck_move_direction == 5:  # 后右前 2秒
            self.ctx.controller.move_s(press=True, press_time=2, release=True)
            self.ctx.controller.move_d(press=True, press_time=2, release=True)
            self.ctx.controller.move_w(press=True, press_time=2, release=True)
        self.stuck_move_direction += 1
        if self.stuck_move_direction > 5:
            self.stuck_move_direction = 0

    @node_from(from_name='运行指令', status='进入战斗')
    @operation_node(name='初始化自动战斗')
    def init_auto_battle(self) -> OperationRoundResult:
        self.ctx.controller.stop_moving_forward()
        if self.ctx.auto_op is None:
            # 只是个兜底 正常情况下 WorldPatrolApp 会做这个初始化
            self.ctx.init_auto_op(self.config.auto_battle)

        self.in_battle = True
        self.ctx.start_auto_battle()
        return self.round_success()

    @node_from(from_name='初始化自动战斗')
    @operation_node(name='自动战斗')
    def auto_battle(self) -> OperationRoundResult:
        if self.ctx.auto_op is None:
            return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

        if self.ctx.auto_op.auto_battle_context.last_check_end_result is not None:
            self.ctx.stop_auto_battle()
            return self.round_success(status=self.ctx.auto_op.auto_battle_context.last_check_end_result)

        self.ctx.auto_op.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True)

        if self.ctx.auto_op.auto_battle_context.last_check_in_battle and self.last_screenshot_time - self.last_check_battle_time > 1:
            mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
            # 更新节流时间戳，避免每轮重复切小地图
            self.last_check_battle_time = self.last_screenshot_time
            if mini_map.play_mask_found:
                return self.round_success(status='发现地图')

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗')
    @operation_node(name='自动战斗结束')
    def after_auto_battle(self) -> OperationRoundResult:
        self.in_battle = False
        self.ctx.stop_auto_battle()
        time.sleep(5)  # 等待一会 自动战斗停止需要松开按键
        # 战斗后，切换到最佳行走位
        if self.ctx.auto_op is not None:
            auto_battle_utils.switch_to_best_agent_for_moving(self.ctx.auto_op)
        self.ctx.controller.turn_vertical_by_distance(300)
        return self.round_success()

    def handle_pause(self) -> None:
        if self.in_battle:
            self.ctx.stop_auto_battle()
        else:
            self.ctx.controller.stop_moving_forward()

    def handle_resume(self) -> None:
        if self.in_battle:
            self.ctx.start_auto_battle()

    def after_operation_done(self, result: OperationResult):
        ZOperation.after_operation_done(self, result)
        self.ctx.controller.stop_moving_forward()


def __debug(area_full_id: str, route_idx: int):
    ctx = ZContext()
    ctx.init_ocr()
    ctx.init_for_application()
    ctx.world_patrol_service.load_data()

    target_route: WorldPatrolRoute | None = None
    for area in ctx.world_patrol_service.area_list:
        if area.full_id != area_full_id:
            continue
        for route in ctx.world_patrol_service.get_world_patrol_routes_by_area(area):
            if route.idx == route_idx:
                target_route = route
                break

    if target_route is None:
        log.error('未找到指定路线')
        return

    op = WorldPatrolRunRoute(ctx, target_route)
    ctx.run_context.start_running()
    op.execute()
    ctx.run_context.stop_running()


if __name__ == '__main__':
    __debug('production_area_building_east_side', 1)
