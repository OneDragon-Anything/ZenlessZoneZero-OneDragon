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
        
        self.config: Optional[WorldPatrolConfig] = self.ctx.run_context.get_config(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.route: WorldPatrolRoute = route
        self.current_large_map: WorldPatrolLargeMap = self.ctx.world_patrol_service.get_route_large_map(route)
        self.current_idx: int = start_idx
        self.current_pos: Point = Point(0, 0)

        self.stuck_move_direction: int = 0  # 脱困使用的方向
        self.route_op_start_time: float = 0  # 某个指令的开始时间
        self.no_pos_start_time: float = 0  # 计算坐标失败的开始时间
        self.stuck_pos: Point = self.current_pos  # 被困的坐标
        self.stuck_pos_start_time: float = 0  # 被困坐标的开始时间

        self.in_battle: bool = False  # 是否在战斗中
        self.last_check_battle_time: float = 0  # 上一次检测是否还在战斗的时间

        # 自适应转向算法状态变量
        self.sensitivity: float = 1.0
        self.last_angle: Optional[float] = None
        self.last_angle_diff_command: Optional[float] = None

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
        self.current_pos = self.ctx.world_patrol_service.get_route_pos_before_op_idx(self.route, self.current_idx)
        if self.current_pos is None:
            return self.round_fail(status='路线或开始下标有误')
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
        target_pos = Point(int(op.data[0]), int(op.data[1]))
        if self.no_pos_start_time == 0:
            move_seconds = 0
        else:
            move_seconds = self.last_screenshot_time - self.no_pos_start_time
        move_seconds += 1
        move_distance = move_seconds * 50  # 随便估的一个跑起来的速度
        mini_map_d = mini_map.rgb.shape[0]
        possible_rect = Rect(
            self.current_pos.x - move_distance - mini_map_d,
            self.current_pos.y - move_distance - mini_map_d,
            self.current_pos.x + move_distance + mini_map_d,
            self.current_pos.y + move_distance + mini_map_d,
        )

        next_pos = self.ctx.world_patrol_service.cal_pos(
            self.current_large_map,
            mini_map,
            possible_rect,
        )
        if next_pos is None:
            no_pos_seconds = 0 if self.no_pos_start_time == 0 else self.last_screenshot_time - self.no_pos_start_time
            if self.no_pos_start_time == 0:
                self.no_pos_start_time = self.last_screenshot_time
            elif no_pos_seconds > 20:
                return self.round_fail(status=f'无法计算坐标')
            elif no_pos_seconds > 4:
                self._get_rid_of_stuck()
            elif no_pos_seconds > 2:
                self.ctx.controller.stop_moving_forward()

            self.ctx.controller.turn_vertical_by_distance(300)

            return self.round_wait(status=f'坐标计算失败 持续 {no_pos_seconds:.2f} 秒')
        else:
            self.no_pos_start_time = 0

        if cal_utils.distance_between(next_pos, self.stuck_pos) < 10:
            if self.stuck_pos_start_time == 0:
                self.stuck_pos_start_time = self.last_screenshot_time
            elif self.last_screenshot_time - self.stuck_pos_start_time > 2:
                self.ctx.controller.stop_moving_forward()
                self._get_rid_of_stuck()
        else:
            self.stuck_pos = next_pos
            self.stuck_pos_start_time = 0

        current_angle = mini_map.view_angle
        self.current_pos = next_pos
        if mini_map.view_angle is not None:
            target_angle = cal_utils.calculate_direction_angle(self.current_pos, target_pos)
            angle_diff = cal_utils.angle_delta(current_angle, target_angle)
            
            # --- 自适应转向算法开始 ---
            # 1. 校准灵敏度 (仅在有历史数据时)
            if self.last_angle is not None and self.last_angle_diff_command is not None:
                # 计算实际转动量
                actual_angle_change = cal_utils.angle_delta(self.last_angle, current_angle)
                
                # 防止除零错误
                if abs(self.last_angle_diff_command) > 1e-6:
                    # 计算理论灵敏度
                    theoretical_sensitivity = actual_angle_change / self.last_angle_diff_command
                    
                    # 步长限制调整
                    sensitivity_change = theoretical_sensitivity - self.sensitivity
                    clipped_change = max(-0.02, min(sensitivity_change, 0.02))
                    self.sensitivity += clipped_change
                    
                    # 可选：打印调试信息
                    # log.debug(f"校准: 理论灵敏度={theoretical_sensitivity:.4f}, 新灵敏度={self.sensitivity:.4f}")
            
            # 2. 计算并执行本次指令
            calibrated_angle_diff = angle_diff * self.sensitivity
            self.ctx.controller.turn_by_angle_diff(calibrated_angle_diff)
            
            # 3. 记录历史数据
            self.last_angle = current_angle
            self.last_angle_diff_command = calibrated_angle_diff
            # --- 自适应转向算法结束 ---

        self.ctx.controller.start_moving_forward()

        if cal_utils.distance_between(self.current_pos, target_pos) < 10:
            self.current_idx += 1
            if not is_next_move:
                self.ctx.controller.stop_moving_forward()
            return self.round_wait(status=f'已到达目标点 {target_pos}')

        return self.round_wait(status=f'当前坐标 {self.current_pos} 角度 {current_angle} 目标点 {target_pos}',
                               wait_round_time=0.3,  # 这个时间设置太小的话 会出现转向之后方向判断不准
                               )

    def _get_rid_of_stuck(self):
        auto_battle_utils.switch_to_best_agent_for_moving(self.ctx.auto_op)  # 移动前切换到最佳角色
        log.info('本次脱困方向 %s' % self.stuck_move_direction)
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
        if self.ctx.auto_op.auto_battle_context.last_check_end_result is not None:
            self.ctx.stop_auto_battle()
            return self.round_success(status=self.ctx.auto_op.auto_battle_context.last_check_end_result)

        self.ctx.auto_op.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True)

        if self.ctx.auto_op.auto_battle_context.last_check_in_battle:
            if self.last_screenshot_time - self.last_check_battle_time > 1:
                mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
                if mini_map.play_mask_found:
                    return self.round_success(status='发现地图')

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗')
    @operation_node(name='自动战斗结束')
    def after_auto_battle(self) -> OperationRoundResult:
        self.in_battle = False
        self.ctx.stop_auto_battle()
        time.sleep(5)  # 等待一会 自动战斗停止需要松开按键
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
    ctx.init_by_config()
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
