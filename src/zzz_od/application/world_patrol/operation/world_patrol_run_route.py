import time

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
        ctx: ZContext,  # 游戏环境上下文，包含控制器、配置等
        route: WorldPatrolRoute,  # 巡逻路线数据，包含移动点位和操作指令
        start_idx: int = 0,  # 从第几个指令开始执行（断点续传用）
        is_restarted: bool = False,  # 是否重启模式（影响容错策略）
    ):
        """
        这是一个专门用于在游戏世界中自动执行巡逻路线的核心组件。
        它能够让角色按照预设的路径自动移动、战斗，并处理各种突发情况。

        核心场景串联：
        1. 正常移动流程：坐标更新 -> 角度计算 -> 转向移动 -> 距离检查 -> 循环执行
        2. 战斗处理流程：检测战斗 -> 停止移动 -> 自动战斗 -> 战斗结束 -> 恢复移动
        3. 异常处理流程：坐标失败/卡住检测 -> 智能回溯 -> 脱困动作 -> 重启判定
        4. 自适应优化：转向灵敏度校准 -> 角色切换优化 -> 移动策略调整

        详细执行逻辑：

        阶段一：坐标定位与状态更新
        - 基于上次位置估算搜索范围（移动距离+小地图尺寸），在大地图中匹配小地图获取精确坐标
        - 搜索范围估算：移动时间×50单位/秒+保守估计1秒，确保覆盖可能的移动范围
        - 处理坐标计算失败：2秒后停止移动，4秒后脱困（不计数），20秒后重启路线
        - 检测位置卡住：同一位置（距离<到达距离阈值）停留2秒以上触发智能回溯或脱困机制
        - 维护各种计时器：无坐标开始时间、卡住开始时间、回溯截止时间等
        - 每轮调整视角（垂直距离300），帮助恢复坐标匹配

        阶段二：智能回溯机制（优先级高于脱困）
        - 卡住时优先尝试回溯到上一个回溯目标点或路线起点
        - 回溯超时：15秒，避免回溯到相同位置造成循环
        - 回溯判定：通过坐标值精确比较（x和y都相等）避免重复回溯同一点
        - 回溯成功后重置脱困尝试次数，回溯失败（不可用/超时）则转入脱困流程
        - 状态机管理：回溯激活标志控制状态，回溯目标点记录位置
        - 距离判定阈值：到达距离阈值，用于判断是否到达回溯点
        - 回溯进行中输出debug日志：当前距离和剩余时间

        阶段三：自适应转向与移动
        - 计算当前位置到目标点的角度差，结合视角信息执行精确转向
        - 自适应灵敏度校准：对比上次角度和上次转向指令，动态调整转向灵敏度
        - 灵敏度初始值：1.0，范围：0.5-2.0，单次调整幅度：±0.02，防止突变
        - 除零保护：只有当上次转向指令绝对值>1e-6时才进行校准
        - 转向策略：角度偏差>2度时点刹转向，≤2度时移动中微调
        - 移动控制：角度校准后开始前进，途径点到达时点刹0.006秒校准
        - 无角度信息时：重置自适应状态，直接向前移动

        阶段四：脱困动作执行
        - 脱困前先切换角色（利用不同体型/站位尝试摆脱卡点）
        - 脱困方向序列（脱困移动方向，共6种，循环使用）：
          方向0：左移1秒 | 方向1：右移1秒
          方向2：后退→左移→前进 各1秒 | 方向3：后退→右移→前进 各1秒
          方向4：后退→左移→前进 各2秒 | 方向5：后退→右移→前进 各2秒
        - 有坐标脱困：脱困尝试次数累加，连续6次失败后重启路线，成功到达目标点后重置
        - 无坐标脱困：不计数，依赖20秒时间上限
        - 脱困日志：有坐标显示"脱困尝试 X/6"，无坐标显示"本次脱困方向 Y"
        - 重启路线标记：重启标志为真时再次卡住直接跳过（同一个地方跌倒了，及时止损，避免高血压）

        阶段五：战斗状态处理
        - 检测小地图消失（播放遮罩未找到）进入战斗，停止移动并初始化自动战斗系统
        - 防御性检查：如果自动战斗操作未初始化则执行兜底初始化（正常由世界巡逻应用完成）
        - 战斗循环：持续检查战斗状态和小地图（间隔1秒），等待战斗结束信号
        - 战斗结束判定：战斗系统内部判定（最后检查结束结果）或小地图重新出现
        - 确认战斗结束后：停止自动战斗→等待5秒让画面稳定→切换最佳行走角色→校准视角
        - 视角校准：垂直距离300，为继续执行路线做准备
        - 备注：等待5秒是因为某些角色（如仪玄）战斗结束双大动画较长

        阶段六：目标到达判定
        - 使用统一的距离阈值（到达距离阈值）判定是否到达目标点
        - 到达途径点时：点刹0.006秒校准→继续向前移动
        - 到达最终目标时：当前索引+1→重置脱困尝试次数→返回成功状态
        - 更新指令索引推进路线执行，所有指令完成时返回成功状态
        - 暂停恢复处理：战斗中标记控制暂停/恢复行为
        - 主循环等待时间：0.3秒，避免转向后方向判断不准确
        - 操作结束清理：无论成功失败都停止移动，释放按键
        """
        ZOperation.__init__(self, ctx, op_name=gt('运行路线'))

        self.config: WorldPatrolConfig = self.ctx.run_context.get_config(
            app_id=world_patrol_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.route: WorldPatrolRoute = route
        self.is_restarted: bool = is_restarted  # 是否为重启的路线
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
        result = self._update_current_pos(mini_map)
        if result is not None:
            return result

        # 回溯态维护与目标点选择
        if self.backtrack_active and self._backtrack_step(self.current_pos, emit_log=True) == 'reached':
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
            possible_rect,
        )
        if not self._is_next_pos_valid(next_pos):
            log.info(f'计算坐标偏移较大 舍弃 {next_pos}')
            next_pos = None

        if next_pos is None:
            # 处理无法计算坐标的情况
            no_pos_seconds = 0 if self.no_pos_start_time == 0 else self.last_screenshot_time - self.no_pos_start_time
            if self.no_pos_start_time == 0:
                # 首次进入无坐标态，记录起始时间
                self.no_pos_start_time = self.last_screenshot_time
            # 达到重启阈值：请求重启
            elif no_pos_seconds > 13.5:
                return self.round_fail(status='坐标计算失败，重启当前路线')
            # 达到脱困阈值：执行脱困（不计数）
            elif no_pos_seconds > 4.5:
                # 如果是重启后的路线，再次卡住时直接跳过，不再尝试脱困
                if self.is_restarted:
                    return self.round_fail(status='坐标计算失败，重启当前路线')
                self._do_unstuck_move('no-pos')
            # 达到停止阈值：停止前进，避免盲走
            elif no_pos_seconds > 1.5:
                self.ctx.controller.stop_moving_forward()

            self.ctx.controller.turn_vertical_by_distance(300)

            return self.round_wait(status=f'坐标计算失败 持续 {no_pos_seconds:.2f} 秒')
        else:
            self.no_pos_start_time = 0  # 成功获取坐标，重置计时器

            if self._process_stuck_with_pos(next_pos):
                return self.round_fail(status='有坐标但卡住，重启当前路线')

            self.current_pos = next_pos
            return None

    def _is_next_pos_valid(self, next_pos: Point | None) -> bool:
        if next_pos is None:
            return False
        """
        判断匹配的下一个坐标是否合法
        1. 距离检查：防止基准点错误导致的大幅跳跃
        2. 角度检查：根据上一坐标、朝向、转向等判断方向是否合理
        Args:
            next_pos: 匹配的坐标
        Returns:
            bool: True 表示坐标合法，False 表示坐标非法
        """
        # 距离检查：如果距离过大（超过合理移动范围），直接拒绝
        # 假设最大移动速度 50 单位/秒，0.3秒一轮，最大移动 15 单位
        # 加上容错，设置为 100 单位（约 2 秒的移动距离）
        distance = cal_utils.distance_between(self.current_pos, next_pos)
        if distance > 100:
            return False

        return self._is_next_pos_in_angle_range(next_pos)

    def _is_next_pos_in_angle_range(self, next_pos: Point) -> bool:
        """
        根据上一坐标、朝向、转向等 判断当前坐标计算结果是否偏离方向
        Args:
            next_pos: 匹配的坐标
        Returns:
            bool: True 表示坐标合法，False 表示坐标非法
        """
        if self.last_angle is None or self.last_angle_diff_command is None:
            return True

        # 只有和上一个距离较远时进行判断 距离较近的计算移动朝向误差大 不进行判断
        # 阈值从20提升到50像素，避免短距离时OCR抖动导致角度计算误差过大
        if cal_utils.distance_between(self.current_pos, next_pos) < 50:
            return True

        # 从上一个坐标 到当前坐标的方向 正右为0 逆时针为正
        move_angle = cal_utils.calculate_direction_angle(self.current_pos, next_pos)

        if self.last_angle_diff_command < 0:
            # 上一次选择了顺时针旋转 要计算角度减少了多少
            if move_angle <= self.last_angle:
                # 假设上一次朝向=45度 转向=-90度 当前移动朝向=5度 则移动转向=5-45
                move_angle_diff = move_angle - self.last_angle
            else:
                # 假设上一次朝向=45度 转向=-90度 当前移动朝向=355度 则移动转向=355-360-45
                move_angle_diff = move_angle - 360 - self.last_angle
        else:
            # 上一次选择了逆时针旋转 要计算角度增加了多少
            if move_angle >= self.last_angle:
                # 假设上一次朝向=300度 转向=90度 当前朝向=350度 则移动转向=350-300
                move_angle_diff = move_angle - self.last_angle
            else:
                # 假设上一次朝向=300度 转向=90度 当前朝向=40度 则移动转向=40+360-300
                move_angle_diff = move_angle + 360 - self.last_angle

        # 当前移动朝向 应该在上一次的朝向和转向的限定范围内
        # 允许一定范围的转向转过了
        # 从10度提升到30度，大幅提升对OCR坐标抖动的容错能力
        allow_angle_diff = 30

        if self.last_angle_diff_command < 0:
            return allow_angle_diff >= move_angle_diff >= self.last_angle_diff_command - allow_angle_diff
        else:
            return -allow_angle_diff <= move_angle_diff <= self.last_angle_diff_command + allow_angle_diff

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
                # 如果是重启后的路线，再次卡住时直接跳过
                if self.is_restarted:
                    log.error('[with-pos]再次卡住，跳过当前路线')
                    return True
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
                and prev_pos.x == last_target.x
                and prev_pos.y == last_target.y
            )
            if prev_pos is None or same_as_last:
                if emit_log and same_as_last:
                    log.info('回溯跳过，回溯点与上次相同')
                return 'unavailable'

            if emit_log:
                log.info(f'尝试回溯到上一个目标点 {prev_pos}')
            self.backtrack_active = True
            self.backtrack_target = prev_pos
            self.backtrack_deadline = now + 15.0
            self.ctx.controller.start_moving_forward()
            return 'started'

        # 维护进行中的回溯：先返回 ongoing，再处理 reached / expired
        distance = cal_utils.distance_between(next_pos, self.backtrack_target)
        reached = distance < self.REACH_DISTANCE
        expired = now >= self.backtrack_deadline
        if not reached and not expired:
            if emit_log:
                log.debug(f'回溯进行中，当前距离目标 {distance:.2f}，剩余时间 {self.backtrack_deadline - now:.1f}秒')
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
        tag: 日志标记（如 'with-pos' 或 'no-pos')
        """
        # 脱困前，切换到下一位（利用不同角色体型/站位尝试摆脱卡点）
        self.ctx.auto_battle_context.switch_next()
        if tag == 'with-pos':
            log.info(f'[{tag}] 脱困尝试 {self.pos_stuck_attempts + 1}/6，方向 {self.stuck_move_direction}')
        else:
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
        if self.ctx.auto_battle_context.auto_op is None:
            # 只是个兜底 正常情况下 WorldPatrolApp 会做这个初始化
            self.ctx.auto_battle_context.init_auto_op(self.config.auto_battle)

        self.in_battle = True
        self.ctx.auto_battle_context.start_auto_battle()
        return self.round_success()

    @node_from(from_name='初始化自动战斗')
    @operation_node(name='自动战斗', mute=True)
    def auto_battle(self) -> OperationRoundResult:
        if self.ctx.auto_battle_context.last_check_end_result is not None:
            self.ctx.auto_battle_context.stop_auto_battle()
            return self.round_success(status=self.ctx.auto_battle_context.last_check_end_result)

        self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True)

        # 每秒检测1次是否退出了战斗
        if self.last_screenshot_time - self.last_check_battle_time > 1:
            self.last_check_battle_time = self.last_screenshot_time
            if not self.ctx.auto_battle_context.last_check_in_battle:
                # 当前不在战斗画面(没有攻击按钮) 但有可能是战斗结束靠近了可交互物 变成了交互按键
                result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
                if result.is_success:
                    return self.round_success(status=result.status)
            else:
                mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
                if mini_map.play_mask_found:
                    return self.round_success(status='发现地图')

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗')
    @operation_node(name='自动战斗结束')
    def after_auto_battle(self) -> OperationRoundResult:
        self.in_battle = False
        self.ctx.auto_battle_context.stop_auto_battle()
        time.sleep(5)  # 等待一会 自动战斗停止需要松开按键
        # 战斗后，切换到最佳行走位
        if self.ctx.auto_battle_context.auto_op is not None:
            auto_battle_utils.switch_to_best_agent_for_moving(self.ctx)
        self.ctx.controller.turn_vertical_by_distance(300)

        # 重置自适应转向状态（战斗后切换角色，转向特性可能不同）
        self.last_angle = None
        self.last_angle_diff_command = None
        self.sensitivity = 1.0

        return self.round_success()

    def handle_pause(self) -> None:
        if self.in_battle:
            self.ctx.auto_battle_context.stop_auto_battle()
        else:
            self.ctx.controller.stop_moving_forward()

    def handle_resume(self) -> None:
        if self.in_battle:
            self.ctx.auto_battle_context.start_auto_battle()

    def after_operation_done(self, result: OperationResult) -> None:
        ZOperation.after_operation_done(self, result)
        self.ctx.controller.stop_moving_forward()


def __debug(area_full_id: str, route_idx: int):
    ctx = ZContext()
    ctx.init()
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
